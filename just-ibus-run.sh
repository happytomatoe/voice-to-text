#!/usr/bin/env bash
# Run Voxtral IBus engine and bridge
# Usage: ./just-ibus-run.sh

set -e

echo "=== Starting Voxtral IBus Integration ==="
echo ""
echo "Instructions:"
echo "1. The engine will start and register with IBus"
echo "2. Switch to Voxtral engine (Super+Space or IBus tray)"
echo "3. The bridge will wait for the socket, then start"
echo "4. Open a text editor and speak into microphone"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Set environment
export IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component:$IBUS_COMPONENT_PATH"
export PYTHONPATH=src

# Start engine in background (using system Python with gi)
echo "Starting engine..."
setsid /usr/bin/python3 src/voice_to_text/ibus/engine.py --ibus > /tmp/voxtral-engine.log 2>&1 &
ENGINE_PID=$!

# Wait for engine to register
sleep 2

# Start bridge in foreground
echo "Starting bridge..."
echo "(Waiting for socket - switch to Voxtral engine to create socket)"
echo ""
uv run python3 src/voice_to_text/ibus/bridge.py

# Cleanup
echo "Shutting down..."
kill $ENGINE_PID 2>/dev/null || true
wait $ENGINE_PID 2>/dev/null || true
