---
date: 2026-05-10T17:12:00+0200
researcher: assistant
git_commit: f60729a5c0f421510b547f45d5250e5fb274c474
branch: main
repository: voice-to-text
topic: "GNOME Extension D-Bus Service Integration"
tags: dbus, gnome-extension, systemd
status: in_progress
last_updated: 2026-05-10
last_updated_by: assistant
type: implementation_strategy
---

# Handoff: D-Bus Service Connection for GNOME Extension

## Task(s)
Working on connecting the GNOME Shell extension to the Python D-Bus backend service. The goal is to have `just dev` start GNOME Shell with the extension, and have the extension successfully communicate with the Python backend via D-Bus.

**Current Status**: Investigating why D-Bus service registration fails when extension tries to connect.

## Critical References
- `extensions/voice-to-text/src/lib/dbusManager.js:2-39` - Extension D-Bus connection code
- `src/groq_voice/dbus_service.py:15-17` - D-Bus service definition (BUS_NAME, OBJECT_PATH, INTERFACE_NAME)
- `src/groq_voice/main.py:213-234` - D-Bus service mode handler

## Recent changes
- `src/groq_voice/dbus_service.py:282` - Fixed `BusOwnerFlags` to `BusNameOwnerFlags`
- `src/groq_voice/main.py:181-184` - Added `--with-gnome-shell` flag to run both service and shell
- `justfile:74-82` - Updated dev recipe to use integrated service mode
- `service/voice-to-text.service` - Created systemd user service definition

## Learnings
1. **Root cause**: System uses `dbus-broker` instead of `dbus-daemon`. D-Bus service auto-activation via `.service` files doesn't work properly in dbus-broker session context.

2. **Attempted approaches**:
   - `.service` file in `~/.local/share/dbus-1/services/` - Not recognized by dbus-broker
   - `.service` file in `/usr/local/share/dbus-1/services/` - Not recognized
   - systemd user service with `Type=dbus` - Failed due to D-Bus name acquisition timeout
   - Running service in same process as gnome-shell via `os.execvp()` - Service runs but still not visible to extension

3. **The error**: Extension logs show "Service not reachable: GDBus.Error:org.freedesktop.DBus.Error.ServiceUnknown: The name org.gnome.Shell.Extensions.VoiceToText was not provided by any .service files"

4. **Key insight**: The service IS running in the same process as gnome-shell now (via `--with-gnome-shell`), but D-Bus still can't find it because there's no `.service` file for auto-activation. The extension's D-Bus proxy expects D-Bus to auto-start the service.

## Artifacts
- `justfile` - Modified dev recipe with timeout and integrated service
- `src/groq_voice/main.py` - Added --with-gnome-shell mode
- `src/groq_voice/dbus_service.py` - Fixed BusNameOwnerFlags
- `service/voice-to-text.service` - Systemd service definition

## Action Items & Next Steps
1. **Option 1 - Fix service file**: Create a proper `.service` file that dbus-broker will recognize. May need to configure dbus-broker to look in custom directories.

2. **Option 2 - Modify extension**: Update `dbusManager.js` to handle the case where service isn't auto-started. Could either:
   - Catch error and show user-friendly message
   - Try to manually spawn the service via `Gio.Subprocess`
   - Use a fallback polling mechanism

3. **Option 3 - Use systemd properly**: Debug why systemd service times out. The service might need `After=dbus.socket` or similar dependencies.

4. **Testing**: To verify any fix, run `just dev` and check:
   - `justdev.log` for extension messages
   - `gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.ListNames` to see if bus name appears

## Other Notes
- The service is running as PID 122994 (from previous test) but not registering on D-Bus
- D-Bus service file format: `[D-BUS Service]` section with `Name=` and `Exec=`
- Timeout added to dev recipe is 30 seconds for quick testing
- The test command is: `just dev` which runs for 30 seconds then exits