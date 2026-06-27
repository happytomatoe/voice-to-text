---
date: 2026-06-26T16:28:36+02:00
researcher: l
git_commit: 540479b
branch: feat/voidce-to-text-ibus
repository: voice-to-text-ibus
topic: "Voxtral IBus Engine Integration - Microphone Icon & Auto-Start Issue"
tags: [ibus, engine, speech-to-text, voxtral, microphone, socket]
status: in-progress
last_updated: 2026-06-26
last_updated_by: l
type: implementation_strategy
---

# Handoff: Voxtral IBus Engine Integration - Fixing Auto-Start & Microphone Icon

## Task(s)

### Completed Tasks:
1. ✅ XML Path Fix - Fixed component path in voxtral.xml
2. ✅ Engine Name Consistency - Fixed name matching between XML and Python
3. ✅ Environment Configuration - Set up ~/.config/environment.d/ibus.conf
4. ✅ Installation Scripts - Created clean justfile with working commands
5. ✅ IBus Registration - Engine registered with IBus daemon
6. ✅ Input Sources - Added to GNOME input sources: `[('xkb', 'us'), ('ibus', 'voxtral')]`
7. ✅ Socket Communication - Verified bridge-to-engine communication works
8. ✅ Keep-alive Timer - Added GLib.MainLoop keep-alive (but not sufficient)

### In-Progress Tasks:
1. 🔄 **Engine Auto-Start** - Engine process stops after ~15 seconds in background
2. 🔄 **Microphone Icon** - Not appearing when switching to Voxtral
3. 🔄 **Socket Creation** - Socket only created when engine is focused (by design)

### Critical Issue - Engine Process Dying:
The engine process dies after ~15 seconds when run in background via `&`. **Solution found: Use `setsid`** to prevent signal propagation from parent shell.

```bash
# This works (engine stays alive 30+ seconds):
setsid /usr/bin/python3 src/voice_to_text/ibus/engine.py --ibus &

# This fails (engine dies after ~15s):
/usr/bin/python3 src/voice_to_text/ibus/engine.py --ibus &
```

## Critical References
- `src/voice_to_text/ibus/engine.py` - Main engine code (lines 257-295: main function)
- `src/voice_to_text/ibus/bridge.py` - Bridge code (connects to engine via socket)
- `~/.local/share/ibus/component/voxtral.xml` - IBus component XML
- `scripts/voxtral_ibus.py` - Combined engine+bridge launcher
- `just-ibus-run.sh` - Simple run script

## Recent Changes
- `src/voice_to_text/ibus/engine.py:257-295` - Added keep-alive timer, improved main function
- `src/voice_to_text/ibus/bridge.py:41-60` - Added socket wait loop with timeout
- `scripts/voxtral_ibus.py:64-85` - Fixed engine startup (added --ibus flag, IBUS_COMPONENT_PATH)
- `justfile` - Updated ibus-verify with proper checks, added daemon check to ibus-engine
- `just-ibus-run.sh` - Updated to use setsid (needs verification)

## Learnings

### Key Architecture Understanding:
1. **Socket is created only when engine is FOCUSED** - This is IBus design, not a bug
2. **Engine process must be started BEFORE switching** - IBus doesn't auto-start engines
3. **Socket communication flow**: Bridge → Socket → Engine → Application
4. **Engine symbol (🎤)** appears in panel only when engine is active and focused

### Root Cause of Engine Dying:
- Background processes (`&`) inherit signal handlers from parent shell
- When shell exits, signals propagate to child processes
- **Fix**: Use `setsid` to create new session and prevent signal propagation

### IBus Integration Flow:
1. IBus daemon reads XML component files from `IBUS_COMPONENT_PATH`
2. Engine registers with IBus via D-Bus
3. When user switches to engine (Super+Space), IBus calls `do_focus_in()`
4. Engine starts socket listener in `do_focus_in()`
5. Bridge connects to socket
6. Audio → Bridge → Voxtral API → Socket → Engine → Application

### Why Microphone Icon Doesn't Appear:
- Engine process dies after ~15 seconds
- When user switches to Voxtral, IBus can't find running engine
- No engine = no socket = no microphone icon
- **Fix**: Keep engine alive with `setsid` + proper background management

## Artifacts
- `src/voice_to_text/ibus/engine.py` - Main engine (MODIFIED)
- `src/voice_to_text/ibus/bridge.py` - Bridge process (MODIFIED)
- `scripts/voxtral_ibus.py` - Combined launcher (MODIFIED)
- `justfile` - Build/run commands (MODIFIED)
- `just-ibus-run.sh` - Simple run script (MODIFIED)
- `~/.local/share/ibus/component/voxtral.xml` - IBus component (CREATED)
- `~/.config/environment.d/ibus.conf` - Environment config (CREATED)
- `USAGE.md` - Usage documentation (CREATED)
- `QUICKSTART.md` - Quick reference (CREATED)
- `test_engine.py` - Engine test script (CREATED)

## Action Items & Next Steps

### Priority 1: Fix Engine Auto-Start
1. Update `just-ibus-run.sh` to use `setsid` for engine startup
2. Update `justfile` `ibus-engine` recipe to use `setsid`
3. Test engine stays alive for 60+ seconds in background

### Priority 2: Verify Microphone Icon
1. Start engine with `setsid`
2. Switch to Voxtral (Super+Space)
3. Verify microphone icon (🎤) appears in panel
4. Start bridge and test speech-to-text

### Priority 3: Test Full Integration
1. Run `./just-ibus-run.sh`
2. Switch to Voxtral
3. Speak into microphone
4. Verify text appears in focused application

### Priority 4: Documentation
1. Update USAGE.md with setsid requirement
2. Document the engine lifecycle (start → focus → socket → bridge)

## Other Notes

### Current Input Sources Configuration:
```
[('xkb', 'us'), ('ibus', 'voxtral')]
```
- US keyboard layout
- Voxtral IBus engine

### Engine Symbol in XML:
```xml
<symbol>🎤</symbol>
```
This is what should appear in the panel when Voxtral is active.

### Socket Path:
```
/run/user/1000/voxtral-ibus.sock
```
- Created by engine when focused
- Used by bridge for communication
- Only exists when engine is running AND focused

### Environment Variables Needed:
```bash
export IBUS_COMPONENT_PATH="$HOME/.local/share/ibus/component"
export PYTHONPATH=src
```

### IBus Daemon Status:
- Must be running for engine to work
- Start with: `ibus-daemon -dx --config=disable --panel=disable`
- Check with: `pgrep ibus-daemon`

### Testing Commands:
```bash
# Start engine (with setsid for background)
setsid /usr/bin/python3 src/voice_to_text/ibus/engine.py --ibus &

# Test socket communication
python3 test_engine.py

# Start bridge
just ibus-bridge

# Full integration
./just-ibus-run.sh
```

### Known Issues:
1. Engine dies after ~15s without `setsid` (FIXED with setsid)
2. Socket only created when engine is focused (BY DESIGN)
3. Microphone icon not appearing (RELATED to engine dying)
4. Bridge waits for socket (CORRECT behavior)

### Next Agent Should:
1. Verify `setsid` fix works in just-ibus-run.sh
2. Test microphone icon appears after fix
3. Test full speech-to-text flow
4. Update documentation with findings
