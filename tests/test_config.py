"""Tests for configuration management."""
import pytest
import tempfile
import os

from voice_to_text.config import ConfigManager

@pytest.fixture
def sample_config():
    config_content = """
providers:
  groq:
    api_key_env: GROQ_API_KEY
    model: whisper-large-v3-turbo
  voxtral:
    api_key_env: VOXTRAL_API_KEY
    model: voxtral-mini-latest
selected_provider: groq
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        config_path = f.name
    yield config_path
    os.unlink(config_path)

def test_config_management(sample_config):
    config_mgr = ConfigManager(sample_config)
    provider = config_mgr.get_selected_provider()
    assert provider in ['groq', 'voxtral']

    provider_config = config_mgr.get_provider_config(provider)
    assert 'api_key_env' in provider_config

def test_provider_instantiation():
    config_mgr = ConfigManager('/home/l/git/voice_to_text/config.yaml')
    provider_name = config_mgr.get_selected_provider()
    provider_config = config_mgr.get_provider_config(provider_name)

    from voice_to_text.providers import get_provider
    try:
        provider = get_provider(provider_name, provider_config)
        assert provider.name == provider_name
    except ValueError as e:
        assert "not set" in str(e)