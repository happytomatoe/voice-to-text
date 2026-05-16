"""faster-whisper transcription provider.

Wraps the `faster-whisper` library (CTranslate2 + INT8 quantised Whisper)
for significantly faster CPU inference compared to vanilla whisper.cpp.
"""

import logging
import os
from typing import Dict, Any
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)


class FasterWhisperProvider(TranscriptionProvider):
    """GPU/CPU Whisper via faster-whisper (CTranslate2 backend).

    On CPU this uses `int8` quantisation which runs ~2-4× faster than
    whisper.cpp at similar accuracy for long-form speech.
    """

    @property
    def name(self) -> str:
        return "faster-whisper"

    def __init__(self, config: Dict[str, Any]):
        self.model_size = config.get("model_size", "small.en")
        self.device = config.get("device", "cpu")
        self.compute_type = config.get("compute_type", "int8")
        self.language = config.get("language", "en")

        from faster_whisper import WhisperModel  # late import
        logger.info(
            "Loading faster-whisper model '%s' on %s (compute_type=%s) …",
            self.model_size, self.device, self.compute_type,
        )
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        logger.info("faster-whisper model loaded.")

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe an audio file using faster-whisper.

        Args:
            audio_path: path to any common audio file / WAV
            language:    language code (e.g. ``"en"``)

        Returns:
            Transcribed text string.
        """
        lang = language or self.language
        logger.info("Transcribing %s with faster-whisper lang=%s", audio_path, lang)
        segments, info = self._model.transcribe(audio_path, language=lang)
        return " ".join(seg.text for seg in segments).strip()
