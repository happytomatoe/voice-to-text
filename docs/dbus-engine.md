# D-Bus Engine Architecture

## Overview

The voice-to-text project uses D-Bus as the inter-process communication (IPC) layer between a **GNOME Shell extension** (the user-facing UI) and a **Python backend** (the recording/transcription engine). This decouples the UI from the audio hardware and network-dependent processing, allowing them to run in separate processes.

```
┌─────────────────────────┐     D-Bus      ┌──────────────────────────┐
│  GNOME Shell Extension  │◄──────────────►│  Python Backend Service  │
│  (GJS / Gio.DBusProxy)  │   session bus   │  (dbus-next / asyncio)   │
└─────────────────────────┘                 └──────────────────────────┘
```

---

## Architecture Layers

### 1. GNOME Shell Extension (`gnome-ext/extension.js`)

- Runs in GNOME Shell's GJS runtime (Mozilla SpiderMonkey JavaScript)
- Provides a **panel indicator** with recording state, audio level visualization, and start/stop controls
- Listens for a **configurable hotkey** (e.g., Super+V) to toggle recording
- Uses `Gio.DBusProxy` to make D-Bus method calls and receive signals
- Also manages a **GNOME SessionManager inhibitor** to prevent sleep during recording

### 2. D-Bus (Session Bus)

