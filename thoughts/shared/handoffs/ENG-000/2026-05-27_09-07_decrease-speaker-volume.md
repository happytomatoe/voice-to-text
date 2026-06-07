---
date: 2026-05-27T09:07:00+02:00
branch: main
repository: /var/home/l/git/voice-to-text
---

# Handoff — Decrease Speaker Volume + Idempotent Rebuild

## Task Status

| Task | Status |
|---|---|
| Decrease speaker volume during recording | ✅ Done |
| GSettings key + Preferences UI | ✅ Done |
| Pass `--decrease-speaker-volume` from extension | ✅ Done |
| Source hash check to skip PyInstaller rebuild | ✅ Done |
| `just reinstall` with hash skip | ✅ Done |
| `just gnome-ext-dev` depends on `reinstall` | ✅ Done |
| `--version` and `--source-hash` CLI flags | ✅ Done |
| Default `record` subcommand | ✅ Done |

## Known Issues

1. **YDotool typing doesn't work** — `gnome-ext/typer.js` uses `ydotool type` which requires root or proper socket setup. Falls back to clipboard when `ydotool` fails. Not related to these changes.

2. **TTY error in non-interactive context** — `voice-to-text --output clipboard` (default) calls `termios.tcgetattr()` which fails with "Inappropriate ioctl for device" when stdin isn't a terminal. This is pre-existing. Workaround: use `--output stdout` for non-TTY use.

3. **Pre-existing changes in working tree** — `voxtral.py`, `test_providers.py`, `test_voxtral.py` have uncommitted modifications not made by this session.

## Files Changed

### Core feature: decrease speaker volume
- `src/voice_to_text/audio.py` — New `SpeakerVolumeManager` class: `save()`, `decrease(percent)`, `restore()`. Uses `wpctl` (PipeWire) → `pactl` (PulseAudio) fallback.
- `src/voice_to_text/main.py` — `--decrease-speaker-volume` CLI arg; wired into both `run_stdout_mode()` and clipboard mode with try/finally for save/restore.
- `src/voice_to_text/config.py` — Added `get_speaker_config()`.
- `config.yaml` — Added `audio.speaker.decrease_volume: 0`.

### GNOME Extension
- `gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml` — New key `decrease-speaker-volume` (int, 0-100, default 0).
- `gnome-ext/prefs.js` — `Adw.SpinRow` bound to new key (step=5, 0-100).
- `gnome-ext/recorder.js` — Reads setting, passes `--decrease-speaker-volume` when > 0.

### Idempotent rebuild + source hash
- `src/voice_to_text/__init__.py` — `source_hash()` function, imports from generated `_build_info.py`.
- `src/voice_to_text/main.py` — `--version` and `--source-hash` CLI flags.
- `.gitignore` — Added `src/voice_to_text/_build_info.py`.
- `justfile` — `build-binary` generates `_build_info.py` with content hash of Python sources. `reinstall` compares embedded hash vs current hash, skips PyInstaller if match (~23ms check vs 15-30s build). `gnome-ext-dev: reinstall gnome-ext-install`.

### UX improvement
- `src/voice_to_text/main.py` — `record` is default subcommand; all record args (`--provider`, `--duration`, `--output`, `--model`, `--decrease-speaker-volume`) available at top level too.

### Tests
- `tests/test_config.py` — Added `test_speaker_config_defaults` and `test_speaker_config_with_values`.

## How to Use

```bash
# Development (runs from source, no binary needed)
just run -- --provider voxtral

# Full dev cycle (rebuilds binary only if source changed)
just gnome-ext-dev

# Just reinstall binary
just reinstall

# Check binary freshness
voice-to-text --version
voice-to-text --source-hash
```

## Next Steps

1. Investigate ydotool typing issue
2. Clean up pre-existing modifications in `voxtral.py`, `test_providers.py`, `test_voxtral.py`
3. Add `_build_info.py` and `__pycache__` cleanup to gitignore or clean targets
4. Consider compiling `gschemas.compiled` into a proper build step instead of tracking in git
