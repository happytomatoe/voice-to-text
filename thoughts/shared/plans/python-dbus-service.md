# Voice-to-Text D-Bus Service Implementation Plan

## Overview

Transform the existing Python voice-to-text CLI application into a headless D-Bus service. Strip all terminal-UI code, refactor providers to async, and integrate dotool for direct keyboard output. The service runs as a systemd --user unit with D-Bus activation and is consumed exclusively by the GNOME Shell extension (replacing the current subprocess/stdio protocol).

## Current State Analysis

**Python application (`src/voice_to_text/`):**
- CLI entry point with argparse (`main.py`): interactive setup, benchmark, terminal UI bars, keyboard polling
- Audio recording via `sounddevice` (blocking `InputStream`)
- 4 transcription providers using synchronous HTTP (`requests`) + WebSocket (`websocket-client`)
- Voxtral provider already partially async (Mistral SDK realtime)
- Bluetooth headset HSP/HFP switching via `pactl` (`bluetooth.py`)
- Speaker volume management via `wpctl`/`pactl` (`SpeakerVolumeManager` in `audio.py`)
- State machine: embedded in CLI flow, not reusable

**GNOME extension (`gnome-ext/`):**
- Spawns Python as subprocess per recording session
- Parses stdout line protocol (START/LEVEL:/STREAM:/TEXT:/ERROR:)
- `typer.js`: dotoolc-based incremental typing (diff algorithm from nerd-dictation)
- Has retry logic for Python spawn failures (symptom of fragile subprocess model)

**Key Discoveries:**
- **dbus-next** is a pure-Python D-Bus library with native asyncio support (zero dependencies) — better fit than dasbus for async services
- Voxtral's Mistral SDK realtime API already uses asyncio (can be adapted)
- `httpx` supports both sync and async APIs — can replace `requests` cleanly
- `websockets` library provides async WebSocket client — replaces `websocket-client`
- `sounddevice` has `AsyncInputStream` (uses callback thread; bridge to asyncio via `asyncio.Queue`)
- `dotoolc` (client to `dotoold` daemon) supports persistent stdin pipes — lower latency than `dotool` direct
- `dotoold` daemon setup via systemd user service is documented (`dotool-quickstart.sh`)

## Desired End State

A Python D-Bus service (`com.happytomatoe.VoiceToText`) that:

1. Runs as a systemd --user unit with D-Bus activation
2. Exposes methods: `StartRecording`, `StopRecording`, `GetStatus`
3. Emits signals: `AudioLevel`, `Error`, `StateChanged`
4. Handles all output internally — typing via continuous `dotoolc` pipe, clipboard via `wl-copy`/`xclip`
5. All provider calls are async (using httpx + websockets + sd.AsyncInputStream)
6. Integrates `dotoolc` for direct keyboard typing when output_method="type"
6. Handles Bluetooth headset switching and speaker volume management
7. Has zero terminal UI — no ANSI codes, no interactive prompts, no keyboard polling
8. GNOME extension connects via `Gio.DBusProxy` instead of spawning subprocess

### Key Constraints:
- All imports must be at module level (per AGENTS.md)
- `dbus-next` is pure Python with zero dependencies (no PyGObject/GLib needed)
- `dotoolc` requires `dotoold` daemon running (set up by `dotool-quickstart.sh`)
- `dotoold` requires `/dev/uinput` access (input group) — system dependency, not a Python concern
- The service must handle only one recording session at a time (GNOME extension is sole client)
- API keys remain in environment variables (same as current setup)

## What We're NOT Doing

- Not adding any new transcription providers beyond the existing 4
- Not replacing the GNOME extension UI — it stays as the consumer
- Not building a CLI client for the D-Bus service (CLI is removed)
- Not handling multiple concurrent recordings
- Not implementing audio playback or TTS
- Not changing the config file format or GSettings schema
- Not supporting Windows/macOS (Linux D-Bus + uinput only)

## Implementation Approach

**Strategy:** Incremental, testable phases. Each phase produces a working artifact.

1. Strip UI code while keeping existing sync providers (safe, testable)
2. Refactor providers to async (parallel with phase 1 — independent work)
3. Build D-Bus service with asyncio event loop (integrates async providers)
4. Add dotool typing integration
5. Package as systemd unit
6. Update GNOME extension

---

## Phase 1: Strip UI/TUI from Python Codebase

### Overview
Remove all terminal-oriented code — interactive setup, level bars, keyboard polling, clipboard, benchmarking. The result is a library-grade Python package with no entry point of its own (service entry point comes in Phase 3).

### Changes Required:

#### 1. `src/voice_to_text/main.py` — Remove entire file
The file is 100% CLI/TUI code. Every function in it is either:
- Interactive setup (`setup_key_interactive`, `setup_interactive`, `set_provider`)
- Terminal UI (`format_level_bar` usage, keyboard polling via `tty.setcbreak`)
- CLI dispatch (`main()`, argument parsing, subcommand dispatch)
- Benchmarking (`run_benchmark`, `_LogCollector`)
- Clipboard (`copy_to_clipboard` — client concern)
- Stdout protocol mode (`run_stdout_mode` — replaced by D-Bus signals)

**Action:** Delete `src/voice_to_text/main.py`

#### 2. `src/voice_to_text/audio.py` — Strip terminal UI
Remove the following, which are only used by `main.py` for the terminal level meter:

```python
# Remove these constants and functions:
METER_WIDTH = 50
GREY = "\033[90m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"
BLOCK = "\u2588"

def format_level_bar(level: float, elapsed: float) -> str:
    ...
```

