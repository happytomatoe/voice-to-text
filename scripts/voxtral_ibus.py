#!/usr/bin/env python3
"""Launcher for Voxtral IBus integration.

This script starts both the IBus engine and the bridge process.
The engine runs in the background (if not already running), and
the bridge captures audio and sends results to the engine.
"""

import logging
import os
import signal
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_SCRIPT = os.path.join(PROJECT_ROOT, "src", "voice_to_text", "ibus", "engine.py")
BRIDGE_SCRIPT = os.path.join(PROJECT_ROOT, "src", "voice_to_text", "ibus", "bridge.py")
SOCKET_PATH = os.environ.get("VOXTRAL_IBUS_SOCKET", "/tmp/voxtral-ibus.sock")

# System Python for IBus engine (needs gi/PyGObject)
SYSTEM_PYTHON = "/usr/bin/python3"


def check_socket_exists() -> bool:
    """Check if the IBus engine socket exists."""
    return os.path.exists(SOCKET_PATH)


def start_engine():
    """Start the IBus engine if not already running."""
    if check_socket_exists():
        logger.info("Engine socket already exists, assuming engine is running")
        return None

    logger.info("Starting IBus engine...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "src")

    process = subprocess.Popen(
        [SYSTEM_PYTHON, ENGINE_SCRIPT],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # Wait for socket to appear
    for _ in range(50):  # 5 seconds max
        if check_socket_exists():
            logger.info("Engine socket ready")
            return process
        time.sleep(0.1)

    logger.error("Engine failed to create socket")
    process.terminate()
    return None


def run_bridge():
    """Run the bridge process."""
    logger.info("Starting bridge...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "src")

    venv_python = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        python_cmd = venv_python
    else:
        python_cmd = sys.executable

    process = subprocess.Popen(
        [python_cmd, BRIDGE_SCRIPT],
        env=env,
    )
    return process


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    engine_process = None
    bridge_process = None

    def cleanup(signum=None, frame=None):
        """Clean up processes on exit."""
        logger.info("Shutting down...")
        if bridge_process and bridge_process.poll() is None:
            bridge_process.terminate()
            bridge_process.wait(timeout=5)
        if engine_process and engine_process.poll() is None:
            engine_process.terminate()
            engine_process.wait(timeout=5)
        # Clean up socket
        try:
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        # Start engine
        engine_process = start_engine()
        if engine_process is None:
            logger.error("Failed to start engine")
            return

        # Start bridge
        bridge_process = run_bridge()
        if bridge_process is None:
            logger.error("Failed to start bridge")
            cleanup()
            return

        # Wait for bridge to finish
        bridge_process.wait()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
