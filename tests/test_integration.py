"""Integration tests for multi-provider system."""
import pytest

def test_provider_factory():
    """Test provider factory works."""
    from voice_to_text.providers import get_batch_provider

    config = {'api_key': 'test_key'}
    provider = get_batch_provider('groq', config)
    assert provider.name == 'groq'

def test_provider_config():
    """Test provider config parsing."""
    import tempfile
    import os

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

    try:
        from voice_to_text.config import ConfigManager
        config_mgr = ConfigManager(config_path)
        provider_name = config_mgr.get_selected_provider()
        provider_config = config_mgr.get_provider_config(provider_name)
        assert provider_name == 'groq'
        assert 'api_key_env' in provider_config
    finally:
        os.unlink(config_path)