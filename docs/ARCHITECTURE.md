# Voice-to-Text Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GNOME Shell                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Extension (extension.js)                                   │   │
│  │  - UI: microphone icon in top bar                           │   │
│  │  - Hotkey listener                                          │   │
│  │  - Sends config over D-Bus                                  │   │
│  └─────────────────────────┬───────────────────────────────────┘   │
│                            │ D-Bus (session bus)                    │
└────────────────────────────┼───────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  D-Bus Service (__main__.py + dbus_service.py)                      │
│  - Exposes: StartRecording, StopRecording, GetStatus                │
│  - Emits signals: AudioLevel, StateChanged, Error, TranscriptionResult │
│  - Runs as systemd user service                                     │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  RecordingEngine (engine.py)                                        │
│  - State machine: idle → recording → processing → idle              │
│  - Orchestrates: audio recording, transcription, output             │
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐                      │
│  │ AsyncAudioRecorder│    │ Output Methods   │                      │
│  │ (sd.InputStream)  │    │ - dotoolc (type) │                      │
│  │ Records mic audio │    │ - clipboard      │                      │
│  │ to WAV file       │    │ - none           │                      │
│  └────────┬─────────┘    └──────────────────┘                      │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Transcription                                                │   │
│  │  - Batch: send WAV file to API, get text back                 │   │
│  │  - Streaming: real-time audio → text via WebSocket            │   │
│  │  - Hybrid: streaming for partials, batch for final            │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. GNOME Extension (`gnome-ext/extension.js`)

**What it is:** A GNOME Shell extension that provides the user interface.

**Responsibilities:**
- Shows microphone icon in the top bar
- Listens for hotkey (configurable)
- Sends `StartRecording` / `StopRecording` commands over D-Bus
- Receives `AudioLevel`, `StateChanged`, `Error`, `TranscriptionResult` signals
- Manages sleep inhibitor (prevents suspend during recording)

**Key state:** `_recording` (boolean) — tracks whether a recording session is active.

### 2. D-Bus Service (`src/voice_to_text/__main__.py` + `dbus_service.py`)

**What it is:** A systemd user service that bridges GNOME Shell (D-Bus) to the Python engine.

**Responsibilities:**
- Listens on session bus for `com.happytomatoe.VoiceToText`
- Exposes methods: `StartRecording(config_json)`, `StopRecording()`, `GetStatus()`
- Emits signals: `AudioLevel(float)`, `StateChanged(string)`, `Error(string)`, `TranscriptionResult(string)`
- Manages lifecycle (startup, shutdown on SIGTERM)

**Interface:**
```
Service:    com.happytomatoe.VoiceToText
ObjectPath: /com/happytomatoe/VoiceToText
Bus:        session
```

### 3. RecordingEngine (`src/voice_to_text/engine.py`)

**What it is:** The core state machine that orchestrates recording and transcription.

**State machine:**
```
         StartRecording()
               │
               ▼
    ┌─────── IDLE ◄──────────────┐
    │          │                  │
    │          │ start()          │ stop() or done
    │          ▼                  │
    │     RECORDING ──────────────┤
    │          │                  │
    │          │ recorder.stop()  │
    │          ▼                  │
    │     PROCESSING ─────────────┘
    │          │
    │          │ transcription done
    └──────────┘
```

**Responsibilities:**
- Manages `AsyncAudioRecorder` (microphone → WAV file)
- Manages transcription providers (batch/streaming/hybrid)
- Manages output (typing via dotoolc, clipboard, or none)
- Emits state changes and transcription results via callbacks

### 4. AsyncAudioRecorder (`src/voice_to_text/engine.py`)

**What it is:** Records audio from the microphone using `sounddevice.InputStream`.

**How it works:**
```
┌─────────────────┐      ┌──────────────┐      ┌─────────────┐
│ sd.InputStream   │      │ asyncio.Queue│      │ WAV File    │
│ (callback thread)│ ───► │ (maxsize=100)│ ───► │ (on disk)   │
│                  │      │              │      │             │
│ Puts raw audio   │      │ Consumer     │      │ Written by  │
│ chunks into queue│      │ reads chunks │      │ callback    │
└─────────────────┘      └──────────────┘      └─────────────┘
```

**Key details:**
- Sample rate: 16kHz, mono, 16-bit
- Block size: 2048 samples (~128ms per chunk)
- Queue maxsize: 100 chunks (~400KB, ~12.8 seconds of audio)
- If queue is full, audio frames are dropped (graceful degradation)

