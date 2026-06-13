#!/usr/bin/env bash
set -euo pipefail
REPO="happytomatoe/voice-to-text"
EXT_UUID="voice-to-text@happytomatoe.com"
INSTALL_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"

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
  git ls-remote --tags --sort=-v:refname "https://github.com/$REPO.git" \
    | awk -F'/' '$NF !~ /\^\{\}$/ { print $NF; exit }'
)
if [ -z "$LATEST_TAG" ]; then
  echo "WARNING: No releases found for $REPO; falling back to source checkout for the GNOME extension."
  HAS_RELEASE=0
else
  HAS_RELEASE=1
fi

if command -v uv &>/dev/null; then
  if [ "$HAS_RELEASE" -eq 0 ]; then
    echo "ERROR: No releases found for $REPO."
    echo "Create a release first: https://github.com/$REPO/releases/new"
    exit 1
  fi

  echo "Installing version $LATEST_TAG..."
  uv tool install "git+https://github.com/$REPO.git@$LATEST_TAG" --force
  echo "Python application installed."
  VOICE_TO_TEXT_CMD="uv tool run voice-to-text"
else
  if [ "$HAS_RELEASE" -eq 0 ]; then
    echo "ERROR: No releases found for $REPO."
    echo "Install uv (https://docs.astral.sh/uv/) or create a release first: https://github.com/$REPO/releases/new"
    exit 1
  fi
  echo "uv not found. Installing standalone binary..."
  LATEST_URL="https://github.com/$REPO/releases/latest/download/voice-to-text"
  curl -L -o /tmp/voice-to-text "$LATEST_URL"
  chmod +x /tmp/voice-to-text
  mkdir -p "$HOME/.local/bin"
  mv /tmp/voice-to-text "$HOME/.local/bin/voice-to-text"
  echo "Binary installed to $HOME/.local/bin/voice-to-text"
  echo "Make sure $HOME/.local/bin is in your PATH."
  VOICE_TO_TEXT_CMD="$HOME/.local/bin/voice-to-text"
fi

# --- Install GNOME extension ---
echo ""
echo "--- Installing GNOME extension ---"

echo "Fetching latest release..."
if [ "$HAS_RELEASE" -eq 0 ]; then
  echo "Falling back to installing the extension from source..."
  rm -rf "$INSTALL_DIR"
  mkdir -p "$INSTALL_DIR/schemas"
  TMPDIR=$(mktemp -d)
  git clone --depth 1 "https://github.com/$REPO.git" "$TMPDIR/repo"
  cp "$TMPDIR/repo/gnome-ext"/*.js "$TMPDIR/repo/gnome-ext"/*.json "$INSTALL_DIR/"
  cp "$TMPDIR/repo/gnome-ext"/*.css "$INSTALL_DIR/" 2>/dev/null || true
  cp "$TMPDIR/repo/gnome-ext"/schemas/*.xml "$INSTALL_DIR/schemas/"
  glib-compile-schemas "$INSTALL_DIR/schemas/"
  rm -rf "$TMPDIR"
else
  RELEASE_URL="https://github.com/happytomatoe/voice-to-text/releases/download/$LATEST_TAG/voice-to-text@happytomatoe.com.shell-extension.zip"
  echo "Downloading: $RELEASE_URL"
  cd /tmp
  curl -LO "$RELEASE_URL"
  filename=$(basename "$RELEASE_URL")
  gnome-extensions install --force /tmp/$filename
  rm -f /tmp/$filename
fi

# --- Configure API key ---
echo ""
echo "--- API Key Configuration ---"
echo "Setting up API key..."
$VOICE_TO_TEXT_CMD setup-key
echo ""
echo "API key configured."

# Install default config (only if user has none)
CONFIG_DIR="$HOME/.config/voice-to-text"
mkdir -p "$CONFIG_DIR"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
if [ -f "$CONFIG_FILE" ]; then
  echo "Existing config found at $CONFIG_FILE; leaving it unchanged."
  echo "Run 'voice-to-text setup' to change the default provider."
else
  echo "Downloading default config..."
  curl -L -o "$CONFIG_FILE" "https://raw.githubusercontent.com/$REPO/main/config.yaml"
  if [ -f "$CONFIG_FILE" ]; then
    echo "Default config installed at $CONFIG_FILE."
    echo "Run 'voice-to-text setup' to change the default provider."
  else
    echo "WARNING: Failed to download default config."
  fi
fi

# --- Configure ydotool daemon ---
SOCKET_PATH="/run/user/$(id -u)/.ydotool_socket"
export YDOTOOL_SOCKET="$SOCKET_PATH"

# 1. Check if the socket already exists and service is running
if [ -S "$SOCKET_PATH" ] && systemctl is-active --quiet ydotool.service 2>/dev/null; then
  echo "ydotool socket already present at $SOCKET_PATH."
else
  echo "ydotool socket missing. Initializing configuration..."

  # 2. Create the system-level drop-in override directory
  sudo mkdir -p /etc/systemd/system/ydotool.service.d

  # 3. Inject the custom socket path configuration
  sudo tee /etc/systemd/system/ydotool.service.d/socket-path.conf >/dev/null <<EOF
[Unit]
After=user-runtime-dir@$(id -u).service
Requires=user-runtime-dir@$(id -u).service

[Service]
ExecStart=
ExecStart=/usr/bin/ydotoold --socket-path=$SOCKET_PATH --socket-perm=666
EOF

  # 4. Reload and restart the service
  sudo systemctl daemon-reload
  sudo systemctl restart ydotool.service
  sleep 1

  # 5. Final verification check
  if [ -S "$SOCKET_PATH" ]; then
    echo "ydotoold started successfully. Socket at $SOCKET_PATH"
    ydotool type -- "voice-to-text fixed"
  else
    echo "ERROR: Socket not found at $SOCKET_PATH"
    sudo journalctl -u ydotool.service --no-pager -n 20
    exit 1
  fi
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Python app: voice-to-text"
echo "GNOME extension: $EXT_UUID (hotkey: Super+W)"
echo ""
echo "Restart your shell or open a new terminal."
echo "Then test with: voice-to-text"
echo ""
echo "Restart GNOME Shell (Alt+F2, r, Enter on X11) or log out/in on Wayland."
