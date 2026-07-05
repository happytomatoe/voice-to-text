#!/usr/bin/env bash
set -euo pipefail
REPO="happytomatoe/voice-to-text"
EXT_UUID="voice-to-text@happytomatoe.com"
INSTALL_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
SERVICE_DIR="$HOME/.config/systemd/user"
DBUS_SERVICE_DIR="$HOME/.local/share/dbus-1/services"

# --- Helper: check if a command is available ---
command_exists() {
  command -v "$1" &>/dev/null
}

# --- Detect OS ---
if command_exists rpm-ostree; then
  PKG_MGR="rpm-ostree"
elif command_exists dnf; then
  PKG_MGR="dnf"
elif command_exists pacman; then
  PKG_MGR="pacman"
elif command_exists apt; then
  PKG_MGR="apt"
else
  echo "ERROR: Unsupported package manager. Supported: rpm-ostree, dnf, pacman, apt"
  exit 1
fi

echo "Detected package manager: $PKG_MGR"
echo ""

# --- Helper: install a package if not already present ---
install_pkg() {
  local pkg="$1"
  if command_exists "$pkg"; then
    echo "  $pkg already installed, skipping."
    return 0
  fi
  case "$PKG_MGR" in
  apt)
    if dpkg -s "$pkg" &>/dev/null; then
      echo "  $pkg already installed, skipping."
      return 0
    fi
    ;;
  dnf | rpm-ostree)
    if rpm -q "$pkg" &>/dev/null; then
      echo "  $pkg already installed, skipping."
      return 0
    fi
    ;;
  pacman)
    if pacman -Qi "$pkg" &>/dev/null; then
      echo "  $pkg already installed, skipping."
      return 0
    fi
    ;;
  esac
  echo "  Installing $pkg..."
  case "$PKG_MGR" in
  rpm-ostree)
    sudo rpm-ostree install -y "$pkg" || true
    ;;
  dnf)
    sudo dnf install -y "$pkg" || true
    ;;
  pacman)
    sudo pacman -S --noconfirm "$pkg" || true
    ;;
  apt)
    sudo apt install -y "$pkg" || true
    ;;
  esac
}

# --- Install prerequisites ---
echo "Installing prerequisites..."
case "$PKG_MGR" in
rpm-ostree)
  install_pkg dotool
  install_pkg unzip
  install_pkg curl
  install_pkg libsecret
  echo ""
  echo "NOTE: rpm-ostree changes require a reboot to take effect."
  echo "      If this is the first time layering packages, reboot before continuing."
  ;;
dnf)
  install_pkg dotool
  install_pkg unzip
  install_pkg curl
  install_pkg libsecret
  ;;
pacman)
  install_pkg dotool
  install_pkg unzip
  install_pkg curl
  install_pkg libsecret
  ;;
apt)
  install_pkg dotool
  install_pkg unzip
  install_pkg curl
  install_pkg libsecret-1-dev
  install_pkg libsecret-tools
  ;;
esac

# --- Install uv if not present ---
if ! command_exists uv; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  if ! command_exists uv; then
    echo "ERROR: Failed to install uv."
    exit 1
  fi
  echo "uv installed."
else
  echo "uv already installed, skipping."
fi

# --- Install Python D-Bus service ---
echo ""
echo "--- Installing Python D-Bus service ---"
echo "Fetching latest release tag..."
LATEST_TAG=$(
  git ls-remote --tags --sort=-v:refname "https://github.com/$REPO.git" |
    awk -F'/' '$NF !~ /\^\{\}$/ { print $NF; exit }'
)
if [ -z "$LATEST_TAG" ]; then
  echo "WARNING: No releases found for $REPO; installing from source."
  REPO_DIR=$(mktemp -d)
  git clone --depth 1 "https://github.com/$REPO.git" "$REPO_DIR"
  uv tool install "$REPO_DIR" --force
  rm -rf "$REPO_DIR"
else
  echo "Installing version $LATEST_TAG..."
  uv tool install "git+https://github.com/$REPO.git@$LATEST_TAG" --force
fi
echo "Python D-Bus service installed (voice-to-text-dbus)."

# --- Install D-Bus service files ---
echo ""
echo "--- Installing D-Bus service files ---"
mkdir -p "$SERVICE_DIR" "$DBUS_SERVICE_DIR"

# Copy service files from the installed package
if [ -d "service" ]; then
  cp service/voice-to-text.service "$SERVICE_DIR/"
  cp service/com.happytomatoe.VoiceToText.service "$DBUS_SERVICE_DIR/"
else
  # Try to find them relative to the installed tool
  TOOL_PATH=$(command -v voice-to-text-dbus || echo "")
  if [ -n "$TOOL_PATH" ]; then
    TOOL_DIR=$(dirname "$(dirname "$TOOL_PATH")")
    SHARE_DIR="$TOOL_DIR/share/voice-to-text"
    if [ -f "$SHARE_DIR/voice-to-text.service" ]; then
      cp "$SHARE_DIR/voice-to-text.service" "$SERVICE_DIR/"
      cp "$SHARE_DIR/com.happytomatoe.VoiceToText.service" "$DBUS_SERVICE_DIR/"
    else
      echo "WARNING: Could not find service files. You may need to install them manually."
    fi
  fi
