"""Parakeet HTTP transcription provider."""

import logging
import os
from typing import Any

import requests

from .base import TranscriptionProvider

logger = logging.getLogger(__name__)


class ParakeetProvider(TranscriptionProvider):
    """Parakeet transcription provider (HTTP mode only)."""

    def __init__(self, config: dict[str, Any]):
        self.model_name = config.get("model", "nvidia/parakeet-tdt-0.6b-v3")
        self.http_endpoint = config.get("http_endpoint", "http://localhost:5092")
        logger.info("Using Parakeet HTTP mode: %s", self.http_endpoint)

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        logger.info("Transcribing %s via HTTP", audio_path)
        url = f"{self.http_endpoint}/v1/audio/transcriptions"
        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
            data = {"model": self.model_name, "language": language}
            response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        result = response.json().get("text", "").strip()
        logger.info("Transcription result: %s", result[:100])
        return result

    @property
    def name(self) -> str:
        return "parakeet"
