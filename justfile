default:
    @just --list

run:
    PYTHONPATH=src .venv/bin/python -m voice_to_text.main

install: build-binary
    uv tool uninstall voice-to-text 2>/dev/null || true
    rm -f ~/.local/bin/voice-to-text
    mkdir -p ~/.local/bin
    cp dist/voice-to-text ~/.local/bin/voice-to-text
    chmod +x ~/.local/bin/voice-to-text

uninstall:
    rm -f ~/.local/bin/voice-to-text
    uv tool uninstall voice-to-text 2>/dev/null || true

# Rebuild & install Python binary (skips PyInstaller if source hash matches)
reinstall:
    #!/usr/bin/env bash
    set -euo pipefail
    SOURCE_HASH=$( (find src/voice_to_text -name '*.py' ! -name '_build_info.py' -type f; echo "voice-to-text.spec") | xargs sha256sum | sort | sha256sum | cut -d' ' -f1)
    BINARY="$HOME/.local/bin/voice-to-text"
    if [ -x "$BINARY" ]; then
        EMBEDDED_HASH=$("$BINARY" --source-hash 2>/dev/null || echo "")
        if [ "$EMBEDDED_HASH" = "$SOURCE_HASH" ]; then
            echo "Binary up to date (hash $SOURCE_HASH)"
            SKIP_BUILD=1
        else
            echo "Binary outdated (embedded ${EMBEDDED_HASH:-none} vs source $SOURCE_HASH), rebuilding..."
        fi
    else
        echo "No binary found at $BINARY, building..."
    fi
    if [ -z "${SKIP_BUILD:-}" ]; then
        printf 'SOURCE_HASH = "%s"\n' "$SOURCE_HASH" > src/voice_to_text/_build_info.py
        uv run pyinstaller voice-to-text.spec
        uv tool uninstall voice-to-text 2>/dev/null || true
        rm -f "$BINARY"
        mkdir -p "$(dirname "$BINARY")"
        cp dist/voice-to-text "$BINARY"
        chmod +x "$BINARY"
        echo "Binary installed to $BINARY"
    fi

build-python:
    uv build --out-dir dist

build-binary:
    #!/usr/bin/env bash
    set -e
    SOURCE_HASH=$( (find src/voice_to_text -name '*.py' ! -name '_build_info.py' -type f; echo "voice-to-text.spec") | xargs sha256sum | sort | sha256sum | cut -d' ' -f1)
    printf 'SOURCE_HASH = "%s"\n' "$SOURCE_HASH" > src/voice_to_text/_build_info.py
    uv run pyinstaller voice-to-text.spec
    echo "Binary built to dist/voice-to-text"

build-release: build-python build-binary gnome-ext-pack
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
# Rebuild binary if stale, install extension, then start a nested GNOME Shell
gnome-ext-dev: reinstall gnome-ext-install
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "${TOOLBOX_PATH:-}" ] || [ "${container:-}" = "oci" ]; then
        echo "Error: Cannot start a development GNOME Shell from within a toolbox container. Run this command on the host system." >&2
        exit 1
    fi
    UUID="voice-to-text@happytomatoe.com"
    gnome-extensions enable "$UUID" 2>/dev/null || true
    GNOME_VERSION=$(gnome-shell --version | awk '{print int($3)}')
    if [ "$GNOME_VERSION" -ge 49 ]; then
      dbus-run-session -- gnome-shell --wayland --devkit 2>&1 | tee /tmp/gnome-shell-nested.log
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
