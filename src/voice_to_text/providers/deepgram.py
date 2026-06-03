"""Deepgram Nova-3 batch transcription provider."""

import logging
import os
from typing import Dict, Any

import requests
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)


class DeepgramProvider(TranscriptionProvider):
    """Deepgram Nova-3 batch file transcription provider."""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key") or os.getenv(
            config.get("api_key_env", "DEEPGRAM_API_KEY")
        )
        if not self.api_key:
            raise ValueError(f"{config.get('api_key_env', 'DEEPGRAM_API_KEY')} not set")
        self.model = config.get("model", "nova-3")
        self.api_url = config.get("api_url", "https://api.deepgram.com")

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

    @property
    def name(self) -> str:
        return "deepgram"