fi

systemctl --user daemon-reload
systemctl --user enable --now voice-to-text.service
echo "D-Bus service enabled."
echo "  Status: systemctl --user status voice-to-text.service"
echo "  Logs:   journalctl --user -u voice-to-text.service -f"

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
  RELEASE_URL="https://github.com/$REPO/releases/download/$LATEST_TAG/$EXT_UUID.shell-extension.zip"
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
if command_exists secret-tool; then
  echo "Setting up API key..."
  echo "Run the following to configure your API key:"
  echo "  secret-tool store --label='Voice-to-Text API Key' com.happytomatoe.VoiceToText api_key"
  echo ""
  echo "Or set the environment variable in your shell profile:"
  echo "  export VOXTRAL_API_KEY=<your-key>"
  echo "  # Or for systemd service, create a drop-in:"
  echo "  # mkdir -p ~/.config/systemd/user/voice-to-text.service.d"
  echo "  # echo '[Service]\\nEnvironment=VOXTRAL_API_KEY=<your-key>' > ~/.config/systemd/user/voice-to-text.service.d/env.conf"
  echo "  # systemctl --user daemon-reload && systemctl --user restart voice-to-text.service"
else
  echo "Install libsecret-tools for secure key storage:"
  echo "  sudo dnf install libsecret  # or equivalent"
  echo "Then set API keys via environment variables:"
  echo "  export VOXTRAL_API_KEY=<your-key>"
  echo "  # Or for systemd service, create a drop-in:"
  echo "  # mkdir -p ~/.config/systemd/user/voice-to-text.service.d"
  echo "  # echo '[Service]\\nEnvironment=VOXTRAL_API_KEY=<your-key>' > ~/.config/systemd/user/voice-to-text.service.d/env.conf"
  echo "  # systemctl --user daemon-reload && systemctl --user restart voice-to-text.service"
fi
echo ""

# Install default config (only if user has none)
CONFIG_DIR="$HOME/.config/voice-to-text"
mkdir -p "$CONFIG_DIR"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
if [ -f "$CONFIG_FILE" ]; then
  echo "Existing config found at $CONFIG_FILE; leaving it unchanged."
else
  echo "Downloading default config..."
  curl -L -o "$CONFIG_FILE" "https://raw.githubusercontent.com/$REPO/main/config.yaml" || true
  if [ -f "$CONFIG_FILE" ]; then
    echo "Default config installed at $CONFIG_FILE."
  else
    echo "WARNING: Failed to download default config."
  fi
fi

# --- Configure dotool daemon (user service) ---
PIPE_PATH="/run/user/$(id -u)/dotool-pipe"

# Create dotoold-wrapper if it doesn't exist
WRAPPER_PATH="$HOME/.local/bin/dotoold-wrapper"
if [ ! -f "$WRAPPER_PATH" ]; then
  echo "Creating dotoold-wrapper..."
  mkdir -p "$HOME/.local/bin"
  cat > "$WRAPPER_PATH" << 'WRAPPER_EOF'
#!/bin/bash
# Wrapper to ensure proper group membership for dotoold
exec sg input -c "PATH=$HOME/.local/bin:\$PATH $HOME/.local/bin/dotoold \$@"
WRAPPER_EOF
  chmod +x "$WRAPPER_PATH"
  echo "dotoold-wrapper created at $WRAPPER_PATH"
else
  echo "dotoold-wrapper already exists, skipping."
fi

if [ -p "$PIPE_PATH" ] && systemctl --user is-active --quiet dotoold.service 2>/dev/null; then
  echo "dotoold pipe already present at $PIPE_PATH."
else
  echo "dotoold pipe missing. Creating user service..."

  mkdir -p ~/.config/systemd/user

  cat > ~/.config/systemd/user/dotoold.service <<EOF
[Unit]
Description=dotoold daemon for keyboard input
After=graphical-session.target

[Service]
Type=simple
ExecStart=$HOME/.local/bin/dotoold-wrapper
Environment=DOTOOL_PIPE=$PIPE_PATH
Restart=always
RestartSec=2
StartLimitBurst=5
StartLimitIntervalSec=60
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now dotoold.service
  sleep 1

  if [ -p "$PIPE_PATH" ]; then
    echo "dotoold started successfully. Pipe at $PIPE_PATH"
    echo "type voice-to-text service installed" | DOTOOL_PIPE="$PIPE_PATH" dotoolc
  else
    echo "ERROR: Pipe not found at $PIPE_PATH"
    journalctl --user -u dotoold.service --no-pager -n 20
    exit 1
  fi
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "The voice-to-text D-Bus service is now installed."
echo ""
echo "Next steps:"
echo "  1. Restart GNOME Shell (Alt+F2, r, Enter on X11) or log out/in on Wayland"
echo "  2. Set your API keys in environment variables or via secret-tool"
echo "  3. Use the hotkey (default: Super+Q) to start/stop recording"
echo ""
echo "Useful commands:"
echo "  systemctl --user status voice-to-text.service   # Service status"
echo "  journalctl --user -u voice-to-text.service -f   # Service logs"
echo "  gnome-extensions prefs $EXT_UUID                # Extension settings"
