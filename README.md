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

You can provide API keys in two ways:

#### 1. Environment Variables (Default)

```bash
export VOXTRAL_API_KEY="your-api-key-here"
export DEEPGRAM_API_KEY="your-api-key-here"
export GROQ_API_KEY="your-api-key-here"
```

#### 2. OS Keyring

Store keys securely in your OS keyring (GNOME Keyring, KDE Wallet, etc.):

```bash
# Store keys
keyring set voice-to-text deepgram
keyring set voice-to-text groq
keyring set voice-to-text voxtral
```

Then enable keyring in your config:

```yaml
transcription:
  api_key_source: "keyring"
```

Or per-provider:

```yaml
deepgram:
  api_key_source: "keyring"
```

The app reads from the keyring service `voice-to-text` with the provider name as username.

#### 3. Configuration File

Put the keys in `~/.config/voice-to-text/config.yaml`:

```yaml
voxtral:
  api_key: "your-api-key-here"

deepgram:
  api_key: "your-api-key-here"
```

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
