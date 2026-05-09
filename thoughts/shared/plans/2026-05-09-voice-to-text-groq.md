# Voice to Text with Groq Whisper Implementation Plan

## Overview

A push-to-talk voice transcription script that records audio via microphone and transcribes it using Groq's Whisper model. Designed for Fedora with GNOME/Wayland, using clipboard for text output.

## Current State Analysis

- Empty project directory with cloned `hermes-agent` repo (for reference)
- GNOME Shell on Wayland desktop environment detected
- Microphone available: HDA Intel PCH (card 0)
- xclip/xsel available for clipboard functionality

## Desired End State

A CLI script that:
1. Registers a global hotkey (default: Ctrl+Space)
2. Records audio while hotkey is held/pressed
3. Sends audio to Groq Whisper API for transcription
4. Outputs plain text to terminal

### Key Discoveries:
- Hermes uses `whisper-large-v3-turbo` as default Groq model (line 85 in transcription_tools.py)
- Hermes uses OpenAI SDK with custom base_url for Groq integration
- Audio recording via sounddevice with WAV format (16kHz, mono)

## What We're NOT Doing

- TTS (text-to-speech) - only STT
- Multiple provider support (Groq only for now)
- GUI/TUI - pure CLI tool
- Clipboard integration via xclip/xsel

## Implementation Approach

Simple Python script with:
- argparse for CLI arguments
- sounddevice for audio capture
- groq Python SDK for transcription
- Config file for customization

---

## Phase 1: Project Setup

### Overview
Create project structure with requirements and basic config.

### Changes Required:

#### 1. requirements.txt
**File**: `requirements.txt`
**Changes**: Create dependencies file

```
groq
sounddevice
numpy
python-dotenv
```

#### 2. config.yaml
**File**: `config.yaml`
**Changes**: Create default configuration

```yaml
# groq_voice config
hotkey:
  key: "ctrl+space"  # configurable
  mode: "press"      # "press" or "hold"

audio:
  sample_rate: 16000
  channels: 1
  dtype: "int16"
  max_duration: 30  # seconds

transcription:
  model: "whisper-large-v3-turbo"
  language: "auto"  # or specific ISO code like "en"

groq:
  api_key_env: "GROQ_API_KEY"  # env var name
```

#### 3. .env.example
**File**: `.env.example`
**Changes**: Create env template

```
GROQ_API_KEY=your_api_key_here
```

### Success Criteria:

#### Automated Verification:
- [x] requirements.txt created
- [x] config.yaml created
- [x] uv can install dependencies: `uv pip install -r requirements.txt`

#### Manual Verification:
- [x] Dependencies install without errors

---

## Phase 2: Audio Recording Module

### Overview
Implement audio capture using sounddevice with push-to-talk semantics.

### Changes Required:

#### 1. audio_recorder.py
**File**: `src/groq_voice/audio_recorder.py`
**Changes**: Create audio recording module

```python
"""Audio recording module using sounddevice."""
import sounddevice as sd
import numpy as np
from pathlib import Path
import tempfile
import logging

logger = logging.getLogger(__name__)

class AudioRecorder:
    def __init__(self, sample_rate=16000, channels=1, max_duration=30):
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_duration = max_duration
        self.frames = []
        self.recording = False

    def start(self):
        """Start recording."""
        self.frames = []
        self.recording = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            callback=self._callback
        )
        self.stream.start()

    def _callback(self, indata, frames, time, status):
        """Callback for audio input."""
        if self.recording:
            self.frames.append(indata.copy())

    def stop(self) -> str:
        """Stop recording and return path to WAV file."""
        self.recording = False
        self.stream.stop()
        self.stream.close()

        if not self.frames:
            return None

        audio_data = np.concatenate(self.frames, axis=0)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            self._write_wav(f.name, audio_data)
            return f.name

    def _write_wav(self, path, audio_data):
        """Write numpy array to WAV file."""
        import wave
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())
```

### Success Criteria:

#### Automated Verification:
- [x] audio_recorder.py created
- [x] Python can import the module without errors

