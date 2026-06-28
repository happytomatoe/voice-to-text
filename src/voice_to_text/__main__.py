#!/usr/bin/env python3
"""D-Bus service entry point for voice-to-text.

Uses dbus-next (pure Python, native asyncio) — no GLib/pygobject needed.
"""

import asyncio
import logging
import signal
import sys

from dbus_next.aio import MessageBus
from dbus_next.constants import BusType

from voice_to_text.dbus_service import OBJECT_PATH, SERVICE_NAME, VoiceToTextInterface

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging for the service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("/tmp/voice-to-text-service.log"),
            logging.StreamHandler(sys.stderr),
        ],
    )


async def run_service() -> None:
    """Connect to session bus, export interface, run until interrupted."""
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    interface = VoiceToTextInterface()
    interface.set_bus(bus)

    bus.export(OBJECT_PATH, interface)
    await bus.request_name(SERVICE_NAME)
    logger.info("Service registered: %s at %s", SERVICE_NAME, OBJECT_PATH)

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

    # Wait for the engine to finish cancelling before disconnecting
    if engine_stop_task:
        try:
            await asyncio.wait_for(engine_stop_task, timeout=5.0)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Engine did not stop in time, disconnecting anyway")

    bus.disconnect()


def main() -> None:
    setup_logging()
    logger.info("Starting voice-to-text D-Bus service")
    asyncio.run(run_service())


if __name__ == "__main__":
    main()
