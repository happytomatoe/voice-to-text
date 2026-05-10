"""Base provider interface for transcription services."""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers."""

    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """Initialize provider with configuration.

        Args:
            config: Provider-specific configuration
        """
        pass

    @abstractmethod
    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file (batch processing).

        Args:
            audio_path: Path to audio file
            language: Language code

        Returns:
            Transcribed text
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        pass

