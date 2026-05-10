default:
    @just --list

run:
    PYTHONPATH=src .venv/bin/python -m voice_to_text.main

install:
    python -m pip install . --user -q --upgrade

uninstall:
    .venv/bin/python -m pip uninstall groq-voice -y

setup-global-hotkey:
    #!/usr/bin/env bash
    KEYBINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voice-to-text"
    dconf write "$KEYBINDING_PATH/name" "'voice-to-text'"
    dconf write "$KEYBINDING_PATH/command" "'alacritty -e bash -c voice-to-text'"
    dconf write "$KEYBINDING_PATH/binding" "'<Super>v'"
    CURRENT=$(dconf read /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings 2>/dev/null || echo "[]")
    if echo "$CURRENT" | grep -q "$KEYBINDING_PATH"; then echo "Hotkey already configured"; elif [ "$CURRENT" = "@as []" ] || [ "$CURRENT" = "[]" ]; then dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings "['$KEYBINDING_PATH/']"; else dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings "[$CURRENT, '$KEYBINDING_PATH/']"; fi
    echo "Global hotkey Super+v configured for voice-to-text"


