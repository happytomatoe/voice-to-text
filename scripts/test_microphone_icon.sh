#!/usr/bin/env bash
# Manual test script for microphone icon verification
# This script starts the engine and provides instructions for testing

set -e

echo "============================================================"
echo "VOXTRAL IBUS - MICROPHONE ICON TEST"
echo "============================================================"
echo ""
echo "INSTRUCTIONS:"
echo "1. This script will start the Voxtral IBus engine"
echo "2. You need to manually switch to Voxtral in IBus:"
echo "   - Press Super+Space (or click IBus tray icon)"
echo "   - Select 'Voxtral' from the input methods"
echo "3. The 🎤 microphone icon should appear in the panel"
echo "4. Watch this terminal for engine logs"
echo ""
echo "NOTES:"
echo "- Socket will be created at: /run/user/$(id -u)/voxtral-ibus.sock"
echo "- Engine log: /tmp/voxtral-engine.log"
echo "- Press Ctrl+C to stop the engine"
echo ""
echo "============================================================"
echo ""

# Set environment
export IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component:$IBUS_COMPONENT_PATH"
export PYTHONPATH=src

# Check if IBus daemon is running
if ! pgrep -x ibus-daemon > /dev/null 2>&1; then
    echo "ERROR: IBus daemon is not running"
    echo "Start with: ibus-daemon -drx --config=disable --panel=disable"
    exit 1
fi

# Kill any existing engine
pkill -f "engine.py" 2>/dev/null || true
sleep 0.5

# Start engine with setsid (so it survives terminal close)
echo "Starting Voxtral IBus engine..."
setsid /usr/bin/python3 src/voice_to_text/ibus/engine.py --ibus 2>&1 | tee /tmp/voxtral-engine.log &
ENGINE_PID=$!

echo "Engine started with PID: $ENGINE_PID"
echo ""
echo "Watching logs..."
echo "============================================================"

# Tail the log file
tail -f /tmp/voxtral-engine.log 2>/dev/null &

# Wait for engine
sleep 2

# Check if engine is running
if kill -0 $ENGINE_PID 2>/dev/null; then
    echo ""
    echo "✓ Engine is running"
    echo ""
    echo "NOW: Switch to Voxtral (Super+Space) and look for the 🎤 icon"
    echo ""
else
    echo "✗ Engine failed to start"
    echo "Check /tmp/voxtral-engine.log for details"
    exit 1
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo "Stopping engine..."
    kill $ENGINE_PID 2>/dev/null || true
    pkill -f "engine.py" 2>/dev/null || true
    echo "Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for Ctrl+C
wait $ENGINE_PID 2>/dev/null || true