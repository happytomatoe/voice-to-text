# voice-to-text

Convert speech to text for free by using free APIs(Voxtral, Groq) on Linux



## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Groq API key](https://console.groq.com/keys) OR [Voxtral API key](https://mistral.ai)(slightly better)
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

Edit [`config.yaml`](./config.yaml) to customize
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

Press **Enter**, **Escape**, or **q** to stop recording when using default duration

## Gnome Hotkey Setup
1. Install [just](https://github.com/casey/just) if you don't have it
2. Run 
```bash
just setup-global-hotkey
```

This configures **Super+v** to launch voice-to-text in Allacrity terminal. Modify the Justfile for other terminals.

## Output Methods

- **clipboard**: Copies text to system clipboard using `xclip`/`xsel`

## License

MIT
