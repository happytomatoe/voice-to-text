# Multi-Provider Transcription System Refactoring Plan

## Overview

Refactor the current Groq Whisper-only transcription system to support multiple providers including Voxtral realtime streaming transcription. This will enable users to select and configure different transcription providers through the configuration system.

## Current State Analysis

**Current Architecture:**
- Single `GroqTranscriber` class in `src/groq_voice/transcriber.py`
- Hardcoded Groq Whisper API usage
- Batch transcription only (record → save file → transcribe)
- Configuration limited to model selection within Groq ecosystem
- No provider abstraction or switching mechanism

**Key Files:**
- `src/groq_voice/transcriber.py`: Current Groq-specific implementation
- `src/groq_voice/main.py`: Main application with hardcoded transcriber instantiation
- `config.yaml`: Basic configuration with model selection
- `src/groq_voice/audio_recorder.py`: Audio capture (will need modification for streaming)

## Desired End State

**Target Architecture:**
- Provider abstraction interface for consistent API
- Multiple provider implementations (Groq, Voxtral, potentially others)
- Realtime streaming support for Voxtral
- Provider selection via configuration
- Backward compatibility with existing Groq Whisper usage

### Key Discoveries:
- Current system uses batch processing (record → file → transcribe)
- Voxtral requires realtime streaming over WebSocket
- Audio format: 16kHz, 16-bit mono (int16) - compatible with both providers
- Need to maintain existing CLI interface and functionality
- Configuration system already exists but needs provider-specific extensions

## What We're NOT Doing

- Not changing the core CLI interface or user experience
- Not implementing TTS/narrator features (out of scope)
- Not changing audio recording format or quality
- Not implementing provider auto-detection or failover (manual selection only)
- Not adding GUI or interactive provider switching during runtime

## Implementation Approach

**Strategy:**
1. Create provider abstraction interface
2. Implement concrete providers (Groq batch, Voxtral streaming)
3. Add provider factory and configuration management
4. Update main application to use provider abstraction
5. Maintain backward compatibility

**Phased Approach:**
- Phase 1: Provider abstraction and Groq migration
- Phase 2: Voxtral streaming implementation
- Phase 3: Configuration and provider selection
- Phase 4: Main application integration
- Phase 5: Testing and validation

## Phase 1: Provider Abstraction Interface

### Overview
Create a base provider interface and migrate existing Groq implementation to use it.

### Changes Required:

#### 1. Provider Interface (`src/groq_voice/providers/base.py`)
**File**: `src/groq_voice/providers/base.py`
**Changes**: New file with abstract base class

```python
"""Base provider interface for transcription services."""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers."""
    
    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration
        """
        pass
    
    @abstractmethod
    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file (batch processing).
        
        Args:
            audio_path: Path to audio file
            language: Language code
            
        Returns:
            Transcribed text
        """
        pass
    
    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes], 
                               language: str = "en") -> AsyncIterator[str]:
        """Transcribe audio stream in realtime.
        
        Args:
            audio_stream: Async iterator yielding audio chunks (bytes)
            language: Language code
            
        Yields:
            Transcription text deltas as they become available
        """
        pass
    
    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Return True if provider supports realtime streaming."""
        pass
    
    @property
    @abstractmethod  
    def name(self) -> str:
        """Provider name identifier."""
        pass
```

#### 2. Groq Provider Implementation (`src/groq_voice/providers/groq.py`)
**File**: `src/groq_voice/providers/groq.py`
**Changes**: New file, migrate existing functionality

