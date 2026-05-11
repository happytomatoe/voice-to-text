# IBus Speech-to-Text Plugin Implementation Plan

## Overview

Convert the existing voice-to-text Python application into an IBus input method engine plugin that allows users to trigger voice input via keyboard shortcut and have transcribed text automatically inserted into any text field.

## Current State Analysis

The existing application (`voice-to-text`):
- Records audio via microphone using `sounddevice`
- Transcribes audio using Groq or Voxtral APIs
- Outputs transcribed text to clipboard
- Has a curses-based UI for recording visualization
- Depends on: groq, sounddevice, numpy, pyyaml, python-dotenv
- Python 3.13+ required

**Key files:**
- `src/voice_to_text/main.py` - Main entry point and recording logic
- `src/voice_to_text/config.py` - Configuration management
- `src/voice_to_text/providers/` - Transcription provider abstraction

## Desired End State

An IBus engine that:
1. Registers as an input method in IBus ("Cloud Speech" or similar)
2. Listens for **Super+q** to toggle recording (press once to start, press again to stop)
3. Shows visual feedback in the preedit area during recording
4. Automatically commits transcribed text to the active input context
5. Shows desktop notifications for status (recording, transcription complete, errors)
6. Stores configuration in `~/.config/voice-to-text/config.yaml`
7. Works with all GTK/Qt applications via IBus

### Key Discoveries:
- IBus Python bindings use GObject Introspection (`gi` module)
- Engines subclass `IBus.Engine` and override virtual methods like `do_process_key_event()`, `do_enable()`, `do_disable()`
- Text is committed via `engine.commit_text(IBus.Text.new("text"))`
- Preedit text shown via `engine.update_preedit_text(text, cursor_pos, visible)`
- Engine registration requires a component XML file in `/usr/share/ibus/component/` or user-local directory

## What We're NOT Doing

