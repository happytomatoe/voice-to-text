# Plan: GNOME Extension Hybrid Mode Support

## Goal
Add hybrid mode support to the GNOME Shell extension so users can enable real-time streaming + batch transcription from the extension UI.

## Current State
- GSettings schema has `provider` key but no `mode` key
- `recorder.js` passes `--provider` and `--language` to CLI but not `--mode`
- No UI for selecting batch vs hybrid mode

## Target State
- User can select mode (batch/hybrid) in extension preferences
- Extension passes `--mode` to CLI
- Hybrid mode uses streaming provider for live text, batch provider for final result

---

## Phase 1: Add Mode to GSettings Schema

**Files to change:**
- `gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml`

**Add new key:**
```xml
<key name="mode" type="s">
  <default>"batch"</default>
  <summary>Transcription mode (batch or hybrid)</summary>
</key>
```

**Verify:** Schema compiles correctly

---

## Phase 2: Update Recorder to Pass Mode

**Files to change:**
- `gnome-ext/recorder.js`

**Changes:**
```javascript
start() {
  const provider = this._settings.get_string('provider');
  const language = this._settings.get_string('language');
  const mode = this._settings.get_string('mode');  // Add this
  const decreaseSpeakerVolume = this._settings.get_int('decrease-speaker-volume');
  
  const argv = [
    this._appPath,
    '--output', 'stdout',
    '--provider', provider,
    '--language', language,
    '--mode', mode,  // Add this
  ];
  // ... rest of start method
}
```

**Verify:** Extension passes --mode to CLI

---

## Phase 3: Handle Live Text in Extension (Optional)

**Files to change:**
- `gnome-ext/extension.js`
- `gnome-ext/recorder.js`

**Note:** The CLI already handles hybrid mode internally - it streams to provider and shows live text via stdout. The extension just needs to handle `LEVEL:` and `TEXT:` lines appropriately.

**Current behavior in recorder.js:**
- `LEVEL:` lines update audio level indicator
- `TEXT:` lines trigger `onTranscription` callback

**No changes needed** - the CLI handles the hybrid flow and outputs final text via `TEXT:` line.

**Verify:** Hybrid mode works end-to-end via extension

---

## Phase 4: Update Preferences UI

**Files to change:**
- `gnome-ext/prefs.js`
- `gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml`

**Add UI for mode selection:**
```javascript
// In prefs.js, add dropdown for mode selection
const modeOptions = ['batch', 'hybrid'];
const modeCombo = new Gtk.DropDown({
  model: Gtk.StringList.new(modeOptions),
});
```

**Verify:** User can select mode in preferences

---

## Verification Checklist

- [ ] Schema compiles: `glib-compile-schemas gnome-ext/schemas/`
- [ ] Extension loads without errors
- [ ] Preferences show mode dropdown
- [ ] Mode selection persists in GSettings
- [ ] `voice-to-text record --mode batch` works via extension
- [ ] `voice-to-text record --mode hybrid` works via extension
- [ ] Live text appears during hybrid recording
- [ ] Final text replaces live text after recording stops

---

## Notes

- The CLI already supports hybrid mode via `--mode hybrid`
- The extension just needs to pass this flag to the CLI
- No changes needed for handling live text output - the CLI handles this internally
- The `recorder.js` already handles `TEXT:` lines for transcription results