"""Parakeet (NVIDIA NeMo) local transcription provider."""

from typing import Dict, Any
import logging
import os

import requests
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)

try:
    import nemo.collections.asr as nemo_asr
    NEMO_AVAILABLE = True
except ImportError:
    NEMO_AVAILABLE = False


class ParakeetProvider(TranscriptionProvider):
    """Parakeet local transcription provider using NVIDIA NeMo."""

    def __init__(self, config: Dict[str, Any]):
        self.mode = config.get("mode", "local")
        self.model_name = config.get("model", "nvidia/parakeet-tdt-0.6b-v3")
        self._model = None

        if self.mode == "http":
            self.http_endpoint = config.get("http_endpoint", "http://localhost:5092")
            logger.info("Using Parakeet HTTP mode: %s", self.http_endpoint)
            return

        if not NEMO_AVAILABLE:
            raise ImportError(
                "NeMo ASR not installed. Install with: pip install 'nemo_toolkit[asr]' soundfile"
            )

        import soundfile as sf
        self._device = config.get("device", "cuda" if os.path.exists("/proc/driver/nvidia") else "cpu")

    def _load_model(self):
        if self._model is None:
            import soundfile as sf
            logger.info("Loading Parakeet model: %s", self.model_name)
            self._model = nemo_asr.models.ASRModel.from_pretrained(model_name=self.model_name)
            try:
                self._model = self._model.to(self._device)
                logger.info("Model moved to %s", self._device)
            except Exception as e:
                logger.warning("Could not move model to %s, using default: %s", self._device, e)
                self._device = "cpu"
            self._model.eval()

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        if self.mode == "http":
            return self._transcribe_http(audio_path)
        return self._transcribe_local(audio_path, language)

    def _transcribe_http(self, audio_path: str) -> str:
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

    def _transcribe_local(self, audio_path: str, language: str = "en") -> str:
        import soundfile as sf
        self._load_model()
        logger.info("Transcribing %s with Parakeet model %s", audio_path, self.model_name)

        data, sr = sf.read(audio_path, dtype="float32", always_2d=True)
        if data.shape[1] != 1:
            raise ValueError(f"Expected mono audio, got {data.shape[1]} channels")
        if sr != 16000:
            raise ValueError(f"Expected 16kHz audio, got {sr} Hz")

        try:
            outputs = self._model.transcribe([audio_path])
            if not outputs:
                raise ValueError("No output from ASR model")

            result = outputs[0]
            if hasattr(result, "text"):
                text = result.text
            elif isinstance(result, str):
                text = result
            else:
                text = str(result)

            logger.info("Transcription result: %s", text[:100])
            return text.strip()
        except Exception as e:
            logger.exception("Parakeet transcription failed")
            raise

    @property
    def name(self) -> str:
        return "parakeet"