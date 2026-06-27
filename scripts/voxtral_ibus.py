#!/usr/bin/env python3
"""Launcher for Voxtral IBus integration.

This script starts both the IBus engine and the bridge process.
The engine runs in the background (if not already running), and
the bridge captures audio and sends results to the engine.
"""

import logging
import os
import signal
import socket
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_SCRIPT = os.path.join(PROJECT_ROOT, "src", "voice_to_text", "ibus", "engine.py")
BRIDGE_SCRIPT = os.path.join(PROJECT_ROOT, "src", "voice_to_text", "ibus", "bridge.py")
SOCKET_PATH = os.environ.get("VOXTRAL_IBUS_SOCKET", os.environ.get("XDG_RUNTIME_DIR", "/tmp") + "/voxtral-ibus.sock")

# System Python for IBus engine (needs gi/PyGObject)
SYSTEM_PYTHON = "/usr/bin/python3"


def check_engine_registered() -> bool:
    """Check if the Voxtral engine is registered with IBus."""
    try:
        import subprocess
        result = subprocess.run(
            ["ibus", "list-engine"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        return "voxtral" in result.stdout.lower()
    except Exception:
        return False


def start_engine():
    """Start the IBus engine if not already running."""
    if check_engine_registered():
        logger.info("Engine is already registered with IBus")
        return None

    logger.info("Starting IBus engine...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "src")
    
    # Set IBUS_COMPONENT_PATH if not already set
    if "IBUS_COMPONENT_PATH" not in env:
        user_component_path = os.path.expanduser("~/.local/share/ibus/component")
        env["IBUS_COMPONENT_PATH"] = f"{user_component_path}:{env.get('IBUS_COMPONENT_PATH', '')}"

    process = subprocess.Popen(
        [SYSTEM_PYTHON, ENGINE_SCRIPT, "--ibus"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # Wait for engine to register with IBus
    for _ in range(50):  # 5 seconds max
        if check_engine_registered():
            logger.info("Engine registered with IBus")
            return process
        time.sleep(0.1)

    logger.error("Engine failed to register with IBus")
    process.terminate()
    return None


def run_bridge():
    """Run the bridge process."""
    logger.info("Starting bridge...")
    logger.info("Note: Bridge will connect when engine is focused")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "src")

    # Use uv run for the bridge
    process = subprocess.Popen(
        ["uv", "run", "python3", BRIDGE_SCRIPT],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
            # Engine might already be registered
            logger.info("Engine is already registered with IBus")

        # Start bridge
        bridge_process = run_bridge()
        if bridge_process is None:
            logger.error("Failed to start bridge")
            cleanup()
            return

        logger.info("\n=== Voxtral IBus Integration Started ===")
        logger.info("To use:")
        logger.info("1. Switch to Voxtral engine (Super+Space or IBus tray)")
        logger.info("2. Open a text editor")
        logger.info("3. The bridge will capture audio and send text to the engine")
        logger.info("\nPress Ctrl+C to stop\n")

        # Wait for bridge to finish
        bridge_process.wait()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
