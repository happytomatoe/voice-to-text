#!/bin/bash

set -x  # Enable debug output

set -e
echo "=== Voxtral IBus Engine Installation ==="

echo "1. Creating IBus component directory..."
COMPONENT_DIR="$HOME/.local/share/ibus/component"
mkdir -p "$COMPONENT_DIR"

echo "2. Installing and fixing the XML component file..."
# Copy the voxtral.xml file from src to component directory
cp "src/voice_to_text/ibus/voxtral.xml" "$COMPONENT_DIR/voxtral.xml"

# Fix the path in the XML file
ORIGINAL_PATH="/var/home/l/git/voice-to-text-ibus"
NEW_PATH="$(pwd)"
sed -i "s|$ORIGINAL_PATH|$NEW_PATH|" "$COMPONENT_DIR/voxtral.xml"

# Verify the fix
EXEC_PATH=$(grep '/usr/bin/python3' "$COMPONENT_DIR/voxtral.xml")
echo "✓ Fixed exec path to: $EXEC_PATH"

echo ""
echo "3. Setting up environment configuration..."
mkdir -p "$HOME/.config/environment.d"

# Create environment file
echo "IBUS_COMPONENT_PATH=$HOME/.local/share/ibus/component:$IBUS_COMPONENT_PATH" > "$HOME/.config/environment.d/ibus.conf"
export IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component:$IBUS_COMPONENT_PATH"
echo "✓ Created environment configuration"

echo ""
echo "4. Updating IBus cache and restarting..."
if command -v ibus > /dev/null 2>&1; then
    ibus write-cache
    ibus restart
    echo "✓ IBus updated and restarted"
else
    echo "⚠️  ibus command not found - please install ibus package manually"
    echo "   Install with: sudo dnf install ibus or sudo apt install ibus"
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "1. Log out and log back in (required for environment.d changes on Silverblue)"
echo "2. Go to: Settings → Keyboard → Input Sources → + → Other → Voxtral"
echo "3. The Voxtral engine should now appear in your input sources list"

echo ""
echo "Files created/modified:"
ls -la "$COMPONENT_DIR/"
echo ""
ls -la "$HOME/.config/environment.d/"