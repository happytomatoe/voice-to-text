"""Tests for configuration management."""
import pytest
import tempfile
import os

from voice_to_text.config import ConfigManager
from voice_to_text.providers import get_batch_provider

@pytest.fixture
def groq_config():
    config_content = """
transcription:
  provider: groq
groq:
  api_key_env: GROQ_API_KEY
  model: whisper-large-v3-turbo
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    yield config_path
    os.unlink(config_path)

def test_config_management(groq_config):
    config_mgr = ConfigManager(groq_config)
    provider = config_mgr.get_selected_provider()
    assert provider == 'groq'

    provider_config = config_mgr.get_provider_config(provider)
    assert 'api_key_env' in provider_config

def test_provider_instantiation(groq_config):
    config_mgr = ConfigManager(groq_config)
    provider_name = config_mgr.get_selected_provider()
    provider_config = config_mgr.get_provider_config(provider_name)

    try:
        provider = get_batch_provider(provider_name, provider_config)
        assert provider.name == provider_name
    except ValueError as e:
        assert "GROQ_API_KEY" in str(e)

def test_speaker_config_defaults(groq_config):
    config_mgr = ConfigManager(groq_config)
    speaker_config = config_mgr.get_speaker_config()
    assert speaker_config == {}

def test_speaker_config_with_values():
    config_content = """
audio:
  speaker:
    decrease_volume: 50
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name

    try:
        config_mgr = ConfigManager(config_path)
        speaker_config = config_mgr.get_speaker_config()
        assert speaker_config.get("decrease_volume") == 50
    finally:
        os.unlink(config_path)