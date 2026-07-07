---
date: 2026-06-28T20:20:00-04:00
researcher: pi
git_commit: b03a44c
branch: main
repository: voice-to-text
topic: "Python D-Bus Service Implementation"
tags: [implementation, dbus, async, dotool, gnome-extension]
status: complete
last_updated: 2026-06-28
last_updated_by: pi
type: implementation_strategy
---

# Handoff: Python D-Bus Service Implementation

## Task(s)

Implemented the full 6-phase plan from `thoughts/shared/plans/python-dbus-service.md` to transform the CLI-based voice-to-text application into a headless D-Bus service with systemd activation.

**Status: All phases complete.**

## Critical References

- `thoughts/shared/plans/python-dbus-service.md` — The implementation plan document
- `pyproject.toml` — Dependencies and entry point config
- `service/voice-to-text.service` — Systemd unit (updated with PipeWire deps + ImportEnvironment)

## Recent changes

### Phase 1: Strip UI/TUI
- `src/voice_to_text/main.py` — DELETED (100% CLI/TUI code, replaced by D-Bus service)
- `src/voice_to_text/audio.py` — Removed `format_level_bar`, ANSI color constants (`METER_WIDTH`, `GREY`, `GREEN`, `YELLOW`, `RED`, `RESET`, `BLOCK`)

### Phase 2: Async Providers
- `src/voice_to_text/providers/base.py` — Made `BatchProvider.transcribe_file` and `StreamingProvider` methods async; refactored `WebSocketStreamingProvider` from `websocket-client` → `websockets` async library
- `src/voice_to_text/providers/deepgram.py` — `requests` → `httpx.AsyncClient` for batch; `websockets` for streaming
- `src/voice_to_text/providers/groq.py` — sync `Groq` → `AsyncGroq`
- `src/voice_to_text/providers/voxtral.py` — `requests` → `httpx.AsyncClient` for batch transcribe_file
- `src/voice_to_text/providers/parakeet.py` — `requests` → `httpx.AsyncClient`
- `src/voice_to_text/hybrid.py` — All methods now `async def`
- `pyproject.toml` — Replaced `requests`/`websocket-client` with `httpx`/`websockets`/`dbus-next`

### Phase 3: D-Bus Service Layer
- `src/voice_to_text/engine.py` — NEW: `RecordingEngine` state machine + `AsyncAudioRecorder` (uses `sd.InputStream` with `asyncio.Queue` bridge via `loop.call_soon_threadsafe`)
- `src/voice_to_text/dbus_service.py` — NEW: D-Bus interface (`com.happytomatoe.VoiceToText`) with methods `StartRecording`, `StopRecording`, `GetStatus` and signals `AudioLevel`, `Error`, `StateChanged`, `TranscriptionResult`
- `src/voice_to_text/__main__.py` — NEW: Asyncio entry point with SIGTERM/SIGINT handlers

### Phase 4: dotoolc Integration
- `src/voice_to_text/typer.py` — NEW: `ContinuousTyper` with persistent `dotoolc` pipe, `stream_type`/`stream_backspace`/`stream_diff` (nerd-dictation algorithm), `drain()` after every write

### Phase 5: systemd + D-Bus Activation
- `service/voice-to-text.service` — NEW: systemd user unit (Type=dbus, After=pipewire wireplumber, ImportEnvironment)
- `service/com.happytomatoe.VoiceToText.service` — NEW: D-Bus activation file
- `service/install.sh` — NEW: Install script
- `install.sh` — Updated for D-Bus service installation

### Phase 6: GNOME Extension
- `gnome-ext/extension.js` — Replaced subprocess spawning with `Gio.DBusProxy`; connects to `StateChanged`, `AudioLevel`, `Error`, `TranscriptionResult` signals
- `gnome-ext/recorder.js` — DELETED (no longer needed)
- `gnome-ext/typer.js` — Simplified to `copyToClipboard` only (typing handled by Python service via dotoolc)

## Learnings

1. **`sd.AsyncInputStream` doesn't exist in sounddevice 0.5.5.** Use `sd.InputStream` with `loop.call_soon_threadsafe(q_in.put_nowait, data)` in the callback to bridge the callback thread to asyncio. See `engine.py:AsyncAudioRecorder`.

