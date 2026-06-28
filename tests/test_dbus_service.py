"""
End-to-end tests for the D-Bus service.

Architecture
------------
Each test spins up a **private** ``dbus-daemon`` process (no interaction with
the real session bus), then connects both the service
(:class:`VoiceToTextInterface`) and a test client to that private bus.

The service uses a :class:`MockRecordingEngine` that simulates state
transitions without touching audio hardware or network APIs, letting us
test the full D-Bus message layer (method calls, replies, errors, signals)
in isolation.

Signal propagation path
    service signal → service bus send() → dbus-daemon → client bus read → callback
(The service's ``send()`` is non-blocking; the actual I/O completes on the
next event-loop iteration.)
"""

import asyncio
import json
import os
import subprocess
import textwrap

import pytest
from dbus_next import DBusError
from dbus_next.aio import MessageBus

from voice_to_text.dbus_service import (
    OBJECT_PATH,
    SERVICE_NAME,
    VoiceToTextInterface,
)
from voice_to_text.engine import EngineState

# ── Bus configuration template ───────────────────────────────────────────
# Permissive policy so our test client can eavesdrop on signals and own any
# name on the private bus.

BUS_CONFIG = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
     "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
    <busconfig>
      <type>session</type>
      <keep_umask/>
      <listen>unix:path={socket_path}</listen>
      <auth>EXTERNAL</auth>
      <policy context="default">
        <allow send_destination="*" eavesdrop="true"/>
        <allow eavesdrop="true"/>
        <allow own="*"/>
      </policy>
    </busconfig>
