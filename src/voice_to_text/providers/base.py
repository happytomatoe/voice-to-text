"""Base provider interface for transcription services."""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import websocket

logger = logging.getLogger(__name__)


class BatchProvider(ABC):
    """Provider that transcribes complete audio files."""

    @abstractmethod
    def __init__(self, config: dict[str, Any]):
        pass

    @abstractmethod
    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
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
    def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        """Initialize a streaming session."""
        pass

    @abstractmethod
    def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk for processing."""
        pass

    @abstractmethod
    def get_partial_result(self) -> str | None:
        """Get latest partial transcript (may change)."""
        pass

    @abstractmethod
    def finalize_stream(self) -> str:
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
    """

    _ws: websocket.WebSocket | None
    _partial_result: str | None

    def _init_ws_state(self) -> None:
        self._ws = None
        self._partial_result = None

    def _connect_ws(self, ws_url: str, headers: dict[str, str]) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        self._ws = websocket.WebSocket()
        self._ws.connect(ws_url, header=headers)
        self._partial_result = None

    def send_audio(self, audio_chunk: bytes) -> None:
        if self._ws is None:
            raise RuntimeError("Stream not started. Call start_stream() first.")
        try:
            self._ws.send(audio_chunk, opcode=websocket.ABNF.OPCODE_BINARY)
            self._process_messages()
        except Exception as e:
            logger.warning("Error sending audio to %s stream: %s", self.name, e)
            self._ws = None
            raise RuntimeError("Streaming connection lost") from e

    def get_partial_result(self) -> str | None:
        return self._partial_result

    def finalize_stream(self) -> str:
        if self._ws is None:
            return self._partial_result or ""

        try:
            self._ws.send(json.dumps({"type": "CloseStream"}))
            self._ws.settimeout(2.0)
            while True:
                try:
                    msg = self._ws.recv()
                    if isinstance(msg, str):
                        data = json.loads(msg)
                        msg_type = data.get("type", "")
                        if msg_type == "Results":
                            channel = data.get("channel", {})
                            alternatives = channel.get("alternatives", [{}])
                            transcript = alternatives[0].get("transcript", "") if alternatives else ""
                            if transcript:
                                self._partial_result = transcript
                except websocket.WebSocketTimeoutException:
                    break
            self._ws.close()
        except Exception as e:
            logger.warning("Error closing %s stream: %s", self.name, e)

        result = self._partial_result or ""
        self._ws = None
        self._partial_result = None
        return result

    def _process_messages(self) -> None:
        if self._ws is None:
            return

        try:
            self._ws.settimeout(0.01)
            while True:
                msg = self._ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)
                    msg_type = data.get("type", "unknown")
                    if msg_type == "Results":
                        channel = data.get("channel", {})
                        alternatives = channel.get("alternatives", [{}])
                        transcript = alternatives[0].get("transcript", "") if alternatives else ""
                        if transcript:
                            self._partial_result = transcript
                    elif msg_type == "Error":
                        logger.error("%s stream error: %s", self.name, data.get("message"))
        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            logger.warning("Error processing %s messages: %s", self.name, e)
            self._ws = None
