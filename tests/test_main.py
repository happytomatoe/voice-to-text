"""Tests for CLI argument parsing."""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


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


class TestSetupKeyInteractive:
    """Issues #1 (persist provider) and #2 (non-interactive env-var path)."""

    def test_env_vars_skip_prompts_and_persist_provider(self, tmp_path, monkeypatch):
        from voice_to_text import main

        # Isolate the user config to a temp dir.
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        env = {
            "VOICE_TO_TEXT_PROVIDER": "groq",
            "VOICE_TO_TEXT_API_KEY": "test-key-123",
        }
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        # Make sure stale vars from the test runner don't leak in
        for k in ("VOICE_TO_TEXT_PROVIDER", "VOICE_TO_TEXT_API_KEY"):
            monkeypatch.delenv(k, raising=False) if k not in env else None
        monkeypatch.setenv("VOICE_TO_TEXT_PROVIDER", "groq")
        monkeypatch.setenv("VOICE_TO_TEXT_API_KEY", "test-key-123")

        # Pretend secret-tool succeeded and the shell is unknown (so the
        # function returns before touching the user's real shell RC).
        fake_run = MagicMock(return_value=MagicMock(returncode=0))
        monkeypatch.setattr(main.subprocess, "run", fake_run)
        monkeypatch.setattr(main, "detect_shell_rc", lambda: None)

        main.setup_key_interactive()

        # secret-tool was called with the right args
        args, _kwargs = fake_run.call_args
        assert args[0][:1] == ["secret-tool"]
        assert args[0][1] == "store"
        assert "groq" in args[0]
        assert _kwargs["input"] == b"test-key-123"

        # And the config was written with provider=groq
        user_config = tmp_path / ".config" / "voice-to-text" / "config.yaml"
        assert user_config.exists()
        assert "provider: groq" in user_config.read_text()

    def test_non_tty_without_env_returns_early(self, tmp_path, monkeypatch, capsys):
        from voice_to_text import main

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("VOICE_TO_TEXT_PROVIDER", raising=False)
        monkeypatch.delenv("VOICE_TO_TEXT_API_KEY", raising=False)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

        # secret-tool must NOT be called
        fake_run = MagicMock()
        monkeypatch.setattr(main.subprocess, "run", fake_run)

        main.setup_key_interactive()

        fake_run.assert_not_called()
        captured = capsys.readouterr()
        assert "Non-interactive" in captured.out
        # No config file should have been created
        assert not (tmp_path / ".config" / "voice-to-text" / "config.yaml").exists()


class TestSetupInteractive:
    """Issue #2 non-interactive path for `setup`, #1 use of save()."""

    def test_env_provider_var_persists_without_prompting(self, tmp_path, monkeypatch, capsys):
        from voice_to_text import main

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("VOICE_TO_TEXT_PROVIDER", "groq")
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

        main.setup_interactive()

        user_config = tmp_path / ".config" / "voice-to-text" / "config.yaml"
        assert user_config.exists()
        assert "provider: groq" in user_config.read_text()
        captured = capsys.readouterr()
        assert "Provider set to: groq" in captured.out

    def test_non_tty_without_env_returns_early(self, tmp_path, monkeypatch, capsys):
        from voice_to_text import main

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("VOICE_TO_TEXT_PROVIDER", raising=False)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

        main.setup_interactive()

        captured = capsys.readouterr()
        assert "Non-interactive" in captured.out
        assert not (tmp_path / ".config" / "voice-to-text" / "config.yaml").exists()
