"""Voxtral realtime streaming transcription provider."""

import os
import logging
import threading
import asyncio
from typing import Dict, Any

from .base import StreamingProvider
from mistralai.client import Mistral
from mistralai.extra.realtime import AudioFormat

logger = logging.getLogger(__name__)


class VoxtralRealtimeProvider(StreamingProvider):
    """Voxtral realtime WebSocket streaming transcription.

    Wraps the ``mistralai`` SDK ``RealtimeTranscription`` session so that
    microphone audio is streamed to the server and partial results are returned.

    The async streaming runs in a dedicated thread with its own event loop
    because the main application is synchronous.
    """

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

        # Audio queue for thread-safe audio passing
        self._audio_queue: asyncio.Queue[bytes] | None = None
        self._partial_result: str | None = None
        self._partial_tokens: list[str] = []
        self._stream_task = None  # concurrent.futures.Future from run_coroutine_threadsafe
        self._closed = False
        
        # Thread + event loop for async streaming
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready_event = threading.Event()

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        raise NotImplementedError(
            "VoxtralRealtimeProvider does not support batch transcription; "
            "use streaming methods instead."
        )

    def _run_event_loop(self):
        """Run the asyncio event loop in a dedicated thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready_event.set()
        self._loop.run_forever()

    def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        """Initialize a streaming session via Voxtral SDK."""
        # Ensure the SDK sees the correct key even if only VOXTRAL_API_KEY is set
        os.environ.setdefault("MISTRAL_API_KEY", self._api_key)

        # Start the event loop thread if not already running
        if self._thread is None or not self._thread.is_alive():
            self._ready_event.clear()
            self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._thread.start()
            self._ready_event.wait(timeout=5.0)  # Wait for loop to be ready
            if self._loop is None:
                raise RuntimeError("Failed to start event loop thread")

        # Create audio queue for this stream
        self._audio_queue = asyncio.Queue(maxsize=100)
        self._partial_tokens = []
        self._closed = False

        # Schedule the streaming coroutine on the event loop
        self._stream_task = asyncio.run_coroutine_threadsafe(
            self._stream(language, sample_rate), self._loop
        )
        logger.info(
            "Starting Voxtral realtime stream: model=%s delay=%sms",
            self._realtime_model,
            self._target_delay_ms,
        )

    async def _stream(self, language: str, sample_rate: int) -> None:
        """Run the Voxtral realtime streaming in the event loop thread."""
        # Initialize client inside the async context
        client = Mistral(api_key=self._api_key)
        rt = client.audio.realtime

        # Get audio chunks from the queue fed by send_audio()
        async def audio_chunks():
            while not self._closed:
                chunk = await self._audio_queue.get()
                yield chunk

        try:
            async for event in rt.transcribe_stream(
                audio_stream=audio_chunks(),
                model=self._realtime_model,
                audio_format=AudioFormat(encoding="pcm_s16le", sample_rate=sample_rate),
                target_streaming_delay_ms=self._target_delay_ms,
                server_url=self._api_url,
            ):
                self._emit(event)
                # Stop on final event
                if getattr(event, "type", None) == "transcription.done":
                    break
        except asyncio.CancelledError:
            logger.info("Voxtral realtime stream cancelled")
        except Exception as exc:
            logger.exception("Voxtral realtime stream error")
            raise RuntimeError(f"Streaming connection lost: {exc}") from exc
        finally:
            if hasattr(rt, "close"):
                rt.close()
            logger.info("Voxtral realtime stream closed")

    def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk for processing - queues it for the async stream."""
        if self._audio_queue is not None and self._loop is not None:
            # Thread-safe: use call_soon_threadsafe to put on the event loop's queue
            self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, audio_chunk)

    def get_partial_result(self) -> str | None:
        """Get latest partial transcript."""
        return self._partial_result

    def finalize_stream(self) -> str:
        """End stream and return final transcript."""
        # Signal closure
        self._closed = True
        
        # Cancel the streaming task if running
        if self._stream_task is not None:
            self._stream_task.cancel()
            try:
                # Wait for the task to finish cancellation (with timeout)
                self._stream_task.result(timeout=5.0)
            except Exception:
                pass  # Ignore cancellation errors
            self._stream_task = None

        # Note: We don't stop the event loop here because the SDK's cleanup
        # needs the loop to be running. The daemon thread will be terminated
        # when the main program exits.
        
        # Return partial result
        result = self._partial_result or ""
        self._partial_result = None
        return result

    def _emit(self, event) -> None:
        kind = getattr(event, "type", None)

        # Debug: log all events
        logger.info("Voxtral realtime event: type=%s", kind)

        if kind == "transcription.language":
            lang = getattr(event, "audio_language", "?")
            logger.info("Language detected: %s", lang)

        elif kind == "transcription.text.delta":
            token = event.text
            self._partial_tokens.append(token)
            self._partial_result = "".join(self._partial_tokens)
            logger.info("Partial result: %s", self._partial_result[:80])

        elif kind == "transcription.segment":
            sid = getattr(event, "speaker_id", None)
            tag = f"[{sid}]" if sid else ""
            text = f"{tag}{event.text}"
            self._partial_result = text
            self._partial_tokens = [text]
            logger.info("Segment: %s", text[:50])

        elif kind == "transcription.done":
            if getattr(event, "text", None):
                self._partial_result = event.text
            usage = getattr(event, "usage", None)
            if usage:
                logger.info("transcription.done usage: %s", usage)

        elif kind == "error":
            detail = getattr(getattr(event, "error", None), "message", str(event))
            logger.error("Voxtral realtime error: %s", detail)
            raise RuntimeError(detail)

        else:
            # Unknown event — forward-compat, never crash
            logger.debug("Unknown realtime event: %s", getattr(event, "content", event))

    @property
    def name(self) -> str:
        return "voxtral_realtime"
