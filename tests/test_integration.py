"""Integration tests for multi-provider system."""
import inspect
import sys
import pytest

sys.path.insert(0, 'src')

from voice_to_text.main import STREAMING_PROVIDERS
from voice_to_text.providers import get_provider
import voice_to_text.main

def test_streaming_provider_routing():
    assert "voxtral" not in STREAMING_PROVIDERS
    assert "groq" not in STREAMING_PROVIDERS

def test_streaming_only_providers_return_value():
    """Streaming providers raise NotImplementedError for transcribe_file."""
    p = get_provider("voxtral_realtime", {"api_key": "dummy"})
    assert p.supports_streaming is True
    with pytest.raises(NotImplementedError):
        p.transcribe_file("dummy.wav")

def test_no_mode_flag_in_argparse():
    """Mode flag removed from argparse; provider determines mode automatically."""
    src = inspect.getsource(voice_to_text.main)
    assert "mode" not in src.split("def main")[1], \
        "`mode` string still appears in main() (remove --mode extraction and routing)"

def test_setup_interactive_no_mode_reference():
    """Setup menu lists providers by name only - no mode/batch/realtime distinction."""
    src = inspect.getsource(voice_to_text.main)
    setup_src = src.split("def setup_interactive()")[1]
    assert "batch" not in setup_src.lower(), \
        "setup_interactive still mentions batch/realtime instead of letting provider decide"
    assert "Voxtral" in setup_src
    assert "Voxtral Realtime" in setup_src