```python
"""Groq Whisper transcription provider."""
from groq import Groq
from typing import AsyncIterator, Dict, Any
import logging
import os
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)

class GroqProvider(TranscriptionProvider):
    """Groq Whisper batch transcription provider."""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key') or os.getenv(config.get('api_key_env', 'GROQ_API_KEY'))
        if not self.api_key:
            raise ValueError(f"{config.get('api_key_env', 'GROQ_API_KEY')} not set")
        self.model = config.get('model', 'whisper-large-v3-turbo')
        self.client = Groq(api_key=self.api_key)
    
    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file using Groq Whisper."""
        logger.info("Transcribing %s with Groq model %s", audio_path, self.model)
        try:
            with open(audio_path, "rb") as f:
                transcription = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=f,
                    language=language,
                    response_format="text"
                )
            result = str(transcription).strip()
            logger.info("Transcription result: %s", result[:100])
            return result
        except Exception as e:
            logger.exception("Groq transcription API call failed")
            raise
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes], 
                               language: str = "en") -> AsyncIterator[str]:
        """Groq does not support streaming transcription."""
        raise NotImplementedError("Groq provider does not support streaming transcription")
    
    @property
    def supports_streaming(self) -> bool:
        return False
    
    @property
    def name(self) -> str:
        return "groq"
```

#### 3. Provider Factory (`src/groq_voice/providers/__init__.py`)
**File**: `src/groq_voice/providers/__init__.py`
**Changes**: New file for provider registration and factory

```python
"""Transcription provider factory and registry."""
from typing import Dict, Any, Type
from .base import TranscriptionProvider
from .groq import GroqProvider

# Provider registry
_PROVIDERS: Dict[str, Type[TranscriptionProvider]] = {
    "groq": GroqProvider,
}

def get_provider(provider_name: str, config: Dict[str, Any]) -> TranscriptionProvider:
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

def register_provider(name: str, provider_class: Type[TranscriptionProvider]):
    """Register a new transcription provider."""
    _PROVIDERS[name] = provider_class
```

### Success Criteria:

#### Automated Verification:
- [ ] Provider interface file exists: `src/groq_voice/providers/base.py`
- [ ] Groq provider implementation exists: `src/groq_voice/providers/groq.py`
- [ ] Provider factory exists: `src/groq_voice/providers/__init__.py`
- [ ] Unit tests pass: `python -m pytest tests/test_providers.py -v`
- [ ] Type checking passes: `mypy src/groq_voice/providers/`
- [ ] Linting passes: `ruff check src/groq_voice/providers/`

#### Manual Verification:
- [ ] Existing Groq functionality works identically through new interface
- [ ] Provider factory correctly instantiates Groq provider
- [ ] Configuration is properly passed to provider instances
- [ ] Error handling works as expected

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that the provider abstraction works correctly before proceeding to streaming implementation.

---

## Phase 2: Voxtral Streaming Provider

### Overview
Implement Voxtral realtime streaming transcription provider with WebSocket support.

### Changes Required:

#### 1. Voxtral Provider Implementation (`src/groq_voice/providers/voxtral.py`)
**File**: `src/groq_voice/providers/voxtral.py`
**Changes**: New file with streaming implementation

```python
"""Voxtral realtime transcription provider."""
import asyncio
import websockets
import json
import logging
from typing import AsyncIterator, Dict, Any, Optional
import os
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)

class VoxtralProvider(TranscriptionProvider):
    """Voxtral realtime streaming transcription provider."""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key') or os.getenv(config.get('api_key_env', 'VOXTRAL_API_KEY'))
        if not self.api_key:
            raise ValueError(f"{config.get('api_key_env', 'VOXTRAL_API_KEY')} not set")
        self.model = config.get('model', 'voxtral-mini-transcribe-realtime-2602')
        self.api_url = config.get('api_url', 'wss://api.mistral.ai')
        self.streaming_delay = config.get('streaming_delay', 500)  # ms
    
    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Voxtral batch transcription (not primary use case)."""
        # Could implement file upload, but streaming is the main feature
        raise NotImplementedError("Voxtral provider focuses on streaming transcription")
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes], 
                               language: str = "en") -> AsyncIterator[str]:
        """Transcribe audio stream in realtime using Voxtral WebSocket API."""
        uri = f"{self.api_url}/v1/audio/realtime/transcribe"
        
        async with websockets.connect(
            uri,
            extra_headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        ) as websocket:
            # Send initial configuration
            config_msg = {
                "model": self.model,
                "language": language,
                "streaming_delay": self.streaming_delay
            }
            await websocket.send(json.dumps(config_msg))
            
            # Start audio streaming task
            async def send_audio():
                async for chunk in audio_stream:
                    await websocket.send(chunk)
            
            audio_task = asyncio.create_task(send_audio())
            
            try:
                # Process incoming transcription events
                async for message in websocket:
                    try:
                        event = json.loads(message)
                        event_type = event.get('type')
                        
                        if event_type == 'transcription_text_delta':
                            text_delta = event.get('text', '')
                            if text_delta:
                                yield text_delta
                        elif event_type == 'transcription_done':
                            break
                        elif event_type == 'error':
                            error_msg = event.get('message', 'Unknown error')
                            logger.error("Voxtral transcription error: %s", error_msg)
                            raise RuntimeError(f"Voxtral transcription error: {error_msg}")
                    except json.JSONDecodeError:
                        logger.warning("Received non-JSON message: %s", message[:100])
            finally:
                audio_task.cancel()
                try:
                    await audio_task
                except asyncio.CancelledError:
                    pass
    
    @property
    def supports_streaming(self) -> bool:
        return True
    
    @property
    def name(self) -> str:
        return "voxtral"
```