- Building a full GUI setup dialog (will use CLI configuration)
- Supporting multiple simultaneous recordings
- Supporting Wayland-specific input methods (using IBus which handles this)
- Adding hotkey registration via DBus (using IBus's built-in mechanism)

## Candidate List vs Auto-Commit Explanation

IBus engines typically work in two ways:

### Option 1: Candidate List (like Pinyin/Anthy)
When you type, the engine shows a list of candidate conversions. You select one (e.g., press 1-5) to commit to the text field.

### Option 2: Auto-Commit (chosen approach)
The engine processes input and automatically commits the result to the text field without showing a selection list.

**Why Auto-Commit for voice input?**
1. Voice transcription produces a single result - no candidates to choose from
2. The user already "selected" the result by speaking it
3. Showing a fake candidate list would be confusing (only one option)
4. Reduces interaction steps: speak → wait → text appears

**How it works:**
1. Press Super+Q → recording starts
2. Press Super+Q again → recording stops, transcription begins
3. Transcribed text is immediately committed to the text field via `engine.commit_text()`

This is similar to how voice input works in mobile keyboards (Gboard, SwiftKey) - the speech is converted and inserted automatically.

## Implementation Approach

The plugin will work as follows:
1. User activates "Cloud Speech" engine in IBus
2. When user presses **Super+q**, engine toggles recording state:
   - If idle → start recording
   - If recording → stop recording and transcribe
3. Recording status shown in preedit text area (e.g., "● Recording... ███░░")
4. After recording stops, transcription begins automatically
5. Transcribed text is committed to the active input context
6. Engine returns to idle state, waiting for next trigger

**Key behavior: Toggle Mode**
- Press Super+q to start recording
- Press Super+q again (while recording) to stop and transcribe
- Maximum recording duration: 30 seconds (configurable)

## Phase 1: Core IBus Engine Structure

### Overview
Create the basic IBus engine class with lifecycle management and key event handling.

### Changes Required:

#### 1. New package: `ibus_cloud/`
**New files:**
- `src/ibus_cloud/__init__.py` - Package init
- `src/ibus_cloud/engine.py` - IBus engine implementation
- `src/ibus_cloud/config.py` - IBus-specific configuration
- `src/ibus_cloud/audio.py` - Audio recording (refactored from main.py)

**Implementation:**
```python
# src/ibus_cloud/engine.py
import gi
gi.require_version('IBus', '1.0')
from gi.repository import IBus, GObject

# GDK key codes: Super = MOD4, q = 0x71
GDK_q = 0x71
IBUS_SUPER_MASK = 0x2000  # IBUS_MOD4_MASK

class CloudSpeechEngine(IBus.Engine):
    def __init__(self):
        super().__init__()
        self._recording = False
        self._transcribing = False

    def do_enable(self):
        """Called when engine is enabled."""
        self.register_properties(IBus.PropList.new())
        self.update_preedit_text(
            IBus.Text.new("Cloud: Press Super+Q to record"), 0, True
        )

    def do_disable(self):
        """Called when engine is disabled."""
        self.stop_recording()

    def do_process_key_event(self, keyval, keycode, state):
        """Handle key events - Super+Q toggles recording."""
        # Check for Super+q (toggle behavior)
        if keyval == GDK_q and (state & IBUS_SUPER_MASK):
            if self._transcribing:
                return True  # Ignore during transcription

            if self._recording:
                # Stop recording and transcribe
                self.stop_recording_and_transcribe()
            else:
                # Start recording
                self.start_recording()
            return True  # Consume the key

        return False  # Pass through other keys

    def start_recording(self):
        """Start audio recording."""
        self._recording = True
        self.update_preedit_text(
            IBus.Text.new("● Recording... (press Super+Q to stop)"), 0, True
        )
        # ... start audio stream

    def stop_recording_and_transcribe(self):
        """Stop recording and start transcription."""
        self._recording = False
        self._transcribing = True
        self.update_preedit_text(
            IBus.Text.new("◐ Transcribing..."), 0, True
        )
        # ... stop audio, transcribe, commit result

    def do_focus_in(self):
        """Called when input context gains focus."""
        pass

    def do_focus_out(self):
        """Called when input context loses focus."""
        if self._recording:
            self.stop_recording_and_transcribe()

    def do_reset(self):
        """Reset engine state."""
        self.stop_recording()
```

### Success Criteria:

#### Automated Verification:
- [x] Engine class can be instantiated without errors
- [x] IBus component XML validates
- [x] Python gi imports work: `python -c "import gi; gi.require_version('IBus', '1.0'); from gi.repository import IBus; print('OK')"`

#### Manual Verification:
- [ ] Engine loads in `ibus-setup` without errors
- [ ] Engine appears in IBus input method list

---

## Phase 2: Audio Recording Integration

### Overview
Integrate the audio recording functionality from the original app into the engine.

### Changes Required:

#### 1. Refactor audio.py
**File**: `src/ibus_engine/audio.py`
- Move audio recording logic from `voice_to_text/main.py`
- Add async recording capability
- Add audio level monitoring for preedit display

```python
# Key additions
import numpy as np
import sounddevice as sd

class AudioRecorder:
    def __init__(self, callback=None):
        self._callback = callback
        self._stream = None
        self._recording = False

    async def start_recording(self, device=None):
        """Start async audio recording."""
        self._recording = True
        # ... setup InputStream with callback

    def stop_recording(self):
        """Stop recording and return audio data."""
        # ... stop stream, return numpy array

    def get_audio_level(self):
        """Get current audio level for visualization."""
        # ... return 0-1 float
```

#### 2. Integrate with Engine
**File**: `src/ibus_cloud/engine.py`
- Add `start_recording()`, `stop_recording()` methods
- Connect audio callback to update preedit text with recording status
- Handle recording timeout

#### 3. Recording Status Indicator (Preedit Display)
The preedit text area shows real-time feedback:

| State | Preedit Text |
|-------|--------------|
| Idle | "Cloud: Press Super+Q to record" |
| Recording | "● Recording... ███░░░░░░" (animated bars) |
| Transcribing | "◐ Transcribing..." |
| Success | Text committed, preedit cleared |
| Error | "Error: [message]" (shown briefly) |

**Audio level visualization:**
- 10 progress bar segments (█ = filled, ░ = empty)
- Updates at 10 Hz (every 100ms)
- Shows current audio input level
- Uses ASCII art: ███░░░░░░

**Implementation:**
```python
def update_recording_indicator(self, audio_level):
    """Update preedit with audio level visualization."""
    filled = int(audio_level * 10)
    bars = "█" * filled + "░" * (10 - filled)
    text = f"● Recording... {bars}"
    self.update_preedit_text(IBus.Text.new(text), 0, True)
```

**Color coding (optional):**
- Idle: Default text color
- Recording: Red/Orange (● indicates active)
- Transcribing: Yellow (◐ indicates processing)

### Success Criteria:

#### Automated Verification:
- [x] `python -c "from ibus_cloud.audio import AudioRecorder"` works
- [x] Audio devices can be queried: `AudioRecorder.list_devices()`

#### Manual Verification:
- [ ] Recording starts when Super+q pressed (first press)
- [ ] Preedit shows recording status (e.g., "● Recording...")
- [ ] Recording stops when Super+q pressed again (toggle)

---

## Phase 3: Transcription Integration

### Overview
Integrate the transcription providers (Groq/Voxtral) into the engine.

### Changes Required:

#### 1. Update providers to work in async context
**File**: `src/voice_to_text/providers/`
- Make transcription calls async-compatible
- Add timeout handling

#### 2. Integrate transcription in engine
**File**: `src/ibus_engine/engine.py`

```python
# In stop_recording() or new transcribe method:
async def transcribe_audio(self):
    audio_data = self._recorder.get_audio()
    # Save to temp WAV file
    # Call transcription provider
    # Return transcribed text

async def on_recording_complete(self):
    text = await self.transcribe_audio()
    if text:
        self.commit_text(IBus.Text.new(text))
        self.show_notification("Voice Input", f"Transcribed: {text[:50]}...")
    else:
        self.update_preedit_text(IBus.Text.new("No speech detected"), 0, True)
```

### Success Criteria:

#### Automated Verification:
- [x] Transcription providers work with audio data
- [x] API keys loaded from config/environment

#### Manual Verification:
- [ ] After recording stops, transcription occurs
- [ ] Transcribed text appears in the active text field

---

## Phase 4: Engine Registration & Packaging

### Overview
Create the necessary files to register the engine with IBus and package for distribution.

### Changes Required:

#### 1. IBus Component XML
**File**: `data/ibus-cloud.xml`
```xml
<?xml version="1.0" encoding="utf-8"?>
<component>
  <engine>
    <name>com.cloud-voice.CloudSpeech</name>
    <description>Cloud Speech Input - Voice to text using cloud APIs</description>
    <language>en</language>
    <license>MIT</license>
    <author>Your Name</author>
    <execute>ibus-engine-cloud</execute>
    <version>0.1.0</version>
  </engine>
  <engines>
    <engine>
      <name>com.cloud-voice.CloudSpeech</name>
      <symbol>☁</symbol>
    </engine>
  </engines>
</component>
```

#### 2. Setup script / entry point
**File**: `src/ibus_cloud/__main__.py`
```python
#!/usr/bin/env python3
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ibus_cloud.engine import CloudSpeechEngineFactory

if __name__ == '__main__':
    from ibus import main
    main('CloudSpeech', [CloudSpeechEngineFactory()])
```

#### 3. Desktop entry for setup
**File**: `data/ibus-setup-cloud.desktop`

#### 4. Package configuration
**File**: `pyproject.toml` - Add new package `ibus-cloud`

### Success Criteria:

#### Automated Verification:
- [x] Component XML validates against DTD
- [x] `python setup.py build` succeeds
- [x] Package can be installed via `pip install .`

#### Manual Verification:
- [ ] Engine appears in IBus preferences after installation
- [ ] Engine can be enabled/disabled via IBus

---

## Phase 5: Configuration & User Experience

### Overview
Add configuration options and improve user experience.

### Changes Required:

#### 1. Config file support
- Continue using existing `config.yaml` format
- Add IBus-specific options:
  - `max_duration` - Maximum recording duration (default: 30 seconds)
  - `audio_device` - Specific audio device index (optional)
  - `notification_enabled` - Show desktop notifications (default: true)

#### 2. Visual improvements
- Show audio level visualization in preedit
- Show "Transcribing..." status
- Different preedit colors for different states

#### 3. Error handling
- Handle missing API keys gracefully
- Handle no audio device
- Handle transcription failures

### Success Criteria:

#### Automated Verification:
- [x] Config loading works with new options
- [x] Invalid config values handled gracefully

#### Manual Verification:
- [ ] Configuration changes take effect after IBus restart
- [ ] Error messages are user-friendly

---

## Testing Strategy

### Unit Tests:
- Engine lifecycle (enable/disable/focus)
- Key event handling
- Audio recorder basic functions
- Transcription provider calls

### Integration Tests:
- Full recording -> transcription -> commit flow
- Works with GTK applications (gedit, Firefox)
- Works with Qt applications (Kalculate, Konsole)
- Works with terminal emulators

### Manual Testing Steps:
1. Enable engine in IBus preferences
2. Open a text field in any application
3. Press Super+Q to start recording (preedit shows "● Recording...")
4. Speak a phrase
5. Press Super+Q again to stop recording (preedit shows "◐ Transcribing...")
6. Wait for transcription (1-2 seconds)
7. Verify text appears in the text field

## Performance Considerations

- Audio recording uses minimal CPU (just buffer capture)
- Transcription is async to avoid blocking IBus
- Preedit updates should be throttled (max 10/sec)
- Use environment variable for API key to avoid config file issues

## Migration Notes

Users upgrading from CLI version:
- Will need to install new package
- Copy existing config or create new one
- Add API keys to environment or config

## References

- IBus Python bindings: https://lazka.github.io/pgi-docs/IBus-1.0/
- IBus component format: https://github.com/ibus/ibus/wiki/Component
- Existing engines for reference: ibus-anthy, ibus-skk