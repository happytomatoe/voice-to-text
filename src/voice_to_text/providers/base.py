"""Base provider interface for transcription services."""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers."""

    supports_streaming: bool = False

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

    async def transcribe_stream(self, *, language: str = "en",
                          **kwargs) -> None:
        """Stream microphone audio and emit text events in real-time.

        Base implementation raises NotImplementedError. Providers that support
        realtime streaming set ``supports_streaming = True`` and override this.

        Args:
            language: Language code (e.g. "en").
            **kwargs: Provider-specific streaming options (realtime_model,
                target_delay_ms, etc.).
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        pass

