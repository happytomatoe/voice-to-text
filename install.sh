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
  sudo dnf install ydotool unzip curl libsecret 2>/dev/null || true
  ;;
pacman)
  sudo pacman -S ydotool unzip curl libsecret 2>/dev/null || true
  ;;
apt)
  sudo apt install ydotool unzip curl libsecret-1-dev libsecret-tools 2>/dev/null || true
  ;;
esac

# --- Install Python application ---
echo ""
echo "--- Installing Python application ---"
echo "Fetching latest release tag..."
LATEST_TAG=$(
  git ls-remote --tags --sort=v:refname https://github.com/happytomatoe/voice-to-text | tail -n 1 | awk -F'/' '{print $NF}'
)

if command -v uv &>/dev/null; then
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
RELEASE_URL="https://github.com/happytomatoe/voice-to-text/releases/download/$LATEST_TAG/voice-to-text@happytomatoe.com.shell-extension.zip"
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
  cd /tmp
  curl -LO "$RELEASE_URL"
  filename=$(basename $RELEASE_URL)
  gnome-extensions install --force /tmp/$filename
  rm -f /tmp/$filename
fi

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
echo "Enter your $API_KEY_ENV: "

secret-tool store --label="$API_KEY_ENV" service $API_KEY_ENV account $USER
export API_KEY=$(secret-tool lookup service $API_KEY_ENV account $USER)
if [ -z "$API_KEY" ]; then
  echo "WARNING: No API key provided. You must set $API_KEY_ENV before using the app."
else
  # Remove old key entries if they exist
  if grep -q "export $API_KEY_ENV=" "$PROFILE" 2>/dev/null; then
    sed -i "/export $API_KEY_ENV=/d" "$PROFILE"
  fi
  # Append new key
  echo "" >>"$PROFILE"
  echo "# voice-to-text API key" >>"$PROFILE"
  echo "export $API_KEY_ENV=\$(secret-tool lookup service '$API_KEY_ENV' account \$USER)" >>"$PROFILE"
  echo "API key saved to $PROFILE"
  # Export for current session
  export "$API_KEY_ENV"="$API_KEY"
fi

# Configure provider in config
CONFIG_DIR="$HOME/.config/voice-to-text"
mkdir -p "$CONFIG_DIR"
cat >"$CONFIG_DIR/config.yaml" <<EOF
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

# Create ydotool daemon

# SOCKET_PATH="/run/user/$(id -u)/.ydotool_socket"
# export YDOTOOL_SOCKET="$SOCKET_PATH"
#
# # 1. Check if the service is already running and the socket exists
# if systemctl --user is-active --quiet ydotool.service && [ -S "$SOCKET_PATH" ]; then
#   echo "ℹ️ ydotool service is already running. Testing typing..."
#   echo ""
#   echo "=== Installation complete ==="
#   echo ""
#   echo "Python app: voice-to-text"
#   echo "GNOME extension: $EXT_UUID (hotkey: Super+W)"
#   echo ""
#   echo "Open a new terminal or run: source $PROFILE"
#   echo "Then test with: voice-to-text"
#   echo ""
#   echo "Restart GNOME Shell (Alt+F2, r, Enter on X11) or log out/in on Wayland. Enable extension extension after relogin or reload"
#
#   exit 0
# fi
#
# echo "🔄 ydotool is not running or socket is missing. Initializing configuration..."
#
# # 2. Create the user-level drop-in override directory
# mkdir -p "$HOME/.config/systemd/user/ydotool.service.d"
#
# # 3. Inject the custom socket path configuration
# cat <<EOF >"$HOME/.config/systemd/user/ydotool.service.d/socket-path.conf"
# [Service]
# ExecStart=
# ExecStart=/usr/bin/ydotoold --socket-path=$SOCKET_PATH --socket-perm=666
# EOF
#
# # 4. Reload, enable, and start the service
# systemctl --user daemon-reload
# systemctl --user enable ydotool.service
# systemctl --user restart ydotool.service
# sleep 1
#
# # 5. Final verification check
# if [ -S "$SOCKET_PATH" ]; then
#   echo "✅ ydotoold started successfully. Socket at $SOCKET_PATH"
#   ydotool type -- "voice-to-text fixed"
# else
#   echo "❌ Socket not found at $SOCKET_PATH"
#   systemctl --user status ydotool.service --no-pager
#   journalctl --user -u ydotool.service --no-pager -n 20
#   exit 1
# fi
echo ""
echo "=== Installation complete ==="
echo ""
echo "Python app: voice-to-text"
echo "GNOME extension: $EXT_UUID (hotkey: Super+W)"
echo ""
echo "Open a new terminal or run: source $PROFILE"
echo "Then test with: voice-to-text"
echo ""
echo "Restart GNOME Shell (Alt+F2, r, Enter on X11) or log out/in on Wayland. Enable extension extension after relogin or reload"