#### 2. Register Voxtral Provider
**File**: `src/groq_voice/providers/__init__.py`
**Changes**: Add Voxtral to provider registry

```python
# Add to imports
from .voxtral import VoxtralProvider

# Add to registry
_PROVIDERS: Dict[str, Type[TranscriptionProvider]] = {
    "groq": GroqProvider,
    "voxtral": VoxtralProvider,
}
```

#### 3. Audio Streaming Adapter (`src/groq_voice/audio_stream.py`)
**File**: `src/groq_voice/audio_stream.py`
**Changes**: New file to adapt audio recorder for streaming

```python
"""Audio streaming adapter for transcription providers."""
import asyncio
import numpy as np
from typing import AsyncIterator
import logging

logger = logging.getLogger(__name__)

class AudioStreamAdapter:
    """Adapt audio recorder to async stream for transcription providers."""
    
    def __init__(self, audio_recorder, chunk_size=4096):
        self.audio_recorder = audio_recorder
        self.chunk_size = chunk_size
        self._queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
    
    def start(self):
        """Start audio capture and streaming."""
        self.audio_recorder.start()
        self._capture_task = asyncio.create_task(self._capture_audio())
    
    async def _capture_audio(self):
        """Capture audio and push to queue."""
        try:
            while not self._stop_event.is_set():
                if self.audio_recorder.frames:
                    # Get accumulated frames
                    audio_data = self.audio_recorder._get_audio_data()
                    self.audio_recorder.frames = []  # Clear frames
                    
                    # Convert to bytes and chunk
                    audio_bytes = audio_data.tobytes()
                    for i in range(0, len(audio_bytes), self.chunk_size):
                        chunk = audio_bytes[i:i + self.chunk_size]
                        await self._queue.put(chunk)
                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
        except Exception as e:
            logger.exception("Audio capture failed")
        finally:
            self._queue.put_nowait(None)  # Signal end
    
    async def __aiter__(self):
        """Async iterator interface."""
        while True:
            item = await self._queue.get()
            if item is None:  # End signal
                break
            yield item
    
    def stop(self):
        """Stop audio capture."""
        self._stop_event.set()
        self.audio_recorder.stop()
        if hasattr(self, '_capture_task'):
            self._capture_task.cancel()
```

### Success Criteria:

#### Automated Verification:
- [ ] Voxtral provider exists: `src/groq_voice/providers/voxtral.py`
- [ ] Audio stream adapter exists: `src/groq_voice/audio_stream.py`
- [ ] Voxtral registered in provider factory
- [ ] Unit tests pass: `python -m pytest tests/test_voxtral.py -v`
- [ ] Type checking passes: `mypy src/groq_voice/providers/voxtral.py src/groq_voice/audio_stream.py`
- [ ] Linting passes: `ruff check src/groq_voice/providers/voxtral.py src/groq_voice/audio_stream.py`

