# Voxtral IBus Engine - Usage Guide

## Quick Start

### 1. Installation (User-Level)

```bash
# Install the engine
just ibus-install

# Log out and log back in to pick up environment variables
```

### 2. Verify Installation

```bash
# Check if everything is set up correctly
just ibus-verify
```

### 3. Run the Engine

```bash
# Start both engine and bridge
just ibus-run

# Or run them separately:
# Terminal 1: Start the engine
just ibus-engine

# Terminal 2: Start the bridge
just ibus-bridge
```

## How It Works

The Voxtral IBus engine consists of two main components:

### 1. IBus Engine (`engine.py`)
- Registers with IBus as an input method
- Creates a Unix socket for communication
- Receives text commands from the bridge
- Commits text to the focused application

### 2. Bridge (`bridge.py`)
- Captures audio from the microphone
- Sends audio to Voxtral for transcription
- Sends transcribed text to the engine via Unix socket

## Usage Flow

1. **Start the engine and bridge** (with `just ibus-run`)
2. **Switch to Voxtral engine** (Super+Space or IBus tray)
3. **Open a text editor** (gedit, nano, VS Code, etc.)
4. **Speak into microphone** - the bridge captures audio
5. **Text appears** - transcribed text is committed to the application

## Available Commands

| Command | Description |
|---------|-------------|
| `just ibus-install` | Install Voxtral engine (user-local) |
| `just ibus-engine` | Start the engine (for testing) |
| `just ibus-bridge` | Start the audio bridge |
| `just ibus-run` | Start both engine and bridge |
| `just ibus-verify` | Verify installation |
| `just ibus-uninstall` | Remove Voxtral engine |
| `just ibus-install-system` | System-wide installation (requires sudo) |

## Configuration

### Environment Variables

- `IBUS_COMPONENT_PATH` - Path to IBus component XML files
- `VOXTRAL_IBUS_SOCKET` - Custom socket path (default: `/run/user/1000/voxtral-ibus.sock`)

### Files

- **Component XML**: `~/.local/share/ibus/component/voxtral.xml`
- **Environment config**: `~/.config/environment.d/ibus.conf`

## Troubleshooting

### Engine doesn't appear in IBus

```bash
# Check if engine is registered
ibus list-engine | grep -i voxtral

# If not found, refresh cache
export IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component"
ibus write-cache
```

### Socket connection fails

```bash
# Check if socket exists
ls -la /run/user/1000/voxtral-ibus.sock

# Check if engine is running
pgrep -a engine.py
```

### Bridge can't connect

- Make sure the engine is focused (selected as active input method)
- The socket is only created when the engine is focused
- Check bridge logs for connection errors

## Architecture

```
┌─────────────┐    Unix Socket    ┌─────────────┐
│   Bridge    │ ◄──────────────► │   Engine    │
│ (audio in)  │                   │ (IBus out)  │
└─────────────┘                   └─────────────┘
       │                               │
       ▼                               ▼
  Microphone                    Focused Application
```

## Technical Details

- **Socket Protocol**: JSON-lines over Unix socket
- **Commands**: `preedit`, `commit`, `clear_preedit`, `shutdown`
- **IBus Integration**: Uses IBus Python bindings (gi/PyGObject)
- **Audio Processing**: Uses sounddevice for microphone capture
- **Transcription**: Uses Voxtral provider for speech-to-text

## Requirements

- Python 3.x with gi/PyGObject (for IBus)
- IBus framework installed
- Microphone access
- Voxtral API access (for transcription)

## Testing

Run the test script to verify the engine works:

```bash
python3 test_engine.py
```

This tests:
- Engine creation
- Socket listener
- Socket communication
- Command processing
