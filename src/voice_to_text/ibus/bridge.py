"""Voxtral Bridge: connects audio capture to IBus engine via socket.

This bridge captures audio from the microphone, sends it to Voxtral
for real-time transcription, and relays the results to the IBus
engine via a Unix socket.
"""

import json
import logging
import os
import socket
import sys
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from voice_to_text.config import ConfigManager
from voice_to_text.providers.voxtral import VoxtralProvider

logger = logging.getLogger(__name__)

# Default socket path (must match engine.py) - use XDG_RUNTIME_DIR for security
DEFAULT_SOCKET_PATH = os.environ.get("XDG_RUNTIME_DIR", "/tmp") + "/voxtral-ibus.sock"
SAMPLE_RATE = 16000
BLOCK_SIZE = 2048  # samples


class VoxtralBridge:
    """Bridge between audio capture and IBus engine."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._socket_path = os.environ.get("VOXTRAL_IBUS_SOCKET", DEFAULT_SOCKET_PATH)
        self._config = config or {}
        self._provider: VoxtralProvider | None = None
        self._socket: socket.socket | None = None
        self._stream: sd.InputStream | None = None
        self._running = False
        self._recording = False

    def _connect_socket(self, wait: bool = True) -> bool:
        """Connect to the IBus engine's Unix socket."""
        # First, try to connect immediately
        try:
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.connect(self._socket_path)
            logger.info("Connected to IBus engine at %s", self._socket_path)
            return True
        except (OSError, ConnectionRefusedError):
            pass
        
        if not wait:
            logger.error("Failed to connect to IBus engine: Socket not found")
            return False
        
        # Wait for the socket to be created (engine needs to be focused)
        logger.info("Waiting for IBus engine socket at %s...", self._socket_path)
        logger.info("(The socket will appear when you switch to Voxtral engine)")
        
        for i in range(100):  # Wait up to 10 seconds
            try:
                self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._socket.connect(self._socket_path)
                logger.info("Connected to IBus engine at %s", self._socket_path)
                return True
            except (OSError, ConnectionRefusedError):
                time.sleep(0.1)
        
        logger.error("Timeout waiting for IBus engine socket")
        logger.error("Make sure to switch to Voxtral engine (Super+Space)")
        return False

    def _send_command(self, command_type: str, text: str = ""):
        """Send a command to the IBus engine via socket."""
        if self._socket is None:
            return

        try:
            cmd = json.dumps({"type": command_type, "text": text})
            self._socket.sendall(f"{cmd}\n".encode("utf-8"))
        except (OSError, BrokenPipeError) as e:
            logger.warning("Failed to send command: %s", e)
            self._socket = None
            # Trigger reconnection on next send
            if self._running:
                self._connect_socket()

    def _on_event(self, event_type: str, text: str):
        """Callback for VoxtralProvider events."""
        logger.debug("Event: %s -> %s", event_type, text[:50] if text else "")

        if event_type == "preedit":
            self._send_command("preedit", text)
        elif event_type == "commit":
            self._send_command("commit", text)

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback for audio stream - sends audio to provider."""
        if status:
            logger.warning("Audio status: %s", status)

        if self._provider and self._recording:
            # Convert int16 to bytes
            audio_bytes = indata.tobytes()
            self._provider.send_audio(audio_bytes)

    def start(self):
        """Start the bridge."""
        logger.info("Starting Voxtral bridge")

        # Connect to IBus engine
        if not self._connect_socket():
            logger.error("Cannot start bridge: IBus engine not available")
            return False

        # Load config
        config_manager = ConfigManager()
        provider_config = config_manager.get_provider_config("voxtral")

        # Create provider with callback
        self._provider = VoxtralProvider(provider_config, event_callback=self._on_event)

        # Start audio stream
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=BLOCK_SIZE,
                dtype="int16",
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            logger.error("Failed to start audio stream: %s", e)
            return False

        # Start Voxtral stream
        self._provider.start_stream(language="en", sample_rate=SAMPLE_RATE)

        self._running = True
        logger.info("Bridge started. Press Ctrl+C to stop.")
        return True

    def stop(self):
        """Stop the bridge."""
        logger.info("Stopping Voxtral bridge")
        self._running = False
        self._recording = False

        # Stop audio stream
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        # Finalize Voxtral stream
        if self._provider:
            try:
                self._provider.finalize_stream()
            except Exception:
                pass
            self._provider = None

        # Disconnect socket
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        logger.info("Bridge stopped")

    def toggle_recording(self):
        """Toggle recording on/off."""
        if not self._running:
            return

        if self._recording:
            # Stop recording - finalize current stream
            self._recording = False
            if self._provider:
                try:
                    result = self._provider.finalize_stream()
                    if result:
                        self._send_command("commit", result)
                except Exception as e:
                    logger.error("Error finalizing stream: %s", e)

                # Start a new stream for next recording
                try:
                    self._provider.start_stream(language="en", sample_rate=SAMPLE_RATE)
                except Exception as e:
                    logger.error("Error starting new stream: %s", e)

            logger.info("Recording stopped")
        else:
            # Start recording
            self._recording = True
            logger.info("Recording started")

    def run(self):
        """Run the bridge until interrupted."""
        if not self.start():
            return

        try:
            # Wait a moment for the stream to initialize
            time.sleep(0.5)

            # Auto-start recording
            self.toggle_recording()

            # Keep running until interrupted
            while self._running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()


def main():
    """Entry point for the bridge."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    bridge = VoxtralBridge()
    bridge.run()


if __name__ == "__main__":
    main()