#### Manual Verification:
- [ ] Voxtral provider can connect to WebSocket API
- [ ] Audio streaming works with Voxtral format requirements
- [ ] Realtime transcription events are properly handled
- [ ] Error handling works for connection issues

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that Voxtral streaming works correctly before proceeding to configuration integration.

---

## Phase 3: Configuration and Provider Selection

### Overview
Enhance configuration system to support provider selection and provider-specific settings.

### Changes Required:

#### 1. Enhanced Configuration (`config.yaml`)
**File**: `config.yaml`
**Changes**: Add provider selection and Voxtral configuration

```yaml
# groq-voice configuration
# Multi-provider transcription system

# Provider selection
transcription:
  provider: "groq"  # "groq" or "voxtral"
  model: "whisper-large-v3-turbo"
  language: "en"
  
# Provider-specific configurations
groq:
  api_key_env: "GROQ_API_KEY"
  
voxtral:
  api_key_env: "VOXTRAL_API_KEY"
  model: "voxtral-mini-transcribe-realtime-2602"
  api_url: "wss://api.mistral.ai"
  streaming_delay: 500  # milliseconds

audio:
  sample_rate: 16000
  channels: 1
  block_size: 2048
  smooth_factor: 0.7

output:
  method: "clipboard"  # only clipboard supported

logging:
  file: "~/.local/share/groq_voice/groq_voice.log"
  level: "info"
```

#### 2. Configuration Manager (`src/groq_voice/config.py`)
**File**: `src/groq_voice/config.py`
**Changes**: New file for enhanced configuration management

```python
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
        self.config_path = config_path or str(Path(__file__).parent.parent / "config.yaml")
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
```

#### 3. Update Main Application Configuration Loading
**File**: `src/groq_voice/main.py`
**Changes**: Replace direct config loading with ConfigManager

```python
# Replace load_config() function with:
from groq_voice.config import ConfigManager

def load_config():
    """Load configuration using ConfigManager."""
    return ConfigManager()
```

### Success Criteria:

#### Automated Verification:
- [ ] Configuration manager exists: `src/groq_voice/config.py`
- [ ] Updated config.yaml with provider settings
- [ ] Configuration loading works: `python -c "from groq_voice.config import ConfigManager; print(ConfigManager().get_selected_provider())"`
- [ ] Type checking passes: `mypy src/groq_voice/config.py`
- [ ] Linting passes: `ruff check src/groq_voice/config.py`

#### Manual Verification:
- [ ] Provider selection works from config file
- [ ] Provider-specific configurations are properly merged
- [ ] Default values work when config is missing
- [ ] Configuration errors are handled gracefully

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that configuration management works correctly before proceeding to main application integration.

---

## Phase 4: Main Application Integration

### Overview
Update the main application to use the new provider system and support both batch and streaming modes.

### Changes Required:

#### 1. Update Main Application (`src/groq_voice/main.py`)
**File**: `src/groq_voice/main.py`
**Changes**: Integrate provider system and add streaming support

```python
# Add imports
from groq_voice.providers import get_provider
from groq_voice.audio_stream import AudioStreamAdapter
import asyncio

# Replace transcriber instantiation (around line 156)
# Old: transcriber = GroqTranscriber(model=model)
# New:
config_mgr = load_config()
selected_provider = config_mgr.get_selected_provider()
provider_config = config_mgr.get_provider_config(selected_provider)
transcriber = get_provider(selected_provider, provider_config)

# Add streaming mode detection and handling
def should_use_streaming(transcriber) -> bool:
    """Determine if we should use streaming based on provider capabilities."""
    # For now, only use streaming if explicitly requested
    # Could add --stream flag or auto-detect based on provider
    return False  # Start with batch mode for compatibility

# Update transcription section (around line 296)
# Old batch-only approach:
# text = transcriber.transcribe(audio_path, language=language)

# New approach with streaming support:
if should_use_streaming(transcriber) and transcriber.supports_streaming:
    print("\nStreaming transcription...")
    logger.info("Starting streaming transcription")
    
    # Create audio stream adapter
    stream_adapter = AudioStreamAdapter(audio_recorder)
    stream_adapter.start()
    
    # Run async transcription
    try:
        text_parts = []
        async for text_delta in transcriber.transcribe_stream(stream_adapter, language=language):
            text_parts.append(text_delta)
            # Could show realtime updates here if desired
        text = ''.join(text_parts).strip()
    except Exception as e:
        logger.exception("Streaming transcription failed")
        raise
    finally:
        stream_adapter.stop()
else:
    # Fall back to batch processing
    print("\nTranscribing...")
    logger.info("Starting transcription")
    text = transcriber.transcribe_file(audio_path, language=language)
```

