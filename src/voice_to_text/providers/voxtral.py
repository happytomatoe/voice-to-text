"""Voxtral batch transcription provider."""

import requests
import logging
from typing import Dict, Any
import os
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)


class VoxtralProvider(TranscriptionProvider):
    """Voxtral batch file transcription provider."""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key") or os.getenv(
            config.get("api_key_env", "VOXTRAL_API_KEY")
        )
        if not self.api_key:
            raise ValueError(f"{config.get('api_key_env', 'VOXTRAL_API_KEY')} not set")
        self.model = config.get("model", "voxtral-mini-latest")
        self.api_url = config.get("api_url", "https://api.mistral.ai")

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file using Voxtral batch transcription API."""
        logger.info("Transcribing %s with Voxtral model %s", audio_path, self.model)

        try:
            with open(audio_path, "rb") as audio_file:
                files = {"file": (os.path.basename(audio_path), audio_file)}
                data = {"model": self.model, "language": language}
                response = requests.post(
                    f"{self.api_url}/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files=files,
                    data=data,
                )

            response.raise_for_status()
            result = response.json()
            text = result.get("text", "").strip()
            logger.info("Transcription result: %s", text[:100])
            return text

        except requests.exceptions.RequestException as e:
            logger.exception("Voxtral transcription API call failed")
            detail = ""
            if e.response is not None:
                try:
                    detail = f": {e.response.json()}"
                except ValueError:
                    detail = f": {e.response.text}"
            raise RuntimeError(f"Voxtral API request failed: {e}{detail}")
        except Exception as e:
            logger.exception("Voxtral transcription failed")
            raise RuntimeError(f"Voxtral transcription failed: {e}")

    @property
    def name(self) -> str:
        return "voxtral"

