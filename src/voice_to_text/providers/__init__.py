"""Transcription provider factory and registry."""
from typing import Dict, Any, Type
from .base import BatchProvider, StreamingProvider
from .groq import GroqProvider
from .deepgram import DeepgramProvider
from .voxtral import VoxtralProvider
from .parakeet import ParakeetProvider

_BATCH_PROVIDERS = {
    "groq": GroqProvider,
    "deepgram": DeepgramProvider,
    "voxtral": VoxtralProvider,
    "parakeet": ParakeetProvider,
}

_STREAMING_PROVIDERS = {
    "groq": GroqProvider,
    "deepgram": DeepgramProvider,
}

def get_batch_provider(name: str, config: Dict[str, Any]) -> BatchProvider:
    """Get batch provider instance."""
    if name not in _BATCH_PROVIDERS:
        raise ValueError(f"Batch provider '{name}' not found. Available: {list(_BATCH_PROVIDERS.keys())}")
    return _BATCH_PROVIDERS[name](config)

def get_streaming_provider(name: str, config: Dict[str, Any]) -> StreamingProvider:
    """Get streaming provider instance."""
    if name not in _STREAMING_PROVIDERS:
        raise ValueError(f"Streaming provider '{name}' not found. Available: {list(_STREAMING_PROVIDERS.keys())}")
    return _STREAMING_PROVIDERS[name](config)

# Legacy compatibility
def get_provider(provider_name: str, config: Dict[str, Any]) -> BatchProvider:
    """Get transcription provider instance (legacy compatibility)."""
    return get_batch_provider(provider_name, config)