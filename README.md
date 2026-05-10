# voice-to-text

Convert speech to text for free by using free APIS(Voxtral, Groq)

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Groq API key](https://console.groq.com/keys) OR [Voxtral API key](https://mistral.ai)
- Linux with `xclip`/`xsel` (X11) for clipboard functionality

## Installation

```bash
# Clone and setup virtual environment

uv venv 
uv sync
uv pip install -e .

# set GROQ_API_KEY or VOXTRAL_API_KEY
export GROQ_API_KEY=""
export VOXTRAL_API_KEY=""
```

## Configuration

Edit [`config.yaml`](./config.yaml) to customize:
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