**Keep:**
- `AudioRecorder` class (with `smoothed_level` property — still emits level via D-Bus signal, just no terminal bar)
- `SpeakerVolumeManager` class (still useful for preventing audio feedback)
- `SAMPLE_RATE`, `BLOCK_SIZE` constants (used by providers)

#### 3. `pyproject.toml` — Remove CLI entry point + unused deps

```diff
 [project.scripts]
-voice-to-text = "voice_to_text.main:main"
+voice-to-text-dbus = "voice_to_text.service:main"
```

Note: This change is tentative; the final entry point may be a different module depending on how the service is designed. Will be finalized in Phase 3.

#### 4. Clean up config references
`config.yaml` at project root — remove any references to `main.py` features. The file itself stays as a development config sample.

### Success Criteria:

#### Automated Verification:
- [ ] Package imports without errors: `python -c "import voice_to_text"`
- [ ] All provider imports work: `python -c "from voice_to_text.providers import get_batch_provider"`
- [ ] `AudioRecorder` class accessible: `python -c "from voice_to_text.audio import AudioRecorder"`
- [ ] No references to deleted functions in remaining code: `grep -r "format_level_bar\|copy_to_clipboard\|run_stdout_mode\|run_benchmark" src/` returns nothing
- [ ] Module-level imports rule not violated

#### Manual Verification:
- [ ] No terminal ANSI codes or interactive prompts in the codebase

---

## Phase 2: Refactor Providers to Async

### Overview
Replace all synchronous HTTP/WebSocket libraries with async alternatives. Every provider's `transcribe_file()` and streaming methods become `async def`. This paves the way for the async D-Bus service loop.

### Changes Required:

#### 1. `pyproject.toml` — Swap dependencies

```diff
 dependencies = [
-  "groq~=1.2.0",
   "sounddevice~=0.5.5",
   "numpy~=2.4.4",
   "pyyaml~=6.0.3",
   "python-dotenv~=1.2.2",
-  "requests~=2.33.1",
-  "websocket-client~=1.8.0",
+  "httpx~=0.28.0",
+  "websockets~=14.0",
+  "dbus-next~=0.2.3",
+  "groq~=1.2.0",
   "mistralai[realtime]~=2.4,!=2.4.6",
 ]
```

- Remove `requests`, `websocket-client` (replaced by `httpx`, `websockets`)
- Add `httpx` (async HTTP client — replaces `requests` for all providers)
- Add `websockets` (async WebSocket — replaces `websocket-client` for Deepgram streaming)
- Add `dbus-next` (D-Bus library — native asyncio, zero dependencies, needed in Phase 3)
- Keep `groq` (its SDK uses httpx internally; `transcribe_file` wrapper becomes async)
- Keep `mistralai` (Voxtral — already uses async internally, just needs `await` wrapper)

#### 2. `src/voice_to_text/providers/base.py` — Make interfaces async

```python
class BatchProvider(ABC):
    @abstractmethod
    async def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file (batch processing)."""
        pass

class StreamingProvider(ABC):
    @abstractmethod
    async def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        pass

    @abstractmethod
    async def send_audio(self, audio_chunk: bytes) -> None:
        pass

    @abstractmethod
    async def get_partial_result(self) -> str | None:
        pass

    @abstractmethod
    async def finalize_stream(self) -> str:
        pass
```

Also refactor `WebSocketStreamingProvider` base class to use `websockets` async library instead of `websocket-client`:

- `_connect_ws()` becomes `async def` using `websockets.connect()`
- `send_audio()` becomes `async def` using `websocket.send()`
- `_process_messages()` becomes `async def` using `async for msg in websocket:`
- `finalize_stream()` becomes `async def` with async send/recv

#### 3. `src/voice_to_text/providers/deepgram.py` — Async refactor

```python
class DeepgramProvider(BatchProvider, WebSocketStreamingProvider):
    async def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        # Replace requests.get with httpx.AsyncClient
        async with httpx.AsyncClient() as client:
            with open(audio_path, "rb") as audio_file:
                response = await client.post(...)
        ...

    async def start_stream(self, ...) -> None:
        # Replace websocket-client connect with websockets.connect
        ...
```

#### 4. `src/voice_to_text/providers/groq.py` — Async refactor

```python
class GroqProvider(BatchProvider):
    async def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        # The groq SDK supports async:
        # transcription = await self.client.audio.transcriptions.create(...)
        # Or run existing sync in executor
        ...
```

