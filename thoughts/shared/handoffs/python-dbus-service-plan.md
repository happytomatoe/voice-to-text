---
date: 2026-06-28T19:55:20+02:00
researcher: l
git_commit: b03a44cc64cb62e0ad06492a66b52a21695b84bd
branch: main
repository: voice-to-text
topic: "Python D-Bus Service Implementation Plan"
tags: [dbus, python, async, dotool, systemd, gnome-extension]
status: in-progress
last_updated: 2026-06-28
last_updated_by: l
type: implementation_strategy
---

# Handoff: Python D-Bus Service Plan (in progress — research phase complete, plan updates partially applied)

## Task(s)

1. **Write implementation plan** for stripping UI/unnecessary elements from the Python voice-to-text application and converting it into a D-Bus service. **Status: ~90% complete** — plan written at `thoughts/shared/plans/python-dbus-service.md`, research completed, but final edits to align plan with research findings are only partially applied.

2. **Research key technical decisions** and update the plan accordingly. **Status: Complete** — research done, but plan updates are only partially applied (see "Incomplete Updates" below).

## Critical References

- **Plan document**: `thoughts/shared/plans/python-dbus-service.md` (~1260 lines, 6 phases)
- **Existing plan to reference**: `thoughts/shared/plans/port-python-to-gnome-extension-ts.md` (previous plan for full TypeScript port — Option A in that plan is the D-Bus approach we're pursuing)
- **Python source**: `src/voice_to_text/` (all providers, audio, hybrid, bluetooth, config)
- **GNOME extension**: `gnome-ext/` (extension.js, recorder.js, typer.js — all to be modified/removed)

## Recent Changes

No code changes. All work is in untracked `thoughts/` directory:
- `thoughts/shared/plans/python-dbus-service.md` — created and iterated on

## Learnings

### Research Findings (critical for plan accuracy)

1. **dbus-next > dasbus** (lines 309, 506-509, 565-567, 594-595, 628 in plan still reference dasbus):
   - `dasbus` is GLib-based, uses `GLib.MainLoop` — **incompatible with asyncio**
   - `dbus-next` is pure Python, zero dependencies, native asyncio, `asyncio.run(main())` works
   - dbus-next has `@signal()`, `@method()` decorators, `MessageBus().connect()` async
   - Example: `bus = await MessageBus().connect(); bus.export('/path', interface); await bus.request_name('com.name')`

2. **dotoolc > dotool for persistent pipes** (Phase 4 code in plan still uses `dotool`):
   - `dotool` (direct) re-registers virtual devices every invocation — latency
   - `dotoolc` (client to `dotoold`) keeps devices registered — faster for persistent pipes
   - `dotoold` is already set up as systemd user service by `dotool-quickstart.sh`
   - The ContinuousTyper should use `dotoolc` not `dotool`

3. **sounddevice AsyncInputStream** exists but uses callback thread:
   - Need `asyncio.Queue` to bridge callback → async world
   - Pattern: `sd.AsyncInputStream` with callback that puts into `asyncio.Queue`, async loop reads from queue

4. **Groq async**: `AsyncGroq` class supports `async/await` natively

5. **systemd Type=dbus**: Confirmed correct for D-Bus activation services

### Plan Structure
- Phase 1: Strip UI/TUI (delete main.py, strip format_level_bar from audio.py)
- Phase 2: Refactor providers to async (httpx, websockets, AsyncGroq)
- Phase 3: Build D-Bus service (dbus-next, engine state machine, entry point)
- Phase 4: Continuous dotoolc pipe (persistent dotoolc, diff typing)
- Phase 5: systemd + D-Bus activation files
- Phase 6: Update GNOME extension (replace subprocess with Gio.DBusProxy)

## Artifacts

- `thoughts/shared/plans/python-dbus-service.md` — main plan document (~1260 lines)
- `thoughts/shared/plans/port-python-to-gnome-extension-ts.md` — previous plan (reference for Option A / D-Bus approach)

## Action Items & Next Steps

### Incomplete Plan Updates (partially applied from research)

The plan has been updated in some places (overview, key discoveries, dependencies, constraints) but several code blocks still reference the old choices:

1. **Phase 3 dbus_service.py code block** (lines ~506-580): Still uses `dasbus` imports (`from dasbus.server.interface import dbus_interface`, `from dasbus.loop import EventLoop`). Needs rewrite to use `dbus_next`:
   ```python
   from dbus_next.service import ServiceInterface, method, signal
   from dbus_next.aio import MessageBus
   ```

2. **Phase 3 __main__.py code block** (lines ~585-640): Still uses `from dasbus.connection import SessionMessageBus` and `dasbus.loop.EventLoop`. Needs rewrite to use `asyncio.run(main())` with `dbus_next.aio.MessageBus`.

3. **Phase 4 ContinuousTyper code** (lines ~687-780): Still uses `shutil.which("dotool")` and references `dotool` binary. Should use `dotoolc` instead. The `dotoold` daemon is assumed running (set up by `dotool-quickstart.sh`).

4. **Phase 3 engine.py code block** (lines ~330-475): Needs to show `sd.AsyncInputStream` + `asyncio.Queue` bridging pattern for audio recording.

5. **Phase 2 success criteria** (line ~294): May still reference `dasbus` in import check — verify and fix.

### After plan is finalized:
- Implement Phase 1 (strip UI) — straightforward deletion
- Implement Phase 2 (async providers) — requires careful testing of each provider
- Implement Phase 3 (D-Bus service) — requires dbus-next integration testing
- Implement Phase 4 (dotoolc) — requires dotoold running
- Implement Phase 5 (systemd) — packaging
- Implement Phase 6 (extension) — requires GNOME Shell testing

## Other Notes

- The user explicitly wants: **full async** (not thread pool), **dbus-next** (not dasbus), **dotoolc** (not dotool direct), **systemd --user unit**, **remove CLI entirely**, **service handles all output** (both typing and clipboard — no text signals needed)
- D-Bus interface is simplified: methods `StartRecording`, `StopRecording`, `GetStatus` + signals `AudioLevel`, `Error`, `StateChanged` only (no StreamingText, no TranscriptionResult)
- The GNOME extension is the sole client — no concurrent client handling needed
- `sounddevice` is NOT being replaced — it stays for audio recording. Only the HTTP/WebSocket libs are swapped (requests→httpx, websocket-client→websockets)
