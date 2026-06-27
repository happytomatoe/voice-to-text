#!/usr/bin/env python3
"""Integration test for Voxtral IBus engine.

This script tests:
1. Engine can be created and started
2. Socket is created when engine is enabled
3. Socket communication works correctly
4. Bridge can connect to engine

Usage:
    python scripts/test_integration.py

Manual test steps (for full integration):
    1. Run: just ibus-engine
    2. Switch to Voxtral (Super+Space)
    3. Run: just ibus-bridge
    4. Speak into microphone
    5. Verify text appears in focused application
"""

import json
import os
import socket
import sys
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SOCKET_PATH = os.environ.get("XDG_RUNTIME_DIR", "/tmp") + "/voxtral-ibus.sock"


def test_engine_socket_directly():
    """Test engine socket creation and communication without IBus."""
    print("\n" + "=" * 60)
    print("TEST: Engine Socket (Direct)")
    print("=" * 60)

    from voice_to_text.ibus.engine import VoxtralEngine

    # Create engine instance
    engine = VoxtralEngine()
    print(f"✓ Engine created, socket path: {engine._socket_path}")

    # Start listener (simulates do_focus_in)
    engine._start_listener()
    print("✓ Socket listener started")

    # Wait for socket
    time.sleep(0.5)

    # Check socket exists
    if os.path.exists(engine._socket_path):
        print(f"✓ Socket created: {engine._socket_path}")
    else:
        print(f"✗ Socket not created at {engine._socket_path}")
        engine._stop_listener()
        return False

    # Test communication
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(engine._socket_path)
        print("✓ Connected to socket")

        # Send test commands
        test_commands = [
            {"type": "preedit", "text": "Test preedit text"},
            {"type": "commit", "text": "Test commit text"},
            {"type": "clear_preedit"},
        ]

        for cmd in test_commands:
            client.sendall(json.dumps(cmd).encode() + b"\n")
            print(f"✓ Sent command: {cmd['type']}")

        client.close()
        print("✓ Socket communication successful")

    except Exception as e:
        print(f"✗ Socket communication failed: {e}")
        engine._stop_listener()
        return False

    # Stop listener
    engine._stop_listener()
    print("✓ Socket listener stopped")

    # Verify socket is cleaned up
    if not os.path.exists(engine._socket_path):
        print("✓ Socket cleaned up")
    else:
        print(f"⚠ Socket still exists: {engine._socket_path}")

    return True


def test_bridge_socket_connection():
    """Test that bridge can connect to engine socket."""
    print("\n" + "=" * 60)
    print("TEST: Bridge Socket Connection")
    print("=" * 60)

    # This test requires the engine to be running
    # We'll just verify the bridge code can attempt connection

    try:
        # Import bridge module
        from voice_to_text.ibus.bridge import VoxtralBridge

        bridge = VoxtralBridge()
        print(f"✓ Bridge created, socket path: {bridge._socket_path}")

        # Check if socket exists (engine must be focused)
        if os.path.exists(bridge._socket_path):
            print(f"✓ Socket exists, attempting connection...")
            if bridge._connect_socket(wait=False):
                print("✓ Bridge connected to engine")
                return True
            else:
                print("✗ Bridge failed to connect")
                return False
        else:
            print(f"⚠ Socket not found at {bridge._socket_path}")
            print("  (Engine needs to be running and focused)")
            return None  # Not a failure, just not ready

    except ImportError as e:
        print(f"⚠ Could not import bridge: {e}")
        print("  (This is OK - bridge requires additional dependencies)")
        return None  # Not a failure, just missing deps


def test_ibus_component():
    """Test IBus component configuration."""
    print("\n" + "=" * 60)
    print("TEST: IBus Component")
    print("=" * 60)

    component_path = os.path.expanduser("~/.local/share/ibus/component/voxtral.xml")

    if not os.path.exists(component_path):
        print(f"✗ Component file not found: {component_path}")
        return False

    print(f"✓ Component file exists: {component_path}")

    # Check content
    with open(component_path) as f:
        content = f.read()

    # Verify key elements
    checks = [
        ("<name>voxtral</name>", "Engine name"),
        ("<symbol>🎤</symbol>", "Microphone symbol"),
        ("--ibus", "IBus flag in exec"),
    ]

    for check, desc in checks:
        if check in content:
            print(f"✓ Found {desc}")
        else:
            print(f"✗ Missing {desc}")
            return False

    return True


def test_environment():
    """Test environment configuration."""
    print("\n" + "=" * 60)
    print("TEST: Environment")
    print("=" * 60)

    # Check IBus daemon
    import subprocess

    result = subprocess.run(["pgrep", "-x", "ibus-daemon"], capture_output=True)
    if result.returncode == 0:
        print("✓ IBus daemon is running")
    else:
        print("⚠ IBus daemon not running")
        print("  Start with: ibus-daemon -drx --config=disable --panel=disable")

    # Check component path
    component_path = os.environ.get("IBUS_COMPONENT_PATH", "")
    if component_path:
        print(f"✓ IBUS_COMPONENT_PATH: {component_path}")
    else:
        print("⚠ IBUS_COMPONENT_PATH not set")
        print("  Add to ~/.config/environment.d/ibus.conf")

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("VOXTRAL IBUS INTEGRATION TEST")
    print("=" * 60)

    results = {}

    # Run tests
    results["environment"] = test_environment()
    results["component"] = test_ibus_component()
    results["engine_socket"] = test_engine_socket_directly()
    results["bridge_connection"] = test_bridge_socket_connection()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test, result in results.items():
        if result is True:
            status = "✓ PASS"
        elif result is False:
            status = "✗ FAIL"
        else:
            status = "⚠ SKIP"
        print(f"  {test}: {status}")

    # Overall result
    failed = sum(1 for r in results.values() if r is False)
    if failed == 0:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())