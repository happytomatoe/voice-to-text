default:
    @just --list

run +args='':
    uv run -m voice_to_text.main {{args}}

install:
    uv pip install -e .
    # Create wrapper script that uses uv run (editable install)
    echo '#!/bin/bash' > ~/.local/bin/voice-to-text
    echo 'cd /var/home/l/git/voice-to-text' >> ~/.local/bin/voice-to-text
    echo 'exec uv run -m voice_to_text.main "$@"' >> ~/.local/bin/voice-to-text
    chmod +x ~/.local/bin/voice-to-text

uninstall:
    uv tool uninstall voice-to-text

reinstall:
        uv tool install . --force-reinstall --force

# Run a nested GNOME Shell for testing the extension
nested-shell:
    #!/usr/bin/env bash
    GNOME_VERSION=$$(gnome-shell --version | awk '{print int($$3)}')
    if [ "$$GNOME_VERSION" -ge 49 ]; then
      dbus-run-session -- gnome-shell --wayland --devkit 2>&1 | tee /tmp/gnome-shell-nested.log
    else
      MUTTER_DEBUG_NESTED=1 dbus-run-session -- gnome-shell --wayland --nested 2>&1 | tee /tmp/gnome-shell-nested.log
    fi

# Reinstall extension from gnome-ext/ and start nested shell
dev-extension:
    rm -f gnome-shell-nested.log voice-to-text.log
    ./gnome-ext/run-dev.sh --nested 2>&1 | tee gnome-shell-nested.log

# Kill running voice-to-text processes
kill:
    pkill -f "voice-to-text" || true
    pkill -f "ydotool" || true

# Reload extension: reinstall files and reset in GNOME Shell
reload-extension:
    ./gnome-ext/run-dev.sh && gnome-extensions reset voice-to-text@happytomatoe.com && gnome-extensions enable voice-to-text@happytomatoe.com

# Pack extension into a ZIP for distribution
pack-extension:
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

# Build Python wheel and sdist for release
build-python:
    uv build --out-dir dist

# Build standalone Linux binary using PyInstaller
build-binary:
    #!/usr/bin/env bash
    uv run pyinstaller \
      --name voice-to-text \
      --onefile \
      --add-data "src/voice_to_text/config.yaml:voice_to_text" \
      src/voice_to_text/main.py \
      --distpath dist \
      --clean
    echo "Binary built to dist/voice-to-text"

# Build all release artifacts: Python wheel, sdist, extension ZIP, and binary
build-release: build-python build-binary pack-extension
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


