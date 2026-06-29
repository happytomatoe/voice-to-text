# Voxtral IBus Integration Implementation Plan

## Overview

Integrate Voxtral real-time speech-to-text into the Linux desktop using the IBus (Intelligent Input Bus) framework. This allows the user to speak into a microphone and have text inserted directly into any focused application (text editors, browsers, terminals) as if it were typed.

## Current State Analysis

- **VoxtralProvider**: A Python class exists in `src/voice_to_text/providers/voxtral.py` that handles streaming transcription via the Mistral SDK. It uses an internal asyncio loop and a thread to manage the stream.
- **IBus**: IBus is the standard input method framework for Linux. To implement a custom input method, an IBus Engine must be created and registered.
- **Gap**: There is no bridge between the `VoxtralProvider`'s transcription events and the IBus API.

## Desired End State

A functional MVP where:
1. An IBus engine is registered and selectable in GNOME/KDE input sources.
2. A bridge process captures audio, sends it to Voxtral, and communicates results to the IBus engine.
3. User experience includes "preedit" (underlined temporary text) and "commit" (finalized text) behavior.

### Key Discoveries:
- IBus engines must run a GObject main loop (`GLib.MainLoop`).
- Direct integration of a heavy STT pipeline into the GObject loop can cause UI lag; a decoupled socket-based communication is the preferred pattern (as seen in `voice-typing-linux`).

## What We're NOT Doing

- Implementing a complex UI/candidate window for now.
- Building a full-fledged installer (manual registration is fine for MVP).
- Supporting multiple languages beyond English for the MVP.

## Implementation Approach

Use a decoupled architecture:
- **`ibus_voxtral_engine.py`**: A lightweight IBus engine that listens on a Unix socket for `preedit` and `commit` commands.
- **`voxtral_bridge.py`**: A bridge that manages the audio capture, `VoxtralProvider` stream, and sends commands to the socket.

## Phase 1: IBus Engine Infrastructure

### Overview
Create the IBus engine and the registration XML.

### Changes Required:

#### 1. IBus Engine Implementation
**File**: `src/voice_to_text/ibus/engine.py` (New)
**Changes**: Implement a class inheriting from `IBus.Engine` that:
- Overrides `do_process_key_event` to return `False` (pass-through).
- Implements `commit(text)` using `self.commit_text()`.
- Implements `preedit(text)` using `self.update_preedit_text()`.
- Runs a background thread with a Unix socket listener to receive commands.

#### 2. Component XML
**File**: `src/voice_to_text/ibus/voxtral.xml` (New)
**Changes**: Create the XML descriptor telling IBus how to launch the engine.

### Success Criteria:

#### Automated Verification:
- [x] `python3 src/voice_to_text/ibus/engine.py` starts without errors.
- [x] XML file is valid.

#### Manual Verification:
- [ ] Run `ibus write-cache --system` and `ibus restart`.
- [ ] "Voxtral" appears as an available input source in system settings.
- [ ] Switching to Voxtral engine does not crash the system.

---

## Phase 2: Voxtral Bridge and Integration

### Overview
Connect the Voxtral provider to the IBus engine.

### Changes Required:

#### 1. Provider Callback Enhancement
**File**: `src/voice_to_text/providers/voxtral.py`
**Changes**: Add an optional `event_callback` to `VoxtralProvider` so it can push transcription events to the bridge in real-time instead of relying on polling `get_partial_result`.

#### 2. Bridge Implementation
**File**: `src/voice_to_text/ibus/bridge.py` (New)
**Changes**:
- Implement audio capture using `PyAudio`.
- Instantiate `VoxtralProvider`.
- In the event callback, send `preedit:TEXT` when `transcription.text.delta` occurs.
- Send `commit:TEXT` when `transcription.segment` or `transcription.done` occurs.
- Connect to the Unix socket defined in `engine.py`.

### Success Criteria:

#### Automated Verification:
- [x] Bridge starts and connects to the IBus socket.
- [x] Audio is successfully captured and sent to the provider.

#### Manual Verification:
- [ ] With Voxtral engine active, speaking into the mic produces underlined text in a text editor.
- [ ] Finalized segments are committed as plain text.

---

## Testing Strategy

### Unit Tests:
- Test the socket protocol (sending `preedit`/`commit` strings).
- Test the `VoxtralProvider` callback triggering.

### Integration Tests:
- End-to-end flow: Mic $\to$ Bridge $\to$ Socket $\to$ IBus $\to$ Application.

### Manual Testing Steps:
1. Launch `engine.py`.
2. Register engine via XML.
3. Switch input source to Voxtral.
4. Launch `bridge.py`.
5. Open a browser, focus a text field, and speak.

## Performance Considerations

- **Latency**: `target_streaming_delay_ms` in `VoxtralProvider` should be tuned (default 400ms).
- **Thread Safety**: Ensure all IBus API calls are wrapped in `GLib.idle_add` to run on the main GObject thread.
