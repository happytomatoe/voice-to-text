default:
    @just --list

run *args:
    PYTHONPATH=src .venv/bin/python -m voice_to_text.__main__ {{args}}

test:
  uv run pytest -n auto
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
# Install the D-Bus service (D-Bus activation only, no systemd)
service-install:
    uv tool install -e .
    mkdir -p ~/.local/share/dbus-1/services/ ~/.local/bin/
    cp service/com.happytomatoe.VoiceToText.service ~/.local/share/dbus-1/services/
    cp service/voice-to-text-env ~/.local/bin/
    cp service/voice-to-text-dbus-wrapper ~/.local/bin/
    chmod +x ~/.local/bin/voice-to-text-env ~/.local/bin/voice-to-text-dbus-wrapper
    @echo "Service installed. D-Bus activation handles startup automatically."

# @category service
# Stop the running service (D-Bus activation will restart on next request)
service-stop:
    pkill -f voice-to-text-dbus || @echo "Service not running"

# @category service
# Run the service directly in the foreground (for debugging)
service-run:
    uv run voice-to-text-dbus

# @category service
# Show service process status
service-status:
    ps aux | grep voice-to-text-dbus | grep -v grep || @echo "Service not running"

# @category service
# Tail service logs
service-logs:
    journalctl --user | grep voice -f

# @category service
# Restart the service by stopping it (D-Bus activation restarts on next extension use)
service-restart: service-stop
    @echo "Service stopped. It will auto-start when GNOME extension requests it."

# @category service
# Reinstall from source
service-reinstall: reinstall
    @echo "Done. Service will auto-start on next extension use."

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
    # Enable extension via dconf (gnome-extensions CLI needs a running session)
    CURRENT=$(dconf read /org/gnome/shell/enabled-extensions)
    if ! echo "$CURRENT" | grep -q "$UUID"; then
      if [ -z "$CURRENT" ] || [ "$CURRENT" = "[]" ]; then
        dconf write /org/gnome/shell/enabled-extensions "['$UUID']"
      else
        dconf write /org/gnome/shell/enabled-extensions "${CURRENT%]}, '$UUID']"
      fi
    fi
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
      voice-to-text-dbus > /tmp/voice-to-text.log 2>&1 &
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
