"""Tests for configuration management."""
import pytest
import sys
sys.path.insert(0, 'src')

from voice_to_text.config import ConfigManager

def test_config_management():
    config_mgr = ConfigManager('/home/l/git/voice_to_text/config.yaml')
    provider = config_mgr.get_selected_provider()
    assert provider in ['groq', 'voxtral']
    
    provider_config = config_mgr.get_provider_config(provider)
    assert 'api_key_env' in provider_config

def test_provider_instantiation():
    config_mgr = ConfigManager('/home/l/git/voice_to_text/config.yaml')
    provider_name = config_mgr.get_selected_provider()
    provider_config = config_mgr.get_provider_config(provider_name)
    
    # Test that we can instantiate the configured provider
    # (won't work without API keys, but should not crash on import/config)
    from voice_to_text.providers import get_provider
    try:
        provider = get_provider(provider_name, provider_config)
        assert provider.name == provider_name
    except ValueError as e:
        # Expected if API key is missing
        assert "not set" in str(e)