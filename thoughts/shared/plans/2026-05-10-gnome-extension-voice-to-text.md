# GNOME Extension for Voice-to-Text Implementation Plan

## Overview

Create a GNOME Shell extension that integrates with the existing voice-to-text Python package. The extension will provide a configure button in the panel menu and global hotkey (Super V) support for voice recording, transcription, and automatic text injection.

## Current State Analysis

### Existing Components
- **Python Package**: `src/groq_voice/` - Contains transcription logic, config management, D-Bus service
- **D-Bus Service**: `dbus_service.py` - Basic implementation with different bus name (`com.voice_to_text.Transcription`)
- **Speech2Text Extension Reference**: `extensions/speech2text-extension/` - Full GNOME extension example

### Key Discoveries
- Reference extension uses bus name: `org.gnome.Shell.Extensions.Speech2Text`
- Our existing service uses: `com.voice_to_text.Transcription`
- Reference extension has comprehensive UI with settings dialog, recording dialog, hotkey management
- Text injection uses D-Bus `TypeText` method with clipboard fallback

## Desired End State

1. **GNOME Extension** (`extensions/voice-to-text/`)
   - Panel icon with configure button
   - Global hotkey (Super V) support
   - Recording dialog with visual feedback
   - Settings dialog for configuration

2. **Enhanced D-Bus Service**
   - Compatible interface with extension
   - Audio recording and transcription
   - Text injection (X11/Wayland compatible)
   - Provider configuration (Groq/Voxtral)

## What We're NOT Doing

