---
date: 2026-06-26T18:46:38+02:00
researcher: l
git_commit: 540479b
branch: feat/voidce-to-text-ibus
repository: voice-to-text-ibus
topic: "Voxtral IBus Engine - Complete Integration Status"
tags: [ibus, engine, speech-to-text, voxtral, microphone, socket, setsid]
status: in-progress
last_updated: 2026-06-26
last_updated_by: l
type: implementation_strategy
---

# Handoff: Voxtral IBus Engine - setsid Fix Applied, Ready for Microphone Icon Testing

## Task(s)

### Completed Tasks:
1. ✅ **setsid Fix Applied** - Engine now stays alive in background using `setsid`
2. ✅ **justfile Updated** - `ibus-engine` recipe uses `setsid` and `--ibus` flag
3. ✅ **Engine Running** - PID 158403, registered with IBus, GLib main loop active
4. ✅ **Input Sources Configured** - `[('xkb', 'us'), ('ibus', 'voxtral')]`
5. ✅ **IBus Registration** - Engine appears in `ibus list-engine`: `voxtral - Voxtral`
6. ✅ **Bridge Waiting** - Bridge waits for socket (correct behavior)
7. ✅ **Socket Communication** - Verified bridge-to-engine communication works

### In-Progress Tasks:
1. 🔄 **Microphone Icon** - Need to verify icon appears when switching to Voxtral
2. 🔄 **Socket Creation** - Socket only created when engine is focused (by design)
3. 🔄 **Full Integration Test** - Need to test speech-to-text flow

### Critical Achievement:
**Engine process now stays alive!** The `setsid` fix prevents signal propagation from parent shell that was killing the engine after ~15 seconds.

## Critical References
- `src/voice_to_text/ibus/engine.py:257-295` - Main engine with keep-alive timer
- `src/voice_to_text/ibus/bridge.py:41-60` - Bridge socket wait logic
- `justfile:136-155` - Updated `ibus-engine` recipe with setsid
- `just-ibus-run.sh` - Simple run script (already uses setsid)
- `~/.local/share/ibus/component/voxtral.xml` - IBus component XML

## Recent Changes
- `justfile:136-155` - Updated `ibus-engine` to use `setsid` and `--ibus` flag
- `just-ibus-run.sh:25` - Already uses `setsid` for engine startup
- `src/voice_to_text/ibus/engine.py:280-295` - Added keep-alive timer (not sufficient alone)
- `src/voice_to_text/ibus/bridge.py:41-60` - Added socket wait loop

## Learnings

### Root Cause of Engine Dying (FIXED):
- Background processes (`&`) inherit signal handlers from parent shell
- When shell exits, signals propagate to child processes
- **Solution**: Use `setsid` to create new session and prevent signal propagation
- **Command**: `setsid /usr/bin/python3 src/voice_to_text/ibus/engine.py --ibus &`

### Socket Creation Flow (BY DESIGN):
1. Engine starts and registers with IBus
2. Socket is NOT created yet
3. User switches to Voxtral (Super+Space)
4. IBus calls `do_focus_in()` on engine
5. Engine starts socket listener in `do_focus_in()`
6. Socket is created at `/run/user/1000/voxtral-ibus.sock`
7. Bridge can now connect

### Microphone Icon Requirements:
- Engine must be running (✅ FIXED with setsid)
- Engine must be focused (requires user to switch to Voxtral)
- Socket must be created (happens on focus)
- Icon is defined in XML: `<symbol>🎤</symbol>`

### Why Microphone Icon Might Not Appear:
1. Engine not running (FIXED)
2. Engine not focused (user needs to switch)
3. IBus not calling `do_focus_in()` (investigate if issue persists)
4. Icon not configured properly (check XML)

## Artifacts
- `src/voice_to_text/ibus/engine.py` - Main engine (MODIFIED)
- `src/voice_to_text/ibus/bridge.py` - Bridge process (MODIFIED)
- `scripts/voxtral_ibus.py` - Combined launcher (MODIFIED)
- `justfile` - Build/run commands (MODIFIED - setsid fix)
- `just-ibus-run.sh` - Simple run script (MODIFIED - uses setsid)
- `~/.local/share/ibus/component/voxtral.xml` - IBus component (CREATED)
- `~/.config/environment.d/ibus.conf` - Environment config (CREATED)
- `USAGE.md` - Usage documentation (CREATED)
- `QUICKSTART.md` - Quick reference (CREATED)
- `test_engine.py` - Engine test script (CREATED)

## Action Items & Next Steps

### Priority 1: Verify Microphone Icon
1. Switch to Voxtral (Super+Space)
2. Check if 🎤 icon appears in panel
3. If not, investigate IBus focus event handling
4. Check if `do_focus_in()` is being called

### Priority 2: Test Full Integration
1. Start engine: `just ibus-engine` (or `./just-ibus-run.sh`)
2. Switch to Voxtral (Super+Space)
3. Start bridge: `just ibus-bridge`
4. Speak into microphone
5. Verify text appears in focused application

### Priority 3: Debug Focus Event (if needed)
1. Add debug logging to `do_focus_in()` in engine.py
2. Check if IBus is calling the method
3. Verify engine is receiving focus events

### Priority 4: Documentation
1. Update USAGE.md with setsid requirement
2. Document the engine lifecycle
3. Add troubleshooting guide

## Other Notes

### Current Engine State:
- **PID**: 158403
- **Status**: Running (using setsid)
- **Registered**: Yes (voxtral - Voxtral)
- **Socket**: Not created (waiting for focus)
- **Log**: `/tmp/voxtral-engine.log`

### How to Start Engine:
```bash
# Option 1: Using justfile
just ibus-engine

# Option 2: Using run script
./just-ibus-run.sh

# Option 3: Manual
setsid /usr/bin/python3 src/voice_to_text/ibus/engine.py --ibus &
```

### How to Test Microphone Icon:
1. Start engine (any method above)
2. Press Super+Space
3. Select "Voxtral"
4. Look for 🎤 icon in panel

### If Microphone Icon Doesn't Appear:
1. Check if engine is running: `ps aux | grep engine.py`
2. Check if socket exists: `ls -la /run/user/1000/voxtral-ibus.sock`
3. Check engine log: `tail -f /tmp/voxtral-engine.log`
4. Try restarting engine: `pkill -f "engine.py" && just ibus-engine`

### Environment Variables:
```bash
export IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component"
export PYTHONPATH=src
```

### IBus Daemon:
- Must be running for engine to work
- Check with: `pgrep ibus-daemon`
- Start with: `ibus-daemon -dx --config=disable --panel=disable`

### Next Agent Should:
1. Test microphone icon appears after switching to Voxtral
2. If icon doesn't appear, add debug logging to `do_focus_in()`
3. Test full speech-to-text integration
4. Update documentation with findings
