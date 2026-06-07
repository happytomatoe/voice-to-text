"""Base provider interface for transcription services."""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BatchProvider(ABC):
    """Provider that transcribes complete audio files."""

    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        pass

    @abstractmethod
    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file (batch processing)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class StreamingProvider(ABC):
    """Provider that transcribes audio in real-time via streaming."""

    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        pass

    @abstractmethod
    def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        """Initialize a streaming session."""
        pass

    @abstractmethod
    def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk for processing."""
        pass

    @abstractmethod
    def get_partial_result(self) -> str | None:
        """Get latest partial transcript (may change)."""
        pass

    @abstractmethod
    def finalize_stream(self) -> str:
        """End stream and return final transcript."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