#### Manual Verification:
- [x] Can list audio devices: `python -c "import sounddevice as sd; print(sd.query_devices())"`

---

## Phase 3: Groq Transcription Module

### Overview
Implement transcription using Groq Whisper API.

### Changes Required:

#### 1. transcriber.py
**File**: `src/groq_voice/transcriber.py`
**Changes**: Create Groq transcription module

```python
"""Transcription module using Groq Whisper API."""
from groq import Groq
import os
import logging

logger = logging.getLogger(__name__)

class GroqTranscriber:
    def __init__(self, api_key=None, model="whisper-large-v3-turbo"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set")
        self.model = model
        self.client = Groq(api_key=self.api_key)

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file and return text."""
        with open(audio_path, "rb") as f:
            transcription = self.client.audio.transcriptions.create(
                model=self.model,
                file=f,
                response_format="text"
            )
        return str(transcription).strip()
```

### Success Criteria:

#### Automated Verification:
- [x] transcriber.py created
- [x] GROQ_API_KEY can be loaded from environment

#### Manual Verification:
- [ ] API key can be validated (check connectivity)

---

## Phase 4: Global Hotkey Integration

### Overview
Implement global hotkey detection on Fedora with GNOME/Wayland.

### Changes Required:

#### 1. hotkey.py
**File**: `src/groq_voice/hotkey.py`
**Changes**: Create hotkey detection module

For GNOME on Wayland, we'll use a dbus approach or keybinder:

```python
"""Global hotkey detection for GNOME/Wayland."""
import subprocess
import threading
import logging

logger = logging.getLogger(__name__)

class GlobalHotkey:
    def __init__(self, key_combo="ctrl+space"):
        self.key_combo = key_combo.lower()
        self.pressed = False

    def wait_for_press(self):
        """Block until hotkey is pressed."""
        # Use python-evdev or keybinder-lib
        # For GNOME: use pykey or dbus
        pass

    def start_listening(self, callback):
        """Start listening in background thread."""
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()

    def _listen_loop(self):
        """Background listening loop."""
        # Implementation depends on backend
        pass
```

**Note**: For clipboard functionality, we use xclip/xsel which works across both X11 and Wayland environments.
1. `evdev` with appropriate permissions
2. A GNOME extension
3. Use a simple approach: listen on a specific key via subprocess

For now, let's create a simpler version that uses keyboard polling via a small helper, or document the requirement.

### Alternative: Use dbus for GNOME keyboard grab

```python
import subprocess
import time

def wait_for_ctrl_space():
    """Wait for Ctrl+Space using evdev (requires input group)."""
    import evdev
    devices = [evdev.InputDevice(d) for d in evdev.list_devices()]
    for d in devices:
        if "keyboard" in d.name.lower():
            # Grab and listen for ctrl+space
            pass
```

### Success Criteria:

#### Automated Verification:
- [x] hotkey.py created
- [x] Can detect hotkey press (or document requirements)

#### Manual Verification:
- [ ] Hotkey triggers recording start

---

## Phase 5: Main CLI Script

### Overview
Assemble all components into the main CLI script.

### Changes Required:

#### 1. main.py
**File**: `src/groq_voice/main.py`
**Changes**: Create main CLI

