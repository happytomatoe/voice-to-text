default:
    @just --list

# IBus Integration Commands

# Quick path for installation (simplest, creates user-local component)
ibus-install:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Installing Voxtral IBus engine (user-local)..."
    
    # Create component directory
    mkdir -p ~/.local/share/ibus/component
    
    # Copy the XML and patch the path (the hardcoded author path)
    cp src/voice_to_text/ibus/voxtral.xml ~/.local/share/ibus/component/voxtral.xml
    # Fix the exec path in the XML
    PROJECT_ROOT=$(pwd)
    sed -i "s|/var/home/l/git/voice-to-text-ibus|$PROJECT_ROOT|" ~/.local/share/ibus/component/voxtral.xml
    
    # Show what we fixed
    FIXED_PATH=$(grep '/usr/bin/python3' ~/.local/share/ibus/component/voxtral.xml)
    echo "✓ Fixed exec path to: $FIXED_PATH"
    
    # Set environment for GNOME/systemd
    mkdir -p ~/.config/environment.d
    echo 'IBUS_COMPONENT_PATH=$HOME/.local/share/ibus/component:$IBUS_COMPONENT_PATH' > ~/.config/environment.d/ibus.conf
    
    # Update ibus cache if available
    if command -v ibus > /dev/null 2>&1; then
        ibus write-cache
        ibus restart
        echo "✓ IBus cache updated and restarted"
    else
        echo "⚠️  ibus not found - please install ibus: sudo dnf install ibus"
    fi
    
    echo ""
    echo "=== Installation Complete ==="
    echo ""
    echo "Next steps for Fedora Silverblue/GNOME:"
    echo "1. Log out and log back in"
    echo "2. Settings → Keyboard → Input Sources → + → Other → Voxtral"
    echo ""
    echo "Files created:"
    ls -la ~/.local/share/ibus/component/
    ls -la ~/.config/environment.d/

# Alternative: System-wide installation (requires sudo)
ibus-install-system:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Installing Voxtral IBus engine (system-wide)..."
    
    # Create component directory with sudo
    sudo mkdir -p /usr/share/ibus/component
    
    # Fix the path in the XML before copying
    PROJECT_ROOT=$(pwd)
    sed -i "s|/var/home/l/git/voice-to-text-ibus|$PROJECT_ROOT|" src/voice_to_text/ibus/voxtral.xml
    
    # Copy to system location with sudo
    sudo cp src/voice_to_text/ibus/voxtral.xml /usr/share/ibus/component/
    
    # Set environment variable
    mkdir -p ~/.config/environment.d
    echo 'IBUS_COMPONENT_PATH=/usr/share/ibus/component:$IBUS_COMPONENT_PATH' > ~/.config/environment.d/ibus.conf
    
    echo "✓ System-wide installation complete"
    echo ""
    echo "System component: /usr/share/ibus/component/voxtral.xml"
    echo "Environment: ~/.config/environment.d/ibus.conf"

# Verify installation
ibus-verify:
    #!/usr/bin/env bash
    echo "=== Verifying IBus Installation ==="
    
    echo "Checking component files..."
    if [[ -f $HOME/.local/share/ibus/component/voxtral.xml ]]; then
        echo "✓ User component exists"
        ls -la ~/.local/share/ibus/component/
    else
        echo "✗ User component missing"
    fi
    
    if [[ -f $HOME/.config/environment.d/ibus.conf ]]; then
        echo "✓ Environment file exists"
        cat ~/.config/environment.d/ibus.conf
    else
        echo "✗ Environment file missing"
    fi
    
    echo ""
    echo "Checking environment..."
    if [[ -n "$IBUS_COMPONENT_PATH" ]]; then
        echo "✓ IBUS_COMPONENT_PATH is set: $IBUS_COMPONENT_PATH"
    else
        echo "⚠  IBUS_COMPONENT_PATH not set in current session"
        echo "  The environment.d file will take effect after login"
    fi
    
    echo ""
    echo "Checking IBus daemon..."
    if pgrep -x ibus-daemon > /dev/null 2>&1; then
        echo "✓ IBus daemon is running"
    else
        echo "✗ IBus daemon is not running"
        echo "  Start with: ibus-daemon -drx"
    fi
    
    echo ""
    echo "Checking IBus availability..."
    if command -v ibus > /dev/null 2>&1; then
        echo "✓ ibus command available"
        ibus version 2>/dev/null || echo "ibus version not available"
        
        echo ""
        echo "Checking for voxtral engine..."
        if ibus list-engine 2>/dev/null | grep -qi voxtral; then
            echo "✓ Voxtral engine found in IBus"
            ibus list-engine 2>/dev/null | grep -i voxtral
        else
            echo "✗ Voxtral engine not found in IBus"
            echo "  This may be because:"
            echo "    - IBus daemon is not running"
            echo "    - Environment variable IBUS_COMPONENT_PATH not set"
            echo "    - Need to log out and log back in after installation"
        fi
    else
        echo "✗ ibus command not found"
        echo "  Install with: sudo dnf install ibus"
    fi

# Start the Voxtral engine (for testing)
ibus-engine:
    #!/usr/bin/env bash
    echo "Starting Voxtral IBus engine..."
    echo "Note: This runs the engine for testing purposes"
    echo "The real IBus integration happens when you select it in System Settings"
    
    # Check if IBus daemon is running
    if ! pgrep -x ibus-daemon > /dev/null 2>&1; then
        echo "✗ IBus daemon is not running"
        echo "  Start with: ibus-daemon -drx"
        exit 1
    fi
    
    cd /var/home/l/git/voice-to-text-ibus
    export IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component"
    export PYTHONPATH=src
    setsid /usr/bin/python3 src/voice_to_text/ibus/engine.py --ibus > /tmp/voxtral-engine.log 2>&1 &
    echo "Engine started with PID: $!"
    echo "Log: /tmp/voxtral-engine.log"

# Bridge (runs the audio transcription bridge)
ibus-bridge:
    #!/usr/bin/env bash
    echo "Starting Voxtral bridge (requires engine to be running)..."
    cd /var/home/l/git/voice-to-text-ibus
    PYTHONPATH=src .venv/bin/python3 src/voice_to_text/ibus/bridge.py

# Combined: engine + bridge
ibus-run:
    #!/usr/bin/env bash
    echo "Starting both Voxtral IBus engine and bridge..."
    cd /var/home/l/git/voice-to-text-ibus
    PYTHONPATH=src .venv/bin/python3 scripts/voxtral_ibus.py

# Uninstall
ibus-uninstall:
    #!/usr/bin/env bash
    echo "Uninstalling Voxtral IBus engine..."
    
    # Remove files
    rm -f ~/.local/share/ibus/component/voxtral.xml
    rm -f ~/.config/environment.d/ibus.conf
    
    # Restart ibus if available
    if command -v ibus > /dev/null 2>&1; then
        ibus write-cache
        ibus restart
        echo "✓ IBus cache updated and restarted"
    fi
    
    echo "✓ Uninstall complete"

