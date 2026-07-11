"""Tests for transcription providers."""

import os

import pytest

from voice_to_text.providers import get_batch_provider, get_streaming_provider
from voice_to_text.providers.elevenlabs import ElevenLabsProvider
from voice_to_text.providers.groq import GroqProvider
from voice_to_text.providers.sixty import SixtyProvider


class TestProviderFactory:
    def test_get_groq_provider(self):
        config = {"api_key": "test_key", "model": "whisper-large-v3-turbo"}
        provider = get_batch_provider("groq", config)
        assert isinstance(provider, GroqProvider)
        assert provider.name == "groq"

    def test_invalid_provider(self):
        with pytest.raises(ValueError):
            get_batch_provider("invalid", {})


class TestGroqProvider:
    def test_initialization(self):
        config = {"api_key": "test_key"}
        provider = GroqProvider(config)
        assert provider.model == "whisper-large-v3-turbo"

    def test_missing_api_key(self):
        old_key = os.environ.pop("GROQ_API_KEY", None)
        try:
            with pytest.raises(ValueError):
                GroqProvider({})
        finally:
            if old_key is not None:
                os.environ["GROQ_API_KEY"] = old_key


class TestSixtyProvider:
    def test_get_sixty_provider(self):
        config = {"api_key": "test_key"}
        provider = get_batch_provider("60db", config)
        assert isinstance(provider, SixtyProvider)
        assert provider.name == "60db"

    def test_get_streaming_provider(self):
        config = {"api_key": "test_key"}
        provider = get_streaming_provider("60db", config)
        assert isinstance(provider, SixtyProvider)
        assert provider.name == "60db"

    def test_initialization(self):
        config = {"api_key": "test_key"}
        provider = SixtyProvider(config)
        assert provider.model == "60db-stt-v01"
        assert provider.api_url == "https://api.60db.ai"

    def test_missing_api_key(self):
        import os

        old_key = os.environ.pop("SIXTYDB_API_KEY", None)
        try:
            with pytest.raises(ValueError):
                SixtyProvider({})
        finally:
            if old_key is not None:
                os.environ["SIXTYDB_API_KEY"] = old_key


class TestElevenLabsProvider:
    def test_initialization(self):
        config = {"api_key": "test_key"}
        provider = ElevenLabsProvider(config)
        assert provider.model == "scribe_v2"
        assert provider.api_url == "https://api.elevenlabs.io"
        assert provider.tag_audio_events is False

    def test_missing_api_key(self):
        old_key = os.environ.pop("ELEVENLABS_API_KEY", None)
        try:
            with pytest.raises(ValueError):
                ElevenLabsProvider({})
        finally:
            if old_key is not None:
                os.environ["ELEVENLABS_API_KEY"] = old_key