### 5. Transcription Providers

**Batch providers** — send complete WAV file, get text back:

| Provider | API | Notes |
|----------|-----|-------|
| `voxtral.py` | Mistral API | Also supports streaming |
| `deepgram.py` | Deepgram API | Also supports streaming |
| `parakeet.py` | Local Parakeet | Runs locally via HTTP |
| `groq.py` | Groq API | Fast inference |

**Streaming providers** — real-time audio → text via WebSocket:

| Provider | Protocol | Notes |
|----------|----------|-------|
| `deepgram.py` | WebSocket | Deepgram Nova-3 |
| `voxtral.py` | Mistral SDK | Mistral Voxtral |

**Hybrid mode** (`hybrid.py`) — uses streaming for partial results, batch for final:

```
┌─────────────────┐      ┌─────────────────┐
│ Streaming Provider│      │ Batch Provider   │
│ (Deepgram/Voxtral)│      │ (Voxtral)        │
│                  │      │                  │
│ Real-time partials│      │ Final accuracy   │
└────────┬────────┘      └────────┬────────┘
         │                        │
         ▼                        ▼
┌─────────────────────────────────────────────┐
│ HybridTranscriber                            │
│ - Sends audio to streaming for partials      │
│ - On stop, sends WAV to batch for final      │
│ - Returns merged result                      │
└─────────────────────────────────────────────┘
```

### 6. Output Methods

| Method | Implementation | How it works |
|--------|----------------|--------------|
| `type` | `typer.py` (dotoolc) | Types text via virtual keyboard using `dotoolc` daemon |
| `clipboard` | `wl-copy`/`xclip`/`xsel` | Copies text to system clipboard |
| `type-fallback-clipboard` | Both | Tries typing, falls back to clipboard if dotoolc unavailable |
| `none` | — | No output (just logs) |

**dotoolc typing flow:**
```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ ContinuousTyper│      │ dotoolc pipe │      │ dotoold      │
│              │ ───► │ (stdin)      │ ───► │ (daemon)     │
│              │      │              │      │              │
│ stream_diff()│      │ type ...\n   │      │ Virtual      │
│ backspace()  │      │ key backspace│      │ keyboard     │
└──────────────┘      └──────────────┘      └──────────────┘
```

## Data Flow: Recording Session

```
1. User clicks microphone icon
         │
         ▼
2. Extension sends StartRecording(config) over D-Bus
         │
         ▼
3. D-Bus service calls engine.start(config)
         │
         ▼
4. Engine opens dotoolc pipe (if typing)
         │
         ▼
5. Engine starts AsyncAudioRecorder
   - Opens WAV file
   - Starts sd.InputStream
   - Audio callback puts chunks in queue
         │
         ▼
6. Engine reads chunks from queue
   - If streaming: sends chunks to streaming provider
   - If typing: sends partial text to dotoolc via stream_diff()
   - Emits AudioLevel signal for UI
         │
         ▼
7. User clicks stop (or hotkey)
         │
         ▼
8. Extension sends StopRecording over D-Bus
         │
         ▼
9. Engine stops recorder
   - Closes sd.InputStream
   - Closes WAV file
   - Puts None sentinel in queue
         │
         ▼
10. Engine transcribes final result
    - If streaming: gets final text from streaming provider
    - If batch: sends WAV to batch provider
    - If hybrid: sends WAV to batch for final accuracy
         │
         ▼
11. Engine outputs result
    - If typing: applies final corrections via stream_diff()
    - If clipboard: copies text to clipboard
         │
         ▼
12. Engine emits TranscriptionResult signal
    - Extension receives text (for logging/notification)
         │
         ▼
13. Engine cleans up
    - Closes dotoolc pipe
    - Deletes temp WAV file
    - Sets state to IDLE
```

## Key Design Decisions

1. **D-Bus as IPC:** GNOME extensions can't import Python modules, so D-Bus is the bridge.

2. **Async throughout:** The engine uses `asyncio` for non-blocking I/O. Audio recording uses a callback thread + queue to bridge into async.

3. **Hybrid mode:** Combines streaming (for instant feedback) with batch (for accuracy). User sees partial text while recording, gets corrected final text on stop.

4. **dotoolc for typing:** Uses a persistent pipe to the `dotoolc` daemon for low-latency virtual keyboard input. Avoids re-registering input devices on each keystroke.

5. **Graceful degradation:** If dotoolc is unavailable, falls back to clipboard. If queue is full, drops audio frames. If transcription fails, reports error to user.
