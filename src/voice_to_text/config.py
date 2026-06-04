"""Configuration management for groq-voice."""

import os
from pathlib import Path
from typing import Dict, Any
import yaml
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manage application configuration with provider support."""

    def __init__(self, config_path: str | None = None):
        # User config path (persistent)
        self.user_config_path = str(
            Path.home() / ".config" / "voice-to-text" / "config.yaml"
        )

        # Look for config in multiple locations
        default_paths = [
            self.user_config_path,  # User config (persistent)
            str(Path(__file__).parent.parent / "config.yaml"),  # Development
            str(Path(__file__).parent / "config.yaml"),  # Alternative dev location
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
                self.config_path = self.user_config_path

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

    def save(self) -> bool:
        """Save config to a persistent location. If current path is inside a temp
        directory (e.g. PyInstaller bundle), migrate to user config path."""
        target = self.config_path
        if "_MEI" in target or "/tmp/" in target:
            target = self.user_config_path
            self.config_path = target
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(target, "w") as f:
                yaml.dump(self.config, f)
            return True
        except Exception:
            return False

    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get configuration for specific provider."""
        provider_config = self.config.get(provider_name, {})

        # Merge with global transcription settings
        transcription_config = self.config.get("transcription", {})

        # Provider-specific config takes precedence
        merged = transcription_config.copy()
        merged.update(provider_config)

        return merged

    def get_selected_provider(self) -> str:
        """Get the selected transcription provider."""
        return self.config.get("transcription", {}).get("provider", "voxtral")

    def get_audio_config(self) -> Dict[str, Any]:
        """Get audio configuration."""
        return self.config.get("audio", {})

    def get_output_config(self) -> Dict[str, Any]:
        """Get output configuration."""
        return self.config.get("output", {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.config.get("logging", {})

    def get_speaker_config(self) -> Dict[str, Any]:
        """Get speaker volume configuration."""
        audio_cfg = self.config.get("audio") or {}
        if not isinstance(audio_cfg, dict):
            return {}
        speaker_cfg = audio_cfg.get("speaker") or {}
        return speaker_cfg if isinstance(speaker_cfg, dict) else {}