**Note:** The `groq` Python SDK already supports async natively (it's built on httpx). We can use:
```python
self.client = Groq(async_client=True)  # or use the default async client
```

#### 5. `src/voice_to_text/providers/voxtral.py` — Minor async adaptation

The Voxtral provider already uses asyncio internally for streaming. The batch `transcribe_file()` uses `requests` — replace with `httpx.AsyncClient`. No structural changes needed to the streaming path.

```python
async def transcribe_file(self, audio_path: str, language: str = "en") -> str:
    async with httpx.AsyncClient() as client:
        with open(audio_path, "rb") as audio_file:
            response = await client.post(
                f"{self._api_url}/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (os.path.basename(audio_path), audio_file)},
                data={"model": self.model, "language": language},
                timeout=120,
            )
        ...
```

#### 6. `src/voice_to_text/providers/parakeet.py` — Async refactor

```python
async def transcribe_file(self, audio_path: str, language: str = "en") -> str:
    async with httpx.AsyncClient() as client:
        with open(audio_path, "rb") as f:
            response = await client.post(...)
        ...
```

#### 7. `src/voice_to_text/hybrid.py` — Make async

```python
class HybridTranscriber:
    async def start_stream(self, ...) -> None:
        await self.streaming.start_stream(...)

    async def on_audio_chunk(self, chunk: bytes) -> str:
        await self.streaming.send_audio(chunk)
        result = await self.streaming.get_partial_result()
        ...

    async def on_recording_stop(self, audio_path: str, language: str) -> str:
        finalized = await self.streaming.finalize_stream()
        return await self.batch.transcribe_file(audio_path, language=language)
```

#### 8. `src/voice_to_text/providers/__init__.py` — Keep as-is (factory functions stay synchronous)

### Success Criteria:

#### Automated Verification:
- [ ] `pip install -e .` resolves dependencies without conflict
- [ ] `python -c "import httpx; import websockets; import dbus_next"` all import
- [ ] `python -c "from voice_to_text.providers import get_batch_provider; p = get_batch_provider('deepgram', {})"` — still works (lazy eval, won't call transcribe_file)
- [ ] Type checking passes: `pyright src/voice_to_text/providers/`
- [ ] All linting passes: `ruff check src/voice_to_text/`

#### Manual Verification:
- [ ] (Requires API keys) Each provider's `transcribe_file()` can be called with `await` in a test script
- [ ] (Requires API keys) Deepgram streaming works with `websockets` async API

---

## Phase 3: Build D-Bus Service Layer

### Overview
Create the D-Bus service daemon with dbus-next, a recording engine state machine, and the asyncio main loop. This is the new entry point for the Python package.

### Changes Required:

#### 1. New file: `src/voice_to_text/engine.py` — Recording Engine (State Machine)

The engine orchestrates the full recording lifecycle asynchronously:

```python
"""
Async recording engine — state machine for the D-Bus service.

States:
  idle       Waiting for StartRecording call
  recording  AudioRecorder is actively capturing audio
  processing Audio stopped, transcription running

Audio recording uses sd.AsyncInputStream with an asyncio.Queue to bridge
the callback thread into the async event loop.
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Callable

import numpy as np
import sounddevice as sd

from voice_to_text.audio import SpeakerVolumeManager
from voice_to_text.bluetooth import activate_headset_mic
from voice_to_text.config import ConfigManager
from voice_to_text.hybrid import HybridTranscriber
from voice_to_text.providers import get_batch_provider, get_streaming_provider
from voice_to_text.typer import ContinuousTyper

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BLOCK_SIZE = 2048


class EngineState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


class AsyncAudioRecorder:
    """Records audio using sd.AsyncInputStream + asyncio.Queue.

    The callback thread puts audio chunks into the queue;
    the async caller reads from the queue.
    """

    def __init__(self, device: int | None = None, sample_rate: int = SAMPLE_RATE):
        self.device = device
        self.sample_rate = sample_rate
        self.smoothed_level: float = 0.0
        self.frame_count: int = 0
        self._stream: sd.AsyncInputStream | None = None
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._wav_file = None
        self._filepath: str | None = None

    async def start(self, filepath: str) -> None:
        import os
        import tempfile
        import wave

        self._filepath = filepath
        fd = os.fdopen(os.open(filepath, os.O_WRONLY | os.O_CREAT, 0o600), "wb")
        self._wav_file = wave.open(fd, "wb")
        self._wav_file.setnchannels(1)
        self._wav_file.setsampwidth(2)
        self._wav_file.setframerate(self.sample_rate)

        self._stream = sd.AsyncInputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            callback=self._audio_callback,
            device=self.device,
        )
        self._stream.start()
        logger.info("AsyncAudioRecorder started (rate=%d, device=%s)",
                    self.sample_rate, self.device)

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Called from the sounddevice callback thread — put data into queue."""
        raw = indata.tobytes()
        if self._wav_file is not None:
            self._wav_file.writeframes(raw)
        self.frame_count += 1
        # Smoothed level for D-Bus AudioLevel signal
        float_data = indata[:, 0].astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(float_data ** 2)))
        self.smoothed_level = 0.7 * self.smoothed_level + 0.3 * rms
        try:
            self._queue.put_nowait(raw)
        except asyncio.QueueFull:
            pass  # drop if consumer is slow

    async def read_chunk(self) -> bytes | None:
        """Await the next audio chunk (or None if stopped)."""
        return await self._queue.get()

    def stop(self) -> str | None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._wav_file:
            self._wav_file.close()
            self._wav_file = None
        filepath = self._filepath
        self._filepath = None
        # Signal consumer that no more data
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        return filepath

    def stop_and_delete(self) -> None:
        import os
        filepath = self.stop()
        if filepath:
            try:
                os.unlink(filepath)
            except OSError:
                pass


class RecordingEngine:
    def __init__(self):
        self.state = EngineState.IDLE
        self._recorder: AsyncAudioRecorder | None = None
        self._transcriber: HybridTranscriber | None = None
        self._batch_provider = None
        self._task: asyncio.Task | None = None
        self._cancel_event = asyncio.Event()

        # Callbacks set by the D-Bus service to emit signals
        self.on_audio_level: Callable[[float], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_state_change: Callable[[EngineState], None] | None = None

    async def start(self, config: dict[str, Any]) -> None:
        """Start recording and transcription."""
        if self.state != EngineState.IDLE:
            raise RuntimeError(f"Cannot start: engine is {self.state.value}")
        self._cancel_event.clear()
        self.state = EngineState.RECORDING
        self._notify_state()
        self._task = asyncio.create_task(self._run(config))

    async def stop(self) -> None:
        """Stop recording gracefully."""
        if self.state == EngineState.IDLE:
            return
        self._cancel_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning("Recording task did not finish in time")
                self._task.cancel()
        self.state = EngineState.IDLE
        self._notify_state()

    async def _run(self, config: dict[str, Any]) -> None:
        """Full recording + transcription pipeline."""
        try:
            import tempfile

            # 1. Activate BT headset mic if configured
            activate_headset_mic()

            # 2. Set up providers
            provider = config.get("provider", "voxtral")
            mode = config.get("mode", "batch")
            language = config.get("language", "en")
            output_method = config.get("output_method", "none")
            use_typing = output_method == "type"

            transcriber = None
            batch_provider = None

            if mode in ("hybrid", "streaming"):
                ...  # set up hybrid transcriber (uses get_streaming_provider)
            else:
                config_mgr = ConfigManager()
                provider_config = config_mgr.get_provider_config(provider)
                batch_provider = get_batch_provider(provider, provider_config)

            # 3. Open dotoolc pipe early if typing
            typer: ContinuousTyper | None = None
            if use_typing:
                try:
                    typer = ContinuousTyper()
                    await typer.start()
                except Exception as e:
                    logger.warning("Typing requested but dotoolc unavailable: %s", e)
                    if self.on_error:
                        self.on_error(f"Typing not available: {e}")

            # 4. Record audio via AsyncInputStream + Queue
            decrease_pct = config.get("decrease_speaker_volume", 50)
            fd, audio_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

            recorder = AsyncAudioRecorder(
                device=config.get("device"),
                sample_rate=SAMPLE_RATE,
            )
            self._recorder = recorder

            with SpeakerVolumeManager.with_decrease(decrease_pct):
                await recorder.start(audio_path)

                # Start streaming if in hybrid mode
                if transcriber:
                    await transcriber.start_stream(language, sample_rate=recorder.sample_rate)

                # Recording loop — read chunks from the queue
                while not self._cancel_event.is_set():
                    chunk = await recorder.read_chunk()
                    if chunk is None:
                        break  # stream ended

                    # Emit audio level for D-Bus signal
                    if self.on_audio_level:
                        self.on_audio_level(recorder.smoothed_level)

                    # Feed streaming provider + type incrementally
                    if transcriber and typer:
                        partial = await transcriber.on_audio_chunk(chunk)
                        if partial:
                            await typer.stream_diff(partial)

            # 5. Transcribe final result
            self.state = EngineState.PROCESSING
            self._notify_state()

            filepath = recorder.stop()
            if filepath and batch_provider:
                text = await batch_provider.transcribe_file(filepath, language)
                if text and typer:
                    await typer.stream_diff(text)

        except Exception as e:
            logger.exception("Recording failed")
            if self.on_error:
                self.on_error(str(e))
        finally:
            if typer:
                await typer.stop()
            self.state = EngineState.IDLE
            self._notify_state()
            self._cleanup()

    def _cleanup(self):
        if self._recorder:
            try:
                self._recorder.stop_and_delete()
            except Exception:
                pass
            self._recorder = None
        self._transcriber = None
        self._task = None

    def _notify_state(self):
        if self.on_state_change:
            self.on_state_change(self.state)
```

#### 2. New file: `src/voice_to_text/dbus_service.py` — D-Bus Interface

```python
"""
D-Bus service definition for voice-to-text.

Uses dbus-next (pure Python, native asyncio, zero dependencies).

Interface: com.happytomatoe.VoiceToText
Object path: /com/happytomatoe/VoiceToText
Bus: session
"""

import asyncio
import json
import logging
from typing import Any

from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, signal

from voice_to_text.engine import RecordingEngine, EngineState

logger = logging.getLogger(__name__)


SERVICE_NAME = "com.happytomatoe.VoiceToText"
OBJECT_PATH = "/com/happytomatoe/VoiceToText"


# Note: dbus-next uses a ServiceInterface subclass with decorators.
# The interface name, methods, signals, and properties are declared
# via @method / @signal decorators — no GLib/pygobject needed.

class VoiceToTextInterface(ServiceInterface):
    """D-Bus interface for voice-to-text recording service."""

    def __init__(self):
        super().__init__("com.happytomatoe.VoiceToText")
        self._engine = RecordingEngine()
        self._connect_engine_signals()
        self._state = "idle"
        self._bus: MessageBus | None = None

    def set_bus(self, bus: MessageBus) -> None:
        self._bus = bus

    def _connect_engine_signals(self):
        """Wire up engine callbacks to D-Bus signal emission."""
        def _on_level(level: float):
            self.emit_signal(
                "AudioLevel",
                "d",  # dbus type: double
                [level],
            )

        def _on_error(msg: str):
            self.emit_signal(
                "Error",
                "s",  # dbus type: string
                [msg],
            )

        def _on_state(state: EngineState):
            self._state = state.value
            self.emit_signal(
                "StateChanged",
                "s",
                [state.value],
            )

        self._engine.on_audio_level = _on_level
        self._engine.on_error = _on_error
        self._engine.on_state_change = _on_state

    @method()
    def StartRecording(self, config: "s") -> None:  # noqa: N802, F821
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
        parsed_config = json.loads(config)
        # Launch async start on the event loop
        loop = asyncio.get_event_loop()
        loop.create_task(self._engine.start(parsed_config))

    @method()
    def StopRecording(self) -> None:  # noqa: N802
        """Stop the current recording session."""
        loop = asyncio.get_event_loop()
        loop.create_task(self._engine.stop())

    @method()
    def GetStatus(self) -> "s":  # noqa: N802, F821
        """Return current state: idle/recording/processing."""
        return self._state

    @signal()
    def AudioLevel(self) -> "d":  # noqa: N802
        """Emitted during recording with current audio level (0.0-1.0)."""
        pass  # return value ignored; actual emission via emit_signal()

    @signal()
    def Error(self) -> "s":  # noqa: N802
        """Emitted on error during recording or transcription."""
        pass

    @signal()
    def StateChanged(self) -> "s":  # noqa: N802
        """Emitted when engine state changes (idle/recording/processing)."""
        pass
```

#### 3. New file: `src/voice_to_text/__main__.py` — Service Entry Point

```python
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

from voice_to_text.dbus_service import (
    VoiceToTextInterface,
    SERVICE_NAME,
    OBJECT_PATH,
)

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging for the service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("/tmp/voice-to-text-service.log"),
            logging.StreamHandler(sys.stderr),
        ],
    )


async def run_service():
    """Connect to session bus, export interface, run until interrupted."""
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    interface = VoiceToTextInterface()
    interface.set_bus(bus)

    bus.export(OBJECT_PATH, interface)
    await bus.request_name(SERVICE_NAME)
    logger.info("Service registered: %s at %s", SERVICE_NAME, OBJECT_PATH)

    # Keep running until SIGTERM/SIGINT
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _shutdown():
        logger.info("Shutting down voice-to-text service")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown)

    await stop_event.wait()
    bus.disconnect()


def main():
    setup_logging()
    logger.info("Starting voice-to-text D-Bus service")
    asyncio.run(run_service())


if __name__ == "__main__":
    main()
```

#### 4. `pyproject.toml` — Update entry point

```diff
 [project.scripts]
-voice-to-text = "voice_to_text.main:main"
+voice-to-text-dbus = "voice_to_text.__main__:main"
```

### Success Criteria:

#### Automated Verification:
- [ ] Service starts without error: `python -m voice_to_text.__main__ &` (runs in background, verify no crash)
- [ ] D-Bus service is registered: `busctl --user list | grep com.happytomatoe.VoiceToText`
- [ ] Interface introspection works: `busctl --user introspect com.happytomatoe.VoiceToText /com/happytomatoe/VoiceToText`
- [ ] Methods visible: `StartRecording`, `StopRecording`, `GetStatus`
- [ ] Signals visible: `AudioLevel`, `Error`, `StateChanged`
- [ ] `pyright src/voice_to_text/` passes
- [ ] `ruff check src/voice_to_text/` passes

#### Manual Verification:
- [ ] `StartRecording` -> engine changes state to "recording"
- [ ] `AudioLevel` signal fires during recording
- [ ] `StopRecording` -> engine stops and transitions to "processing" then "idle"
- [ ] `Error` signal fires when provider fails
- [ ] Service survives SIGTERM and shuts down cleanly

---

## Phase 4: Add Continuous dotoolc Pipe Integration

### Overview
Integrate a persistent `dotoolc` (client to `dotoold` daemon) process for real-time keyboard output. Instead of spawning a new subprocess per text chunk, open `dotoolc` once at recording start and feed a continuous stdin stream of `type ...\n` and `key backspace\n` commands as streaming transcription results arrive. This gives zero-latency typing with near-zero overhead.

**Why `dotoolc` (not `dotool` direct)?**
- `dotool` re-registers virtual input devices on every invocation — adds latency
- `dotoolc` is a client to `dotoold` which keeps devices registered — lower latency
- `dotoold` is already set up as a systemd user service by `dotool-quickstart.sh`
- The diff algorithm (backspace + retype) flows through the same stdin pipe

### Changes Required:

#### 1. New file: `src/voice_to_text/typer.py` — Persistent dotoolc pipe

```python
"""
Continuous dotoolc typing engine for voice-to-text.

Keeps a persistent `dotoolc` (client to dotoold daemon) process open
and feeds it a stream of `type ...\n` and `key backspace\n` commands
via stdin. The process stays alive for the duration of the recording session.

dotoolc (vs. dotool direct): dotoolc is a client to the dotoold daemon,
which keeps virtual input devices registered — lower latency than dotool
which re-registers devices on every invocation. dotoold is assumed running
(set up by dotool-quickstart.sh as a systemd user service).

References:
- dotool docs: https://git.sr.ht/~geb/dotool
- nerd-dictation diff algorithm: https://github.com/ideasman42/nerd-dictation
"""

import asyncio
import logging
import shutil

logger = logging.getLogger(__name__)


class DotoolcNotFoundError(RuntimeError):
    """Raised when dotoolc is not found in PATH."""


class ContinuousTyper:
    """Types text via a persistent pipe to the `dotoolc` binary.
    
    Usage:
        typer = ContinuousTyper()
        await typer.start()              # open pipe (once at recording start)
        await typer.stream_type("hello") # push text immediately
        await typer.stream_backspace(3)  # backspace last 3 chars
        ...
        await typer.stop()               # close pipe (recording done)
    """

    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._dotoolc_path: str | None = None
        self._typed_text: str = ""

    async def start(self) -> None:
        """Start a persistent dotoolc process and keep stdin open."""
        self._dotoolc_path = shutil.which("dotoolc")
        if not self._dotoolc_path:
            # Check ~/.local/bin as fallback
            import os
            local_bin = os.path.expanduser("~/.local/bin/dotoolc")
            if os.path.isfile(local_bin) and os.access(local_bin, os.X_OK):
                self._dotoolc_path = local_bin
            else:
                raise DotoolcNotFoundError(
                    "dotoolc not found in PATH or ~/.local/bin. "
                    "Install dotool: https://git.sr.ht/~geb/dotool\n"
                    "dotoolc requires dotoold running (dotool-quickstart.sh)"
                )

        self._process = await asyncio.create_subprocess_exec(
            self._dotoolc_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        self._typed_text = ""
        logger.info("Continuous dotoolc pipe opened (pid=%d)", self._process.pid)

    async def stream_type(self, text: str) -> None:
        """Push text instantly into the open dotoolc pipe.
        
        Text is written as `type <text>\n` and flushed immediately.
        Handles newlines by emitting `key enter` between lines.
        """
        if not self._process or self._process.returncode is not None:
            logger.warning("dotoolc pipe not open, restarting...")
            await self.start()

        assert self._process is not None
        assert self._process.stdin is not None

        try:
            lines = text.split("\n")
            for i, line in enumerate(lines):
                cmd = f"type {line}\n"
                self._process.stdin.write(cmd.encode("utf-8"))
                if i < len(lines) - 1:
                    self._process.stdin.write(b"key enter\n")

            await self._process.stdin.drain()
            self._typed_text += text
        except Exception as e:
            logger.error("Failed to stream text to dotoolc: %s", e)
            raise

    async def stream_backspace(self, count: int) -> None:
        """Backspace `count` characters via the dotoolc pipe."""
        if not self._process or not self._process.stdin:
            return
        try:
            for _ in range(count):
                self._process.stdin.write(b"key backspace\n")
            await self._process.stdin.drain()
            self._typed_text = self._typed_text[:-count]
        except Exception as e:
            logger.error("Failed to stream backspaces to dotoolc: %s", e)

    async def stream_diff(self, new_text: str) -> None:
        """Diff the new text against the previously typed text and send only
        the necessary corrections (backspaces + new suffix).
        
        This is the nerd-dictation incremental typing algorithm:
        1. Find common prefix length between old and new text
        2. Backspace the differing suffix
        3. Type only the new suffix
        """
        if new_text == self._typed_text:
            return

        old_text = self._typed_text

        # Find common prefix length
        common_len = 0
        min_len = min(len(old_text), len(new_text))
        while common_len < min_len and old_text[common_len] == new_text[common_len]:
            common_len += 1

        backspace_count = len(old_text) - common_len
        new_suffix = new_text[common_len:]

        if backspace_count > 0:
            await self.stream_backspace(backspace_count)
        if new_suffix:
            await self.stream_type(new_suffix)

    async def stop(self) -> None:
        """Close the dotoolc pipe and wait for the process to exit."""
        if self._process and self._process.stdin:
            try:
                self._process.stdin.close()
                await self._process.wait()
            except Exception:
                pass
            finally:
                logger.info("Continuous dotoolc pipe closed")
                self._process = None
                self._typed_text = ""

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def typed_text(self) -> str:
        return self._typed_text
```

#### 2. Integrate ContinuousTyper into RecordingEngine

The engine opens the dotoolc pipe when recording starts (if output_method="type"), feeds streaming text directly into it, and closes the pipe when recording stops.

In `engine.py`:

```python
from voice_to_text.typer import ContinuousTyper, DotoolcNotFoundError

class RecordingEngine:
    def __init__(self):
        ...
        self._typer: ContinuousTyper | None = None

    async def _run(self, config: dict[str, Any]) -> None:
        """Full recording + transcription pipeline."""
        try:
            # Determine if we need typing
            output_method = config.get("output_method", "none")
            use_typing = output_method == "type"

            # 1. Open dotoolc pipe early if typing
            if use_typing:
                try:
                    self._typer = ContinuousTyper()
                    await self._typer.start()
                    logger.info("Continuous dotoolc pipe opened for recording session")
                except DotoolcNotFoundError as e:
                    logger.warning("Typing requested but dotoolc not found: %s", e)
                    if self.on_error:
                        self.on_error(f"Typing not available: {e}")
                    self._typer = None

            # 2. Activate BT headset mic if configured
            ...

            # 3. Set up providers
            ...

            # 4. Record audio with streaming transcription
            ... recording loop ...
            while not self._cancel_event.is_set():
                await asyncio.sleep(0.02)
                if self.on_audio_level:
                    self.on_audio_level(recorder.smoothed_level)

                # Feed streaming text directly into dotoolc pipe
                if transcriber and self._typer:
                    partial = await transcriber.on_audio_chunk(chunk)
                    if partial:
                        # Incremental diff: backspace + retype only what changed
                        await self._typer.stream_diff(partial)

            # 5. Final transcription
            self.state = EngineState.PROCESSING
            self._notify_state()
            recorder.stop()

            if recorder.filepath:
                if transcriber:
                    text = await transcriber.on_recording_stop(recorder.filepath, language)
                else:
                    text = await batch_provider.transcribe_file(recorder.filepath, language)

                # If we were streaming incrementally, the final text might be more
                # accurate than the accumulated streaming text. Just type the final
                # diff corrections.
                if text and self._typer:
                    # The incremental typing already has most of the text on screen.
                    # Diff against what we've actually typed so we only emit corrections.
                    await self._typer.stream_diff(text)

        except Exception as e:
            logger.exception("Recording failed")
            if self.on_error:
                self.on_error(str(e))
        finally:
            # Close dotoolc pipe
            if self._typer:
                await self._typer.stop()
                self._typer = None
            self.state = EngineState.IDLE
            self._notify_state()
            self._cleanup()
```

#### 3. Update D-Bus interface to accept typing config

The `StartRecording` config string gets a new key:
```json
{
  "output_method": "type",
  "provider": "voxtral",
  "language": "en",
  "mode": "hybrid",
  ...
}
```

### Key Design Decisions:

**Why `dotoolc` (not `dotool` direct)?**
- `dotoolc` is a client to `dotoold` daemon which keeps virtual input devices registered — lower latency
- `dotool` re-registers devices on every invocation — adds latency per session
- `dotoold` is already set up as a systemd user service by `dotool-quickstart.sh`
- Single `dotoolc` process per recording session, no lingering state

**Why stream directly during recording (not after)?**
- In hybrid/streaming mode, partial results arrive during recording
- Streaming them directly into dotool gives near-instant feedback on screen
- The diff algorithm corrects misrecognitions as they're refined
- When final transcription arrives, only final corrections need typing

**What about timing (keydelay/typedelay)?**
- Set `keydelay 0\ntypedelay 0\n` at the start of the pipe to eliminate delays
- Each `type` command is a single write + drain, so inter-command delay is just the pipe latency (~microseconds)

### Success Criteria:

#### Automated Verification:
- [ ] `ContinuousTyper` class imports without error
- [ ] `stream_type("hello\nworld")` produces "type hello\nkey enter\ntype world\n"
- [ ] `stream_diff` algorithm produces correct backspace counts for various inputs
- [ ] `typer.py` passes pyright

#### Manual Verification:
- [ ] `ContinuousTyper` with `dotoolc` installed and `dotoold` running:
      ```python
      typer = ContinuousTyper()
      await typer.start()
      await typer.stream_type("Hello ")  # appears immediately
      await typer.stream_diff("Hello World")  # appends "World"
      await typer.stream_diff("Hello everyone")  # backspaces "World", types "everyone"
      await typer.stop()
      ```
- [ ] Error handling when dotoolc not found gives clear, actionable error
- [ ] Persistent pipe survives large amounts of text (stress test)

---

## Phase 5: systemd + D-Bus Activation Files

### Overview
Package the service for systemd --user with D-Bus activation. When the GNOME extension calls the D-Bus method, systemd auto-starts the service.

### Changes Required:

#### 1. New file: `service/com.happytomatoe.VoiceToText.service` — D-Bus activation file

```ini
[D-BUS Service]
Name=com.happytomatoe.VoiceToText
Exec=/bin/sh -c 'exec $(command -v voice-to-text-dbus || echo $HOME/.local/bin/voice-to-text-dbus)'
User=user
```

This file goes in `/usr/share/dbus-1/services/` or `~/.local/share/dbus-1/services/`.

#### 2. New file: `service/voice-to-text.service` — systemd user unit

```ini
[Unit]
Description=Voice-to-Text D-Bus Service
After=graphical-session.target
Requires=graphical-session.target

[Service]
Type=dbus
BusName=com.happytomatoe.VoiceToText
ExecStart=%h/.local/bin/voice-to-text-dbus
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

#### 3. New file: `service/install.sh` — Installation script

```bash
#!/bin/bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
SERVICE_DIR="${HOME}/.config/systemd/user"
DBUS_SERVICE_DIR="${HOME}/.local/share/dbus-1/services"

mkdir -p "$INSTALL_DIR" "$SERVICE_DIR" "$DBUS_SERVICE_DIR"

# Install the Python package
uv tool install -e .

# Copy service files
cp service/voice-to-text.service "$SERVICE_DIR/"
cp service/com.happytomatoe.VoiceToText.service "$DBUS_SERVICE_DIR/"

# Reload systemd
systemctl --user daemon-reload

echo "Service installed. Enable with:"
echo "  systemctl --user enable --now voice-to-text.service"
```

#### 4. Update `justfile` — Add service management recipes

```justfile
# Install the D-Bus service
service-install:
    uv tool install -e .
    mkdir -p ~/.config/systemd/user ~/.local/share/dbus-1/services/
    cp service/voice-to-text.service ~/.config/systemd/user/
    cp service/com.happytomatoe.VoiceToText.service ~/.local/share/dbus-1/services/
    systemctl --user daemon-reload
    systemctl --user enable --now voice-to-text.service

service-status:
    systemctl --user status voice-to-text.service

service-logs:
    journalctl --user -u voice-to-text.service -f

service-stop:
    systemctl --user stop voice-to-text.service

service-restart:
    systemctl --user restart voice-to-text.service
```

#### 5. Update `install.sh` — Root install script

Replace the Python CLI installation with the service installation.

### Success Criteria:

#### Automated Verification:
- [ ] Service files are syntactically valid: `systemd-analyze verify service/voice-to-text.service`
- [ ] D-Bus service file has correct format

#### Manual Verification:
- [ ] `systemctl --user enable --now voice-to-text.service` starts the service
- [ ] `busctl --user list | grep com.happytomatoe` shows the service
- [ ] `systemctl --user stop voice-to-text.service` stops cleanly
- [ ] D-Bus activation works: kill the service, call a method, service auto-restarts
- [ ] Service survives user session restart
- [ ] Service restarts on crash

---

## Phase 6: Update GNOME Extension to Use D-Bus

### Overview
Replace `Recorder.js` (subprocess spawning + stdout protocol parsing) with direct D-Bus calls via `Gio.DBusProxy`. The extension becomes a thin client that calls the service and handles UI.

### Changes Required:

#### 1. `gnome-ext/extension.js` — Replace subprocess with D-Bus proxy

```javascript
// Remove: GLib.find_program_in_path('voice-to-text')
// Remove: Recorder import and instantiation
// Add: Gio.DBusProxy for com.happytomatoe.VoiceToText

const VoiceToTextIface = `
<node>
  <interface name="com.happytomatoe.VoiceToText">
    <method name="StartRecording">
      <arg type="s" name="config" direction="in"/>
    </method>
    <method name="StopRecording"/>
    <method name="GetStatus">
      <arg type="s" direction="out"/>
    </method>
    <signal name="AudioLevel">
      <arg type="d" name="level"/>
    </signal>
    <signal name="Error">
      <arg type="s" name="message"/>
    </signal>
    <signal name="StateChanged">
      <arg type="s" name="state"/>
    </signal>
  </interface>
</node>`;

const VoiceToTextProxy = Gio.DBusProxy.makeProxyWrapper(VoiceToTextIface);
```

**Key changes:**
- Remove `this._binPath`, `this._recorder` subprocess management
- Replace with `this._proxy = new VoiceToTextProxy(...)`
- `_start()` calls `this._proxy.StartRecordingSync(JSON.stringify(config))` with `output_method` set to "type" (or "clipboard")
- `_stop()` calls `this._proxy.StopRecordingSync()`
- `this._proxy.connectSignal('StateChanged', ...)` updates indicator UI
- `this._proxy.connectSignal('Error', ...)` shows notification
- `this._proxy.connectSignal('AudioLevel', ...)` drives level meter
- Remove `this._stopTimeoutId` logic (D-Bus RPC is reliable, no spawn timeout needed)
- Remove retry logic (D-Bus activation handles service availability)

#### 2. `gnome-ext/recorder.js` — Remove entirely

The entire file is replaced by D-Bus proxy calls in `extension.js`.

#### 3. `gnome-ext/typer.js` — Remove entirely

Typing has moved to the Python service via the continuous dotoolc pipe (`ContinuousTyper` in `src/voice_to_text/typer.py`). The extension no longer needs to:
- Spawn dotoolc or manage typing queues
- Implement the nerd-dictation diff algorithm
- Track `_lastTyped` state

All of this is handled by the service. The extension's role is just to call `StartRecording` with the appropriate `output_method` ("type" or "clipboard") and the service handles typing via dotoolc or clipboard via `wl-copy`/`xclip` internally. The extension only needs the `StateChanged`, `AudioLevel`, and `Error` signals for UI updates.

#### 4. Update `extension.js` signal wiring

```javascript
_start() {
    if (this._recording) return;

    this._indicator.setProcessing();
    this._recording = true;

    const config = {
        provider: this._settings.get_string('provider'),
        language: this._settings.get_string('language'),
        mode: this._settings.get_string('mode'),
        streaming_provider: this._settings.get_string('streaming-provider'),
        batch_provider: this._settings.get_string('batch-provider'),
        decrease_speaker_volume: this._settings.get_int('decrease-speaker-volume'),
        output_method: this._settings.get_string('output-method'),
    };

    this._proxy.StartRecordingSync(JSON.stringify(config));
    this._ensureInhibitor();
}
```

### Success Criteria:

#### Manual Verification:
- [ ] Extension connects to D-Bus service without errors
- [ ] Recording starts via D-Bus method call
- [ ] Audio level meter updates in real time from D-Bus signals
- [ ] Text is typed into the active window (type output method)
- [ ] Text is copied to clipboard (clipboard output method)
- [ ] Error handling works — service crash shows notification
- [ ] No subprocess spawning in the extension anymore
- [ ] Extension works without Python binary in PATH (service runs via D-Bus)

---

## Testing Strategy

### Unit Tests (Phase 2 & 4):
- Provider tests: mock httpx/websockets responses, test async transcribe_file methods
- `ContinuousTyper` tests: verify correct stream_type/stream_backspace/stream_diff output
- Diff algorithm tests: verify correct backspace counts and suffix for various inputs

### Integration Tests (Phase 3):
- D-Bus service start/stop lifecycle
- Engine state machine transitions (idle→recording→processing→idle)
- Signal emission on state changes

### Manual Testing (All Phases):
- Full cycle: call StartRecording → wait → StopRecording → verify StateChanged transitions (idle→recording→processing→idle)
- BT headset HSP/HFP switching during recording
- Speaker volume decrease/restore
- Typing via dotoolc into various applications
- Error cases: no API key, no microphone, provider timeout
- Extension UI: level meter, progress indicator, stop button

## Performance Considerations

- **D-Bus overhead:** Negligible for audio levels (10-50Hz) and text results (once per recording)
- **Audio latency:** `sd.AsyncInputStream` adds no measurable latency vs synchronous
- **Provider calls:** httpx async is slightly faster than requests under concurrency
- **Typing latency:** dotoolc adds ~2ms per key (configurable via keydelay); diff algorithm ensures minimal keystrokes
- **Service memory:** ~50MB for Python runtime + provider SDKs

## Migration Notes

1. **Existing users** will need to:
   - Reinstall via updated install.sh (or manually enable systemd service)
   - Update the GNOME extension (via normal extension update path)
   - The D-Bus service will need `dotoold` running for type output (already handled by dotool-quickstart.sh)

2. **Backwards compatibility:** The old `voice-to-text` CLI command is removed. Users relying on CLI must switch to the extension or write a thin D-Bus client.

3. **Development workflow:**
   - Run service manually: `python -m voice_to_text.__main__`
   - Test with `busctl` commands
   - Debug with logs at `/tmp/voice-to-text-service.log`

## References

- dbus-next documentation: https://dbus-next.readthedocs.io/
- httpx async guide: https://www.python-httpx.org/async/
- websockets library: https://websockets.readthedocs.io/
- dotool source: https://git.sr.ht/~geb/dotool
- Existing streaming WebSocket base: `src/voice_to_text/providers/base.py`
- Existing diff typing algorithm: `gnome-ext/typer.js`
- Existing BT headset code: `src/voice_to_text/bluetooth.py`
