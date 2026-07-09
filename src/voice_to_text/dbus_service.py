"""
D-Bus service definition for voice-to-text.

Uses dbus-next (pure Python, native asyncio, zero dependencies).

Interface: com.happytomatoe.VoiceToText
Object path: /com/happytomatoe/VoiceToText
Bus: session

In dbus-next, signals are emitted by calling the ``@signal()``-decorated method.
The return value of that method is sent as the signal payload.
"""

import asyncio
import json
import logging

import sounddevice as sd

from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method, signal

from voice_to_text.engine import EngineState, RecordingEngine

logger = logging.getLogger(__name__)


SERVICE_NAME = "com.happytomatoe.VoiceToText"
OBJECT_PATH = "/com/happytomatoe/VoiceToText"


# ── Signal values (stashed by callbacks, read by signal getters) ──────
# dbus-next signals: the @signal() method's return value is emitted.
# We stash the current value on the interface and the signal method reads it.

class VoiceToTextInterface(ServiceInterface):
    """D-Bus interface for voice-to-text recording service.

    Exposes ``StartRecording``, ``StopRecording``, ``GetStatus`` methods
    and ``AudioLevel``, ``Error``, ``StateChanged`` signals.

    Signals are emitted by calling the ``@signal()`` method directly —
    e.g. ``self.StateChanged()`` — which dbus-next's decorator rewrites
    to call ``_handle_signal`` with the return value.
    """

    def __init__(self, engine: RecordingEngine | None = None):
        super().__init__("com.happytomatoe.VoiceToText")
        self._engine = engine or RecordingEngine()
        self._state = "idle"
        self._last_level: float = 0.0
        self._last_error: str = ""
        self._current_device: int | None = None
        self._connect_engine_signals()
        self._bus: MessageBus | None = None

    def set_bus(self, bus: MessageBus) -> None:
        self._bus = bus

    def _connect_engine_signals(self):
        """Wire up engine callbacks to D-Bus signal emission."""
        def _on_level(level: float):
            self._last_level = level
            self.AudioLevel()   # calls @signal() method → emits via dbus-next

        def _on_error(msg: str):
            self._last_error = msg
            self.Error()

        def _on_state(state: EngineState):
            self._state = state.value
            self.StateChanged()

        self._engine.on_audio_level = _on_level
        self._engine.on_error = _on_error
        self._engine.on_state_change = _on_state

    # ── Methods ──────────────────────────────────────────────────────────

    @method()
    def StartRecording(self, config: "s") -> None:  # noqa: N802, F821  # pyright: ignore[reportUndefinedVariable]
        """Start recording with JSON config string.

        Config keys:
          provider (str): transcription provider
          language (str): language code
          mode (str): "batch", "hybrid", or "streaming"
          streaming_provider (str): for hybrid/streaming modes
          batch_provider (str): for hybrid mode
          device (int|None): audio device index
          decrease_speaker_volume (int): 0-100
          output_method (str): "type", "clipboard", or "none"
        """
        if self._engine.state != EngineState.IDLE:
            raise DBusError(
                "com.happytomatoe.VoiceToText.Error.AlreadyRecording",
                f"Cannot start: engine is {self._engine.state.value}",
            )
        try:
            parsed_config = json.loads(config)
        except json.JSONDecodeError as e:
            raise DBusError(
                "com.happytomatoe.VoiceToText.Error.InvalidConfig",
                f"Invalid JSON config: {e}",
            )
        if not isinstance(parsed_config, dict):
            raise DBusError(
                "com.happytomatoe.VoiceToText.Error.InvalidConfig",
                f"Expected JSON object, got {type(parsed_config).__name__}",
            )
        logger.info("D-Bus StartRecording received config: %s", parsed_config)
        # Track selected device for GetAudioDevice method
        device_val = parsed_config.get('device')
        if device_val is not None and device_val != '':
            try:
                self._current_device = int(device_val)
            except (ValueError, TypeError):
                self._current_device = None
        else:
            self._current_device = None
        loop = asyncio.get_running_loop()
        loop.create_task(self._engine.start(parsed_config))

    @method()
    def StopRecording(self) -> None:  # noqa: N802
        """Stop the current recording session."""
        loop = asyncio.get_running_loop()
        loop.create_task(self._engine.stop())

    @method()
    def GetStatus(self) -> "s":  # noqa: N802, F821  # pyright: ignore[reportUndefinedVariable]
        """Return current state: idle/recording/processing."""
        return self._state

    @method()
    def GetAudioDevices(self) -> "s":  # noqa: N802, F821  # pyright: ignore[reportUndefinedVariable]
        """Return JSON list of available audio input devices.

        Each device has: name, index, channels, default_samplerate, is_default
        """
        devices = []
        default_idx = sd.default.device[0]  # input device

        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append({
                    "name": dev["name"],
                    "index": i,
                    "channels": dev["max_input_channels"],
                    "default_samplerate": dev["default_samplerate"],
                    "is_default": i == default_idx,
                })

        return json.dumps(devices)

    @method()
    def GetAudioDevice(self) -> "s":  # noqa: N802, F821  # pyright: ignore[reportUndefinedVariable]
        """Return the current audio device index or empty string for default."""
        return str(self._current_device) if self._current_device is not None else ""

    # ── Signals ──────────────────────────────────────────────────────────

    @signal()
    def AudioLevel(self) -> "d":  # noqa: N802, F821  # pyright: ignore[reportUndefinedVariable]
        """Emitted during recording with current audio level (0.0-1.0)."""
        return self._last_level

    @signal()
    def Error(self) -> "s":  # noqa: N802, F821  # pyright: ignore[reportUndefinedVariable]
        """Emitted on error during recording or transcription."""
        return self._last_error

    @signal()
    def StateChanged(self) -> "s":  # noqa: N802, F821  # pyright: ignore[reportUndefinedVariable]
        """Emitted when engine state changes (idle/recording/processing)."""
        return self._state


