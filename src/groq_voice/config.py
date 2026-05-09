"""Configuration management for groq-voice."""
import os
from pathlib import Path
from typing import Dict, Any
import yaml
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manage application configuration with provider support."""
    
    def __init__(self, config_path: str = None):
        # Look for config in multiple locations
        default_paths = [
            str(Path(__file__).parent.parent / "config.yaml"),  # Development
            str(Path(__file__).parent / "config.yaml"),  # Alternative dev location
            str(Path.home() / ".config" / "groq_voice" / "config.yaml"),  # User config
            str(Path(__file__).parent.parent.parent / "config.yaml"),  # Root project
        ]
        
        # Use provided path or find first existing one
        if config_path:
            self.config_path = config_path
        else:
            for path in default_paths:
                if Path(path).exists():
                    self.config_path = path
                    break
            else:
                # Default to project root config.yaml
                self.config_path = str(Path(__file__).parent.parent.parent / "config.yaml")
        
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning("Config file not found: %s", self.config_path)
            return {}
        except yaml.YAMLError as e:
            logger.error("Failed to parse config: %s", e)
            return {}
    
    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get configuration for specific provider."""
        provider_config = self.config.get(provider_name, {})
        
        # Merge with global transcription settings
        transcription_config = self.config.get('transcription', {})
        
        # Provider-specific config takes precedence
        merged = transcription_config.copy()
        merged.update(provider_config)
        
        return merged
    
    def get_selected_provider(self) -> str:
        """Get the selected transcription provider."""
        return self.config.get('transcription', {}).get('provider', 'groq')
    
    def get_audio_config(self) -> Dict[str, Any]:
        """Get audio configuration."""
        return self.config.get('audio', {})
    
    def get_output_config(self) -> Dict[str, Any]:
        """Get output configuration."""
        return self.config.get('output', {})