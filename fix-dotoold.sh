#!/bin/bash
set -euo pipefail

UID_ACTUAL="${SUDO_UID:-$(id -u)}"
PIPE_PATH="/run/user/$UID_ACTUAL/dotool-pipe"

# Create the directory for the pipe
mkdir -p "$(dirname "$PIPE_PATH")" 2>/dev/null || true

# Set the environment variable for dotoold
export DOTOOL_PIPE="$PIPE_PATH"

# Create systemd user service for dotoold
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/dotoold.service <<EOF
[Unit]
Description=dotoold daemon for keyboard input
After=graphical-session.target
StartLimitBurst=3
StartLimitIntervalSec=60

[Service]
Type=simple
ExecStart=$HOME/.local/bin/dotoold-wrapper
Environment=DOTOOL_PIPE=$PIPE_PATH
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now dotoold.service
sleep 1

if [ -p "$PIPE_PATH" ] && systemctl --user is-active --quiet dotoold.service; then
    echo "✅ dotoold is running. Pipe at $PIPE_PATH"
    echo "type voice-to-text fixed" | DOTOOL_PIPE="$PIPE_PATH" dotoolc
else
    echo "❌ Pipe not found at $PIPE_PATH"
    journalctl --user -u dotoold.service --no-pager -n 20
    exit 1
fi
