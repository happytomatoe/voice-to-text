---
date: 2026-05-10T19:42:52+00:00
researcher: opencode
git_commit: f60729a5c0f421510b547f45d5250e5fb274c474
branch: main
repository: voice-to-text
topic: "Voice to Text Extension Not Loading"
tags: [gnome-shell, extension, debugging]
status: in_progress
last_updated: 2026-05-10
last_updated_by: opencode
type: implementation_strategy
---

# Handoff: Voice to Text Extension Not Loading

## Task(s)
This session's primary task was to debug why the Voice to Text GNOME Shell extension is not showing any indicators or moving parts when triggered by the Super+V shortcut. The extension is installed and the D-Bus service appears to be running correctly, but the extension itself is not loading or executing its code within the GNOME Shell development session.

## Critical References
- `justfile`
- `extensions/voice-to-text/src/extension.js`
- `extensions/voice-to-text/src/lib/keybindingManager.js`
- `extensions/voice-to-text/src/lib/uiManager.js`
- `extensions/voice-to-text/src/lib/dbusManager.js`
- `src/groq_voice/dbus_service.py`

## Recent changes
- `extensions/voice-to-text/src/lib/keybindingManager.js`: Added more verbose logging to the `setupKeybinding` function.
- `extensions/voice-to-text/src/extension.js`: Added verbose logging to the `enable` and `toggleRecording` functions.

## Learnings
- The D-Bus service (`voice-to-text.service`) seems to be starting and running correctly in the user's systemd session.
- The extension files are correctly copied to `~/.local/share/gnome-shell/extensions/voice-to-text@l/` and the `metadata.json` is valid.
- Despite adding extensive `console.log` statements in `extension.js`, no output from these logs appears in `justdev.log`.
- `gnome-extensions list` does not show `voice-to-text@l` as an available extension, even though its files are present in the correct directory.
- The presence of another extension, `speech2text-extension@kaveh.page`, which consistently fails to load with a UUID mismatch error, might be interfering with the loading of subsequent extensions, including `voice-to-text@l`.
- The `dbus-run-session gnome-shell --devkit --wayland` command used in the `just dev` script might be creating an isolated session where extensions aren't loaded in the usual manner, or where the `gnome-extensions enable` command's effect doesn't persist.

## Artifacts
- `thoughts/shared/handoffs/general/2026-05-10_19-42-52_voice-to-text-extension-not-loading.md` (this document)

## Action Items & Next Steps
1. **Remove interfering extension**: Remove `speech2text-extension@kaveh.page` from `~/.local/share/gnome-shell/extensions/` to eliminate potential conflicts.
2. **Verify extension loading**: After removing the conflicting extension, restart the `just dev` session and check `justdev.log` for `[VoiceToText]` logs to confirm the extension is now being loaded and enabled.
3. **Debug extension activation**: If the extension still doesn't load, investigate alternative methods for enabling or debugging extensions within the `dbus-run-session gnome-shell --devkit --wayland` environment.
4. **Check for alternative extension loading paths**: Investigate if the `--devkit` flag or `dbus-run-session` changes the default extension loading paths or mechanisms.

## Other Notes
- The current approach of using `console.log` for debugging within the extension is effective if the extension actually loads. The primary hurdle is getting the extension to be recognized and initialized by GNOME Shell in the dev environment.