"""
Async recording engine — state machine for the D-Bus service.

States:
  idle       Waiting for StartRecording call
  recording  AudioRecorder is actively capturing audio
  processing Audio stopped, transcription running

Audio recording uses ``sd.InputStream`` with an ``asyncio.Queue`` to bridge
the callback thread into the async event loop.
"""

import asyncio
import logging
import os
import tempfile
from collections.abc import Callable
from enum import Enum
from typing import Any

import numpy as np
import sounddevice as sd

from voice_to_text.audio import SpeakerVolumeManager
from voice_to_text.bluetooth import activate_headset_mic
from voice_to_text.config import ConfigManager
from voice_to_text.hybrid import HybridTranscriber
from voice_to_text.providers import get_batch_provider, get_streaming_provider
from voice_to_text.typer import ContinuousTyper, DotoolcNotFoundError

CLIPBOARD_CMDS = [
    ["wl-copy", "--type", "text/plain"],
    ["xclip", "-selection", "clipboard"],
    ["xsel", "--clipboard", "--input"],
]

logger = logging.getLogger(__name__)


def _copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard via wl-copy/xclip/xsel."""
    import subprocess

    for cmd in CLIPBOARD_CMDS:
        try:
            proc = subprocess.run(cmd, input=text.encode(), timeout=5.0)
            if proc.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    logger.warning("No clipboard tool found (tried: wl-copy, xclip, xsel)")
    return False

SAMPLE_RATE = 16000
BLOCK_SIZE = 2048


class EngineState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


class AsyncAudioRecorder:
    """Records audio using ``sd.InputStream`` (blocking callback) + ``asyncio.Queue``.

    The ``sd.InputStream`` callback runs in a sounddevice-internal thread.
    It writes audio chunks directly to the ``asyncio.Queue``, which is
    thread-safe for ``put_nowait``. The async consumer reads from the queue.
    """

    def __init__(
        self,
        device: int | None = None,
        sample_rate: int = SAMPLE_RATE,
    ):
        self.device = device
        self.sample_rate = sample_rate
        self.smoothed_level: float = 0.0
        self.frame_count: int = 0
        self._stream: Any = None
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._wav_file = None
        self._filepath: str | None = None

    async def start(self, filepath: str) -> None:
        import wave

        self._filepath = filepath
        fd = os.fdopen(os.open(filepath, os.O_WRONLY | os.O_CREAT, 0o600), "wb")
        self._wav_file = wave.open(fd, "wb")
        self._wav_file.setnchannels(1)
        self._wav_file.setsampwidth(2)
        self._wav_file.setframerate(self.sample_rate)

        # Store event loop reference for thread-safe callback
        self._loop = asyncio.get_running_loop()

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            callback=self._audio_callback,
            device=self.device,
        )
        self._stream.start()
        logger.info(
            "AsyncAudioRecorder started (rate=%d, device=%s)",
            self.sample_rate,
            self.device,
        )

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Called from the sounddevice callback thread — put data into queue.

        Uses ``loop.call_soon_threadsafe`` to safely interact with the
        ``asyncio.Queue`` from the callback thread.
        """
        raw = indata.tobytes()
        if self._wav_file is not None:
            self._wav_file.writeframes(raw)
        self.frame_count += 1
        # Smoothed level for D-Bus AudioLevel signal
        float_data = indata[:, 0].astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(float_data**2)))
        self.smoothed_level = 0.7 * self.smoothed_level + 0.3 * rms
        self._loop.call_soon_threadsafe(self._queue.put_nowait, raw)

    async def read_chunk(self) -> bytes | None:
        """Await the next audio chunk (or None if stopped)."""
        return await self._queue.get()

    def stop(self) -> str | None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._wav_file:
            self._wav_file.close()
            self._wav_file = None
        filepath = self._filepath
        self._filepath = None
        # Signal consumer that no more data
        self._queue.put_nowait(None)
        return filepath

    def stop_and_delete(self) -> None:
        filepath = self.stop()
        if filepath:
            try:
                os.unlink(filepath)
            except OSError:
                pass