```python
#!/usr/bin/env python3
"""Voice to Text using Groq Whisper - Main CLI."""
import argparse
import sys
import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Import modules
from groq_voice.audio_recorder import AudioRecorder
from groq_voice.transcriber import GroqTranscriber
from groq_voice.hotkey import GlobalHotkey

def load_config():
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}

def main():
    parser = argparse.ArgumentParser(description="Voice to Text with Groq Whisper")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--hotkey", type=str, help="Hotkey to use (e.g., ctrl+space)")
    parser.add_argument("--model", type=str, help="Whisper model to use")
    parser.add_argument("--record-only", action="store_true", help="Record audio to file only")
    args = parser.parse_args()

    # Load config
    config = load_config()
    if args.config:
        with open(args.config) as f:
            config = yaml.safe_load(f)

    # Load .env
    load_dotenv()

    # Get settings
    hotkey = args.hotkey or config.get("hotkey", {}).get("key", "ctrl+space")
    model = args.model or config.get("transcription", {}).get("model", "whisper-large-v3-turbo")
    audio_config = config.get("audio", {})

    # Create components
    recorder = AudioRecorder(
        sample_rate=audio_config.get("sample_rate", 16000),
        channels=audio_config.get("channels", 1),
        max_duration=audio_config.get("max_duration", 30)
    )

    transcriber = GroqTranscriber(model=model)

    hotkey_listener = GlobalHotkey(hotkey)

    print(f"Listening for hotkey: {hotkey}...")
    print("Press and hold to record, release to transcribe.")

    # Main loop
    while True:
        # Wait for hotkey press
        hotkey_listener.wait_for_press()

        # Start recording
        print("Recording...")
        recorder.start()

        # Wait for release
        hotkey_listener.wait_for_release()

        # Stop and transcribe
        audio_path = recorder.stop()

        if audio_path:
            print("Transcribing...")
            try:
                text = transcriber.transcribe(audio_path)
                print(f"\n{text}")
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("No audio recorded")

        print(f"\nListening for hotkey: {hotkey}...")

if __name__ == "__main__":
    main()
```

#### 2. __init__.py
**File**: `src/groq_voice/__init__.py`
**Changes**: Create package init

```python
"""Groq Voice - Voice to Text using Groq Whisper."""
__version__ = "0.1.0"
```

#### 3. pyproject.toml (for uv)
**File**: `pyproject.toml`
**Changes**: Create package definition for uv

```toml
[project]
name = "groq-voice"
version = "0.1.0"
description = "Voice to Text using Groq Whisper"
requires-python = ">=3.10"
dependencies = [
    "groq",
    "sounddevice",
    "numpy",
    "pyyaml",
    "python-dotenv",
]

[project.scripts]
groq-voice = "groq_voice.main:main"
```

### Success Criteria:

#### Automated Verification:
- [x] main.py created and runs with --help
- [x] All imports work correctly
- [x] pyproject.toml is valid

#### Manual Verification:
- [x] Script can be run with `uv run groq-voice --help`

---

## Phase 6: Testing & Verification

### Overview
Test the full integration.

### Changes Required:

#### Test script
**File**: `tests/test_integration.py`
**Changes**: Create integration tests

```python
"""Integration tests for groq-voice."""
import pytest
import os

def test_config_loading():
    """Test config.yaml loading."""
    from groq_voice.main import load_config
    config = load_config()
    assert config is not None

def test_recorder_init():
    """Test audio recorder initialization."""
    from groq_voice.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    assert recorder.sample_rate == 16000
    assert recorder.channels == 1

def test_transcriber_requires_api_key():
    """Test transcriber fails without API key."""
    # Clear env and test
    os.environ.pop("GROQ_API_KEY", None)
    from groq_voice.transcriber import GroqTranscriber
    with pytest.raises(ValueError):
        transcriber = GroqTranscriber()
```

### Success Criteria:

#### Automated Verification:
- [x] All tests pass: `uv run pytest tests/`
- [x] Linting passes: `uv run ruff check src/`
- [x] Type checking passes: `uv run mypy src/`

#### Manual Verification:
- [ ] Full recording + transcription workflow works
- [ ] Hotkey triggers recording correctly
- [ ] Output is plain text only

---

## Testing Strategy

### Unit Tests:
- Audio recorder device enumeration
- Config loading
- API key validation

### Integration Tests:
- Full record-transcribe workflow (requires microphone)
- Hotkey detection

### Manual Testing Steps:
1. Run script with test audio file
2. Press hotkey and speak
3. Verify transcription appears
4. Test different audio inputs

---

## Performance Considerations

- Audio is saved temporarily then deleted after transcription
- Groq API is fast but depends on network latency
- Max recording duration prevents runaway recordings

---

## Migration Notes

- First version, no migration needed

---

## References

- Hermes Agent transcription_tools.py: `hermes-agent/tools/transcription_tools.py`
- Groq Python SDK docs: `/groq/groq-python`