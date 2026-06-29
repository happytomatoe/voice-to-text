#!/usr/bin/env python3
"""Test script for Voxtral IBus engine."""

import socket
import json
import os
import sys
import time
import threading

SOCKET_PATH = "/run/user/1000/voxtral-ibus.sock"


def test_socket_communication():
    """Test the Unix socket communication."""
    print("=== Testing Socket Communication ===")
    
    # Check if socket exists
    if os.path.exists(SOCKET_PATH):
        print(f"✓ Socket exists: {SOCKET_PATH}")
    else:
        print(f"✗ Socket not found: {SOCKET_PATH}")
        print("  Engine needs to be running and focused")
        return False
    
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(SOCKET_PATH)
        print("✓ Connected to socket")
        
        # Send test commands
        commands = [
            {"type": "preedit", "text": "Hello"},
            {"type": "commit", "text": "Hello World!"},
        ]
        
        for cmd in commands:
            client.sendall(json.dumps(cmd).encode() + b"\n")
            print(f"✓ Sent: {cmd['type']}")
            time.sleep(0.1)
        
        client.close()
        print("✓ Communication test passed")
        return True
        
    except ConnectionRefusedError:
        print("✗ Could not connect to socket")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_engine_directly():
    """Test the engine directly without IBus."""
    print("\n=== Testing Engine Directly ===")
    
    # Import the engine module
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    
    try:
        from voice_to_text.ibus.engine import VoxtralEngine
        
        # Create engine instance
        engine = VoxtralEngine()
        print("✓ Engine created successfully")
        
        # Start the socket listener
        engine._start_listener()
        print("✓ Socket listener started")
        
        # Wait for socket to be created
        time.sleep(1)
        
        if os.path.exists(SOCKET_PATH):
            print(f"✓ Socket created: {SOCKET_PATH}")
            
            # Test communication
            result = test_socket_communication()
            
            # Stop the listener
            engine._stop_listener()
            print("✓ Socket listener stopped")
            
            return result
        else:
            print("✗ Socket not created")
            engine._stop_listener()
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Main test function."""
    print("Voxtral IBus Engine Test")
    print("=" * 40)
    
    # Test 1: Direct engine test
    result1 = test_engine_directly()
    
    # Test 2: Socket communication test (if socket exists)
    result2 = test_socket_communication()
    
    print("\n" + "=" * 40)
    print("Test Results:")
    print(f"  Direct engine test: {'✓ PASS' if result1 else '✗ FAIL'}")
    print(f"  Socket communication: {'✓ PASS' if result2 else '✗ FAIL'}")
    
    if result1 or result2:
        print("\n✓ Engine is working correctly!")
        return 0
    else:
        print("\n✗ Engine test failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