- The **session bus** (not system bus) — each user has their own session bus
- Well-known name: `com.happytomatoe.VoiceToText`
- Object path: `/com/happytomatoe/VoiceToText`
- Pure Python implementation using [`dbus-next`](https://github.com/altdesktop/python-dbus-next) — no GLib or PyGObject dependency
- Async-first: all methods are dispatched on the asyncio event loop

### 3. Python Backend (`voice_to_text/` package)

- Registered as a **systemd user service** (`systemctl --user enable --now voice-to-text.service`)
- Exports the D-Bus interface and runs the recording/transcription pipeline
- Uses `sounddevice` (PortAudio bindings) for audio capture in a background thread
- Supports multiple transcription providers (Voxtral, Deepgram, Groq, Parakeet)
- Implements **batch**, **streaming**, and **hybrid** transcription modes

---

## D-Bus Interface Definition

The interface is defined in `src/voice_to_text/dbus_service.py` and exposed via `dbus-next`.

### Interface: `com.happytomatoe.VoiceToText`

**Object path:** `/com/happytomatoe/VoiceToText`  
**Bus:** Session bus

#### Methods

| Method | Input | Output | Description |
|---|---|---|---|
| `StartRecording` | `s` — JSON config string (see below for format) | — | Start recording with provider/language/mode config |
| `StopRecording` | — | — | Stop the current recording session |
| `GetStatus` | — | `s` | Return current state: `"idle"`, `"recording"`, or `"processing"` |

> **`StartRecording` config format:** Although the D-Bus type is `s` (string), the caller sends a JSON-encoded object. The GNOME extension sends all fields from its settings — here's an example of the JSON string passed over the wire:
>
> ```json
> {"provider":"voxtral","language":"en","mode":"hybrid","streaming_provider":"voxtral","batch_provider":"voxtral","decrease_speaker_volume":50,"output_method":"type","bluetooth_headset_change_to_handsfree_to_record":true}
> ```

#### Signals

| Signal | Payload | Description |
|---|---|---|
| `StateChanged` | `s` — `"idle"` / `"recording"` / `"processing"` | Emitted on every engine state transition |
| `AudioLevel` | `d` — float 0.0–1.0 | Emitted periodically during recording with smoothed RMS level |
| `Error` | `s` — error message | Emitted when recording or transcription encounters an error |

#### Error Codes (returned as DBusError)

- `com.happytomatoe.VoiceToText.Error.AlreadyRecording` — `StartRecording` called while already recording
- `com.happytomatoe.VoiceToText.Error.InvalidConfig` — invalid JSON or missing required fields

### XML Introspection

```xml
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
</node>
```

---

## Component Breakdown

### 1. Service Entry Point (`__main__.py`)

```python
async def run_service() -> None:
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    interface = VoiceToTextInterface()
    interface.set_bus(bus)
    bus.export(OBJECT_PATH, interface)
    await bus.request_name(SERVICE_NAME)
    # Wait for SIGTERM/SIGINT...
```

Responsibilities:
- Connects to the user's **session bus**
- Creates the `VoiceToTextInterface` and exports it at the object path
- Requests the well-known name (auto-replaces stale instances)
- Listens for `SIGTERM`/`SIGINT` and gracefully stops the engine before disconnecting

### 2. D-Bus Interface (`dbus_service.py`)

The `VoiceToTextInterface` class extends `dbus_next.service.ServiceInterface` and:

- **Wraps the `RecordingEngine`** — delegates `StartRecording` and `StopRecording` to it
- **Parses the JSON config** in `StartRecording` before passing it to the engine
- **Bridges engine callbacks to D-Bus signals** — wires up `on_audio_level`, `on_error`, `on_state_change`, `on_transcription_result` to their corresponding `@signal()`-decorated methods
- **Validates state** — rejects `StartRecording` if not idle (raises `DBusError`)

**Signal wiring pattern:**

```python
# Engine callback → stash value → dbus-next emits @signal() return value
def _on_level(level: float):
    self._last_level = level
    self.AudioLevel()   # dbus-next rewrites this to emit the signal

@signal()
def AudioLevel(self) -> "d":
    return self._last_level  # value read at signal-emission time
```

### 3. Recording Engine (`engine.py`)

The `RecordingEngine` is the core orchestrator. It runs as an `asyncio.Task` and manages:

**State machine:**

```
  ┌─────────┐   StartRecording()   ┌───────────┐
  │  IDLE   │ ───────────────────► │ RECORDING │
  └────▲────┘                      └─────┬─────┘
       │                           audio stops,
       │                         transcription starts
       │                                │
       │                          ┌─────▼──────┐
       │      stop/finish         │ PROCESSING │
       └──────────────────────────┘            ┘
```

**Key components inside `_run()`:**

1. **Output setup** — opens a `ContinuousTyper` pipe to `dotoolc` if `output_method` is `"type"` or `"type-fallback-clipboard"`
2. **Bluetooth activation** — calls `activate_headset_mic()` to switch a Bluetooth headset to HSP/HFP profile
3. **Provider setup** — initializes the configured batch and/or streaming providers
4. **Recording** — starts `AsyncAudioRecorder` (see below), feeds audio chunks to the transcriber
5. **Transcription** — finalizes the stream or runs batch transcription
6. **Output** — types the text via `dotoolc` or copies to clipboard

### 4. AsyncAudioRecorder (`engine.py`)

Bridges the synchronous `sounddevice` threading world into asyncio:

```
sd.InputStream callback thread          asyncio event loop
┌──────────────────────────┐     ┌──────────────────────────┐
│  _audio_callback(indata) │────►│  Queue.put_nowait(raw)   │
│  - writes to .wav file   │     │  read_chunk() awaits     │
│  - computes RMS level    │     │  consumer loops          │
└──────────────────────────┘     └──────────────────────────┘
```

- Uses `loop.call_soon_threadsafe` to safely enqueue audio chunks into an `asyncio.Queue`
- Records to a **temporary WAV file** on disk for batch transcription
- Applies exponential smoothing to the audio level for the `AudioLevel` signal
- The consumer checks a cancellation event with a 0.1s timeout for responsive stop

### 5. HybridTranscriber (`hybrid.py`)

Combines a **streaming provider** (real-time partial results during recording) with a **batch provider** (high-quality final transcription):

```
Recording → streaming.send_audio(chunk) → get_partial_result() → display/type live
                                                                    │
Recording stops → batch.transcribe_file(wav)  ←──────────────────── final text
                 ↑ fallback if batch fails: streaming.finalize_stream()
```

- `on_audio_chunk(chunk)` — sends to streaming provider, returns partial text for live display/typing
- `on_recording_stop(path)` — first finalizes the streaming session, then runs batch transcription for better accuracy

### 6. Provider System (`providers/`)

```
providers/
├── __init__.py    # Factory functions: get_batch_provider(), get_streaming_provider()
├── base.py        # Abstract base classes: BatchProvider, StreamingProvider
├── deepgram.py    # Deepgram SDK (streaming + batch)
├── groq.py        # Groq Whisper API (batch only)
├── parakeet.py    # Local NVIDIA Parakeet via HTTP (batch only)
└── voxtral.py     # Mistral Voxtral API (streaming + batch)
```

**Three modes controlled by config:**

| Mode | Streaming Provider | Batch Provider | Use Case |
|---|---|---|---|
| `batch` | — | ✓ | Record first, then transcribe. Highest quality. |
| `streaming` | ✓ | — | Live text as you speak, no final correction. |
| `hybrid` | ✓ | ✓ | Live text + final batch correction. Best of both. |

### 7. GNOME Extension (`gnome-ext/extension.js`)

The client-side D-Bus proxy:

```javascript
const VoiceToTextProxy = Gio.DBusProxy.makeProxyWrapper(VoiceToTextIface);
this._proxy = new VoiceToTextProxy(
    Gio.DBus.session,
    'com.happytomatoe.VoiceToText',
    '/com/happytomatoe/VoiceToText'
);
```

**Signal connections:**

```javascript
this._proxy.connectSignal('StateChanged', (proxy, name, [state]) => {
    if (state === 'recording') this._indicator.setRecordingActive();
    else if (state === 'idle')   this._indicator.setRecording(false);
});
this._proxy.connectSignal('AudioLevel', (proxy, name, [level]) => {
    this._indicator.updateLevel(level);
});
```

**Additional GNOME Shell features:**
- **Sleep inhibitor** — prevents suspend while recording via `org.gnome.SessionManager.Inhibit`
- **Notifications** — shows recording status and errors via `MessageTray`
- **Hotkey registration** — configurable via GNOME Settings (Super+V by default)

---

## Data Flow: A Complete Recording Session

```
GNOME Extension                    D-Bus                     Python Backend
─────────────────                  ─────                     ──────────────

1. User presses hotkey
   or clicks "Record"
        │
        ▼
   _start()
        │
        ├── Set config from
        │   GNOME settings
        │   (provider, language,
        │    mode, output method...)
        │
        ├── proxy.StartRecordingAsync(jsonConfig) ──────►
        │                                                  │
        │                                            VoiceToTextInterface
        │                                            .StartRecording(config)
        │                                                  │
        │                                            Parse JSON config
        │                                                  │
        │                                            engine.start(config)
        │                                                  │
        │                                            ┌─────▼──────┐
        │                                            │  RECORDING │
        │                                            └─────┬──────┘
        │                                                  │
        │◄──────────────────── StateChanged("recording") ──┤
        │                                                  │
   setRecordingActive()                              AsyncAudioRecorder
        │                                           starts sd.InputStream
        │                                                  │
   ┌────┴────┐                                      ┌─────▼──────┐
   │ Ongoing │── AudioLevel(0.0..1.0) ──────────────►│ Audio      │
   │ audio   │── AudioLevel(0.0..1.0) ──────────────►│ capture    │
   │ meter   │        ... every chunk ...            │ + chunks   │
   │ update  │                                      │ + .wav     │
   └─────────┘                                      └─────┬──────┘
                                                          │
                                       streaming.send_audio(chunk)
                                       streaming.get_partial_result()
                                                          │
                                        For "type" mode: ContinuousTyper
                                        types partial text dotoolc keystrokes
                                                          │
2. User presses hotkey
   or clicks "Stop"
        │
        ▼
   _stop()
        │
        ├── proxy.StopRecordingSync() ─────────────────►
        │                                                │
        │                                          engine.stop()
        │                                                │
        │                                          _cancel_event.set()
        │                                          await task completes
        │                                                │
        │                                          ┌──────────┐
        │                                          │PROCESSING│
        │                                          └────┬─────┘
        │                                                │
        │                                          transcriber
        │                                          .on_recording_stop(
        │                                            audio_path)
        │                                                │
        │                                    ┌───────────┴──────────┐
        │                                    │ batch / hybrid       │
        │                                    │ transcribe .wav file │
        │                                    └───────────┬──────────┘
        │                                                │
        │◄──────────────── TranscriptionResult(text) ────┤
        │                                                │
   (notification)                                  output_method:
        │                                           type → dotoolc
        │                                           clipboard → wl-copy
        │◄──────────────── StateChanged("idle") ────────┤
        │                                                │
   setRecording(false)                             ──── IDLE ────
```

---

## Configuration Format (JSON)

Passed as the string argument to `StartRecording`:

```json
{
  "provider": "voxtral",
  "language": "en",
  "mode": "batch",
  "streaming_provider": "voxtral",
  "batch_provider": "voxtral",
  "device": null,
  "decrease_speaker_volume": 50,
  "output_method": "type"
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | string | `"voxtral"` | Batch provider name |
| `language` | string | `"en"` | Language code |
| `mode` | string | `"batch"` | `"batch"`, `"streaming"`, or `"hybrid"` |
| `streaming_provider` | string | from config | Provider for streaming mode |
| `batch_provider` | string | from config | Provider for batch transcription |
| `device` | int or null | `null` | Audio device index (null = default) |
| `decrease_speaker_volume` | int | 50 | 0–100: speaker attenuation during recording |
| `bluetooth_headset_change_to_handsfree_to_record` | bool | `true` | Auto-switch Bluetooth headset to HSP/HFP mic mode |
| `output_method` | string | `"none"` | `"type"`, `"type-fallback-clipboard"`, `"clipboard"`, or `"none"` |

---

## Deployment

The Python backend is deployed as a **systemd user service**:

```ini
# ~/.config/systemd/user/voice-to-text.service
[Unit]
Description=Voice-to-Text D-Bus Service

[Service]
ExecStart=%h/.local/bin/voice-to-text-dbus
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now voice-to-text.service
```

The GNOME extension is installed separately and connects to the service at runtime. If the service isn't running, the extension shows a notification with the systemd command.

---

## How D-Bus Signals Flow (dbus-next Internals)

The `dbus-next` library's `@signal()` decorator rewrites a method call like `self.AudioLevel()` into `self._handle_signal("AudioLevel", (return_value,))`, which serializes the signal and sends it on the bus.

```
                    dbus-next (Python)                    dbus-daemon              GNOME (GJS)
                    ─────────────────                    ──────────              ───────────

engine callback
     │
     ▼
self._last_level = level ①     │                           │                       │
self.AudioLevel()           ②  │                           │                       │
     │                          │                           │                       │
     ▼                          │                           │                       │
@signal() returns level     ③  │                           │                       │
     │                          │                           │                       │
     ▼                          │                           │                       │
_handle_signal()             ④  │                           │                       │
     │                          │                           │                       │
     ▼                          │                           │                       │
Message.signal() →             │                           │                       │
  bus.send() (writes to        │                           │                       │
  socket, non-blocking)     ⑤  │                           │                       │
     │                          │                           │                       │
     │    ──────────────────────┼─────────────────────────► │                       │
     │                          │         ⑥                │                       │
     │                          │                           │   read socket          │
     │                          │                           │   ──────────►          │
     │                          │                           │   ⑦                   │
     │                          │                           │                       │
     │                          │                           │   callback(proxy,      │
     │                          │                           │     name, [level])  ⑧ │
     │                          │                           │                       │
     │                          │                           │   this._indicator      │
     │                          │                           │     .updateLevel(lvl)  │
```

1. Engine callback fires with a new audio level
2. `self._last_level` is stashed, `self.AudioLevel()` called
3. The `@signal()` decorator causes dbus-next to read `self._last_level`
4. The return value is wrapped in a `Message` of type `signal`
5. `bus.send()` writes to the bus socket (non-blocking)
6. `dbus-daemon` receives, validates, and forwards the signal
7. The GNOME client's `Gio.DBusProxy` reads the signal on the next GLib main-loop iteration
8. The signal callback is invoked with `[level]`

**Note:** Because `dbus-next` signal emission is non-blocking and the actual I/O completes on a subsequent event-loop tick, there is a small **propagation delay** (~1 event-loop iteration). The test suite accounts for this with a `_SIGNAL_WAIT = 0.05s` sleep.

---

## Testing Strategy

The test suite (`tests/test_dbus_service.py`) tests the D-Bus layer **in isolation**:

- Spins up a **private `dbus-daemon`** (no interaction with the real session bus)
- Connects both the service and a client proxy to that private bus
- Uses a `MockRecordingEngine` that records method calls and fires callbacks directly
- Tests three categories:
  - **Methods**: `GetStatus`, `StartRecording`, `StopRecording` — correct return values, error handling
  - **Signals**: `StateChanged`, `AudioLevel`, `TranscriptionResult`, `Error` — delivered with correct payloads
  - **Edge cases**: double-start rejection, stop-when-idle safety, invalid JSON handling