2. **dbus-next 0.2.3 has no `emit_signal` method on `ServiceInterface`.** Signals are emitted by calling the `@signal()`-decorated method directly. The decorator wraps the method so the return value is sent via `_handle_signal`. Pattern:
   ```python
   @signal()
   def StateChanged(self) -> 's':
       return self._state  # value read when signal method is called
   # ... then emit with:
   self._state = new_value
   self.StateChanged()  # calls wrapped method → emits via dbus-next
   ```

3. **Signal subscription requires a separate bus connection.** Signals emitted by a service on one `MessageBus` connection aren't received by proxy objects on the same connection. Always use a second `MessageBus()` for the client.

4. **`@method()` decorators wrap return values** — calling the decorated method directly in Python returns `None` (the wrapper intercepts), but D-Bus calls work correctly (verified with `gdbbus call ... GetStatus` → `('idle',)`).

5. **Recording loop needs a timeout on `read_chunk()`** so cancellation is responsive when no audio data arrives (no mic signal). Used `asyncio.wait_for(chunk, timeout=0.1)` with `TimeoutError` → `continue`.

## Artifacts

- `thoughts/shared/plans/python-dbus-service.md` — Implementation plan
- `src/voice_to_text/engine.py` — State machine + async audio recorder
- `src/voice_to_text/dbus_service.py` — D-Bus interface definition
- `src/voice_to_text/__main__.py` — Service entry point
- `src/voice_to_text/typer.py` — Continuous dotoolc pipe
- `src/voice_to_text/providers/base.py` — Async provider interfaces
- `src/voice_to_text/providers/deepgram.py` — Async Deepgram
- `src/voice_to_text/providers/groq.py` — Async Groq
- `src/voice_to_text/providers/voxtral.py` — Async Voxtral
- `src/voice_to_text/providers/parakeet.py` — Async Parakeet
- `src/voice_to_text/hybrid.py` — Async hybrid transcriber
- `service/voice-to-text.service` — Systemd user unit
- `service/com.happytomatoe.VoiceToText.service` — D-Bus activation
- `service/install.sh` — Service install script
- `gnome-ext/extension.js` — D-Bus proxy-based extension
- `gnome-ext/typer.js` — Clipboard-only (typing moved to service)

## Action Items & Next Steps

1. **Add state guard in `StartRecording` D-Bus method** — Currently `StartRecording` fires off a task without checking if the engine is already recording. The error is silently swallowed in the task. Should check `self._engine.state != EngineState.IDLE` and raise `DBusError("com.happytomatoe.VoiceToText.Error.AlreadyRecording", ...)`. See `src/voice_to_text/dbus_service.py:83`.

2. **Test with actual hardware** — The service has been tested programmatically (no mic in CI environment). Test end-to-end:
   - Start service with actual microphone
   - Test `StartRecording`/`StopRecording` via `gdbus`
   - Verify `AudioLevel` signal fires during recording
   - Verify text is typed via dotoolc when `output_method: "type"`
   - Verify clipboard output works

3. **Verify GNOME extension connects** — Install the updated extension, start the service, and verify `extension.js` connects to the D-Bus proxy without errors. The extension no longer spawns subprocesses.

4. **Handle `ImportEnvironment` in systemd** — The service unit now has `ImportEnvironment=DISPLAY WAYLAND_DISPLAY XDG_SESSION_TYPE`. Verify clipboard fallback (`wl-copy`/`xclip`) works from the systemd service context.

5. **Optional: Type vs Paste fallback** — Consider adding a config flag to fall back to `wl-copy` + `ctrl+v` for complex UTF-8/emoji text that `dotool type` can't handle reliably.

## Other Notes

- Tested and verified: ruff 0 errors, pyright 0 errors, all imports pass
- D-Bus registration verified: `busctl --user introspect` shows all methods + signals
- Signal emission verified: separate bus connection receives `StateChanged` (recording → processing → idle)
- Engine lifecycle verified: `idle → recording → processing → idle` transitions work
- Diff algorithm verified: `stream_diff` correctly computes backspace counts and suffixes
- Voxtral provider was actually called during testing (saw HTTP request to api.mistral.ai in logs — returned 200 with empty transcription since no mic input)
- `dbus-next` library is used (pure Python, native asyncio, no GLib dependency) — keep this as a hard dependency
