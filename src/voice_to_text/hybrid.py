"""Hybrid transcriber combining streaming and batch providers."""

import logging

from .providers.base import BatchProvider, StreamingProvider

logger = logging.getLogger(__name__)


class HybridTranscriber:
    """Combines streaming provider for real-time text with batch provider for final accuracy."""

    def __init__(self, streaming: StreamingProvider, batch: BatchProvider):
        self.streaming = streaming
        self.batch = batch
        self.partial_text = ""

    def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        """Start the streaming session."""
        self.streaming.start_stream(language, sample_rate=sample_rate)
        self.partial_text = ""

    def on_audio_chunk(self, chunk: bytes) -> str:
        """Called during recording. Returns live text for display."""
        logger.debug("Hybrid.on_audio_chunk: %d bytes", len(chunk))
        try:
            self.streaming.send_audio(chunk)
            result = self.streaming.get_partial_result()
            if result:
                self.partial_text = result
                logger.debug("Streaming partial len=%d", len(result))
            else:
                logger.debug("No partial result from streaming provider")
        except Exception as e:
            logger.warning("Streaming connection lost, continuing without live text: %s", e)
        return self.partial_text

    def on_recording_stop(self, audio_path: str, language: str) -> str:
        """Called when recording stops. Returns accurate batch text."""
        try:
            finalized = self.streaming.finalize_stream()
            if finalized:
                self.partial_text = finalized
        except Exception as e:
            logger.warning("Error finalizing stream: %s", e)
        try:
            return self.batch.transcribe_file(audio_path, language=language)
        except Exception as e:
            logger.warning("Batch transcription failed, falling back to streaming transcript: %s", e)
            return self.partial_text
