#!/bin/bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
SERVICE_DIR="${HOME}/.config/systemd/user"
DBUS_SERVICE_DIR="${HOME}/.local/share/dbus-1/services"

mkdir -p "$INSTALL_DIR" "$SERVICE_DIR" "$DBUS_SERVICE_DIR"

# Install the Python package
uv tool install . --force

# Copy service files
cp service/voice-to-text.service "$SERVICE_DIR/"
cp service/com.happytomatoe.VoiceToText.service "$DBUS_SERVICE_DIR/"

# Reload systemd
systemctl --user daemon-reload

echo "Service installed. Enable with:"
echo "  systemctl --user enable --now voice-to-text.service"
echo ""
echo "Check status with:"
echo "  systemctl --user status voice-to-text.service"
echo ""
echo "View logs with:"
echo "  journalctl --user -u voice-to-text.service -f"
