"""Deepgram Nova-3 transcription provider (batch and streaming)."""

import logging
from typing import Any

import requests

from .base import BatchProvider, WebSocketStreamingProvider, resolve_api_key

logger = logging.getLogger(__name__)


class DeepgramProvider(BatchProvider, WebSocketStreamingProvider):
    """Deepgram Nova-3 transcription provider (batch and streaming)."""

    def __init__(self, config: dict[str, Any]):
        self.api_key = resolve_api_key(config, "DEEPGRAM_API_KEY")
        self.model = config.get("model", "nova-3")
        self.api_url = config.get("api_url", "https://api.deepgram.com")
        self._init_ws_state()

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
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
        ws_url = (
            f"{self.api_url.replace('https://', 'wss://').replace('http://', 'ws://')}/v1/listen"
            f"?model={self.model}"
            f"&language={language}"
            f"&encoding=linear16"
            f"&sample_rate={sample_rate}"
            f"&interim_results=true"
        )
        headers = {"Authorization": f"Token {self.api_key}"}
        self._connect_ws(ws_url, headers)
        logger.info("Deepgram stream started (sample_rate=%d)", sample_rate)

    @property
    def name(self) -> str:
        return "deepgram"
