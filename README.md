# voice-to-text

Convert speech to text for free by using free APIs on Linux

# Providers

Cloud:

- Voxtral
- Groq
- Deepgram

Local:
- Parakeet

This repo contains gnome extension and python application

<https://github.com/user-attachments/assets/a51d6826-e417-4e69-afd0-9ff40799d3a1>

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Groq API key](https://console.groq.com/keys) OR [Voxtral API key](https://mistral.ai)
- Linux with `xclip`/`xsel` (X11) if you'll use clipboard functionality

## Installation

```bash
 curl -sSL https://raw.githubusercontent.com/happytomatoe/voice-to-text/refs/heads/main/install.sh | bash
```

If you want to use Parakeet check out [this script](./parakeet-v2.sh)

## How to use

- Press Super+W
- Dictate
- Press Super+W

## Configuration

### API Keys

The voice-to-text service runs as a D-Bus activated service and loads API keys from your keyring at startup. Use `secret-tool` to store keys securely and the service will retrieve them automatically via `secret-tool`.

#### Store keys with secret-tool

```bash
# Store Mistral/Voxtral key (you'll be prompted to type it securely)
secret-tool store --label="Mistral API Key" service mistral_api_key account $(whoami)

# Store Deepgram key (optional)
secret-tool store --label="Deepgram API Key" application voice-to-text provider deepgram

# Store Groq key (optional)
secret-tool store --label="Groq API Key" application voice-to-text provider groq
```

#### Reload keys

```bash
# Stop the service — it will auto-restart on next use with fresh keys
pkill -f voice-to-text-dbus
```

### Other Settings

Edit [`config.yaml`](./config.yaml) to customize if you are using python app or right click on microphone icon->Preferences if you are using gnome extension

## Output Methods

- **clipboard**: Copies text to system clipboard using `xclip`/`xsel`
- **output** - used by gnome extension

## Attribution

- The diff-based incremental typing algorithm in [`gnome-ext/typer.js`](./gnome-ext/typer.js) is inspired by [nerd-dictation](https://github.com/ideasman42/nerd-dictation)

## License

MIT
