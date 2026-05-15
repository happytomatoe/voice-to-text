#!/usr/bin/env bash
set -euo pipefail

REPO="happytomatoe/voice-to-text"
EXT_UUID="voice-to-text@happytomatoe.com"
INSTALL_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"

echo "=== voice-to-text installer ==="
echo ""

# --- Detect OS ---
if command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
elif command -v pacman &>/dev/null; then
    PKG_MGR="pacman"
elif command -v apt &>/dev/null; then
    PKG_MGR="apt"
else
    echo "ERROR: Unsupported package manager. Supported: dnf, pacman, apt"
    exit 1
fi

echo "Detected package manager: $PKG_MGR"
echo ""

# --- Install prerequisites ---
echo "Installing prerequisites..."
case "$PKG_MGR" in
    dnf)
        sudo dnf install -y ydotool unzip curl 2>/dev/null || true
        ;;
    pacman)
        sudo pacman -S --noconfirm ydotool unzip curl 2>/dev/null || true
        ;;
    apt)
        sudo apt install -y ydotool unzip curl 2>/dev/null || true
        ;;
esac

# --- Install Python application ---
echo ""
echo "--- Installing Python application ---"

if command -v uv &>/dev/null; then
    echo "Fetching latest release tag..."
    LATEST_TAG=$(curl -s "https://api.github.com/repos/$REPO/releases/latest" \
        | grep '"tag_name"' \
        | cut -d '"' -f 4)

    if [ -z "$LATEST_TAG" ] || [ "$LATEST_TAG" = "null" ]; then
        echo "ERROR: No releases found for $REPO."
        echo "Create a release first: https://github.com/$REPO/releases/new"
        exit 1
    fi

    echo "Installing version $LATEST_TAG..."
    uv tool install "git+https://github.com/$REPO.git@$LATEST_TAG" --force
    echo "Python application installed."
else
    echo "uv not found. Installing standalone binary..."
    LATEST_URL="https://github.com/$REPO/releases/latest/download/voice-to-text"
    curl -L -o /tmp/voice-to-text "$LATEST_URL"
    chmod +x /tmp/voice-to-text
    mkdir -p "$HOME/.local/bin"
    mv /tmp/voice-to-text "$HOME/.local/bin/voice-to-text"
    echo "Binary installed to $HOME/.local/bin/voice-to-text"
    echo "Make sure $HOME/.local/bin is in your PATH."
fi

# --- Install GNOME extension ---
echo ""
echo "--- Installing GNOME extension ---"

echo "Fetching latest release..."
RELEASE_URL=$(curl -s "https://api.github.com/repos/$REPO/releases/latest" \
    | grep "browser_download_url.*shell-extension.zip" \
    | cut -d '"' -f 4)

if [ -z "$RELEASE_URL" ] || [ "$RELEASE_URL" = "null" ]; then
    echo "ERROR: Could not find extension ZIP in latest release."
    echo "Falling back to installing from source..."
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/schemas"
    TMPDIR=$(mktemp -d)
    git clone --depth 1 "https://github.com/$REPO.git" "$TMPDIR/repo"
    cp "$TMPDIR/repo/gnome-ext"/*.js "$TMPDIR/repo/gnome-ext"/*.json "$TMPDIR/repo/gnome-ext"/*.css "$INSTALL_DIR/"
    cp "$TMPDIR/repo/gnome-ext"/schemas/*.xml "$INSTALL_DIR/schemas/"
    glib-compile-schemas "$INSTALL_DIR/schemas/"
    rm -rf "$TMPDIR"
else
    echo "Downloading: $RELEASE_URL"
    curl -L -o /tmp/voice-to-text-ext.zip "$RELEASE_URL"
    gnome-extensions install --force /tmp/voice-to-text-ext.zip
    rm -f /tmp/voice-to-text-ext.zip
fi

gnome-extensions enable "$EXT_UUID"
echo "GNOME extension installed and enabled."

# --- Configure provider and API key ---
echo ""
echo "--- Configuration ---"

# Detect shell profile
if [ -f "$HOME/.zprofile" ]; then
    PROFILE="$HOME/.zprofile"
elif [ -f "$HOME/.bash_profile" ]; then
    PROFILE="$HOME/.bash_profile"
elif [ -f "$HOME/.profile" ]; then
    PROFILE="$HOME/.profile"
else
    PROFILE="$HOME/.profile"
    touch "$PROFILE"
fi

echo "Shell profile: $PROFILE"
echo ""

# Choose provider
echo "Choose transcription provider:"
echo "  1) Groq (fast, free tier)"
echo "  2) Voxtral (slightly better quality)"
echo ""
read -rp "Select [1/2] (default: 1): " PROVIDER_CHOICE
case "$PROVIDER_CHOICE" in
    2)
        PROVIDER="voxtral"
        API_KEY_ENV="VOXTRAL_API_KEY"
        ;;
    *)
        PROVIDER="groq"
        API_KEY_ENV="GROQ_API_KEY"
        ;;
esac

echo "Selected provider: $PROVIDER"
echo ""

# Get API key
read -rp "Enter your $API_KEY_ENV: " API_KEY
if [ -z "$API_KEY" ]; then
    echo "WARNING: No API key provided. You must set $API_KEY_ENV before using the app."
else
    # Remove old key entries if they exist
    if grep -q "export $API_KEY_ENV=" "$PROFILE" 2>/dev/null; then
        sed -i "/export $API_KEY_ENV=/d" "$PROFILE"
    fi
    # Append new key
    echo "" >> "$PROFILE"
    echo "# voice-to-text API key" >> "$PROFILE"
    echo "export $API_KEY_ENV='$API_KEY'" >> "$PROFILE"
    echo "API key saved to $PROFILE"
    # Export for current session
    export "$API_KEY_ENV"="$API_KEY"
fi

# Configure provider in config
CONFIG_DIR="$HOME/.config/voice-to-text"
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/config.yaml" <<EOF
transcription:
  provider: "$PROVIDER"
  language: "en"

groq:
  api_key_env: "GROQ_API_KEY"

voxtral:
  api_key_env: "VOXTRAL_API_KEY"
  model: "voxtral-mini-latest"

audio:
  sample_rate: 16000
  channels: 1
  block_size: 2048
  smooth_factor: 0.7

logging:
  file: "/tmp/groq_voice.log"
  level: "info"
EOF
echo "Provider configured: $PROVIDER"

# --- Done ---
echo ""
echo "=== Installation complete ==="
echo ""
echo "Python app: voice-to-text"
echo "GNOME extension: $EXT_UUID (hotkey: Super+W)"
echo ""
echo "Open a new terminal or run: source $PROFILE"
echo "Then test with: voice-to-text"
echo ""
echo "Restart GNOME Shell (Alt+F2, r, Enter on X11) or log out/in on Wayland."
