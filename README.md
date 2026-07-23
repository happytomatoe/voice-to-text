# voice-to-text

Convert speech to text for free by using free APIs on Linux

# Providers

Cloud:

- Voxtral
- Groq
- Deepgram
- 60db
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

You can provide API keys in three ways:

#### 1. Environment Variables (Default)

```bash
export VOXTRAL_API_KEY="your-api-key-here"
export DEEPGRAM_API_KEY="your-api-key-here"
export GROQ_API_KEY="your-api-key-here"
export SIXTYDB_API_KEY="your-api-key-here"
export ELEVENLABS_API_KEY="your-api-key-here"
```

#### 2. OS Keyring

Store keys securely in your OS keyring (GNOME Keyring, KDE Wallet, etc.):

Requires `libsecret-tools` (Linux) or `keyring` Python package. The app reads from the keyring with `service=voice-to-text` and `username=<provider>`.

```bash
# Store API keys using secret-tool (Linux/GNOME Keyring)
secret-tool store --label="Deepgram API Key"   service voice-to-text username deepgram
secret-tool store --label="Voxtral API Key"    service voice-to-text username voxtral
secret-tool store --label="Groq API Key"       service voice-to-text username groq
secret-tool store --label="60db API Key"       service voice-to-text username 60db
secret-tool store --label="ElevenLabs API Key" service voice-to-text username elevenlabs
```

Or using the Python `keyring` library:

```bash
python3 -c "import keyring, getpass; keyring.set_password('voice-to-text', 'deepgram', getpass.getpass('Deepgram key: '))"
python3 -c "import keyring, getpass; keyring.set_password('voice-to-text', 'voxtral', getpass.getpass('Voxtral key: '))"
python3 -c "import keyring, getpass; keyring.set_password('voice-to-text', 'groq', getpass.getpass('Groq key: '))"
python3 -c "import keyring, getpass; keyring.set_password('voice-to-text', '60db', getpass.getpass('60db key: '))"
python3 -c "import keyring, getpass; keyring.set_password('voice-to-text', 'elevenlabs', getpass.getpass('ElevenLabs key: '))"

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
