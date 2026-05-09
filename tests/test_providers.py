"""Tests for transcription providers."""
import pytest
import sys
sys.path.insert(0, 'src')

from groq_voice.providers import get_provider, TranscriptionProvider
from groq_voice.providers.groq import GroqProvider

class TestProviderFactory:
    def test_get_groq_provider(self):
        config = {'api_key': 'test_key', 'model': 'whisper-large-v3-turbo'}
        provider = get_provider('groq', config)
        assert isinstance(provider, GroqProvider)
        assert provider.name == 'groq'
        assert not provider.supports_streaming
    
    def test_invalid_provider(self):
        with pytest.raises(ValueError):
            get_provider('invalid', {})

class TestGroqProvider:
    def test_initialization(self):
        config = {'api_key': 'test_key'}
        provider = GroqProvider(config)
        assert provider.model == 'whisper-large-v3-turbo'
    
    def test_missing_api_key(self):
        # Unset the environment variable for this test
        import os
        old_key = os.environ.pop('GROQ_API_KEY', None)
        try:
            with pytest.raises(ValueError):
                GroqProvider({})
        finally:
            if old_key is not None:
                os.environ['GROQ_API_KEY'] = old_key