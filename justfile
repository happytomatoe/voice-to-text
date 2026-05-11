default:
    @just --list

run:
    PYTHONPATH=src .venv/bin/python -m voice_to_text.main

install:
    uv pip install -e .

uninstall:
    .venv/bin/python -m pip uninstall groq-voice -y

setup-global-hotkey:
    #!/usr/bin/env bash
    KEYBINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voice-to-text"
    dconf write "$KEYBINDING_PATH/name" "'voice-to-text'"
    dconf write "$KEYBINDING_PATH/command" "'alacritty -e bash -c voice-to-text'"
    dconf write "$KEYBINDING_PATH/binding" "'<Super>q'"
    CURRENT=$(dconf read /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings 2>/dev/null || echo "[]")
    if echo "$CURRENT" | grep -q "$KEYBINDING_PATH"; then echo "Hotkey already configured"; elif [ "$CURRENT" = "@as []" ] || [ "$CURRENT" = "[]" ]; then dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings "['$KEYBINDING_PATH/']"; else dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings "[$CURRENT, '$KEYBINDING_PATH/']"; fi
    echo "Global hotkey Super+q configured for voice-to-text"

ibus-start:
    PYTHONPATH=src .venv/bin/python ibus-engine-cloud &

ibus-test:
    @echo "Testing IBus Cloud Speech engine..."
    @echo "1. Open a text field: gedit"
    @echo "2. Press Super+Space to switch input method"
    @echo "3. Select 'Cloud Speech'"
    @echo "4. Press Super+q to start recording"
    @echo ""
    @echo "Or run: ibus engine com.cloud-voice.CloudSpeech"

ibus-switch:
    ibus engine com.cloud-voice.CloudSpeech

ibus-log:
    tail -f /tmp/ibus-cloud.log

install-daemon:
    uv pip install -e .
    mkdir -p ~/.config/systemd/user/
    cp service/voice-daemon.service ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable voice-daemon.service
    systemctl --user start voice-daemon.service

uninstall-daemon:
    systemctl --user stop voice-daemon.service
    systemctl --user disable voice-daemon.service
    rm ~/.config/systemd/user/voice-daemon.service

run-daemon:
    voice-daemon

kill-daemon:
    pkill -f "voice-daemon" || echo "No daemon running"


