# voice-to-text

Convert speech to text for free by using free APIs(Voxtral, Groq) on Linux

![Demo](./demo.gif)

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Groq API key](https://console.groq.com/keys) OR [Voxtral API key](https://mistral.ai)(slightly better)
- Linux with `xclip`/`xsel` (X11) for clipboard functionality

## Installation

### Python Application

Install the latest release directly from GitHub using `uv`:

```bash
uv tool install git+https://github.com/happytomatoe/voice-to-text.git
```

Or download the standalone binary from [GitHub Releases](https://github.com/happytomatoe/voice-to-text/releases):

```bash
curl -LO https://github.com/happytomatoe/voice-to-text/releases/latest/download/voice-to-text
chmod +x voice-to-text
./voice-to-text
```

### GNOME Extension

Install the latest release with one command:

```bash
curl -L -o /tmp/vtt-ext.zip \
  $(curl -s https://api.github.com/repos/happytomatoe/voice-to-text/releases/latest \
    | grep "browser_download_url.*shell-extension.zip" \
    | cut -d '"' -f 4)
gnome-extensions install --force /tmp/vtt-ext.zip
gnome-extensions enable voice-to-text@happytomatoe.com
```

### Install from source

```bash
git clone https://github.com/happytomatoe/voice-to-text.git
cd voice-to-text

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

### Prerequisites

The extension requires `ydotool` for typing text into applications:

```bash
# Fedora
sudo dnf install ydotool

# Arch
sudo pacman -S ydotool

# Ubuntu/Debian
sudo apt install ydotool
```

> **Note:** `ydotool` requires proper permissions. See [ydotool setup](https://github.com/ReimuNotMoe/ydotool) if typing doesn't work.

### Install latest release

```bash
curl -L -o /tmp/vtt-ext.zip \
  $(curl -s https://api.github.com/repos/happytomatoe/voice-to-text/releases/latest \
    | grep "browser_download_url.*shell-extension.zip" \
    | cut -d '"' -f 4)
gnome-extensions install --force /tmp/vtt-ext.zip
gnome-extensions enable voice-to-text@happytomatoe.com
```

### Install from source (development)

```bash
UUID="voice-to-text@happytomatoe.com"
SRC="gnome-ext"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"

mkdir -p "$DEST/schemas"
cp "$SRC"/*.js "$SRC"/*.json "$SRC"/*.css "$DEST/"
cp "$SRC"/schemas/*.xml "$DEST/schemas/"
glib-compile-schemas "$DEST/schemas/"
gnome-extensions enable "$UUID"
```

Alternatively, use `just dev-extension` to install and test in a nested GNOME Shell session.

### Extension Manager app

1. Install [Extension Manager](https://flathub.org/apps/com.mattjakeman.ExtensionManager):
   ```bash
   flatpak install flathub com.mattjakeman.ExtensionManager
   ```
2. Open Extension Manager, go to **Browse**, and search for "Voice to Text"
3. Click **Install**

### extensions.gnome.org

1. Install the browser connector:
   ```bash
   # Fedora
   sudo dnf install chrome-gnome-shell

   # Ubuntu/Debian
   sudo apt install chrome-gnome-shell
   ```
2. Visit [extensions.gnome.org](https://extensions.gnome.org) and toggle the extension on

### After installing

Restart GNOME Shell (`Alt+F2`, type `r`, press Enter on X11) or log out/in (Wayland). Verify the extension is active:

```bash
gnome-extensions list
gnome-extensions info voice-to-text@happytomatoe.com
```

You should see a microphone icon in the top bar. Click it to start recording, or press **Super+W**.

## Output Methods

- **clipboard**: Copies text to system clipboard using `xclip`/`xsel`
- **stdout**: Prints text to stdout (used by the GNOME extension)

## License

MIT
