#!/bin/bash
set -euo pipefail

UID_ACTUAL="${SUDO_UID:-$(id -u)}"
PIPE_PATH="/run/user/$UID_ACTUAL/.dotool_pipe"

# Create the directory for the pipe
sudo mkdir -p "$(dirname "$PIPE_PATH")"
sudo chown "$UID_ACTUAL:$UID_ACTUAL" "$(dirname "$PIPE_PATH")" 2>/dev/null || true

# Set the environment variable for dotoold
export DOTOOL_PIPE="$PIPE_PATH"

# Create systemd service for dotoold
sudo tee /etc/systemd/system/dotool.service.d/override.conf > /dev/null <<EOF
[Unit]
After=user-runtime-dir@$UID_ACTUAL.service
Requires=user-runtime-dir@$UID_ACTUAL.service

[Service]
ExecStart=
ExecStart=/usr/bin/dotoold
Environment=DOTOOL_PIPE=%t/dotool_pipe
EOF

sudo systemctl daemon-reload
sudo systemctl restart dotool.service
sleep 1

if [ -p "$PIPE_PATH" ]; then
    echo "✅ dotoold is running. Pipe at $PIPE_PATH"
    echo "type voice-to-text fixed" | dotoolc
else
    echo "❌ Pipe not found at $PIPE_PATH"
    sudo journalctl -u dotool.service --no-pager -n 20
    exit 1
fi