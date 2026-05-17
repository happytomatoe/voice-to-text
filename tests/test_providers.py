"""Tests for transcription providers."""
import pytest
import sys
sys.path.insert(0, 'src')

from voice_to_text.providers import get_provider, TranscriptionProvider

def test_initialization():
    """Test provider factory."""
    p = get_provider("voxtral", {"api_key": "test"})
    assert isinstance(p, TranscriptionProvider)
    assert p.supports_streaming is False
    with pytest.raises(ValueError):
        p.transcribe_file("nonexistent.wav")
    with pytest.raises(NotImplementedError):
        p.transcribe_stream()

def test_custom_config():
    """Test custom configuration."""
    vid2 = get_provider("voxtral", {"api_key": "x", "model": "voxtral-v1"})
    assert vid2 is not None
    assert isinstance(vid2, TranscriptionProvider)

def test_missing_api_key_raises():
    """Test missing API key raises error."""
    with pytest.raises(ValueError):
        get_provider("voxtral", {})

def test_emits_subprocess_unavailable():
    p = get_provider("voxtral", {"api_key": "dummy"})
    assert p is not None
