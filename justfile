default:
    @just --list

run *args:
    PYTHONPATH=src .venv/bin/python -m voice_to_text.__main__ {{args}}

# Benchmark: record 10s of audio, test all providers 3x each
benchmark:
    echo "Benchmarking moved to service; use the old CLI for now:"
    echo "  PYTHONPATH=src .venv/bin/python -c 'import asyncio; from voice_to_text.providers import get_batch_provider; ...'"

install:
    uv tool install -e .

uninstall:
    rm -f ~/.local/bin/voice-to-text-dbus
    uv tool uninstall voice-to-text 2>/dev/null || true

# Reinstall Python package from source
reinstall:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Reinstalling voice-to-text from source..."
    uv tool install -e . --force
    echo "voice-to-text-dbus reinstalled from source"

build-python:
    uv build --out-dir dist

# @category service
# Install the D-Bus service (systemd unit + dbus activation)
service-install:
    uv tool install -e .
    mkdir -p ~/.config/systemd/user ~/.local/share/dbus-1/services/
    cp service/voice-to-text.service ~/.config/systemd/user/
    cp service/com.happytomatoe.VoiceToText.service ~/.local/share/dbus-1/services/
    systemctl --user daemon-reload
    systemctl --user enable --now voice-to-text.service

# @category service
# Start the systemd unit (activate after install or manual stop)
service-start:
    systemctl --user start voice-to-text.service

# @category service
# Run the service directly in the foreground (for debugging)
service-run:
    uv run voice-to-text-dbus

# @category service
# Show service status
service-status:
    systemctl --user status voice-to-text.service

# @category service
# Tail service logs
service-logs:
    journalctl --user -u voice-to-text.service -f

# @category service
# Stop the service
service-stop:
    systemctl --user stop voice-to-text.service

# @category service
# Restart the service
service-restart:
    systemctl --user restart voice-to-text.service

# @category service
# Reinstall from source and restart (iterative dev cycle)
service-reinstall:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Reinstalling voice-to-text from source..."
    uv tool install -e . --force
    echo "Restarting service..."
    systemctl --user restart voice-to-text.service || {
        echo "Note: service not running yet — use 'just service-start' or 'just service-run'"
    }
    echo "Done. Tail logs with: just service-logs"

# @category gnome-ext
# Install extension, then start a nested GNOME Shell
gnome-ext-dev: reinstall gnome-ext-install
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "${TOOLBOX_PATH:-}" ] || [ "${container:-}" = "oci" ]; then
        echo "Error: Cannot start a development GNOME Shell from within a toolbox container. Run this command on the host system." >&2
        exit 1
    fi
    echo "" > /tmp/gnome-shell-nested.log
    echo "" > /tmp/voice-to-text.log
    if ! rpm -q mutter-devkit &>/dev/null; then
        echo "mutter-devkit not installed, installing..."
        if command -v rpm-ostree &>/dev/null; then
            sudo rpm-ostree install mutter-devkit
            echo "mutter-devkit was staged via rpm-ostree. Reboot, then rerun 'just gnome-ext-dev'." >&2
            exit 1
        else
            sudo dnf install -y mutter-devkit
        fi
    fi
    UUID="voice-to-text@happytomatoe.com"
    gnome-extensions enable "$UUID" 2>/dev/null || true
    GNOME_VERSION=$(gnome-shell --version | awk '{print int($3)}')
    if [ "$GNOME_VERSION" -ge 49 ]; then
      DEVKIT_FLAG=--devkit
      export MUTTER_DEBUG_NESTED=
    else
      DEVKIT_FLAG=--nested
      export MUTTER_DEBUG_NESTED=1
    fi

    # Start the D-Bus service inside the isolated session bus so the
    # GNOME extension can find and call it on real hardware.
    # Trap EXIT/INT/TERM to kill the background service when the shell exits,
    # otherwise the orphaned service keeps the microphone open.
    dbus-run-session -- sh -c "
      voice-to-text-dbus 2>&1 | tee -a /tmp/voice-to-text.log &
      DBUS_PID=\$!
      sleep 1
      trap 'kill \$DBUS_PID 2>/dev/null || true' EXIT INT TERM
      gnome-shell --wayland $DEVKIT_FLAG
    " 2>&1 | tee /tmp/gnome-shell-nested.log

# Install extension files directly (no nested shell)
gnome-ext-install:
    #!/usr/bin/env bash
    UUID="voice-to-text@happytomatoe.com"
    DEST=$HOME/.local/share/gnome-shell/extensions/$UUID
    mkdir -p "$DEST/schemas"
    cp gnome-ext/*.js gnome-ext/*.json gnome-ext/*.css "$DEST/" 2>/dev/null || true
    cp gnome-ext/schemas/*.xml "$DEST/schemas/"
    glib-compile-schemas "$DEST/schemas/"
    echo "Extension installed to $DEST"

# Uninstall extension by removing it from the extensions directory
gnome-ext-uninstall:
    rm -rf ~/.local/share/gnome-shell/extensions/voice-to-text@happytomatoe.com
    echo "Extension uninstalled"

# Reinstall files and reset in GNOME Shell
gnome-ext-reload:
    ./gnome-ext/run-dev.sh && gnome-extensions reset voice-to-text@happytomatoe.com && gnome-extensions enable voice-to-text@happytomatoe.com

# Pack extension into a ZIP for distribution
gnome-ext-pack:
    #!/usr/bin/env bash
    UUID="voice-to-text@happytomatoe.com"
    SRC="gnome-ext"
    rm -rf "dist/$UUID"
    mkdir -p "dist/$UUID/schemas"
    cp "$SRC"/*.js "$SRC"/*.json "$SRC"/*.css "dist/$UUID/"
    cp "$SRC"/schemas/*.xml "dist/$UUID/schemas/"
    glib-compile-schemas "dist/$UUID/schemas/"
    cd dist && zip -r "$UUID.shell-extension.zip" "$UUID"
    echo "Extension packed to dist/$UUID.shell-extension.zip"
