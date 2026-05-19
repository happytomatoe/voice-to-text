"""Parakeet HTTP transcription provider."""

from typing import Dict, Any
import logging
import os

import requests
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)


class ParakeetProvider(TranscriptionProvider):
    """Parakeet transcription provider (HTTP mode only)."""

    def __init__(self, config: Dict[str, Any]):
        self.model_name = config.get("model", "nvidia/parakeet-tdt-0.6b-v3")
        self.http_endpoint = config.get("http_endpoint", "http://localhost:5092")
        logger.info("Using Parakeet HTTP mode: %s", self.http_endpoint)

    def transcribe_file(self, audio_path: str) -> str:
        logger.info("Transcribing %s via HTTP", audio_path)
        url = f"{self.http_endpoint}/v1/audio/transcriptions"
        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
            data = {"model": self.model_name}
            response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        result = response.json().get("text", "").strip()
        logger.info("Transcription result: %s", result[:100])
        return result

    def _transcribe_http(self, audio_path: str) -> str:
        """Transcribe via HTTP endpoint (OpenAI-compatible)."""
        return self.transcribe_file(audio_path)

    @property
    def name(self) -> str:
        return "parakeet"