""")


# ── Mock engine ──────────────────────────────────────────────────────────


class MockRecordingEngine:
    """Simulates recording-engine state transitions without hardware.

    Records every call and fires the registered callbacks so that the
    D-Bus service's signal-emission chain is exercised end-to-end.
    """

    def __init__(self):
        self.state = EngineState.IDLE
        self.on_audio_level = None  # Callable[[float], None]
        self.on_error = None  # Callable[[str], None]
        self.on_state_change = None  # Callable[[EngineState], None]
        self.on_transcription_result = None  # Callable[[str], None]

        self.started_config: dict | None = None
        """:meth:`start` was called with this config (``None`` otherwise)."""

        self.stop_called: bool = False
        """:meth:`stop` was called at least once."""

    async def start(self, config: dict) -> None:
        self.started_config = config
        self.state = EngineState.RECORDING
        if self.on_state_change:
            self.on_state_change(EngineState.RECORDING)

    async def stop(self) -> None:
        # Match the real engine: no-op when already idle
        if self.state == EngineState.IDLE:
            return
        self.stop_called = True
        self.state = EngineState.IDLE
        if self.on_state_change:
            self.on_state_change(EngineState.IDLE)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def dbus_socket_path(tmp_path):
    """Absolute path for the private bus Unix domain socket."""
    return str(tmp_path / "bus.socket")


@pytest.fixture
def bus_config_path(tmp_path, dbus_socket_path):
    """Write a permissive ``dbus-daemon`` config and return its path."""
    path = tmp_path / "dbus.conf"
    path.write_text(BUS_CONFIG.format(socket_path=dbus_socket_path))
    return str(path)


@pytest.fixture
async def bus_address(bus_config_path, dbus_socket_path):
    """Start a private ``dbus-daemon`` and yield its bus address.

    The daemon runs ``--nofork`` so it shares the test-process lifecycle.
    It is terminated (and waited on) during teardown.
    """
    proc = subprocess.Popen(
        [
            "dbus-daemon",
            "--config-file",
            bus_config_path,
            "--nofork",
            "--print-address=1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for the Unix socket to appear on disk
    for _ in range(100):
        if os.path.exists(dbus_socket_path):
            break
        await asyncio.sleep(0.02)
    else:
        proc.terminate()
        pytest.fail("dbus-daemon socket did not appear within 2 s timeout")

    # Read the bus address from stdout (printed once at startup)
    assert proc.stdout is not None
    address_line = proc.stdout.readline()
    address = address_line.decode().strip()
    assert address, "dbus-daemon did not print a bus address"

    yield address

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture
async def mock_engine():
    """Fresh :class:`MockRecordingEngine` per test."""
    return MockRecordingEngine()


@pytest.fixture
async def dbus_test_env(bus_address, mock_engine):
    """Set up the service and client on the private bus.

    Yields ``(mock_engine, proxy_interface)``.

    * ``mock_engine`` – the same instance injected into the service
      (tests can fire callbacks directly).
    * ``proxy`` – a ``dbus-next`` proxy that makes real D-Bus method
      calls to the service.
    """
    # ── Service side ──────────────────────────────────────────────
    service_bus = await MessageBus(bus_address=bus_address).connect()
    interface = VoiceToTextInterface(engine=mock_engine)
    interface.set_bus(service_bus)
    service_bus.export(OBJECT_PATH, interface)
    await service_bus.request_name(SERVICE_NAME)

    # ── Client side ───────────────────────────────────────────────
    client_bus = await MessageBus(bus_address=bus_address).connect()
    introspection = await client_bus.introspect(SERVICE_NAME, OBJECT_PATH)
    obj = client_bus.get_proxy_object(SERVICE_NAME, OBJECT_PATH, introspection)
    proxy = obj.get_interface("com.happytomatoe.VoiceToText")

    yield mock_engine, proxy

    client_bus.disconnect()
    service_bus.disconnect()


# ── Constants for signal-propagation waits ──────────────────────────────
# ``dbus-next`` signal emission goes: service buffered-write → dbus-daemon
# → client read → callback.  Each hop needs an event-loop tick.
_SIGNAL_WAIT = 0.05


# ======================================================================
# Tests
# ======================================================================


class TestGetStatus:
    """``GetStatus`` method."""

    async def test_initial_state_is_idle(self, dbus_test_env):
        """:meth:`GetStatus` returns ``"idle"`` on a fresh service."""
        _, proxy = dbus_test_env
        status = await proxy.call_get_status()
        assert status == "idle"

    async def test_recording_after_start(self, dbus_test_env):
        """:meth:`GetStatus` returns ``"recording"`` after a start."""
        _, proxy = dbus_test_env
        await proxy.call_start_recording('{"provider": "test"}')
        await asyncio.sleep(_SIGNAL_WAIT)
        assert await proxy.call_get_status() == "recording"

    async def test_idle_after_stop(self, dbus_test_env):
        """:meth:`GetStatus` returns ``"idle"`` after stop completes."""
        _, proxy = dbus_test_env
        await proxy.call_start_recording("{}")
        await asyncio.sleep(_SIGNAL_WAIT)
        await proxy.call_stop_recording()
        await asyncio.sleep(_SIGNAL_WAIT)
        assert await proxy.call_get_status() == "idle"


class TestStartRecording:
    """``StartRecording`` method."""

    async def test_invalid_json_raises_dbus_error(self, dbus_test_env):
        """Invalid JSON config raises a ``DBusError`` (not a crash)."""
        _, proxy = dbus_test_env
        with pytest.raises(DBusError) as excinfo:
            await proxy.call_start_recording("not valid json at all")
        assert "Invalid JSON" in str(excinfo.value)

    async def test_empty_json_is_accepted(self, dbus_test_env):
        """Valid JSON ``{}`` is accepted by the interface."""
        mock_engine, proxy = dbus_test_env
        await proxy.call_start_recording("{}")
        await asyncio.sleep(_SIGNAL_WAIT)
        assert mock_engine.started_config == {}

    async def test_parsed_config_passed_to_engine(self, dbus_test_env):
        """The JSON config is parsed and delivered to the engine."""
        mock_engine, proxy = dbus_test_env
        config = {"provider": "voxtral", "language": "en", "mode": "batch"}
        await proxy.call_start_recording(json.dumps(config))
        await asyncio.sleep(_SIGNAL_WAIT)
        assert mock_engine.started_config == config

    async def test_double_start_raises_error(self, dbus_test_env):
        """Calling :meth:`StartRecording` while already recording fails."""
        _, proxy = dbus_test_env
        await proxy.call_start_recording("{}")
        await asyncio.sleep(_SIGNAL_WAIT)  # engine transitions to RECORDING

        with pytest.raises(DBusError) as excinfo:
            await proxy.call_start_recording("{}")
        assert "Cannot start" in str(excinfo.value)


class TestStopRecording:
    """``StopRecording`` method."""

    async def test_stop_when_idle_is_safe(self, dbus_test_env):
        """:meth:`StopRecording` on an idle engine does not crash."""
        mock_engine, proxy = dbus_test_env
        await proxy.call_stop_recording()
        assert not mock_engine.stop_called
        assert await proxy.call_get_status() == "idle"

    async def test_stop_passed_to_engine(self, dbus_test_env):
        """:meth:`StopRecording` delegates to the engine."""
        mock_engine, proxy = dbus_test_env
        await proxy.call_start_recording("{}")
        await asyncio.sleep(_SIGNAL_WAIT)
        await proxy.call_stop_recording()
        await asyncio.sleep(_SIGNAL_WAIT)
        assert mock_engine.stop_called


class TestSignals:
    """D-Bus signals (``StateChanged``, ``AudioLevel``, etc.)."""

    # ── StateChanged ──────────────────────────────────────────────

    async def test_state_changed_on_start(self, dbus_test_env):
        """:data:`StateChanged` fires ``"recording"`` when the engine starts."""
        _, proxy = dbus_test_env
        changes = []
        proxy.on_state_changed(changes.append)

        await proxy.call_start_recording("{}")
        await asyncio.sleep(_SIGNAL_WAIT)

        assert "recording" in changes

    async def test_state_changed_on_stop(self, dbus_test_env):
        """:data:`StateChanged` fires ``"idle"`` when the engine stops."""
        _, proxy = dbus_test_env
        changes = []
        proxy.on_state_changed(changes.append)

        await proxy.call_start_recording("{}")
        await asyncio.sleep(_SIGNAL_WAIT)
        await proxy.call_stop_recording()
        await asyncio.sleep(_SIGNAL_WAIT)

        assert "idle" in changes

    # ── AudioLevel ────────────────────────────────────────────────

    async def test_audio_level_signal(self, dbus_test_env):
        """:data:`AudioLevel` delivers values fired by the engine callback."""
        mock_engine, proxy = dbus_test_env
        levels = []
        proxy.on_audio_level(levels.append)

        mock_engine.on_audio_level(0.42)  # triggers the full D-Bus signal path
        await asyncio.sleep(_SIGNAL_WAIT)

        assert len(levels) >= 1
        assert levels[0] == pytest.approx(0.42)

    # ── TranscriptionResult ───────────────────────────────────────

    async def test_transcription_result_signal(self, dbus_test_env):
        """:data:`TranscriptionResult` delivers text from the engine."""
        mock_engine, proxy = dbus_test_env
        texts = []
        proxy.on_transcription_result(texts.append)

        mock_engine.on_transcription_result("hello world")
        await asyncio.sleep(_SIGNAL_WAIT)

        assert texts == ["hello world"]

    # ── Error ─────────────────────────────────────────────────────

    async def test_error_signal(self, dbus_test_env):
        """:data:`Error` delivers error messages from the engine."""
        mock_engine, proxy = dbus_test_env
        errors = []
        proxy.on_error(errors.append)

        mock_engine.on_error("test error message")
        await asyncio.sleep(_SIGNAL_WAIT)

        assert errors == ["test error message"]

    # ── Multiple signals ──────────────────────────────────────────

    async def test_multiple_audio_level_events(self, dbus_test_env):
        """Multiple :data:`AudioLevel` values are received in order."""
        mock_engine, proxy = dbus_test_env
        levels = []
        proxy.on_audio_level(levels.append)

        mock_engine.on_audio_level(0.1)
        mock_engine.on_audio_level(0.5)
        mock_engine.on_audio_level(0.9)
        await asyncio.sleep(_SIGNAL_WAIT)

        assert len(levels) >= 3

    async def test_state_changed_multiple_transitions(self, dbus_test_env):
        """:data:`StateChanged` fires for each transition of a full cycle."""
        _, proxy = dbus_test_env
        changes = []
        proxy.on_state_changed(changes.append)

        await proxy.call_start_recording("{}")
        await asyncio.sleep(_SIGNAL_WAIT)
        await proxy.call_stop_recording()
        await asyncio.sleep(_SIGNAL_WAIT)

        # Order: idle→recording (start), recording→idle (stop)
        assert changes == ["recording", "idle"]