#### 2. Add Provider Selection CLI Argument
**File**: `src/groq_voice/main.py`
**Changes**: Add --provider argument

```python
# Add to argument parser (around line 100)
record_parser.add_argument(
    "--provider",
    type=str,
    choices=["groq", "voxtral"],
    help="Transcription provider to use"
)

# Update config loading to respect CLI override
provider_override = args.provider if hasattr(args, 'provider') and args.provider else None
selected_provider = provider_override or config_mgr.get_selected_provider()
```

### Success Criteria:

#### Automated Verification:
- [ ] Main application runs without errors: `python -m groq_voice.main --help`
- [ ] Groq provider works: `python -m groq_voice.main record --duration 3 --provider groq`
- [ ] Voxtral provider works (when configured): `python -m groq_voice.main record --duration 3 --provider voxtral`
- [ ] Unit tests pass: `python -m pytest tests/test_integration.py -v`
- [ ] Type checking passes: `mypy src/groq_voice/main.py`
- [ ] Linting passes: `ruff check src/groq_voice/main.py`

#### Manual Verification:
- [ ] Existing Groq functionality works identically
- [ ] Provider selection via CLI works
- [ ] Provider selection via config works
- [ ] Error messages are clear when provider is misconfigured
- [ ] Streaming mode works when enabled
- [ ] Batch mode still works as fallback

**Implementation Note**: After completing this phase and all automated verification passes, pause here for comprehensive manual testing of all provider combinations and modes before finalizing.

---

## Phase 5: Testing and Validation

### Overview
Comprehensive testing to ensure all functionality works correctly.

### Changes Required:

#### 1. Unit Tests (`tests/test_providers.py`)
**File**: `tests/test_providers.py`
**Changes**: Add comprehensive provider tests

```python
"""Tests for transcription providers."""
import pytest
from groq_voice.providers import get_provider, TranscriptionProvider
from groq_voice.providers.groq import GroqProvider
from groq_voice.providers.voxtral import VoxtralProvider

class TestProviderFactory:
    def test_get_groq_provider(self):
        config = {'api_key': 'test_key', 'model': 'whisper-large-v3-turbo'}
        provider = get_provider('groq', config)
        assert isinstance(provider, GroqProvider)
        assert provider.name == 'groq'
        assert not provider.supports_streaming
    
    def test_get_voxtral_provider(self):
        config = {'api_key': 'test_key', 'model': 'voxtral-mini-transcribe-realtime-2602'}
        provider = get_provider('voxtral', config)
        assert isinstance(provider, VoxtralProvider)
        assert provider.name == 'voxtral'
        assert provider.supports_streaming
    
    def test_invalid_provider(self):
        with pytest.raises(ValueError):
            get_provider('invalid', {})

class TestGroqProvider:
    def test_initialization(self):
        config = {'api_key': 'test_key'}
        provider = GroqProvider(config)
        assert provider.model == 'whisper-large-v3-turbo'
    
    def test_missing_api_key(self):
        with pytest.raises(ValueError):
            GroqProvider({})

class TestVoxtralProvider:
    def test_initialization(self):
        config = {'api_key': 'test_key'}
        provider = VoxtralProvider(config)
        assert provider.model == 'voxtral-mini-transcribe-realtime-2602'
        assert provider.api_url == 'wss://api.mistral.ai'
    
    def test_missing_api_key(self):
        with pytest.raises(ValueError):
            VoxtralProvider({})
```

#### 2. Integration Tests (`tests/test_integration.py`)
**File**: `tests/test_integration.py`
**Changes**: Add integration tests for full workflow