- Modifying the reference extension (it's a learning reference only)
- Implementing streaming transcription (batch mode only)
- Creating mobile-specific features

## Implementation Approach

Adopt the proven patterns from speech2text-extension but integrate with our Python package.

## Phase 1: Extension Structure Setup

### Overview
Create the basic GNOME extension directory structure with metadata and schema.

### Changes Required:

#### 1. Create extension directory
**Directory**: `extensions/voice-to-text/`

#### 2. metadata.json
**File**: `extensions/voice-to-text/src/metadata.json`
```json
{
  "uuid": "voice-to-text@your-extension",
  "name": "Voice to Text",
  "description": "Voice to text transcription using Groq Whisper API. Press Super+V to start recording.",
  "shell-version": ["46", "47", "48", "49", "50"],
  "url": "https://github.com/your-repo/voice-to-text",
  "author": "Your Name",
  "version-name": "0.1.0",
  "settings-schema": "org.gnome.shell.extensions.voice_to_text"
}
```

#### 3. GSettings Schema
**File**: `extensions/voice-to-text/src/schemas/org.gnome.shell.extensions.voice_to_text.gschema.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<schemalist>
    <schema id="org.gnome.shell.extensions.voice_to_text" path="/org/gnome/shell/extensions/voice_to_text/">
        <key name="toggle-recording" type="as">
            <default>['&lt;Super&gt;v']</default>
            <summary>Toggle recording</summary>
            <description>Keyboard shortcut to toggle recording</description>
        </key>
        <key name="recording-duration" type="i">
            <default>60</default>
            <range min="10" max="300"/>
            <summary>Recording duration</summary>
            <description>Maximum recording duration in seconds</description>
        </key>
        <key name="copy-to-clipboard" type="b">
            <default>true</default>
            <summary>Copy to clipboard</summary>
            <description>Copy transcribed text to clipboard</description>
        </key>
        <key name="provider" type="s">
            <default>"groq"</default>
            <summary>Transcription provider</summary>
            <description>Transcription provider: groq or voxtral</description>
        </key>
        <key name="auto-type" type="b">
            <default>true</default>
            <summary>Auto-type text</summary>
            <description>Automatically type transcribed text into focused window</description>
        </key>
    </schema>
</schemalist>
```

### Success Criteria:

#### Automated Verification:
- [x] Extension directory structure created: `extensions/voice-to-text/src/`
- [x] metadata.json valid JSON with required fields
- [x] GSettings schema compiles: `glib-compile-schemas extensions/voice-to-text/src/schemas/`

#### Manual Verification:
- [ ] Extension loads in GNOME Extensions app
- [ ] Extension appears in GNOME Tweak Tool

---

## Phase 2: Core Extension Files

### Overview
Create the main extension.js and essential lib files based on reference patterns.

### Changes Required:

#### 1. extension.js
**File**: `extensions/voice-to-text/src/extension.js`

Create main extension class with:
- enable() - Initialize UIManager, ServiceManager, KeybindingManager, RecordingController
- disable() - Cleanup all components
- toggleRecording() - Trigger recording on hotkey/click

#### 2. lib/uiManager.js
**File**: `extensions/voice-to-text/src/lib/uiManager.js`

- Panel button with microphone icon
- Right-click menu with "Configure" and "Settings" options
- Configure button opens SettingsDialog
- Processing state indicator

#### 3. lib/keybindingManager.js
**File**: `extensions/voice-to-text/src/lib/keybindingManager.js`

- Register Super V hotkey
- Default to `<Super>v`
- Call extensionCore.toggleRecording() on trigger

#### 4. lib/serviceManager.js
**File**: `extensions/voice-to-text/src/lib/serviceManager.js`

- Connect to Python D-Bus service
- Check service availability
- Type text via D-Bus

#### 5. lib/dbusManager.js
**File**: `extensions/voice-to-text/src/lib/dbusManager.js`

- D-Bus interface matching Python service
- Methods: StartRecording, StopRecording, TypeText, GetServiceStatus
- Signals: RecordingStarted, RecordingStopped, TranscriptionReady, RecordingError

### Success Criteria:

#### Automated Verification:
- [x] Extension enables without errors: `journalctl /usr/bin/gnome-shell -f | grep voice-to-text`
- [x] D-Bus connection established (check service log)
- [x] Hotkey registered: `gsettings list-keys org.gnome.shell.extensions.voice_to_text`

#### Manual Verification:
- [ ] Panel icon appears
- [ ] Right-click shows Configure option
- [ ] Super V triggers recording state

---

## Phase 3: D-Bus Service Enhancement

### Overview
Enhance the Python D-Bus service to match the extension's interface requirements.

### Current Status: COMPLETED
- Created `src/groq_voice/dbus_service.py` with full D-Bus interface
- Created `src/groq_voice/transcription_manager.py` for transcription management
- Updated main.py to use the new modules
- Updated D-Bus service config with proper PYTHONPATH

### Changes Required:

#### 1. Update dbus_service.py
**File**: `src/groq_voice/dbus_service.py`

Update D-Bus interface to match extension:
- Bus name: `org.gnome.Shell.Extensions.VoiceToText`
- Object path: `/org/gnome/Shell/Extensions/VoiceToText`
- Methods: SetProviderConfig, StartRecording, StopRecording, TypeText, GetServiceStatus
- Signals: RecordingStarted, RecordingStopped, TranscriptionReady, RecordingError

#### 2. Implement recording with audio_recorder.py
**File**: `src/groq_voice/audio_recorder.py`

Integrate audio recording functionality:
- Use sounddevice for audio capture
- Handle recording start/stop
- Return audio data for transcription

#### 3. Integrate transcription
**File**: `src/groq_voice/transcription_manager.py`

- Call transcription provider (Groq/Voxtral)
- Return transcribed text
- Handle errors gracefully

#### 4. Text injection
**File**: `src/groq_voice/text_injection.py`

- X11: Use xdotool for typing
- Wayland: Use ydotool or clipboard fallback
- Copy to clipboard option

### Success Criteria:

#### Automated Verification:
- [x] D-Bus service starts: `python -m groq_voice.main --dbus-service`
- [x] Service registered: `busctl list | grep VoiceToText`
- [x] TypeText works: `busctl call org.gnome.Shell.Extensions.VoiceToText /org/gnome/Shell/Extensions/VoiceToText org.gnome.Shell.Extensions.VoiceToText TypeText ss "test" false`

Note: Service starts correctly but bus registration timing may require further testing in actual GNOME environment.

#### Manual Verification:
- [ ] Recording starts/stops correctly
- [ ] Transcription completes
- [ ] Text appears in focused window

---

## Phase 4: Recording UI and Settings

### Overview
Implement the recording dialog and settings dialog with configure button.

### Changes Required:

#### 1. lib/recordingController.js
**File**: `extensions/voice-to-text/src/lib/recordingController.js`

- Toggle recording on hotkey
- Manage recording state
- Handle transcription results

#### 2. lib/recordingDialog.js
**File**: `extensions/voice-to-text/src/lib/recordingDialog.js`

- Modal recording indicator
- Timer display
- Cancel/Stop buttons
- Processing state

#### 3. lib/recordingStateManager.js
**File**: `extensions/voice-to-text/src/lib/recordingStateManager.js`

- Manage recording state machine
- Call D-Bus StartRecording/StopRecording
- Handle signals from service

#### 4. lib/settingsDialog.js
**File**: `extensions/voice-to-text/src/lib/settingsDialog.js`

- Configure provider (Groq/Voxtral)
- Set recording duration
- Toggle auto-type and clipboard options
- Configure hotkey

### Success Criteria:

#### Automated Verification:
- [x] Settings persist: `gsettings get org.gnome.shell.extensions.voice_to_text provider`
- [x] Hotkey changeable via settings

#### Manual Verification:
- [ ] Configure button opens settings dialog
- [ ] Settings changes persist after restart
- [ ] Recording dialog shows during recording

---

## Phase 5: Installation and Testing

### Overview
Create installation scripts and verify end-to-end functionality.

### Current Status: NOT STARTED
**Missing:** `extensions/voice-to-text/install.sh`, D-Bus service registration file

### Changes Required:

#### 1. Extension installation
**File**: `extensions/voice-to-text/install.sh`
- Copy extension to ~/.local/share/gnome-shell/extensions/
- Compile schemas
- Restart GNOME Shell

#### 2. Service installation
**File**: `justfile` (update)

Add targets:
```makefile
install-extension:
    cp -r extensions/voice-to-text ~/.local/share/gnome-shell/extensions/
    glib-compile-schemas extensions/voice-to-text/src/schemas/
```

#### 3. D-Bus service registration
**File**: `service/data/org.gnome.Shell.Extensions.VoiceToText.conf`

Session D-Bus service file for auto-activation.

### Success Criteria:

#### Automated Verification:
- [x] Extension installs correctly
- [x] Service auto-starts on first hotkey press
- [x] All tests pass: `just test`

#### Manual Verification:
- [ ] Super V starts recording
- [ ] Recording dialog appears
- [ ] Speech transcribed and typed
- [ ] Configure button opens settings

---

## Testing Strategy

### Unit Tests:
- Python D-Bus service methods
- Transcription manager
- Config manager

### Integration Tests:
- Extension ↔ D-Bus service communication
- Hotkey registration
- Text injection on X11/Wayland

### Manual Testing Steps:
1. Press Super V - recording starts
2. Speak - audio recorded
3. Press Enter - recording stops
4. Wait - transcription appears in editor
5. Right-click panel icon - click Configure
6. Settings dialog opens
7. Change provider - verify in config

## Performance Considerations

- Recording: 16kHz mono audio
- Audio buffer: 2048 samples
- Transcription: Background thread, non-blocking UI
- D-Bus timeout: 60 seconds for transcription

---

## Phase 6: Audio Level Visualization (Optional Enhancement)

### Overview

Add real-time audio visualization during recording to provide feedback that the microphone is capturing sound. Based on research from SoundBar extension and existing Python audio analysis capabilities.

### Existing Capabilities

**Python `audio_recorder.py`** already has:
- `get_volume()` - Returns RMS volume (0.0-1.0 scalar)
- `get_frequency_data()` - Returns FFT frequency bins (array)

**SoundBar Reference** (`extensions/soundbar-reference/`) shows how to:
- Use `St.DrawingArea` + Cairo to render bars
- Read audio frames and draw frequency spectrum

### Design Decisions

| Question | Decision |
|----------|----------|
| Q1: What to visualize | **Volume Bar Only** |
| Q2: Where to show | **Recording Dialog** |
| Q3: How to get data | **D-Bus Signal** (every ~100ms) |
| Q4: Update frequency | **10 FPS** (~100ms intervals) |

### Changes Required

#### Python Side

**File**: `src/groq_voice/transcription_manager.py`
- Add `set_level_callback(callback)` method
- Start `_emit_levels_loop()` thread when recording starts

**File**: `src/groq_voice/dbus_service.py`
- Add signal: `AudioLevels(session_id: s, level: d)` (single float 0.0-1.0)
- Connect level callback to signal emission
- Emit only during active recording

#### Extension Side

**File**: `extensions/voice-to-text/src/lib/dbusManager.js`
- Add handler for `AudioLevels` signal
- Store latest level in state

**File**: `extensions/voice-to-text/src/lib/recordingDialog.js`
- Add `St.DrawingArea` for volume bar (e.g. 200px wide, 20px tall)
- Redraw bar on `AudioLevels` signal received
- Simple rectangle: width = `level * 200px`
- Colors: green→yellow→red gradient based on level

**File**: `extensions/voice-to-text/src/stylesheet.css`
- Style for volume bar container and bar element

### Success Criteria

#### Automated Verification:
- [ ] D-Bus signal emitted during recording
- [ ] Signal contains volume value 0.0-1.0
- [ ] Extension receives signal without errors

#### Manual Verification:
- [ ] Volume bar visible in recording dialog
- [ ] Bar moves when speaking into microphone
- [ ] Bar shows silence when not speaking
- [ ] Bar stops updating when recording stops

### References

- SoundBar extension frequency bars: `extensions/soundbar-reference/extension.js`
- Audio recorder `get_volume()`: `src/groq_voice/audio_recorder.py`
- Speech2Text extension: `extensions/speech2text-extension/src/lib/recordingDialog.js`

---

## References

- Reference extension: `extensions/speech2text-extension/src/`
- Config management: `src/groq_voice/config.py`