class RecordingEngine:
    """Orchestrates the full recording → transcription pipeline asynchronously.

    Attributes:
        state: Current :class:`EngineState`.
        on_audio_level: Callback invoked with a float level (0.0-1.0).
        on_error: Callback invoked with an error message string.
        on_state_change: Callback invoked with the new :class:`EngineState`.
    """

    def __init__(self):
        self.state = EngineState.IDLE
        self._recorder: AsyncAudioRecorder | None = None
        self._transcriber: HybridTranscriber | None = None
        self._batch_provider = None
        self._task: asyncio.Task | None = None
        self._cancel_event = asyncio.Event()
        self._typer: ContinuousTyper | None = None

        # Callbacks set by the D-Bus service to emit signals
        self.on_audio_level: Callable[[float], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_state_change: Callable[[EngineState], None] | None = None

    async def start(self, config: dict[str, Any]) -> None:
        """Start recording and transcription."""
        if self.state != EngineState.IDLE:
            raise RuntimeError(f"Cannot start: engine is {self.state.value}")
        self._cancel_event.clear()
        self._task = asyncio.create_task(self._run(config))

    async def stop(self) -> None:
        """Stop recording gracefully."""
        self._cancel_event.set()
        task = self._task
        if task and not task.done():
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except (TimeoutError, asyncio.CancelledError):
                logger.warning("Recording task did not finish in time")
                task.cancel()
                # If the task's finally block already nulled self._task,
                # that's fine — our local reference still lets us wait
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (TimeoutError, asyncio.CancelledError):
                    pass
        if self.state != EngineState.IDLE:
            self.state = EngineState.IDLE
            self._notify_state()

    async def _run(self, config: dict[str, Any]) -> None:
        """Full recording + transcription pipeline."""
        try:
            # 1. Determine output method
            output_method = config.get("output_method", "none")
            use_typing = output_method in ("type", "type-fallback-clipboard")
            logger.info("Engine config: output_method=%s, use_typing=%s", output_method, use_typing)

            # 2. Open dotoolc pipe early if typing
            typer: ContinuousTyper | None = None
            fallback_to_clipboard = False
            if use_typing:
                try:
                    typer = ContinuousTyper()
                    await typer.start()
                    logger.info("Continuous dotoolc pipe opened for recording session")
                except DotoolcNotFoundError as e:
                    logger.warning("Typing requested but dotoolc not found: %s", e)
                    if self.on_error:
                        self.on_error(f"Typing not available: {e}")
                    # If fallback mode, we'll use clipboard when typing fails
                    if output_method == "type-fallback-clipboard":
                        fallback_to_clipboard = True
                        logger.info("Will fall back to clipboard output")
            self._typer = typer

            # 3. Activate BT headset mic if enabled in config
            if config.get("bluetooth_headset_change_to_handsfree_to_record", True):
                try:
                    activate_headset_mic()
                except Exception as e:
                    logger.debug("BT headset activation skipped: %s", e)

            # 4. Set up providers
            provider = config.get("provider", "voxtral")
            mode = config.get("mode", "batch")
            language = config.get("language", "en")

            transcriber: HybridTranscriber | None = None
            batch_provider = None

            if mode in ("hybrid", "streaming"):
                config_mgr = ConfigManager()
                hybrid_cfg = config_mgr.config.get("transcription", {}).get("hybrid", {})
                streaming_name = config.get("streaming_provider") or hybrid_cfg.get("streaming_provider", "deepgram")
                if mode == "hybrid":
                    batch_name = config.get("batch_provider") or hybrid_cfg.get("batch_provider", "voxtral")
                    streaming_config = config_mgr.get_provider_config(streaming_name)
                    batch_config = config_mgr.get_provider_config(batch_name)
                    streaming_provider = get_streaming_provider(streaming_name, streaming_config)
                    batch_provider = get_batch_provider(batch_name, batch_config)
                else:
                    # streaming mode — use streaming provider as both
                    streaming_config = config_mgr.get_provider_config(streaming_name)
                    streaming_provider = get_streaming_provider(streaming_name, streaming_config)
                    batch_provider = None  # no batch in pure streaming mode
                transcriber = HybridTranscriber(streaming_provider, batch_provider or streaming_provider)  # type: ignore[arg-type]
            else:
                config_mgr = ConfigManager()
                provider_config = config_mgr.get_provider_config(provider)
                batch_provider = get_batch_provider(provider, provider_config)

            self._transcriber = transcriber
            self._batch_provider = batch_provider

            # 5. Record audio via InputStream + Queue
            decrease_pct = config.get("decrease_speaker_volume", 50)
            fd, audio_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

            recorder = AsyncAudioRecorder(
                device=config.get("device"),
                sample_rate=SAMPLE_RATE,
            )
            self._recorder = recorder

            with SpeakerVolumeManager.with_decrease(decrease_pct):
                if self._cancel_event.is_set():
                    return
                await recorder.start(audio_path)
                self.state = EngineState.RECORDING
                self._notify_state()

                # Start streaming if in hybrid mode
                if transcriber:
                    await transcriber.start_stream(language, sample_rate=recorder.sample_rate)

                # Recording loop — read chunks from the queue
                # Use a short timeout so cancellation is responsive even
                # when no audio data arrives (no microphone signal etc.)
                while not self._cancel_event.is_set():
                    try:
                        chunk = await asyncio.wait_for(recorder.read_chunk(), timeout=0.1)
                    except TimeoutError:
                        continue  # no data yet, re-check cancellation
                    if chunk is None:
                        break  # stream ended

                    # Emit audio level for D-Bus signal
                    if self.on_audio_level:
                        self.on_audio_level(recorder.smoothed_level)

                    # Feed streaming provider + type incrementally
                    if transcriber and typer:
                        partial = await transcriber.on_audio_chunk(chunk)
                        if partial:
                            await typer.stream_diff(partial)
                    elif transcriber:
                        await transcriber.on_audio_chunk(chunk)

            # 6. Stop microphone before transitioning to processing
            filepath = recorder.stop()
            self.state = EngineState.PROCESSING
            self._notify_state()
            if filepath:
                if transcriber:
                    text = await transcriber.on_recording_stop(filepath, language)
                else:
                    assert batch_provider is not None
                    text = await batch_provider.transcribe_file(filepath, language)

                # If we were typing incrementally, apply final corrections
                if text and typer:
                    await typer.stream_diff(text)

                # Handle clipboard output if configured
                if text and output_method == "clipboard":
                    _copy_to_clipboard(text)
                # Fallback to clipboard if typing failed in fallback mode
                elif text and fallback_to_clipboard:
                    logger.info("Falling back to clipboard output")
                    _copy_to_clipboard(text)

                logger.info("Transcription result: %s", text[:200] if text else "(empty)")

        except Exception as e:
            logger.exception("Recording failed")
            if self.on_error:
                self.on_error(str(e))
        finally:
            # Close dotoolc pipe
            if self._typer:
                try:
                    await self._typer.stop()
                except Exception:
                    pass
                self._typer = None
            self.state = EngineState.IDLE
            self._notify_state()
            self._cleanup()

    def _cleanup(self):
        if self._recorder:
            try:
                self._recorder.stop_and_delete()
            except Exception:
                pass
            self._recorder = None
        self._transcriber = None
        self._batch_provider = None
        self._task = None

    def _notify_state(self):
        if self.on_state_change:
            self.on_state_change(self.state)
