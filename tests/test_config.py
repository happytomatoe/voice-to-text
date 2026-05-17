"""Tests for configuration management."""
import sys, os
sys.path.insert(0, 'src')

from voice_to_text.config import ConfigManager
from voice_to_text.providers import get_provider

def test_config_management():
    """Test config.yaml loading using the project's own config file."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(repo_root, "config.yaml")
    config_mgr = ConfigManager(config_path)

    provider = config_mgr.get_selected_provider()
    assert provider in ['groq', 'voxtral']

    provider_config = config_mgr.get_provider_config(provider)
    assert 'api_key_env' in provider_config

    # The default config file must also expose the realtime section
    rt_config = config_mgr.config.get("voxtral_realtime", {})
    assert "realtime_model" in rt_config
    assert "target_delay_ms" in rt_config

def test_provider_instantiation():
    """Test that the configured provider can be instantiated (may raise on missing key)."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_mgr = ConfigManager(os.path.join(repo_root, "config.yaml"))
    provider_name = config_mgr.get_selected_provider()
    provider_config = config_mgr.get_provider_config(provider_name)
    try:
        provider = get_provider(provider_name, provider_config)
        assert provider.name == provider_name
    except ValueError as e:
        assert "not set" in str(e)
