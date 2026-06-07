"""Groq Whisper transcription provider (batch and streaming)."""

import json
import logging
import os
from typing import Dict, Any, Optional

from groq import Groq
import websocket
from .base import BatchProvider, StreamingProvider

logger = logging.getLogger(__name__)


class GroqProvider(BatchProvider, StreamingProvider):
    """Groq Whisper transcription provider (batch and streaming)."""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key") or os.getenv(
            config.get("api_key_env", "GROQ_API_KEY")
        )
        if not self.api_key:
            raise ValueError(f"{config.get('api_key_env', 'GROQ_API_KEY')} not set")
        self.model = config.get("model", "whisper-large-v3-turbo")
        self.client = Groq(api_key=self.api_key)
        self._ws: Optional[websocket.WebSocket] = None
        self._partial_result: Optional[str] = None

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file using Groq Whisper."""
        logger.info("Transcribing %s with Groq model %s", audio_path, self.model)
        try:
            with open(audio_path, "rb") as f:
                transcription = self.client.audio.transcriptions.create(
                    model=self.model, file=f, language=language, response_format="text"
                )
            result = str(transcription).strip()
            logger.info("Transcription result: %s", result[:100])
            return result
        except Exception as e:
            logger.exception("Groq transcription API call failed")
            raise

    def start_stream(self, language: str = "en") -> None:
        """Initialize a streaming session via WebSocket."""
        ws_url = "wss://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        self._ws = websocket.WebSocket()
        self._ws.connect(ws_url, header=headers)
        self._partial_result = None
        logger.info("Groq stream started")

    def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk over WebSocket."""
        if self._ws is None:
            raise RuntimeError("Stream not started. Call start_stream() first.")
        self._ws.send(audio_chunk, opcode=websocket.ABNF.OPCODE_BINARY)
        self._process_messages()

    def get_partial_result(self) -> Optional[str]:
        """Get latest partial transcript."""
        return self._partial_result

    def finalize_stream(self) -> str:
        """End stream and return final transcript."""
        if self._ws is None:
            return self._partial_result or ""
        
        try:
            self._ws.send(json.dumps({"type": "CloseStream"}))
            self._ws.close()
        except Exception as e:
            logger.warning("Error closing Groq stream: %s", e)
        
        result = self._partial_result or ""
        self._ws = None
        self._partial_result = None
        return result

    def _process_messages(self) -> None:
        """Process incoming WebSocket messages."""
        if self._ws is None:
            return
        
        try:
            self._ws.settimeout(0.01)
            while True:
                msg = self._ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)
                    if data.get("type") == "Results":
                        transcript = (
                            data.get("channel", {})
                            .get("alternatives", [{}])[0]
                            .get("transcript", "")
                        )
                        if transcript:
                            self._partial_result = transcript
                            logger.debug("Partial result: %s", transcript[:50])
                    elif data.get("type") == "Error":
                        logger.error("Groq stream error: %s", data.get("message"))
        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            logger.warning("Error processing Groq messages: %s", e)

    @property
    def name(self) -> str:
        return "groq"

