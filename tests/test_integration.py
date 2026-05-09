"""Integration tests for multi-provider system."""
import pytest
import sys
sys.path.insert(0, 'src')

def test_config_loading():
    """Test config.yaml loading."""
    from groq_voice.main import load_config
    config = load_config()
    assert hasattr(config, 'get_selected_provider')

def test_provider_instantiation():
    """Test provider instantiation through main config."""
    from groq_voice.main import load_config
    from groq_voice.providers import get_provider
    
    config = load_config()
    provider_name = config.get_selected_provider()
    provider_config = config.get_provider_config(provider_name)
    
    # Test that we can instantiate the configured provider
    try:
        provider = get_provider(provider_name, provider_config)
        assert provider.name == provider_name
    except ValueError as e:
        # Expected if API key is missing
        assert "not set" in str(e)

def test_cli_help():
    """Test that CLI help works."""
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "groq_voice.main", "record", "--help"
    ], capture_output=True, text=True, cwd="src")
    assert result.returncode == 0
    assert "--provider" in result.stdout