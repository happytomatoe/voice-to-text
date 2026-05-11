---
date: 2026-05-10T17:25:00+0200
researcher: assistant
git_commit: HEAD
branch: main
repository: voice-to-text
topic: "D-Bus Service via Systemd Integration"
tags: dbus, systemd, gnome-extension
status: in_progress
last_updated: 2026-05-10
last_updated_by: assistant
type: implementation_strategy
---

# Handoff: D-Bus Service via Systemd Integration

## Task(s)
Working on connecting GNOME Shell extension to Python D-Bus backend service via systemd user service. The goal is to have the extension communicate with the Python backend via D-Bus with proper systemd integration.

**Current Status:** Service starts and registers on D-Bus, but method calls cause crashes due to GLib/PyGObject API incompatibility.

## Critical References
- `extensions/voice-to-text/src/lib/dbusManager.js:2-39` - Extension D-Bus connection code
- `src/groq_voice/dbus_service.py:175-295` - D-Bus service registration and methods
- `src/groq_voice/main.py:217-255` - D-Bus service mode handler

## Recent changes
- `service/data/org.gnome.Shell.Extensions.VoiceToText.service` - Added SystemdService directive
- `service/voice-to-text.service` - Changed Type=simple to Type=dbus, added BusName
- `justfile:35-44` - Added install-services recipe
- `src/groq_voice/main.py:228-255` - Fixed --dbus-service mode to register bus name
- `src/groq_voice/dbus_service.py:175-290` - Multiple attempts to fix register function for GLib 2.88+

## Learnings
1. **Root cause of crash:** GLib 2.88+ changed GObject.Closure API, PyGObject doesn't handle it properly - causes segfault when method calls are made
2. **What works:** Service starts, acquires bus name, visible in D-Bus names list
3. **What doesn't work:** Method invocations cause immediate crash
4. **D-Bus activation:** Using `SystemdService=` in .service file properly triggers systemd to start the service

## Artifacts
- `service/data/org.gnome.Shell.Extensions.VoiceToText.service` - D-Bus activation file
- `service/voice-to-text.service` - Systemd user service definition
- `justfile:35-44` - install-services recipe

## Action Items & Next Steps
1. **Option 1 (Recommended):** Modify extension to handle manual service spawning - Update `dbusManager.js` to catch connection errors and spawn service via `Gio.Subprocess` or show user-friendly message
2. **Option 2:** Convert to dbus-python library - Rewrite D-Bus service using pure Python dbus instead of gi.repository
3. **Decision needed:** User must choose which path to pursue

## Other Notes
- The service name `org.gnome.Shell.Extensions.VoiceToText` is correctly registered on session bus
- Testing: `systemctl --user start voice-to-text.service && gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.ListNames | grep voice`
- The systemd + D-Bus activation path is correct, only the PyGObject method handling is broken

(End of file - total 55 lines)