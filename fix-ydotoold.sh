#!/bin/bash
set -euo pipefail

SOCKET_PATH="/run/user/$(id -u)/.ydotool_socket"

sudo mkdir -p /etc/systemd/system/ydotool.service.d
sudo tee /etc/systemd/system/ydotool.service.d/socket-path.conf > /dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/ydotoold --socket-path=$SOCKET_PATH --socket-perm=666
EOF

sudo systemctl daemon-reload
sudo systemctl restart ydotool.service
sleep 1

if [ -S "$SOCKET_PATH" ]; then
    echo "✅ ydotoold is running. Socket at $SOCKET_PATH"
    ydotool type -- "voice-to-text fixed"
else
    echo "❌ Socket not found at $SOCKET_PATH"
    sudo journalctl -u ydotool.service --no-pager -n 20
    exit 1
fi
