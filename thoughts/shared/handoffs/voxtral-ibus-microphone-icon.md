---
date: 2026-06-26T18:47:56+02:00
researcher: l
git_commit: 540479b
branch: feat/voidce-to-text-ibus
repository: voice-to-text-ibus
topic: "Voxtral IBus Engine - Microphone Icon Investigation"
tags: [ibus, engine, speech-to-text, voxtral, microphone, socket, setsid, gnome]
status: in-progress
last_updated: 2026-06-26
last_updated_by: l
type: implementation_strategy
---

# Handoff: Voxtral IBus Engine - Engine Running, Microphone Icon Not Appearing

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
1. 🔄 **Microphone Icon** - NOT appearing when switching to Voxtral
2. 🔄 **Socket Creation** - Socket only created when engine is focused (by design)
3. 🔄 **Full Integration Test** - Need to test speech-to-text flow

### Critical Issue - Microphone Icon Not Appearing:
**User reports**: After pressing Super+Space and selecting Voxtral, no microphone icon appears in the panel.

**Hypothesis**: The engine is running but IBus is not calling `do_focus_in()` when the user switches to Voxtral. This could be because:
1. IBus is not properly activating the engine
2. The engine's `do_focus_in()` method is not being called
3. The GNOME shell is not displaying the engine symbol

## Critical References
- `src/voice_to_text/ibus/engine.py:257-295` - Main engine with keep-alive timer
- `src/voice_to_text/ibus/engine.py:50-60` - `do_focus_in()` method (starts socket listener)
- `src/voice_to_text/ibus/bridge.py:41-60` - Bridge socket wait logic
- `justfile:136-155` - Updated `ibus-engine` recipe with setsid
- `~/.local/share/ibus/component/voxtral.xml` - IBus component XML (contains `<symbol>🎤</symbol>`)

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

### Why Microphone Icon Might Not Appear (INVESTIGATE):
1. Engine not running (FIXED)
2. Engine not focused (user needs to switch)
3. IBus not calling `do_focus_in()` (INVESTIGATE THIS)
4. Icon not configured properly (check XML)
5. GNOME shell not displaying engine symbols (check GNOME settings)

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

### Priority 1: Investigate Microphone Icon Issue
1. Add debug logging to `do_focus_in()` in engine.py
2. Check if IBus is calling the method when user switches to Voxtral
3. Verify engine is receiving focus events
4. Check GNOME shell settings for engine symbol display

### Priority 2: Test Full Integration
1. Start engine: `just ibus-engine` (or `./just-ibus-run.sh`)
2. Switch to Voxtral (Super+Space)
3. Check engine log for "VoxtralEngine focused in" message
4. Start bridge: `just ibus-bridge`
5. Speak into microphone
6. Verify text appears in focused application

### Priority 3: Debug Focus Event (if needed)
1. Add debug logging to `do_focus_in()` in engine.py
2. Check if IBus is calling the method
3. Verify engine is receiving focus events
4. Check if socket is created after focus

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
5. Check engine log: `tail -f /tmp/voxtral-engine.log`

### If Microphone Icon Doesn't Appear:
1. Check if engine is running: `ps aux | grep engine.py`
2. Check engine log for focus events: `grep "focused in" /tmp/voxtral-engine.log`
3. Check if socket exists: `ls -la /run/user/1000/voxtral-ibus.sock`
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
1. Add debug logging to `do_focus_in()` method in engine.py
2. Test if focus events are being received
3. Check GNOME shell settings for engine symbol display
4. Test full speech-to-text integration
5. Update documentation with findings