```python
"""Integration tests for multi-provider system."""
import pytest
from groq_voice.config import ConfigManager
from groq_voice.providers import get_provider

def test_config_management():
    config_mgr = ConfigManager()
    provider = config_mgr.get_selected_provider()
    assert provider in ['groq', 'voxtral']
    
    provider_config = config_mgr.get_provider_config(provider)
    assert 'api_key_env' in provider_config

def test_provider_instantiation():
    config_mgr = ConfigManager()
    provider_name = config_mgr.get_selected_provider()
    provider_config = config_mgr.get_provider_config(provider_name)
    
    # Test that we can instantiate the configured provider
    # (won't work without API keys, but should not crash on import/config)
    try:
        provider = get_provider(provider_name, provider_config)
        assert provider.name == provider_name
    except ValueError as e:
        # Expected if API key is missing
        assert "not set" in str(e)
```

### Success Criteria:

#### Automated Verification:
- [ ] All unit tests pass: `python -m pytest tests/ -v`
- [ ] Test coverage is adequate: `python -m pytest --cov=src tests/ --cov-report=term`
- [ ] No regressions in existing functionality
- [ ] All type checking passes: `mypy src/ tests/`
- [ ] All linting passes: `ruff check src/ tests/`

#### Manual Verification:
- [ ] All providers work in both CLI and config modes
- [ ] Error handling is robust and user-friendly
- [ ] Performance is acceptable for both batch and streaming
- [ ] No memory leaks or resource issues
- [ ] Configuration changes are properly loaded

## Phase 6: Groq API Integration

### Overview
Implement Groq API integration for transcription services.

### Changes Required:

#### 1. Groq API Provider Implementation (`src/groq_voice/providers/groq_api.py`)
**File**: `src/groq_voice/providers/groq_api.py`
**Changes**: New file with Groq API implementation

```python
"""Groq API transcription provider."""
from groq import Groq
from typing import AsyncIterator, Dict, Any
import logging
import os
from .base import TranscriptionProvider

logger = logging.getLogger(__name__)

class GroqAPIProvider(TranscriptionProvider):
    """Groq API transcription provider."""
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key') or os.getenv(config.get('api_key_env', 'GROQ_API_KEY'))
        if not self.api_key:
            raise ValueError(f"{config.get('api_key_env', 'GROQ_API_KEY')} not set")
        self.model = config.get('model', 'whisper-large-v3-turbo')
        self.client = Groq(api_key=self.api_key)
    
    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file using Groq API."""
        logger.info("Transcribing %s with Groq API model %s", audio_path, self.model)
        try:
            with open(audio_path, "rb") as f:
                transcription = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=f,
                    language=language,
                    response_format="text"
                )
            result = str(transcription).strip()
            logger.info("Transcription result: %s", result[:100])
            return result
        except Exception as e:
            logger.exception("Groq API transcription failed")
            raise
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes], 
                               language: str = "en") -> AsyncIterator[str]:
        """Groq API does not support streaming transcription."""
        raise NotImplementedError("Groq API provider does not support streaming transcription")
    
    @property
    def supports_streaming(self) -> bool:
        return False
    
    @property
    def name(self) -> str:
        return "groq_api"
```

#### 2. Register Groq API Provider
**File**: `src/groq_voice/providers/__init__.py`
**Changes**: Add Groq API to provider registry

```python
# Add to imports
from .groq_api import GroqAPIProvider

# Add to registry
_PROVIDERS: Dict[str, Type[TranscriptionProvider]] = {
    "groq": GroqProvider,
    "voxtral": VoxtralProvider,
    "groq_api": GroqAPIProvider,
}
```

#### 3. Update Configuration for Groq API
**File**: `config.yaml`
**Changes**: Add Groq API configuration

```yaml
# Add to provider-specific configurations
groq_api:
  api_key_env: "GROQ_API_KEY"
  model: "whisper-large-v3-turbo"
```

### Success Criteria:

#### Automated Verification:
- [ ] Groq API provider exists: `src/groq_voice/providers/groq_api.py`
- [ ] Groq API registered in provider factory
- [ ] Unit tests pass: `python -m pytest tests/test_groq_api.py -v`
- [ ] Type checking passes: `mypy src/groq_voice/providers/groq_api.py`
- [ ] Linting passes: `ruff check src/groq_voice/providers/groq_api.py`

#### Manual Verification:
- [ ] Groq API provider works correctly
- [ ] Configuration is properly loaded
- [ ] Error handling works as expected
- [ ] Integration with main application works

---

## Testing Strategy

### Unit Tests:
- Provider interface compliance
- Provider factory functionality
- Configuration management
- Error handling scenarios
- Edge cases (missing configs, invalid providers)

### Integration Tests:
- Full workflow from audio capture to transcription
- Provider switching functionality
- Configuration loading and merging
- CLI argument handling

### Manual Testing Steps:
1. Test Groq provider with existing functionality
2. Test Voxtral provider with streaming (when API keys available)
3. Test provider switching via CLI arguments
4. Test provider switching via config file
5. Test error conditions (missing API keys, network issues)
6. Verify backward compatibility
7. Test performance with different audio lengths

## Performance Considerations

- **Memory**: Streaming mode should use less memory than batch mode
- **Latency**: Voxtral streaming should show lower latency than Groq batch
- **CPU**: Audio streaming adapter should be efficient
- **Network**: WebSocket connections should be properly managed and cleaned up

## Migration Notes

**Backward Compatibility:**
- Existing Groq functionality remains unchanged
- Configuration file is backward compatible (adds new sections)
- CLI interface remains the same (adds optional --provider flag)
- Default behavior uses Groq provider as before

**Breaking Changes:**
- None expected for existing users
- New configuration options are additive only

**Migration Path:**
1. Update to new version
2. Configure Voxtral API key if desired
3. Optionally switch provider in config or via CLI
4. No changes required for existing Groq users

## References

- Original Groq implementation: `src/groq_voice/transcriber.py`
- Voxtral API documentation: https://api.mistral.ai
- WebSocket streaming specification: RFC 6455
- Asyncio best practices: PEP 492

## Implementation Timeline

| Phase | Estimated Duration | Key Deliverables |
|-------|-------------------|------------------|
| 1. Provider Abstraction | 2-4 hours | Interface, Groq migration, factory |
| 2. Voxtral Streaming | 4-6 hours | Voxtral provider, audio adapter |
| 3. Configuration | 2-3 hours | Config manager, provider selection |
| 4. Main Integration | 3-5 hours | Updated main app, CLI support |
| 5. Testing | 4-6 hours | Comprehensive test suite, validation |
| 6. Groq API Integration | 2-3 hours | Groq API provider implementation |
| **Total** | **17-27 hours** | Full multi-provider system with Groq API |

## Risk Assessment

**High Risk:**
- Voxtral WebSocket API compatibility issues
- Real-time streaming performance problems
- Audio format compatibility between providers

**Medium Risk:**
- Configuration complexity
- Provider switching edge cases
- Memory management in streaming mode

**Low Risk:**
- Backward compatibility
- CLI interface changes
- Type checking and linting

## Contingency Plans

1. **Voxtral API issues**: Implement fallback to batch mode
2. **Performance problems**: Add buffering and optimization
3. **Configuration complexity**: Provide clear documentation and examples
4. **Compatibility issues**: Maintain old transcriber as legacy option

## Success Metrics

1. **Functional**: All providers work correctly
2. **Performance**: Streaming latency < 1 second, memory usage stable
3. **Reliability**: No crashes or resource leaks in 100 test runs
4. **Usability**: Clear error messages, easy provider switching
5. **Compatibility**: 100% backward compatibility with existing usage
6. **Groq API Integration**: Groq API provider works correctly and integrates seamlessly

## Next Steps

1. Begin Phase 1: Provider Abstraction Interface
2. Implement base interface and migrate Groq provider
3. Create provider factory system
4. Verify with unit tests before proceeding
5. Implement Phase 6: Groq API Integration after Phase 5 testing is complete

Would you like me to begin implementing Phase 1 now, or would you prefer to review or modify any aspects of this plan first?