---
date: 2026-05-11T10:38:30-04:00
researcher: opencode
git_commit: 
branch: main
repository: voice-to-text
topic: "IBus Cloud Speech Engine Implementation"
tags: ibus, input-method, voice-to-text, python-gi
status: in_progress
last_updated: 2026-05-11
last_updated_by: opencode
type: implementation_strategy
---

# Handoff: IBus Cloud Speech Engine Integration

## Task(s)
Implementing an IBus input method engine that allows voice-to-text via Super+Q hotkey. The implementation is in progress with the core engine structure working - the engine initializes, registers with IBus, and `do_enable()` is called successfully when switched to.

**Current Status:**
- Phase 1-4 implementation complete (engine structure, audio, transcription, registration)
- Engine registers in IBus and appears in `ibus list-engine`
- Engine creation works - `do_create_engine` and `do_enable` execute successfully
- **Issue**: D-Bus timeout when trying to switch to the engine via `ibus engine com.cloud-voice.CloudSpeech`

## Critical References
- Plan: `thoughts/shared/plans/2026-05-11-ibus-cloud-plugin.md`
- IBus Python example: `/usr/share/ibus-stt/` (working Python IBus engine)
- IBus GI docs: `lazka.github.io/pgi-docs/IBus-1.0/`

## Recent changes
- Created `src/ibus_cloud/engine.py` - CloudSpeechEngine class with do_enable, do_process_key_event
- Created `src/ibus_cloud/audio.py` - AudioRecorder with callback support
- Created `src/ibus_cloud/config.py` - ConfigManager
- Created `ibus-engine-cloud` launcher with CloudSpeechFactory pattern
- Fixed `IBus.Text.new_from_string()` (not `.new()`)
- Fixed engine init to pass `connection` and `object_path` to parent

## Learnings
- IBus Python GI bindings differ from the old `import ibus` module
- Factory must inherit from `IBus.Factory` and override `do_create_engine()`
- Engine must be initialized with `super().__init__(connection=bus.get_connection(), object_path=object_path)`
- Use `IBus.Text.new_from_string()` not `IBus.Text.new()`
- The stt engine at `/usr/share/ibus-stt/` is the best reference for modern Python IBus engines

## Artifacts
- `src/ibus_cloud/__init__.py:1` - Package init
- `src/ibus_cloud/engine.py:37` - CloudSpeechEngine class
- `src/ibus_cloud/audio.py:18` - AudioRecorder class
- `src/ibus_cloud/config.py:12` - ConfigManager class
- `ibus-engine-cloud:30` - Launcher with CloudSpeechFactory
- `data/ibus-cloud.xml:1` - IBus component XML

## Action Items & Next Steps
1. Debug D-Bus timeout when switching to engine - possibly a registration/connection issue
2. Test actual voice recording and transcription once engine switching works
3. Verify Super+Q key event handling

## Other Notes
The engine starts, factory is created, and when `ibus engine com.cloud-voice.CloudSpeech` is called, the factory's `do_create_engine` is invoked and creates the engine successfully. The `do_enable()` method runs and sets preedit text. However, the `ibus engine` command fails with "Set global engine failed: The connection is closed" timeout. This suggests the engine might be exiting or crashing after creation, or there's a D-Bus naming/registration issue.