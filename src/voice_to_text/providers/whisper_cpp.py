"""Whisper.cpp local transcription provider.

Invokes the compiled whisper-cli binary to transcribe audio locally,
without requiring any cloud API.
"""

import logging
import os
import re
import subprocess
from typing import Dict, Any
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)

WHISPER_CPP_DIR = os.path.expanduser("~/whisper.cpp")
WHISPER_CLI_BIN = os.path.join(WHISPER_CPP_DIR, "build", "bin", "whisper-cli")
DEFAULT_MODEL = os.path.join(WHISPER_CPP_DIR, "models", "ggml-small.bin")

# Whisper.cpp timestamps look like  [00:00:00.000 --> 00:00:11.000]
_TIMESTAMP_RE = re.compile(r"^\[[\d:.]+\s+-->\s+[\d:.]+\]\s*")


class WhisperCppProvider(TranscriptionProvider):
    """Local Whisper transcription via whisper.cpp."""

    @property
    def name(self) -> str:
        return "whisper"

    def __init__(self, config: Dict[str, Any]):
        self.cli_bin = config.get(
            "cli_bin",
            os.environ.get("WHISPER_CLI_BIN", WHISPER_CLI_BIN),
        )
        self.model_path = config.get(
            "model_path",
            os.environ.get("WHISPER_MODEL_PATH", DEFAULT_MODEL),
        )
        self.language = config.get("language", "en")
        self.threads = config.get("threads", os.cpu_count() or 4)

        if not os.path.isfile(self.cli_bin):
            raise FileNotFoundError(
                f"whisper-cli binary not found at: {self.cli_bin}\n"
                "Build whisper.cpp first or set the WHISPER_CLI_BIN environment variable."
            )
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(
                f"Whisper model not found at: {self.model_path}\n"
                "Download a model (e.g. `small`) or set WHISPER_MODEL_PATH."
            )

    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe an audio file using the local whisper.cpp binary.

        Args:
            audio_path: Path to a WAV file (16-bit PCM, 16 kHz, mono is ideal).
            language:  Language code (e.g. ``"en"``, ``"fr"``).

        Returns:
            The transcribed text string.
        """
        lang = language or self.language

        cmd = [
            self.cli_bin,
            "-m", self.model_path,
            "-f", audio_path,
            "-l", lang,
            "-t", str(self.threads),
        ]

        logger.info(
            "Running whisper.cpp: %s …", " ".join(str(c) for c in cmd)
        )
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error("whisper-cli stderr: %s", result.stderr)
            raise RuntimeError(
                f"whisper-cli failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        # whisper-cli writes segments like:
        #   [00:00:00.000 --> 00:00:11.000]  And so my fellow Americans ...
        # Strip the timestamp prefix on each line and collect non-empty segments.
        segments = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Remove leading timestamp bracket
            text = _TIMESTAMP_RE.sub("", line)
            if text:
                segments.append(text)

        return "\n".join(segments).strip()
