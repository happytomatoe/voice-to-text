# Voxtral IBus Integration Guide

This guide explains how to register and use the Voxtral speech-to-text engine as an IBus input method on Linux.

## Prerequisites

- Linux with IBus framework installed
- Python 3.13+ with the following packages:
  - `gi` (PyGObject) - for IBus integration
  - `sounddevice` - for audio capture
  - `numpy` - for audio processing
  - `mistralai[realtime]` - for Voxtral API
- Mistral API key (set as `VOXTRAL_API_KEY` or `MISTRAL_API_KEY` environment variable)

## Quick Start

The easiest way to run Voxtral IBus integration:

```bash
cd /var/home/l/git/voice-to-text-ibus
python3 scripts/voxtral_ibus.py
```

This will:
1. Start the IBus engine process
2. Start the audio capture bridge
3. Begin listening for speech

## Manual Registration

If you want to register the engine permanently with IBus:

### 1. Install the Component

**Option A: System-wide (requires sudo)**
```bash
sudo cp src/voice_to_text/ibus/voxtral.xml /usr/share/ibus/component/
```

**Option B: User-local (recommended for Silverblue and immutable systems)**
```bash
mkdir -p ~/.config/ibus/component/
cp src/voice_to_text/ibus/voxtral.xml ~/.config/ibus/component/
```

### 2. Set Environment Variable

IBus needs to know where to find your custom component files. Add to your shell profile (`~/.bashrc`, `~/.zshrc`, or `~/.profile`):

```bash
export IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component:$IBUS_COMPONENT_PATH"
```

Alternatively, on Fedora/Silverblue with GNOME, create an environment file:

```bash
echo 'IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component:$IBUS_COMPONENT_PATH"' > ~/.config/environment.d/ibus.conf
```

### 3. Update IBus Cache

```bash
ibus write-cache
ibus restart
```

> **Note:** On Fedora Silverblue, you may need to log out and back in for the environment variable to take effect.

### 4. Add as Input Source

1. Open Settings → Keyboard → Input Sources
2. Click the "+" button
3. Select "Other" → "Voxtral"
4. Click "Add"

**Alternative:** You can also add Voxtral to the preload engines:
```bash
ibus config --preload-engines org.freedesktop.IBus.Voxtral
```

## Usage

### Starting the Engine

Once registered, you can start the Voxtral engine from the system tray or by running:

```bash
python3 scripts/voxtral_ibus.py
```

Or start just the bridge (if engine is already running):

```bash
PYTHONPATH=src .venv/bin/voice-to-text-ibus  # or directly:
PYTHONPATH=src .venv/bin/python3 src/voice_to_text/ibus/bridge.py
```

### Stopping

Press `Ctrl+C` in the terminal where you started the script, or:

```bash
pkill -f voxtral_ibus.py
```

## Architecture

```
┌─────────────────┐     Unix Socket      ┌─────────────────┐
│   Bridge        │ ────────────────────> │   IBus Engine   │
│                 │                       │                 │
│ - Audio Capture │                       │ - GLib Loop     │
│ - Voxtral API   │                       │ - IBus API      │
│ - Event Callback│                       │ - Socket Server │
└─────────────────┘                       └─────────────────┘
```

- **Bridge** (`bridge.py`): Runs in the venv Python environment, captures audio, sends to Voxtral API, and sends commands to the engine via Unix socket.
- **Engine** (`engine.py`): Runs in system Python (with gi), receives commands via socket, and sends text to the focused application via IBus.

## Socket Protocol

The bridge communicates with the engine using newline-delimited commands:

- `preedit:<text>` - Update the underlined temporary text
- `commit:<text>` - Commit finalized text to the application
- `clear_preedit` - Clear the preedit text
- `shutdown` - Shut down the engine

## Configuration

The bridge uses the standard `voice-to-text` configuration file at `~/.config/voice-to-text/config.yaml`.

Example configuration:

```yaml
transcription:
  provider: voxtral

voxtral:
  api_key: your-mistral-api-key-here
  realtime_model: voxtral-mini-transcribe-realtime-2602
  target_delay_ms: 400
```

## Troubleshooting

### Engine not starting

1. Check if IBus is running: `ibus list-engine`
2. Check the engine logs for errors
3. Verify the socket path: `/tmp/voxtral-ibus.sock`

### No text appearing

1. Ensure the engine is selected as the active input source
2. Check that the bridge is connected to the socket
3. Verify microphone permissions

### Audio not captured

1. Test microphone: `python3 -c "import sounddevice; print(sounddevice.query_devices())"`
2. Check PulseAudio/PipeWire is running
3. Try a different audio device

## Files

- `src/voice_to_text/ibus/engine.py` - IBus engine implementation
- `src/voice_to_text/ibus/bridge.py` - Audio bridge to Voxtral
- `src/voice_to_text/ibus/voxtral.xml` - IBus component descriptor
- `scripts/voxtral_ibus.py` - Launcher script
