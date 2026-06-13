"""Groq Whisper transcription provider."""

import logging
import os
from typing import Any

from groq import Groq

from .base import TranscriptionProvider

logger = logging.getLogger(__name__)


class GroqProvider(TranscriptionProvider):
    """Groq Whisper batch transcription provider."""

    def __init__(self, config: dict[str, Any]):
        self.api_key = config.get("api_key") or os.getenv(config.get("api_key_env", "GROQ_API_KEY"))
        if not self.api_key:
            raise ValueError(f"{config.get('api_key_env', 'GROQ_API_KEY')} not set")
        self.model = config.get("model", "whisper-large-v3-turbo")
        self.client = Groq(api_key=self.api_key)

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
        except Exception:
            logger.exception("Groq transcription API call failed")
            raise

    @property
    def name(self) -> str:
        return "groq"
