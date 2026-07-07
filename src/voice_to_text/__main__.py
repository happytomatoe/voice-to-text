#!/usr/bin/env python3
"""D-Bus service entry point for voice-to-text.

Uses dbus-next (pure Python, native asyncio) — no GLib/pygobject needed.
"""

import asyncio
import logging
import signal
import sys
import time
from datetime import datetime

from dbus_next.aio import MessageBus
from dbus_next.constants import BusType, RequestNameReply

from voice_to_text.dbus_service import OBJECT_PATH, SERVICE_NAME, VoiceToTextInterface

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging for the service with file output and timestamps."""
    # Get log file path from config or default
    import os
    log_file = os.environ.get('VOICE_TO_TEXT_LOG', '/tmp/voice-to-text.log')
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )
    
    # Add profiling start marker
    logger.info("=== VOICE-TO-TEXT SERVICE STARTUP PROFILE ===")


async def run_service_with_profiling() -> None:
    """Connect to session bus, export interface, with timing info."""
    startup_start = time.time()
    
    # Import the engine class for timing
    from voice_to_text.engine import RecordingEngine
    
    # Profile D-Bus connection
    bus_connect_start = time.time()
    logger.info("Connecting to D-Bus session bus...")
    
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    
    bus_connect_time = time.time() - bus_connect_start
    logger.info(f"D-Bus connection completed in {bus_connect_time:.3f}s")
    
    # Profile interface creation
    interface_start = time.time()
    logger.info("Creating VoiceToTextInterface...")
    
    interface = VoiceToTextInterface()
    interface.set_bus(bus)
    
    interface_time = time.time() - interface_start
    logger.info(f"VoiceToTextInterface created in {interface_time:.3f}s")
    
    # Profile service registration
    export_start = time.time()
    logger.info("Exporting interface to D-Bus...")
    
    bus.export(OBJECT_PATH, interface)
    
    logger.info("Requesting D-Bus service name...")
    reply = await bus.request_name(SERVICE_NAME)
    
    export_time = time.time() - export_start
    logger.info(f"Service registration completed in {export_time:.3f}s")
    
    if reply != RequestNameReply.PRIMARY_OWNER:
        logger.error("Failed to own D-Bus name %s (reply=%s)", SERVICE_NAME, reply)
        bus.disconnect()
        raise SystemExit(1)
    
    logger.info(f"Service registered: {SERVICE_NAME} at {OBJECT_PATH}")
    
    # Profile engine startup
    engine_start_start = time.time()
    logger.info("Starting recording engine...")
    
    # Mock config for profiling (engine won't actually start due to missing API keys)
    # In production, this would use real config from file
    mock_config = {
        "provider": "voxtral",
        "language": "en",
        "mode": "batch",
        "device": None,
        "decrease_speaker_volume": 0,
        "output_method": "none"
    }
    
    try:
        await interface._engine.start(mock_config)
        engine_start_time = time.time() - engine_start_start
        logger.info(f"Engine start completed in {engine_start_time:.3f}s")
        
        # Add a log marker for minimal recording
        await asyncio.sleep(0.1)
        await interface._engine.stop()
        
        logger.info("=== STARTUP TIMING SUMMARY ===")
        total_startup = time.time() - startup_start
        logger.info(f"Total startup time: {total_startup:.3f}s")
        logger.info(f"  - D-Bus connection: {bus_connect_time:.3f}s")
        logger.info(f"  - Interface creation: {interface_time:.3f}s")
        logger.info(f"  - Service registration: {export_time:.3f}s")
        logger.info(f"  - Engine startup: {engine_start_time:.3f}s")
        
        # Performance analysis
        components = [
            ("D-Bus connection", bus_connect_time),
            ("Interface creation", interface_time),
            ("Service registration", export_time),
            ("Engine startup", engine_start_time),
        ]
        
        slowest = max(components, key=lambda x: x[1])
        
        if slowest[1] > 0.5:
            logger.warning(f"PERFORMANCE ISSUE: Component '{slowest[0]}' took {slowest[1]:.3f}s (>500ms)")
            logger.warning(f"This may account for delays in the 0.5-1s range you reported.")
        
    except Exception as e:
        error_time = time.time() - engine_start_start
        logger.error(f"Engine startup failed after {error_time:.3f}s: {type(e).__name__}: {e}")
    
    logger.info("Service ready and running. Press Ctrl+C to stop.")
    
    # Keep running until SIGTERM/SIGINT
    stop_event = asyncio.Event()
    engine_stop_task: asyncio.Task | None = None
    loop = asyncio.get_event_loop()

    def _shutdown() -> None:
        logger.info("Shutting down voice-to-text service")
        # Cancel any active recording gracefully before exit
        nonlocal engine_stop_task
        engine_stop_task = asyncio.create_task(interface._engine.stop())
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown)

    await stop_event.wait()

    # Log shutdown
    shutdown_start = time.time()
    logger.info("Shutting down...")
    
    if engine_stop_task:
        try:
            await asyncio.wait_for(engine_stop_task, timeout=16.0)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Engine did not stop in time, disconnecting anyway")

    bus.disconnect()
    
    shutdown_time = time.time() - shutdown_start
    logger.info(f"Service shutdown completed in {shutdown_time:.3f}s")
    logger.info("=== SERVICE STOPPED ===")


def main() -> None:
    setup_logging()
    logger.info("Starting voice-to-text D-Bus service")
    asyncio.run(run_service_with_profiling())


if __name__ == "__main__":
    main()