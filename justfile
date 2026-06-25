default:
    @just --list

run *args:
    PYTHONPATH=src .venv/bin/python -m voice_to_text.main {{args}}

# Benchmark: record 10s of audio, test all providers 3x each
benchmark:
    PYTHONPATH=src .venv/bin/python -m voice_to_text.main benchmark --duration 10

# Benchmark: generate synthetic audio then test providers (no microphone needed)
benchmark-gen:
    python scripts/generate_test_audio.py --duration 12 --output /tmp/vtt-bench.wav
    PYTHONPATH=src .venv/bin/python -m voice_to_text.main benchmark --audio-file /tmp/vtt-bench.wav --runs 3

# Benchmark: test specific providers with an audio file
benchmark-file path runs="3":
    PYTHONPATH=src .venv/bin/python -m voice_to_text.main benchmark --audio-file {{path}} --runs {{runs}}

install:
    uv tool install -e .

uninstall:
    rm -f ~/.local/bin/voice-to-text
    uv tool uninstall voice-to-text 2>/dev/null || true

# Reinstall Python package from source
reinstall:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Reinstalling voice-to-text from source..."
    uv tool install -e . --force
    echo "voice-to-text reinstalled from source"

build-python:
    uv build --out-dir dist

build-release: build-python gnome-ext-pack
    echo "All release artifacts built in dist/"
    ls -la dist/

setup-global-hotkey:
    #!/usr/bin/env bash
    KEYBINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voice-to-text"
    dconf write "$KEYBINDING_PATH/name" "'voice-to-text'"
    dconf write "$KEYBINDING_PATH/command" "'alacritty -e bash -l -c voice-to-text'"
    dconf write "$KEYBINDING_PATH/binding" "'<Super>q'"
    CURRENT=$(dconf read /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings 2>/dev/null)
    if [ -z "$CURRENT" ] || [ "$CURRENT" = "@as []" ]; then
        dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings "['$KEYBINDING_PATH/']"
    elif echo "$CURRENT" | grep -q "$KEYBINDING_PATH"; then
        echo "Hotkey already configured"
    else
        dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings "${CURRENT%]}, '$KEYBINDING_PATH/']"
    fi
    echo "Global hotkey Super+q configured for voice-to-text"

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
      dbus-run-session -- gnome-shell --wayland --devkit  2>&1 | tee /tmp/gnome-shell-nested.log
    else
      MUTTER_DEBUG_NESTED=1 dbus-run-session -- gnome-shell --wayland --nested 2>&1 | tee /tmp/gnome-shell-nested.log
    fi
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

# -------------------------------------------
# IBus Integration Commands
# -------------------------------------------

# Install IBus component (register the Voxtral engine with IBus)
ibus-install:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Installing Voxtral IBus engine..."
    
    # Create user component directory
    mkdir -p ~/.config/ibus/component/
    cp src/voice_to_text/ibus/voxtral.xml ~/.config/ibus/component/
    
    # Try system directory (may fail if read-only, e.g. on Silverblue)
    sudo cp src/voice_to_text/ibus/voxtral.xml /usr/share/ibus/component/ 2>/dev/null || true
    
    # Set environment variable for user directory (required on Silverblue)
    echo 'export IBUS_COMPONENT_PATH="$HOME/.config/ibus/component:$IBUS_COMPONENT_PATH"' >> ~/.bashrc 2>/dev/null || true
    echo 'export IBUS_COMPONENT_PATH="$HOME/.config/ibus/component:$IBUS_COMPONENT_PATH"' >> ~/.zshrc 2>/dev/null || true
    
    # Update IBus cache
    ibus write-cache
    
    echo "Voxtral IBus engine installed!"
    echo ""
    echo "IMPORTANT: On Fedora Silverblue or other immutable systems:"
    echo "  1. Log out and back in to apply the IBUS_COMPONENT_PATH environment variable"
    echo "  2. Run: ibus write-cache && ibus restart"
    echo ""
    echo "Then add Voxtral as an input source:"
    echo "  Settings → Keyboard → Input Sources → + → Other → Voxtral"

# Uninstall IBus component
ibus-uninstall:
    #!/usr/bin/env bash
    echo "Uninstalling Voxtral IBus engine..."
    rm -f ~/.local/share/ibus/component/voxtral.xml
    ibus write-cache
    echo "Voxtral IBus engine uninstalled!"

# Start the IBus engine only (for debugging)
ibus-engine:
    PYTHONPATH=src /usr/bin/python3 src/voice_to_text/ibus/engine.py

# Start the bridge only (requires engine to be running)
ibus-bridge:
    PYTHONPATH=src .venv/bin/python3 src/voice_to_text/ibus/bridge.py

# Start both engine and bridge
ibus-run:
    PYTHONPATH=src .venv/bin/python3 scripts/voxtral_ibus.py

# Test that the engine can be imported
ibus-test:
    PYTHONPATH=src /usr/bin/python3 -c "from voice_to_text.ibus.engine import VoxtralEngine; print('Engine imports OK')"
