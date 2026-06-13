"""Groq Whisper transcription provider (batch only)."""

import logging
from typing import Any

from groq import Groq

from .base import BatchProvider, resolve_api_key

logger = logging.getLogger(__name__)


class GroqProvider(BatchProvider):
    """Groq Whisper batch transcription provider.

    Note: Groq does not support WebSocket streaming for audio transcription.
    Their API is REST-only. Use batch transcription with fast inference.
    """

    def __init__(self, config: dict[str, Any]):
        self.api_key = resolve_api_key(config, "GROQ_API_KEY")
        self.model = config.get("model", "whisper-large-v3-turbo")
        self.client = Groq(api_key=self.api_key)

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
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

    def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        raise NotImplementedError(
            "Groq does not support WebSocket streaming for audio transcription. "
            "Use batch transcription or choose a different provider for streaming."
        )

    @property
    def name(self) -> str:
        return "groq"
