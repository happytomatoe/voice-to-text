"""Voxtral realtime streaming transcription provider."""

import asyncio
import os
import struct
import logging
import time
from typing import Dict, Any

from .base import TranscriptionProvider

logger = logging.getLogger(__name__)

# 16 kHz × 0.020 s × 2 bytes/sample = 640 bytes per chunk
_CHUNK_BYTES = 640
_20MS = int(16000 * 0.020)  # 320 frames per chunk


class VoxtralRealtimeStreamingProvider(TranscriptionProvider):
    """Voxtral realtime WebSocket streaming transcription.

    Wraps the ``mistralai`` SDK ``RealtimeTranscription`` session so that
    microphone audio is streamed to the server and results are emitted as
    plain-text ``LEVEL:`` / ``TEXT:`` / ``FINAL:`` / ``ERROR:`` / ``LANG:``
    lines on stdout.
    """

    supports_streaming = True

    def __init__(self, config: Dict[str, Any]):
        self._api_key = (
            config.get("api_key")
            or os.getenv(config.get("api_key_env", "VOXTRAL_API_KEY"))
            or os.getenv("MISTRAL_API_KEY")
        )
        if not self._api_key:
            raise ValueError(
                f"{config.get('api_key_env', 'VOXTRAL_API_KEY')} / MISTRAL_API_KEY not set"
            )
        self._api_url = config.get("api_url", "https://api.mistral.ai")
        # Separate model fields: batch vs streaming
        self._model = config.get("model", "voxtral-mini-latest")
        self._realtime_model = config.get(
            "realtime_model", "voxtral-mini-transcribe-realtime-2602"
        )
        self._target_delay_ms = config.get("target_delay_ms", 400)
        self._device = config.get("device")

    # ------------------------------------------------------------------
    # TranscriptionProvider base class stubs (streaming-only provider)
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "voxtral_realtime"

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        raise NotImplementedError(
            "VoxtralRealtimeStreamingProvider does not support batch transcription; "
            "use transcribe_stream() instead."
        )

    # ------------------------------------------------------------------
    # Public sync API (called from main.py)
    # ------------------------------------------------------------------

    async def transcribe_stream(self, *, language: str = "en", **kwargs) -> None:
        """Block until the realtime stream finishes.

        Runs the asyncio event loop so callers don't need to be async-aware.
        All results / status lines are printed to stdout directly.
        """
        device = kwargs.get("device")
        if device is not None:
            self._device = device
        return await self._stream(language=language)

    # ------------------------------------------------------------------
    # Internal async helpers
    # ------------------------------------------------------------------

    async def _stream(self, language: str) -> None:
        from mistralai.client import Mistral
        from mistralai.extra.realtime import AudioFormat

        # Ensure the SDK sees the correct key even if only VOXTRAL_API_KEY is set
        os.environ.setdefault("MISTRAL_API_KEY", self._api_key)

        client = Mistral(api_key=self._api_key)
        rt = client.audio.realtime

        # The SDK expects an async iterable yielding raw PCM bytes
        async def audio_chunks():
            async for raw in self._mic_chunks():
                yield raw

        logger.info(
            "Starting realtime stream: model=%s delay=%sms",
            self._realtime_model,
            self._target_delay_ms,
        )

        try:
            async for event in rt.transcribe_stream(
                audio_stream=audio_chunks(),
                model=self._realtime_model,
                audio_format=AudioFormat(encoding="pcm_s16le", sample_rate=16000),
                target_streaming_delay_ms=self._target_delay_ms,
                server_url=self._api_url,
            ):
                self._emit(event)
                # Stop on final event
                if getattr(event, "type", None) == "transcription.done":
                    break
        except Exception as exc:
            logger.exception("Realtime stream error")
            print(f"ERROR:{exc}", flush=True)
        finally:
            rt.close() if hasattr(rt, "close") else None
            logger.info("Realtime stream closed")

    async def _mic_chunks(self):
        """Async generator — reads 20 ms int16-LE mono chunks from the default mic."""
        import sounddevice as sd
        import numpy as np

        loop = asyncio.get_running_loop()
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=32)
        last_level_time = time.time()

        def sd_callback(indata, _frames, _time, _status):
            nonlocal last_level_time
            data = bytes(indata[:, 0])  # int16 LE, mono

            now = time.time()
            if now - last_level_time >= 0.1:
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float64)
                rms = np.sqrt(np.mean(samples**2))
                level = min(rms / 32768.0, 1.0)
                print(f"LEVEL:{level:.4f}", flush=True)
                last_level_time = now

            loop.call_soon_threadsafe(q.put_nowait, data)

        with sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype="int16",
            blocksize=_20MS,
            callback=sd_callback,
            device=self._device,
        ):
            while True:
                chunk = await q.get()
                yield chunk

    # ------------------------------------------------------------------
    # Event → stdout
    # ------------------------------------------------------------------

    def _emit(self, event) -> None:
        kind = getattr(event, "type", None)
        
        # Debug: log all events
        logger.info("Event received: type=%s, event=%s", kind, event)
        print(f"DEBUG:EVENT:{kind}", flush=True)
        
        # Also print all attributes for debugging
        if hasattr(event, '__dict__'):
            for attr, value in event.__dict__.items():
                logger.info("  Event attr: %s=%s", attr, value)

        if kind == "transcription.language":
            lang = getattr(event, "audio_language", "?")
            print(f"LANG:{lang}", flush=True)

        elif kind == "transcription.text.delta":
            print(f"TEXT:{event.text}", flush=True)

        elif kind == "transcription.segment":
            sid = getattr(event, "speaker_id", None)
            tag = f"[{sid}]" if sid else ""
            print(f"TEXT:{tag}{event.text}", flush=True)

        elif kind == "transcription.done":
            print(f"FINAL:{event.text}", flush=True)
            usage = getattr(event, "usage", None)
            if usage:
                logger.info("transcription.done usage: %s", usage)

        elif kind == "error":
            detail = getattr(getattr(event, "error", None), "message", str(event))
            print(f"ERROR:{detail}", flush=True)

        else:
            # UnknownRealtimeEvent — forward-compat, never crash
            logger.debug("Unknown realtime event: %s", getattr(event, "content", event))
