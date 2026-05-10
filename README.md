# voice-to-text

Voice to text using Groq Whisper and Voxtral APIs with Gnome hotkey integration.

## Requirements

- Python 3.10+
- [Groq API key](https://console.groq.com/keys) OR [Voxtral API key](https://mistral.ai)
- Linux with `xclip`/`xsel` (X11) for clipboard functionality

## Installation

```bash
# Clone and setup virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -e .

# set GROQ_API_KEY or VOXTRAL_API_KEY
export GROQ_API_KEY=""
export VOXTRAL_API_KEY=""
```

## Configuration

Edit `config.yaml` to customize:

```yaml
audio:
  sample_rate: 16000
  channels: 1
  max_duration: 30
  duration: 5  # 0 = wait for keypress

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
```

## Usage

```bash
# Run with default config
voice-to-text

# Specify recording duration
voice-to-text --duration 10

# Specify provider
voice-to-text --provider groq
voice-to-text --provider voxtral

# Interactive setup to configure provider
voice-to-text setup
```

Press **Enter**, **Escape**, or **q** to stop recording when using default duration (0).

## Gnome Hotkey Setup

```bash
just install-ghostty
```

This configures **Super+v** to launch voice-to-text in Ghostty terminal. Modify the justfile for other terminals.

## Output Methods

- **clipboard**: Copies text to system clipboard using `xclip`/`xsel`

## License

MIT
