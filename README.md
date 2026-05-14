# voice-to-text

Convert speech to text for free by using free APIs(Voxtral, Groq) on Linux

![Demo](./demo.gif)

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

If you are on Linux you can use next approach to store credentials securely
```bash
# For fedora - 
sudo dnf install libsecret
# Store
secret-tool store --label="mistral api key" service voxtral_api_key account $USER

# Retrieve
export VOXTRAL_API_KEY=$(secret-tool lookup service voxtral_api_key account $USER)
```

## Configuration

Edit [`config.yaml`](./config.yaml) to customize

## Usage

### Simple mode (CLI)

```bash
# Record and copy transcribed text to clipboard
voice-to-text

# Specify recording duration (seconds, 0 = wait for key)
voice-to-text --duration 10

# Output to stdout instead of clipboard (for pipes/scripts)
voice-to-text --output stdout

# Specify provider
voice-to-text --provider groq
voice-to-text --provider voxtral

# List audio input devices
voice-to-text devices

# Interactive setup to configure provider
voice-to-text setup
```

Press **Enter** to stop recording and transcribe, **Escape** or **q** to cancel.

### GNOME Extension mode

The GNOME Shell extension adds a microphone icon to the top bar with an audio level visualizer. Click the mic to start recording, click the stop button to stop. A global hotkey (**Super+W**) toggles recording. Transcribed text is typed directly into the focused application.

## GNOME Extension Installation

```bash
UUID="voice-to-text@happytomatoe.com"
SRC="gnome-ext"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"

# Copy extension files
mkdir -p "$DEST/schemas"
cp "$SRC"/*.js "$SRC"/*.json "$SRC"/*.css "$DEST/"
cp "$SRC"/schemas/*.xml "$DEST/schemas/"
glib-compile-schemas "$DEST/schemas/"

# Enable the extension
gnome-extensions enable "$UUID"
```

Alternatively, use `just dev-extension` to install and test in a nested GNOME Shell session.

After installing, the extension needs `ydotool` for typing text into applications:

```bash
# Fedora
sudo dnf install ydotool

# Arch
sudo pacman -S ydotool
```

## Output Methods

- **clipboard**: Copies text to system clipboard using `xclip`/`xsel`
- **stdout**: Prints text to stdout (used by the GNOME extension)

## License

MIT
