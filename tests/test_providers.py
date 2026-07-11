"""Tests for transcription providers."""

import os

import pytest

from voice_to_text.providers import get_batch_provider
from voice_to_text.providers.elevenlabs import ElevenLabsProvider
from voice_to_text.providers.groq import GroqProvider


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
