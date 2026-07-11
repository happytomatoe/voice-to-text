# voice-to-text

Convert speech to text for free by using free APIs on Linux

# Providers

Cloud:

- Voxtral
- Groq
- Deepgram
- ElevenLabs

Local:
- Parakeet

This repo contains gnome extension and python application

<https://github.com/user-attachments/assets/a51d6826-e417-4e69-afd0-9ff40799d3a1>

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Groq API key](https://console.groq.com/keys) OR [Voxtral API key](https://mistral.ai) OR [ElevenLabs API key](https://elevenlabs.io/app/settings/api-keys)
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

The voice-to-text service loads API keys from your system keyring at startup using `secret-tool`.

**Store only the key for the provider you use:**

```bash
# For Voxtral/Mistral (default provider)
secret-tool store --label="Mistral API Key" service mistral_api_key account $USER

# For Deepgram (if using deepgram provider)
secret-tool store --label="Deepgram API Key" application voice-to-text provider deepgram

# For Groq (if using groq provider)
secret-tool store --label="Groq API Key" application voice-to-text provider groq

# For ElevenLabs (if using elevenlabs provider)
secret-tool store --label="ElevenLabs API Key" application voice-to-text provider elevenlabs
```

Check which provider you're using in `~/.config/voice-to-text/config.yaml`.

#### Reload keys

```bash
# Stop the service — it will auto-restart on next use with fresh keys
just service-stop
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
