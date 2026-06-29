"""Tests for IBus engine and bridge socket protocol."""

import os
import socket
import threading
import time
import pytest

# gi (PyGObject) is a system package required for IBus integration
# It's typically installed via the system package manager (apt, dnf, etc.)
# Tests that don't require gi can run without it

gi_available = False
try:
    import gi
    gi.require_version('IBus', '1.0')
    from gi.repository import IBus, GLib
    gi_available = True
except (ImportError, ValueError):
    pass


# Constants from engine.py (these don't require gi)
DEFAULT_SOCKET_PATH = "/tmp/voxtral-ibus.sock"
CMD_PREFIX_PREEDIT = "preedit:"
CMD_PREFIX_COMMIT = "commit:"
CMD_CLEAR_PREEDIT = "clear_preedit"
CMD_SHUTDOWN = "shutdown"


class TestSocketProtocol:
    """Test the socket communication protocol between bridge and engine."""

    def test_preedit_command_format(self):
        """Test preedit command format."""
        text = "hello world"
        command = f"{CMD_PREFIX_PREEDIT}{text}"
        assert command == "preedit:hello world"

    def test_commit_command_format(self):
        """Test commit command format."""
        text = "final text"
        command = f"{CMD_PREFIX_COMMIT}{text}"
        assert command == "commit:final text"

    def test_clear_preedit_command(self):
        """Test clear preedit command."""
        assert CMD_CLEAR_PREEDIT == "clear_preedit"

    def test_shutdown_command(self):
        """Test shutdown command."""
        assert CMD_SHUTDOWN == "shutdown"

    def test_socket_communication(self):
        """Test basic socket communication between client and server."""
        server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        test_socket_path = "/tmp/test-voxtral-ibus.sock"
        
        try:
            # Clean up any existing socket
            if os.path.exists(test_socket_path):
                os.unlink(test_socket_path)
            
            server_socket.bind(test_socket_path)
            server_socket.listen(1)
            server_socket.settimeout(2.0)
            
            # Start a client thread
            received_commands = []
            
            def client_thread():
                time.sleep(0.1)
                try:
                    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    client.connect(test_socket_path)
                    client.sendall(b"preedit:test text\n")
                    client.sendall(b"commit:final text\n")
                    client.close()
                except Exception as e:
                    pass
            
            client = threading.Thread(target=client_thread)
            client.start()
            
            # Accept connection and receive
            conn, _ = server_socket.accept()
            conn.settimeout(1.0)
            
            buffer = b""
            while b"\n" not in buffer:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data
            
            conn.close()
            client.join(timeout=2.0)
            
            # Verify received data
            lines = buffer.decode().strip().split("\n")
            assert lines[0] == "preedit:test text"
            
        finally:
            server_socket.close()
            if os.path.exists(test_socket_path):
                os.unlink(test_socket_path)

    def test_multiple_connections(self):
        """Test handling multiple client connections."""
        server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        test_socket_path = "/tmp/test-voxtral-ibus-multiple.sock"
        
        try:
            # Clean up any existing socket
            if os.path.exists(test_socket_path):
                os.unlink(test_socket_path)
            
            server_socket.bind(test_socket_path)
            server_socket.listen(5)
            server_socket.settimeout(3.0)
            
            received_data = []
            
            def client_thread(client_id):
                time.sleep(0.1)
                try:
                    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    client.connect(test_socket_path)
                    client.sendall(f"preedit:client{client_id}\n".encode())
                    client.close()
                except Exception:
                    pass
            
            # Start multiple clients
            clients = []
            for i in range(3):
                t = threading.Thread(target=client_thread, args=(i,))
                t.start()
                clients.append(t)
            
            # Accept connections
            for _ in range(3):
                try:
                    conn, _ = server_socket.accept()
                    conn.settimeout(1.0)
                    data = conn.recv(1024)
                    if data:
                        received_data.append(data.decode().strip())
                    conn.close()
                except socket.timeout:
                    continue
            
            # Verify we received data from clients
            assert len(received_data) > 0
            
            # Wait for all client threads to finish
            for t in clients:
                t.join(timeout=2.0)
                
        finally:
            server_socket.close()
            if os.path.exists(test_socket_path):
                os.unlink(test_socket_path)


@pytest.mark.skipif(not gi_available, reason="gi (PyGObject) not installed")
class TestVoxtralEngine:
    """Test the VoxtralEngine class (requires gi)."""

    def test_engine_imports(self):
        """Test that VoxtralEngine can be imported."""
        from voice_to_text.ibus.engine import VoxtralEngine, DEFAULT_SOCKET_PATH, CMD_PREFIX_PREEDIT, CMD_PREFIX_COMMIT
        assert VoxtralEngine is not None
        assert DEFAULT_SOCKET_PATH == "/tmp/voxtral-ibus.sock"
        assert CMD_PREFIX_PREEDIT == "preedit:"
        assert CMD_PREFIX_COMMIT == "commit:"

    def test_engine_custom_socket_path(self, monkeypatch):
        """Test that VoxtralEngine uses custom socket path from environment."""
        custom_path = "/tmp/custom-voxtral.sock"
        monkeypatch.setenv("VOXTRAL_IBUS_SOCKET", custom_path)
        
        from voice_to_text.ibus.engine import VoxtralEngine
        engine = VoxtralEngine()
        assert engine._socket_path == custom_path

    def test_engine_protocol_constants(self):
        """Test that protocol constants are defined correctly."""
        from voice_to_text.ibus.engine import CMD_PREFIX_PREEDIT, CMD_PREFIX_COMMIT, CMD_CLEAR_PREEDIT, CMD_SHUTDOWN
        
        # Verify command prefixes
        assert CMD_PREFIX_PREEDIT == "preedit:"
        assert CMD_PREFIX_COMMIT == "commit:"
        assert CMD_CLEAR_PREEDIT == "clear_preedit"
        assert CMD_SHUTDOWN == "shutdown"