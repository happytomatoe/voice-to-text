# Plan: Fix Streaming in GNOME Extension

## Problem
Streaming transcription works from CLI but fails in the GNOME extension when running in a nested GNOME Shell (`gnome-ext-dev`).

## Root Cause
1. **Groq doesn't support streaming** - `groq.py` uses `wss://api.groq.com/openai/v1/audio/transcriptions` which is just the REST endpoint with `wss://` prefix. Only Deepgram has real WebSocket streaming (`wss://api.deepgram.com/v1/listen`).

2. **API keys not available in nested GNOME Shell** - The extension spawns the binary which reads `os.getenv("DEEPGRAM_API_KEY")`. In a nested `dbus-run-session -- gnome-shell --wayland --devkit`, shell RC files (`.bashrc`, `.zshrc`) are not sourced, so env vars from `secret-tool` / shell config are missing.

3. **Config mismatch** - `config.yaml` has `provider: "parakeet"` but gschema defaults to `provider: "voxtral"`. Neither matters for streaming (uses `streaming-provider: "deepgram"`), but batch provider config is inconsistent.

## Solution

### 1. Add secret-tool fallback to config.py
Add `get_api_key()` helper that tries:
1. `config.get("api_key")` - explicit in config
2. `os.getenv(config.get("api_key_env"))` - environment variable
3. `secret-tool lookup application voice-to-text provider <provider>` - secret store

### 2. Update providers to use config.get_api_key()
Modify `DeepgramProvider.__init__`, `GroqProvider.__init__`, `VoxtralProvider.__init__`, `ParakeetProvider.__init__` to call `config.get_api_key()` instead of inline logic.

### 3. Fix Groq streaming (mark as unsupported)
Either:
- Remove `StreamingProvider` from `GroqProvider` class (it doesn't work)
- Or raise `NotImplementedError` if `start_stream()` called on Groq

### 4. Align config defaults
- Update `config.yaml` `provider: "voxtral"` to match gschema default
- Or update gschema to match config.yaml

### 5. Test
- `just gnome-ext-dev` → verify streaming works in nested shell
- `groq-voice record --mode hybrid --output stdout` → verify CLI still works

## Files to Modify
1. `src/voice_to_text/config.py` - add `get_api_key()` function
2. `src/voice_to_text/providers/deepgram.py` - use `config.get_api_key()`
3. `src/voice_to_text/providers/groq.py` - use `config.get_api_key()` + remove fake streaming
4. `src/voice_to_text/providers/voxtral.py` - use `config.get_api_key()`
5. `src/voice_to_text/providers/parakeet.py` - use `config.get_api_key()`
6. `config.yaml` or `gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml` - align defaults

## Acceptance Criteria
- `just gnome-ext-dev` starts nested shell
- Press Super+W → recording starts, streaming text appears in focused window
- Press Super+W → recording stops, final text appears
- Logs show "Streaming partial: ..." and "TEXT: ..." prefixes