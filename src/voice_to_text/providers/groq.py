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

    def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        """Initialize a streaming session via WebSocket."""
        ws_url = "wss://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        self._ws = websocket.WebSocket()
        self._ws.connect(ws_url, header=headers)
        self._partial_result = None
        logger.info("Groq stream started")

    def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk over WebSocket."""
        logger.debug("Groq send_audio: %d bytes", len(audio_chunk))
        if self._ws is None:
            raise RuntimeError("Stream not started. Call start_stream() first.")
        try:
            self._ws.send(audio_chunk, opcode=websocket.ABNF.OPCODE_BINARY)
            self._process_messages()
        except Exception as e:
            logger.warning("Error sending audio to Groq stream: %s", e)
            self._ws = None
            raise RuntimeError("Streaming connection lost") from e

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
                logger.debug("Groq received message type: %s", type(msg).__name__)
                if isinstance(msg, str):
                    data = json.loads(msg)
                    msg_type = data.get("type", "unknown")
                    logger.debug("Groq message type: %s, raw: %s", msg_type, msg[:200])
                    if msg_type == "Results":
                        channel = data.get("channel", {})
                        alternatives = channel.get("alternatives", [{}])
                        transcript = alternatives[0].get("transcript", "") if alternatives else ""
                        is_final = data.get("is_final", False)
                        logger.debug("Groq Results: is_final=%s, transcript=%r, channel_keys=%s", is_final, transcript, list(channel.keys()))
                        if transcript:
                            self._partial_result = transcript
                            logger.info("Partial result (final=%s): %s", is_final, transcript[:50])
                    elif msg_type == "Error":
                        logger.error("Groq stream error: %s", data.get("message"))
        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            logger.warning("Error processing Groq messages: %s", e)
            self._ws = None

    @property
    def name(self) -> str:
        return "groq"

