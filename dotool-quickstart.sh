#!/bin/bash

# dotool-quickstart.sh
# FULL AUTOMATION: Installs dotool (via Toolbox or Container) and sets up the persistent daemon on Fedora Silverblue.

set -e

echo "🚀 Starting FULL dotool automation setup..."

# 1. Prerequisites Check (Input Group)
echo "🔍 Checking prerequisites..."
if ! getent group input > /dev/null; then
    echo "⚠️  The 'input' group is missing from your system."
    echo "This group is required to access /dev/uinput."
    echo ""
    echo "Please run the following commands as root on your host:"
    echo "  sudo groupadd -r input"
    echo "  sudo usermod -aG input $USER"
    echo "  sudo reboot"
    echo ""
    echo "After rebooting, please run this script again."
    exit 1
fi

if ! id -nG | grep -qw input; then
    echo "⚠️  Your current user is not a member of the 'input' group."
    echo "Please run: sudo usermod -aG input $USER"
    echo "Then log out and back in, or reboot, before running this script again."
    exit 1
fi

# 2. Binary Installation
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

if [[ -f "$BIN_DIR/dotool" && -f "$BIN_DIR/dotoolc" && -f "$BIN_DIR/dotoold" ]]; then
    echo "✅ dotool binaries already present in $BIN_DIR."
else
    echo "📦 Binaries not found. Attempting automated build..."
    
    INSTALL_SUCCESS=false
    
    # Attempt 1: Toolbox (as recommended in the original prompt)
    if command -v toolbox > /dev/null 2>&1; then
        echo "🛠️  Attempting build via Toolbox..."
        TOOLBOX_NAME="dotool-build"
        
        # Create toolbox if not exists
        if ! toolbox list | grep -q "$TOOLBOX_NAME"; then
            toolbox create -c "$TOOLBOX_NAME" > /dev/null 2>&1 || true
        fi
        
        # Run build sequence exactly as recommended
        if toolbox run -c "$TOOLBOX_NAME" sh -c "
            sudo dnf install -y gcc make libev-devel systemd-devel git
            rm -rf /tmp/dotool-build
            git clone https://git.sr.ht/~geb/dotool /tmp/dotool-build
            cd /tmp/dotool-build && make
            cp dotool dotoolc dotoold $HOME/.local/bin/
        "; then
            echo "✅ dotool binaries successfully built via Toolbox."
            INSTALL_SUCCESS=true
        else
            echo "⚠️  Toolbox build failed."
        fi
    fi
    
    # Attempt 2: Fallback to Podman/Docker if Toolbox failed or is missing
    if [ "$INSTALL_SUCCESS" = false ]; then
        CONTAINER_BIN=""
        if command -v podman > /dev/null 2>&1; then
            CONTAINER_BIN="podman"
        elif command -v docker > /dev/null 2>&1; then
            CONTAINER_BIN="docker"
        fi
        
        if [ -n "$CONTAINER_BIN" ]; then
            echo "🐳 Attempting fallback build via $CONTAINER_BIN..."
            if $CONTAINER_BIN run --rm \
                -v "$BIN_DIR:/out:Z" \
                golang:latest sh -c "
                    set -e; apt-get update && apt-get install -y git libev-dev libxkbcommon-dev
                    git clone https://git.sr.ht/~geb/dotool /tmp/dotool
                    cd /tmp/dotool
                    go build -o /out/dotool .
                    cat dotoolc > /out/dotoolc
                    cat dotoold > /out/dotoold
                "; then
                echo "✅ dotool binaries successfully built via $CONTAINER_BIN."
                INSTALL_SUCCESS=true
            else
                echo "⚠️  Container build failed."
            fi
        fi
    fi
    
    if [ "$INSTALL_SUCCESS" = false ]; then
        echo ""
        echo "❌ Failed to automate the build of dotool."
        echo "On Fedora Silverblue, it is recommended to build dotool inside a Toolbox container."
        echo ""
        echo "Run the following in a toolbox:"
        echo "  sudo dnf install -y gcc make libev-devel systemd-devel"
        echo "  git clone https://git.sr.ht/~geb/dotool"
        echo "  cd dotool && make"
        echo "  cp dotool dotoolc dotoold $HOME/.local/bin/"
        echo ""
        read -p "Do you want to continue with the daemon setup anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Exiting. Please install the binaries first."
            exit 1
        fi
    fi
fi

# Ensure binaries are executable
chmod +x "$BIN_DIR/dotool" "$BIN_DIR/dotoolc" "$BIN_DIR/dotoold" 2>/dev/null || true

# 3. Create dotoold-wrapper
WRAPPER_PATH="$BIN_DIR/dotoold-wrapper"
echo "⚙️ Creating dotoold-wrapper at $WRAPPER_PATH..."
cat > "$WRAPPER_PATH" << EOF
#!/bin/bash
# Wrapper to ensure proper group membership for dotoold
exec sg input -c "$BIN_DIR/dotoold \$@"
EOF
chmod +x "$WRAPPER_PATH"

# 4. Create systemd user service
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
SERVICE_FILE="$SERVICE_DIR/dotoold.service"

echo "⚙️ Creating systemd user service at $SERVICE_FILE..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=dotoold daemon for keyboard input
After=graphical-session.target

[Service]
Type=simple
ExecStart=$WRAPPER_PATH
Restart=always
RestartSec=2
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# 5. Enable and Start Daemon
echo "⚡ Enabling and starting dotoold daemon..."
systemctl --user daemon-reload
systemctl --user enable dotoold.service
systemctl --user restart dotoold.service

# 6. Enable User Linger
echo "🕒 Enabling user linger for boot-time persistence..."
loginctl enable-linger "$USER"

# 7. Final Verification
echo "🧪 Verifying installation..."
sleep 2
if systemctl --user is-active --quiet dotoold.service; then
    echo "✅ dotoold service is active."
else
    echo "❌ dotoold service failed to start. Check 'journalctl --user -u dotoold.service'."
    exit 1
fi

# Test dotoolc
if echo "type Build Successful" | "$BIN_DIR/dotoolc" > /dev/null 2>&1; then
    echo "✅ dotoolc communication verified!"
else
    echo "⚠️ dotoolc failed to communicate with the daemon."
    echo "This might be due to missing group membership. Try logging out and back in."
fi

echo ""
echo "🎉 dotool setup complete!"
echo "You can now use: echo \"type Hello World\" | dotoolc"
