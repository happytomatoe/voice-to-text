"""Transcription provider factory and registry."""

from typing import Any

from .base import TranscriptionProvider
from .deepgram import DeepgramProvider
from .groq import GroqProvider
from .parakeet import ParakeetProvider
from .voxtral import VoxtralProvider

# Provider registry
_PROVIDERS: dict[str, type[TranscriptionProvider]] = {
    "deepgram": DeepgramProvider,
    "groq": GroqProvider,
    "voxtral": VoxtralProvider,
    "parakeet": ParakeetProvider,
}


def get_provider(provider_name: str, config: dict[str, Any]) -> TranscriptionProvider:
    """Get transcription provider instance.

    Args:
        provider_name: Name of provider to use
        config: Provider-specific configuration

    Returns:
        Configured provider instance

    Raises:
        ValueError: If provider not found
    """
    if provider_name not in _PROVIDERS:
        raise ValueError(f"Provider '{provider_name}' not found. Available: {list(_PROVIDERS.keys())}")

    return _PROVIDERS[provider_name](config)


def register_provider(name: str, provider_class: type[TranscriptionProvider]):
    """Register a new transcription provider."""
    _PROVIDERS[name] = provider_class
