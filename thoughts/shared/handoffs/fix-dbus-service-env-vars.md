---
date: 2026-07-07T08:50:00+02:00
researcher: l
git_commit: 2d4b4e3
branch: main
repository: voice-to-text
topic: "Fix D-Bus Service Environment Variables"
tags: [dbus, systemd, environment-variables, secrets, voice-to-text]
status: complete
last_updated: 2026-07-07
last_updated_by: l
type: implementation_strategy
---

# Handoff: Fix D-Bus Service Environment Variables

## Task(s)
1. **Research env var propagation** (completed): Found approaches for propagating env vars into D-Bus services and injecting secrets
2. **Diagnose env var issue** (completed): Root cause found - conflicting systemd and D-Bus activation services
3. **Fix the conflict** (completed): Removed systemd service, updated to use only D-Bus activation with wrapper script

## Critical References
- `docs/dbus-env-var-research.md` - Research document with 8 approaches for env var propagation and secret injection
- `~/.local/share/dbus-1/services/com.happytomatoe.VoiceToText.service` - D-Bus activation file
- `~/.local/bin/voice-to-text-dbus-wrapper` - New wrapper script that sources env file before starting service

## Recent changes
- `service/voice-to-text.service`: Deleted (removed systemd service)
- `service/install.sh`: Updated to only install D-Bus service, removed systemd references
- `install.sh`: Updated API key messages and useful commands to remove systemd references
- `~/.local/share/dbus-1/services/com.happytomatoe.VoiceToText.service`: Updated to use wrapper script
- `~/.local/bin/voice-to-text-dbus-wrapper`: Created - wrapper that sources env file before starting service

## Learnings

### Root Cause
The voice-to-text service had **two conflicting service managers**:
1. **D-Bus activation** (`~/.local/share/dbus-1/services/`) - auto-starts when GNOME extension requests the D-Bus name
2. **systemd service** (`~/.config/systemd/user/`) - independent service manager

**The conflict:**
- D-Bus activation fires first (07:02) when extension loads
- systemd service tries to start later (08:18) but D-Bus name is already taken
- D-Bus activated service has **no env vars** because it bypasses systemd's `ExecStartPre` and `EnvironmentFile`

### Why D-Bus activation had no env vars
The D-Bus service file ran: `Exec=/bin/sh -c 'exec $(command -v voice-to-text-dbus)'`
- No `EnvironmentFile` directive
- No `ExecStartPre` to generate the env file
- The `environment.d` file had malformed syntax (leading spaces + literal `$(command)` strings)

### Solution Pattern
For D-Bus services that need env vars, use a **wrapper script** that:
1. Generates the env file (calls `voice-to-text-env`)
2. Sources the env file
3. Runs the actual service

### D-Bus vs systemd (when to use what)
- **systemd user service**: Always-on daemons, crash restart, environment var support
- **D-Bus activation**: On-demand start, resource-efficient, single-instance enforcement
- **For this project**: D-Bus activation is correct (service starts on demand when extension requests it)

## Artifacts
- `docs/dbus-env-var-research.md` - Comprehensive research on env var propagation approaches
- `~/.local/bin/voice-to-text-dbus-wrapper` - Wrapper script for D-Bus activation with env vars
- `service/install.sh` - Updated install script (D-Bus only)
- `install.sh` - Updated root install script (D-Bus only)

## Action Items & Next Steps
1. **Test the fix**: Use the GNOME extension to trigger voice-to-text and verify env vars are loaded
2. **Verify secret-tool integration**: Ensure `voice-to-text-env` script correctly retrieves secrets from keyring
3. **Update documentation**: Update any docs that reference systemd service commands
4. **Consider**: The `environment.d/voice-to-text.conf` file still has the malformed syntax (literal `$(command)` strings) - this file may not be needed anymore since we use the wrapper script

## Other Notes
- Old stuck process (PID 3241) was holding the D-Bus name - was killed during fix
- The D-Bus name `com.happytomatoe.VoiceToText` is now properly managed by D-Bus activation only
- The wrapper script at `~/.local/bin/voice-to-text-dbus-wrapper` needs to be deployed to user machines (not in the repo's service/ directory)
- Consider adding the wrapper script to the repo's service/ directory for easier installation
