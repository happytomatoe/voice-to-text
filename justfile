default:
    @just --list

run:
    PYTHONPATH=src .venv/bin/python -m voice_to_text.main

install:
    uv tool install .

uninstall:
    .venv/bin/python -m pip uninstall groq-voice -y

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
    ./gnome-ext/run-dev.sh --nested 2>&1 | tee /tmp/gnome-shell-nested.log

# Reload extension: reinstall files and reset in GNOME Shell
reload-extension:
    ./gnome-ext/run-dev.sh 2>/dev/null; gnome-extensions reset voice-to-text@happytomatoe.com

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


