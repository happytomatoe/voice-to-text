"""Deepgram Nova-3 transcription provider (batch and streaming)."""

import json
import logging
import os
from typing import Dict, Any, Optional

import requests
import websocket
from .base import BatchProvider, StreamingProvider

logger = logging.getLogger(__name__)


class DeepgramProvider(BatchProvider, StreamingProvider):
    """Deepgram Nova-3 transcription provider (batch and streaming)."""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key") or os.getenv(
            config.get("api_key_env", "DEEPGRAM_API_KEY")
        )
        if not self.api_key:
            raise ValueError(f"{config.get('api_key_env', 'DEEPGRAM_API_KEY')} not set")
        self.model = config.get("model", "nova-3")
        self.api_url = config.get("api_url", "https://api.deepgram.com")
        self._ws: Optional[websocket.WebSocket] = None
        self._partial_result: Optional[str] = None

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file using Deepgram Nova-3 API."""
        logger.info("Transcribing %s with Deepgram model %s", audio_path, self.model)

        try:
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "audio/wav",
            }
            with open(audio_path, "rb") as audio_file:
                response = requests.post(
                    f"{self.api_url}/v1/listen",
                    params={"model": self.model, "language": language},
                    headers=headers,
                    data=audio_file,
                )

            response.raise_for_status()
            result = response.json()
            text = (
                result.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "")
                .strip()
            )
            logger.info("Transcription result: %s", text[:100])
            return text

        except requests.exceptions.RequestException as e:
            logger.exception("Deepgram transcription API call failed")
            detail = ""
            if e.response is not None:
                try:
                    detail = f": {e.response.json()}"
                except ValueError:
                    detail = f": {e.response.text}"
            raise RuntimeError(f"Deepgram API request failed: {e}{detail}") from e
        except Exception as e:
            logger.exception("Deepgram transcription failed")
            raise RuntimeError(f"Deepgram transcription failed: {e}")

    def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        """Initialize a streaming session via WebSocket."""
        ws_url = (
            f"wss://api.deepgram.com/v1/listen"
            f"?model={self.model}"
            f"&language={language}"
            f"&encoding=linear16"
            f"&sample_rate={sample_rate}"
            f"&interim_results=true"
        )
        headers = {"Authorization": f"Token {self.api_key}"}

        self._ws = websocket.WebSocket()
        self._ws.connect(ws_url, header=headers)
        self._partial_result = None
        logger.info("Deepgram stream started (sample_rate=%d)", sample_rate)

    def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk over WebSocket."""
        logger.debug("Deepgram send_audio: %d bytes", len(audio_chunk))
        if self._ws is None:
            raise RuntimeError("Stream not started. Call start_stream() first.")
        try:
            self._ws.send(audio_chunk, opcode=websocket.ABNF.OPCODE_BINARY)
            self._process_messages()
        except Exception as e:
            logger.warning("Error sending audio to Deepgram stream: %s", e)
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
            logger.warning("Error closing Deepgram stream: %s", e)
        
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
                logger.debug("Deepgram received message type: %s", type(msg).__name__)
                if isinstance(msg, str):
                    data = json.loads(msg)
                    msg_type = data.get("type", "unknown")
                    logger.debug("Deepgram message type: %s, raw: %s", msg_type, msg[:200])
                    if msg_type == "Results":
                        channel = data.get("channel", {})
                        alternatives = channel.get("alternatives", [{}])
                        transcript = alternatives[0].get("transcript", "") if alternatives else ""
                        is_final = data.get("is_final", False)
                        logger.debug("Deepgram Results: is_final=%s, transcript=%r, channel_keys=%s", is_final, transcript, list(channel.keys()))
                        if transcript:
                            self._partial_result = transcript
                            logger.info("Partial result (final=%s): %s", is_final, transcript[:50])
                    elif msg_type == "Error":
                        logger.error("Deepgram stream error: %s", data.get("message"))
        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            logger.warning("Error processing Deepgram messages: %s", e)
            self._ws = None

    @property
    def name(self) -> str:
        return "deepgram"
