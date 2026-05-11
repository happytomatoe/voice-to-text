"""IBus-specific configuration management."""

import os
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manage IBus engine configuration."""

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        """Load configuration from file."""
        config_paths = [
            str(Path.home() / ".config" / "voice-to-text" / "config.yaml"),
            str(Path(__file__).parent.parent.parent / "config.yaml"),
        ]

        for path in config_paths:
            if Path(path).exists():
                try:
                    with open(path) as f:
                        return yaml.safe_load(f) or {}
                except Exception as e:
                    logger.warning("Failed to load config from %s: %s", path, e)

        return {}

    def get_max_duration(self):
        """Get maximum recording duration in seconds."""
        return self.config.get("audio", {}).get("duration", 30)

    def get_audio_device(self):
        """Get audio device index (None for default)."""
        return self.config.get("audio", {}).get("device")

    def get_notifications_enabled(self):
        """Check if notifications are enabled."""
        return self.config.get("ibus", {}).get("notifications", True)

    def get_selected_provider(self):
        """Get selected transcription provider."""
        return self.config.get("transcription", {}).get("provider", "groq")

    def get_provider_config(self, provider_name):
        """Get configuration for specific provider."""
        provider_config = self.config.get(provider_name, {})
        transcription_config = self.config.get("transcription", {})
        merged = transcription_config.copy()
        merged.update(provider_config)
        return merged