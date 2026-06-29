"""Base provider interface for transcription services."""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BatchProvider(ABC):
    """Provider that transcribes complete audio files."""

    @abstractmethod
    def __init__(self, config: dict[str, Any]):
        pass

    @abstractmethod
    async def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file (batch processing)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class StreamingProvider(ABC):
    """Provider that transcribes audio in real-time via streaming."""

    @abstractmethod
    def __init__(self, config: dict[str, Any]):
        pass

    @abstractmethod
    async def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        """Initialize a streaming session."""
        pass

    @abstractmethod
    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk for processing."""
        pass

    @abstractmethod
    async def get_partial_result(self) -> str | None:
        """Get latest partial transcript (may change)."""
        pass

    @abstractmethod
    async def finalize_stream(self) -> str:
        """End stream and return final transcript."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


def resolve_api_key(
    config: dict[str, Any],
    default_env: str,
    extra_envs: tuple[str, ...] = (),
) -> str:
    """Resolve API key from config or environment variables.

    Raises ValueError if not found.
    """
    key = config.get("api_key")
    if not key:
        env_var = config.get("api_key_env", default_env)
        key = os.getenv(env_var)
    if not key:
        for env in extra_envs:
            key = os.getenv(env)
            if key:
                break
    if not key:
        all_vars = (config.get("api_key_env", default_env),) + extra_envs
        raise ValueError(f"None of {all_vars} are set")
    return key


class WebSocketStreamingProvider(StreamingProvider):
    """Shared WebSocket streaming logic for providers using the Deepgram-compatible protocol.

    Subclasses implement: __init__, transcribe_file, start_stream (URL/headers), name.

    Uses the ``websockets`` async library (replaces legacy websocket-client).
    """

    _partial_result: str | None
    _finalized_text: str
    _ws: Any  # websockets.WebSocketClientProtocol | None

    def _init_ws_state(self) -> None:
        self._partial_result = None
        self._finalized_text = ""
        self._ws = None

    async def _connect_ws(self, ws_url: str, headers: dict[str, str]) -> None:
        """Open a persistent WebSocket connection."""
        import websockets

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        ws_headers = list(headers.items())
        self._ws = await websockets.connect(ws_url, additional_headers=ws_headers)
        self._partial_result = None
        self._finalized_text = ""

    async def send_audio(self, audio_chunk: bytes) -> None:
        if self._ws is None:
            raise RuntimeError("Stream not started. Call start_stream() first.")
        try:
            await self._ws.send(audio_chunk)
            await self._process_messages()
        except Exception as e:
            logger.warning("Error sending audio to %s stream: %s", self.name, e)
            self._ws = None
            raise RuntimeError("Streaming connection lost") from e

    async def get_partial_result(self) -> str | None:
        if self._partial_result:
            return (
                (self._finalized_text + " " + self._partial_result).strip()
                if self._finalized_text
                else self._partial_result
            )
        return self._finalized_text or None

    async def finalize_stream(self) -> str:
        if self._ws is None:
            result = (
                (self._finalized_text + " " + self._partial_result).strip()
                if self._partial_result
                else self._finalized_text
            )
            self._partial_result = None
            self._finalized_text = ""
            return result

        try:
            await self._ws.send(json.dumps({"type": "CloseStream"}))
            try:
                async with asyncio.timeout(2.0):
                    while True:
                        msg = await self._ws.recv()
                        if isinstance(msg, str):
                            data = json.loads(msg)
                            msg_type = data.get("type", "")
                            if msg_type == "Results":
                                channel = data.get("channel", {})
                                alternatives = channel.get("alternatives", [{}])
                                transcript = alternatives[0].get("transcript", "") if alternatives else ""
                                if transcript:
                                    self._finalized_text = (self._finalized_text + " " + transcript).strip()
            except TimeoutError:
                pass
            await self._ws.close()
        except Exception as e:
            logger.warning("Error closing %s stream: %s", self.name, e)

        result = self._finalized_text
        self._ws = None
        self._partial_result = None
        self._finalized_text = ""
        return result

    async def _process_messages(self) -> None:
        if self._ws is None:
            return

        try:
            async with asyncio.timeout(0.01):
                while True:
                    msg = await self._ws.recv()
                    if isinstance(msg, str):
                        data = json.loads(msg)
                        msg_type = data.get("type", "unknown")
                        if msg_type == "Results":
                            logger.debug("Deepgram Results: %s", msg)
                            channel = data.get("channel", {})
                            alternatives = channel.get("alternatives", [{}])
                            transcript = alternatives[0].get("transcript", "") if alternatives else ""
                            is_final = data.get("is_final", False)
                            if is_final and transcript:
                                self._finalized_text = (self._finalized_text + " " + transcript).strip()
                                self._partial_result = None
                            elif transcript:
                                self._partial_result = transcript
                        elif msg_type == "Error":
                            logger.error("%s stream error: %s", self.name, data.get("message"))
        except (TimeoutError, asyncio.CancelledError):  # noqa: UP041
            pass
        except Exception as e:
            logger.warning("Error processing %s messages: %s", self.name, e)
            self._ws = None
