"""Hybrid transcriber combining streaming and batch providers."""

from typing import Optional
from .providers.base import BatchProvider, StreamingProvider


class HybridTranscriber:
    """Combines streaming provider for real-time text with batch provider for final accuracy."""

    def __init__(self, streaming: StreamingProvider, batch: BatchProvider):
        self.streaming = streaming
        self.batch = batch
        self.partial_text = ""

    def start_stream(self, language: str = "en") -> None:
        """Start the streaming session."""
        self.streaming.start_stream(language)
        self.partial_text = ""

    def on_audio_chunk(self, chunk: bytes) -> str:
        """Called during recording. Returns live text for display."""
        self.streaming.send_audio(chunk)
        self.partial_text = self.streaming.get_partial_result() or self.partial_text
        return self.partial_text

    def on_recording_stop(self, audio_path: str, language: str) -> str:
        """Called when recording stops. Returns accurate batch text."""
        self.streaming.finalize_stream()
        try:
            return self.batch.transcribe_file(audio_path, language=language)
        except Exception:
            return self.partial_text