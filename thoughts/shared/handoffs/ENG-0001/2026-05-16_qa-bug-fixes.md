---
date: 2026-05-16
branch: fix/bugs
commit: 174f903
repository: /var/home/l/git/voice-to-text
---

# Handoff: QA Bug Fixes for Voice-to-Text GNOME Extension

## Fixed Bugs

| # | Bug | Description | File | Commit |
|---|-----|-------------|------|--------|
| 1 | Stop button invisible | `_stopBtn` created but never added to `_box` layout | `indicator.js` | fe36a43 |
| 2 | FD leak | `stdin`/`stderr` from `spawn_async_with_pipes` never closed | `recorder.js` | fe36a43 |
| 3 | Zombie processes | `DO_NOT_REAP_CHILD` flag set but no `child_watch_add` to reap | `recorder.js` | fe36a43 |
| 4 | Non-idempotent stop | `stop()` left `_proc` set; calling twice could signal reused PID | `recorder.js` | fe36a43 |
| 5 | Stale async callback | `read_line_async` callback could fire after `stop()`/`disable()` with no error handling | `recorder.js` | 8e53b08 |
| 6 | Unsafe disable order | `disable()` destroyed indicator before stopping recorder, leaked references | `extension.js` | 96b0f55 |
| 7 | Dead `onStart` callback | `onStart` assigned but never invoked — no way to start from UI | `indicator.js` | 05b06bf |
| 8 | Cairo double-free | `cr.$dispose()` on a context owned by `St.DrawingArea` | `indicator.js` | 3edad9e |
| 9 | Broken meter fill | `fillW <= radius` skipped right edge, creating degenerate polygon | `indicator.js` | c83d06a |
| 10 | Stale recorder ref | `_recorder` never nulled in `_setIdle()`, old callbacks could interfere | `extension.js` | 6dde019 |
| 11 | Spawn failure ignored | `ok` from `spawn_async_with_pipes` never checked, invalid PID used | `recorder.js` | 2e9bb44 |
| 12 | Silent ydotool failure | `typeText()` had no error handling; failed typing silently lost text | `typer.js` | 49f2e50, d03dcd0 |
| 13 | Syntax error (regression) | Whitespace typo in `this._recorder.onTranscription` assignment | `extension.js` | 174f903 |

## Remaining QA Bugs (NOT YET FIXED)

| # | Bug | Description | File | Severity | Notes |
|---|-----|-------------|------|----------|-------|
| 14 | Wrong GNOME version | `metadata.json` lists "45" but `GioUnix` needs 46+ | `metadata.json` | Medium | User reverted fix — keep as-is |
| 15 | ERROR doesn't stop recorder | `ERROR:` line emitted but recorder keeps reading | `recorder.js` | Low | QA #2 suggested stopping on ERROR |
| 16 | Hotkey success unchecked | `addKeybinding()` return value ignored, logs success even on failure | `hotkey.js` | Low | QA #2 suggested checking return |
| 17 | Deprecated notify API | `Main.notify()` deprecated since GNOME 46 | `extension.js` | Low | QA #1 suggested MessageTray migration |
| 18 | Unused CSS class | `.vtt-meter` defined but no actor uses it | `stylesheet.css` | Low | Cosmetic cleanup |
| 19 | Premature idle state | `_stop()` calls `_setIdle()` before transcription is received | `extension.js` | Medium | QA #2 suggested "processing" state |

## Recent Changes (13 commits)

All on branch `fix/bugs`. Key changes:
- `recorder.js`: FD cleanup, child_watch_add for reaping, cancellable for async reads, try/catch error handling, spawn success check
- `indicator.js`: stop button added to box, micro icon click toggles recording, removed cr.$dispose(), fixed fill path for low levels
- `extension.js`: disable() cleanup order, null refs, clipboard fallback on ydotool failure
- `typer.js`: try/catch with clipboard fallback

## Critical Learnings

1. **Bug 5 iteration**: Initially added `_stopped` flag + `Cancellable` + stream close in `stop()` — this broke transcription because the stream was closed before the child could emit `TEXT:` after SIGINT. Fixed by keeping stream open, only using `try/catch` for graceful close when child exits.
2. **`PanelMenu.Button` signals**: No `clicked` signal exists. Use `button-press-event` on child actors instead.
3. **`GLib.spawn_command_line_async`** returns `[ok, pid]` tuple — can check success.
4. **Clipboard fallback**: `St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text)` works in GNOME Shell.

## Artifacts
- `/tmp/gnome-shell-nested.log` — debug output from `just debug`
- `gnome-ext/run-dev.sh` — dev extension runner

## Next Steps
1. Continue fixing remaining bugs (#14-#19) if user wants
2. Test full recording flow end-to-end (start → record → stop → text appears)
3. Consider running `just debug` to verify all fixes work together

## `/resume_handoff` Command
Resume from this handoff: `/resume_handoff /var/home/l/git/voice-to-text/thoughts/shared/handoffs/ENG-0001/2026-05-16_qa-bug-fixes.md`
