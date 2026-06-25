"""IBus engine for Voxtral speech-to-text integration.

This engine listens on a Unix socket for preedit/commit commands
from the bridge process and relays them to the active application
through the IBus framework.
"""

import logging
import os
import socket
import sys
import threading

import gi

gi.require_version("IBus", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import GLib, IBus

logger = logging.getLogger(__name__)

# Default socket path for bridge communication
DEFAULT_SOCKET_PATH = "/tmp/voxtral-ibus.sock"

# Protocol commands
CMD_PREFIX_PREEDIT = "preedit:"
CMD_PREFIX_COMMIT = "commit:"
CMD_CLEAR_PREEDIT = "clear_preedit"
CMD_SHUTDOWN = "shutdown"


class VoxtralEngine(IBus.Engine):
    """IBus engine that receives text from Voxtral bridge via Unix socket."""

    _preedit_text: str = ""
    _preedit_visible: bool = False
    _socket_path: str
    _server_socket: socket.socket | None = None
    _client_socket: socket.socket | None = None
    _running: bool = False
    _listener_thread: threading.Thread | None = None

    def __init__(self):
        self._socket_path = os.environ.get("VOXTRAL_IBUS_SOCKET", DEFAULT_SOCKET_PATH)
        super().__init__()
        logger.info("VoxtralEngine initialized, socket: %s", self._socket_path)

    def do_focus_in(self):
        """Called when the engine is focused in."""
        logger.debug("VoxtralEngine focused in")
        self._start_listener()

    def do_focus_out(self):
        """Called when the engine is focused out."""
        logger.debug("VoxtralEngine focused out")

    def do_process_key_event(self, keyval: int, keycode: int, state: int) -> bool:
        """Process key events. Return False to pass through all keys."""
        return False

    def do_destroy(self):
        """Called when engine is destroyed."""
        self._stop_listener()

    def do_reset(self):
        """Called when engine is reset."""
        self._clear_preedit()

    def _start_listener(self):
        """Start the Unix socket listener if not already running."""
        if self._running:
            return

        # Clean up stale socket
        try:
            if os.path.exists(self._socket_path):
                os.unlink(self._socket_path)
        except OSError:
            pass

        self._running = True
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        logger.info("Socket listener started on %s", self._socket_path)

    def _stop_listener(self):
        """Stop the Unix socket listener."""
        self._running = False

        # Send shutdown command to self to unblock accept()
        try:
            tmp = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            tmp.connect(self._socket_path)
            tmp.sendall(CMD_SHUTDOWN.encode())
            tmp.close()
        except (OSError, ConnectionRefusedError):
            pass

        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)
        self._listener_thread = None

        # Clean up socket file
        try:
            if os.path.exists(self._socket_path):
                os.unlink(self._socket_path)
        except OSError:
            pass

        logger.info("Socket listener stopped")

    def _listen_loop(self):
        """Listen for commands on the Unix socket."""
        try:
            self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(self._socket_path)
            self._server_socket.listen(1)
            self._server_socket.settimeout(1.0)

            while self._running:
                try:
                    client, _ = self._server_socket.accept()
                    self._client_socket = client
                    self._handle_client(client)
                except socket.timeout:
                    continue
                except OSError:
                    if self._running:
                        logger.exception("Socket accept error")
                    break

        except Exception:
            logger.exception("Listener loop failed")
        finally:
            if self._server_socket:
                self._server_socket.close()
                self._server_socket = None

    def _handle_client(self, client: socket.socket):
        """Handle commands from a connected client."""
        client.settimeout(0.5)
        buffer = b""

        while self._running:
            try:
                data = client.recv(4096)
                if not data:
                    break

                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    command = line.decode("utf-8", errors="replace").strip()
                    if command:
                        self._process_command(command)

            except socket.timeout:
                continue
            except (OSError, BrokenPipeError):
                break

        client.close()
        self._client_socket = None

    def _process_command(self, command: str):
        """Process a command from the bridge."""
        logger.debug("Received command: %s", command[:100])

        if command == CMD_SHUTDOWN:
            self._running = False
            return

        if command.startswith(CMD_PREFIX_COMMIT):
            text = command[len(CMD_PREFIX_COMMIT) :]
            self._commit_text(text)

        elif command.startswith(CMD_PREFIX_PREEDIT):
            text = command[len(CMD_PREFIX_PREEDIT) :]
            self._update_preedit(text)

        elif command == CMD_CLEAR_PREEDIT:
            self._clear_preedit()

        else:
            logger.warning("Unknown command: %s", command[:50])

    def _commit_text(self, text: str):
        """Commit text to the focused application via IBus."""
        if not text:
            return

        # Clear any preedit first
        self._clear_preedit()

        # Use GLib.idle_add to run on the main thread
        GLib.idle_add(self._do_commit, text)

    def _do_commit(self, text: str):
        """Actually commit text (must run on main thread)."""
        logger.info("Committing: %s", text[:50])
        ibus_text = IBus.Text.new_from_string(text)
        self.commit_text(ibus_text)
        return False  # Remove from idle queue

    def _update_preedit(self, text: str):
        """Update preedit (underlined temporary text)."""
        if not text:
            self._clear_preedit()
            return

        self._preedit_text = text
        self._preedit_visible = True
        GLib.idle_add(self._do_update_preedit, text)

    def _do_update_preedit(self, text: str):
        """Actually update preedit (must run on main thread)."""
        logger.debug("Preedit: %s", text[:50])
        ibus_text = IBus.Text.new_from_string(text)
        attrs = IBus.AttrList()
        # UNDERLINE type = 1, value = 0 (single underline), from 0 to len(text)
        attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE, 0, 0, len(text)))
        ibus_text.set_attributes(attrs)
        self.update_preedit_text(ibus_text, len(text), bool(len(text)))
        return False  # Remove from idle queue

    def _clear_preedit(self):
        """Clear the preedit text."""
        if self._preedit_visible:
            self._preedit_visible = False
            self._preedit_text = ""
            GLib.idle_add(self._do_clear_preedit)

    def _do_clear_preedit(self):
        """Actually clear preedit (must run on main thread)."""
        logger.debug("Clearing preedit")
        text = IBus.Text.new_from_string("")
        self.update_preedit_text(text, 0, False)
        return False  # Remove from idle queue


def main():
    """Entry point for the IBus engine process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    logger.info("Starting Voxtral IBus engine")

    # Check if running under IBus (passed --ibus flag)
    running_under_ibus = "--ibus" in sys.argv
    if "--ibus" in sys.argv:
        sys.argv.remove("--ibus")

    # Create the engine and register it with IBus
    engine = VoxtralEngine()
    bus = IBus.Bus()
    factory = IBus.Factory.new(bus.get_connection())
    factory.add_engine("Voxtral", engine.__class__)

    # Always start the socket listener
    # When running under IBus, do_focus_in will also be called
    engine._start_listener()

    # Run the main loop
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        logger.info("Engine interrupted")
    finally:
        loop.quit()


if __name__ == "__main__":
    main()
