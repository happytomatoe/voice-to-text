"""Tests for CLI argument parsing."""
import os
import subprocess
import sys
from pathlib import Path


def test_parses_extension_invocation_without_record():
    """GNOME extension calls without 'record' subcommand — must not argparse-error.

    Regression: removing _add_record_args from the root parser caused
    'voice-to-text --output stdout --provider groq --language en' to
    fail with unrecognized arguments (exit code 2).
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(
        Path(__file__).parent.parent / "src"
    )
    result = subprocess.run(
        [
            sys.executable, "-m", "voice_to_text.main",
            "--output", "stdout",
            "--provider", "groq",
            "--language", "en",
        ],
        capture_output=True, text=True, timeout=10,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode != 2, (
        f"Argparse rejected extension's args (exit 2):\n{result.stderr}"
    )
