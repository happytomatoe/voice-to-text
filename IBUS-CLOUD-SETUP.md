# IBus Cloud Speech Engine Setup Guide

This guide covers setting up the Cloud Speech input method engine for IBus, allowing voice-to-text via Super+Q hotkey.

## Prerequisites

- Python 3.13+
- IBus daemon running
- Audio input device (microphone)
- Groq or Voxtral API key for transcription

## Installation

### 1. Install System Dependencies

```bash
# Fedora/RHEL
sudo dnf install python3-gobject-devel ibus

# Debian/Ubuntu
sudo apt install python3-gi python3-gi-cairo gir1.2-ibus-1.0
```

### 2. Install Voice-to-Text Dependencies

```bash
cd /path/to/voice-to-text
pip install -e .
```

### 3. Configure API Keys

Create `~/.config/voice-to-text/config.yaml`:

```yaml
transcription:
  provider: groq  # or "voxtral"
  language: en

groq:
  api_key: your_groq_api_key_here

voxtral:
  api_key: your_voxtral_api_key_here

audio:
  duration: 30  # max recording duration in seconds
```

### 4. Register IBus Component

```bash
# Copy component XML to system IBus directory (requires sudo)
sudo cp data/ibus-cloud.xml /usr/share/ibus/component/

# Reload IBus
ibus write-cache
ibus restart
```

### 5. Verify Engine is Available

```bash
ibus list-engine | grep -i cloud
```

Should show:
```
com.cloud-voice.CloudSpeech - Cloud Speech
```

## Running the Engine

### Option 1: Run Manually

```bash
# Start the engine in background
./ibus-engine-cloud --ibus &
```

### Option 2: Switch to Engine

```bash
ibus engine com.cloud-voice.CloudSpeech
```

### Option 3: Use via Desktop Settings

Open IBus preferences or system input method settings and select "Cloud Speech".

## Usage

1. **Activate**: Switch to Cloud Speech input method
2. **Start Recording**: Press `Super+Q` (Windows key + Q)
3. **Stop Recording**: Press `Super+Q` again
4. **Result**: Transcribed text is automatically inserted into the active text field

### Visual Feedback

- **Idle**: "Cloud: Press Super+Q to record"
- **Recording**: "● Recording... ███░░░░░░" (audio level visualization)
- **Transcribing**: "◐ Transcribing..."

## Troubleshooting

### Engine Not Appearing in List

```bash
# Check if component is registered
ibus list-engine | grep cloud

# If not, try reloading
ibus write-cache && ibus restart
```

### Switch Fails with "Connection Closed"

Check logs:
```bash
cat /tmp/ibus-cloud.log
```

Ensure the launcher script is executable:
```bash
chmod +x ibus-engine-cloud
```

### No Audio Devices Found

```bash
# List available audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### API Key Issues

Verify your config file exists:
```bash
cat ~/.config/voice-to-text/config.yaml
```

## Development

### Running from Source

```bash
# Set Python path
export PYTHONPATH=$PYTHONPATH:/path/to/voice-to-text/src

# Run with debug logging
python3 ibus-engine-cloud --ibus
```

### Logs

- Engine logs: `/tmp/ibus-cloud.log`
- Default log: `/tmp/voice-to-text.log`

## Files

- `src/ibus_cloud/engine.py` - Main engine implementation
- `src/ibus_cloud/audio.py` - Audio recording
- `src/ibus_cloud/config.py` - Configuration
- `ibus-engine-cloud` - Launcher script
- `data/ibus-cloud.xml` - IBus component definition

## References

- [IBus Reference Manual](https://ibus.github.io/docs/ibus-1.5/)
- [IBus Python GI Docs](https://lazka.github.io/pgi-docs/IBus-1.0/)
- [IBus STT Engine](https://github.com/PhilippeRo/ibus-stt) - Reference Python IBus engine