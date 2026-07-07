# Port Python Voice-to-Text to Gnome Shell Extension (TypeScript)

## Overview

Port the complete voice-to-text Python application (`src/voice_to_text/`) into the existing Gnome Shell extension skeleton (`gnome-ext/`), replacing Python entirely with TypeScript compiled via esbuild to GJS-compatible JavaScript. The result is a fully self-contained gnome extension with no external Python dependency.

## Current State Analysis

**Python Application (`src/voice_to_text/`):**
- CLI entry point (`main.py`): argparse, recording, transcription, output modes
- Audio recording via `sounddevice` (PortAudio bindings) → temp WAV files
- Config via YAML (`ConfigManager`)
- 4 transcription providers:
  - Voxtral: batch (REST) + streaming (Mistral async SDK)
  - Deepgram: batch (REST) + streaming (WebSocket, shared base)
  - Groq: batch only (REST)
  - Parakeet: batch only (local HTTP)
- Hybrid transcider: streaming live text + final batch for accuracy
- Bluetooth headset: HSP/HFP profile switching via `pactl`
- Speaker volume management: `wpctl`/`pactl` save/decrease/restore
- Output: clipboard (`xclip`/`xsel`) or stdout line protocol
- Sleep inhibition via `secret-tool` (unused in flow) and systemd inhibitor

**Existing Gnome Extension (`gnome-ext/`):**
| File | Purpose |
|---|---|
| `extension.js` | Main extension class, spawns Python subprocess, reads stdout protocol |
| `indicator.js` | Panel button with audio level meter, recording UI |
| `hotkey.js` | Hotkey registration via `Main.wm.addKeybinding` |
| `recorder.js` | Subprocess management, stdout parsing, retry logic |
| `typer.js` | dotoolc-based incremental typing (diff algorithm from nerd-dictation) |
| `prefs.js` | Preferences window (Adw) |
| `metadata.json` | Extension metadata, GNOME 45-50 |
| `org.gnome.shell.extensions.voice-to-text.gschema.xml` | GSettings schema |
| `stylesheet.css` | Styling |

**Key Discoveries:**
- The extension already has a proper GSettings schema with all necessary settings (providers, modes, hotkey, etc.)
- `@girs/gnome-shell` v50.0.3 provides TypeScript type definitions for GNOME Shell API (St, Meta, Clutter, Shell, etc.)
- `@girs/gjs` provides GJS runtime types (GLib, Gio, GObject)
- `@girs/gstreamer-1.0` provides GStreamer types for audio capture
- esbuild is the de facto standard for bundling TypeScript → GJS-compatible JS (used by rounded-window-corners extension)
- GStreamer's `appsrc` + `audioconvert` + `autoaudiosrc` pipeline can replace `sounddevice`

## Desired End State

An installable GNOME Shell extension that:

1. Records audio directly via GStreamer in GJS (no Python subprocess)
2. Transcribes via Voxtral, Deepgram, Groq, and/or Parakeet providers
3. Supports batch, streaming, and hybrid modes (streaming + batch)
4. Auto-switches BT headset to HSP/HFP for microphone capture
5. Manages speaker volume during recording
6. Outputs text via dotoolc (type) or clipboard
7. Shows audio level meter in the top panel
8. Has full preferences dialog
9. Is built from TypeScript source via esbuild
10. Passes type checking with `@girs/gnome-shell` types

### Key Constraints:
- All GNOME Shell imports (`gi://`, `resource://`) must be external in esbuild
- GJS supports ES modules in GNOME 45+ via `import` syntax
- GObject subclasses use `GObject.registerClass()` (already done in indicator.js)
- TypeScript decorators are NOT compatible with GJS — use `GObject.registerClass` pattern

## What We're NOT Doing

- Not porting `parakeet-v2.sh` or install scripts (they work independently)
- Not porting `debugging.md` or test infrastructure initially
- Not adding new providers beyond what Python supports
- Not adding TTS/voice synthesis
- Not supporting Windows/macOS (GNOME Shell only)
- Not replacing dotoolc (it remains as the typing engine)

## Implementation Approach

**Strategy:** Incremental replacement. Each phase produces a testable artifact. The existing JS extension continues to work while we build the TS replacement in a parallel directory structure.

**Directory layout (new):**
```
gnome-ext/
├── src/                    # TypeScript source
│   ├── extension.ts        # Main extension class
│   ├── indicator.ts        # Panel indicator
│   ├── hotkey.ts           # Hotkey management
│   ├── typer.ts            # dotoolc typing
│   ├── prefs.ts            # Preferences window
│   ├── audio.ts            # GStreamer audio capture
│   ├── config.ts           # GSettings wrapper
│   ├── bluetooth.ts        # BT headset HSP/HFP switching
│   ├── speaker.ts          # Speaker volume management
│   ├── providers/
│   │   ├── index.ts        # Provider factory/registry
│   │   ├── base.ts         # BatchProvider/StreamingProvider interfaces
│   │   ├── deepgram.ts     # Deepgram provider
│   │   ├── groq.ts         # Groq provider
│   │   ├── voxtral.ts      # Voxtral provider
│   │   └── parakeet.ts     # Parakeet provider
│   └── hybrid.ts           # HybridTranscriber
├── dist/                   # Compiled output (esbuild)
├── schemas/                # GSettings (unchanged)
├── metadata.json           # Extension metadata (unchanged)
├── stylesheet.css          # Styles (unchanged)
├── package.json            # npm project
├── tsconfig.json           # TypeScript config
├── esbuild.config.mjs      # Build script
└── run-dev.sh              # Slightly modified
```

---

## Phase 1: Build Infrastructure

### Overview
Set up the TypeScript build pipeline, install type definitions, verify basic compilation.

### Changes Required:

#### 1. Create `gnome-ext/package.json`
Initialize npm project with:
```json
{
  "name": "voice-to-text-gnome",
  "private": true,
  "scripts": {
    "build": "node esbuild.config.mjs",
    "watch": "node esbuild.config.mjs --watch",
    "check": "tsc --noEmit",
    "install-ext": "bash run-dev.sh"
  },
  "devDependencies": {
    "esbuild": "^0.28.1",
    "typescript": "^6.0.3"
  },
  "dependencies": {
    "@girs/gnome-shell": "^50.0.3",
    "@girs/gjs": "^4.0.4",
    "@girs/gstreamer-1.0": "^1.24.0-4.0.4",
    "@girs/gst-plugins-base-1.0": "^1.24.0-4.0.4",
    "@girs/gio-2.0": "^2.88.0-4.0.4",
    "@girs/glib-2.0": "^2.88.0-4.0.4",
    "@girs/gobject-2.0": "^2.88.0-4.0.4"
  }
}
```

#### 2. Create `gnome-ext/tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ES2020",
    "moduleResolution": "bundler",
    "strict": true,
    "skipLibCheck": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "declaration": false,
    "sourceMap": false
  },
  "include": ["src/**/*.ts"]
}
```

#### 3. Create `gnome-ext/esbuild.config.mjs`
```javascript
import esbuild from 'esbuild';
import { rmSync } from 'fs';

const args = process.argv.slice(2);
const watch = args.includes('--watch');

// Clean dist
rmSync('dist', { recursive: true, force: true });

const config = {
  entryPoints: [
    'src/extension.ts',
    'src/prefs.ts',
  ],
  outdir: 'dist',
  bundle: true,
  format: 'esm',
  target: 'es2020',
  platform: 'node',  // GJS is node-like
  external: [
    'gi://*',        // GObject introspection imports
    'resource://*',  // GNOME Shell resource imports
    '@girs/*',       // Type defs only, not runtime
  ],
};

if (watch) {
  const ctx = await esbuild.context(config);
  await ctx.watch();
  console.log('Watching for changes...');
} else {
  await esbuild.build(config);
  console.log('Built to dist/');
}
```

#### 4. Update `gnome-ext/run-dev.sh`
- After copying files, also copy `dist/*.js` to the extension dir
- Or symlink the dist directory

#### 5. Verify compilation
- `npm run check` passes (tsc --noEmit)
- `npm run build` produces `dist/extension.js` and `dist/prefs.js`

### Verification

#### Automated:
- [ ] `npm install` succeeds
- [ ] `npm run check` passes (tsc noEmit)
- [ ] `npm run build` produces `dist/extension.js` and `dist/prefs.js`
- [ ] Build outputs contain no `gi://` or `resource://` bundled (kept as external)

#### Manual:
- [ ] Extension installs via `run-dev.sh` and appears in gnome-extensions list
- [ ] Extension loads without errors in Looking Glass (`lg`)

---

## Phase 2: Provider Abstraction (TypeScript)

### Overview
Port all 4 transcription providers to TypeScript, maintaining the same interface pattern as Python.

### Changes Required:

#### 1. `gnome-ext/src/providers/base.ts`
TypeScript interfaces matching Python's ABCs:

```typescript
export interface BatchProvider {
  readonly name: string;
  transcribeFile(audioPath: string, language?: string): Promise<string>;
}

export interface StreamingProvider {
  readonly name: string;
  startStream(language?: string, sampleRate?: number): void;
  sendAudio(chunk: ArrayBuffer): void;
  getPartialResult(): string | null;
  finalizeStream(): string;
}
```

**WebSocket integration:** GJS has `Gio.SocketClient` and `Gio.SocketConnection` for WebSocket-like communication. Alternatively, use `Soup` (from `@girs/soup-3.0`) for WebSocket support.

Key differences from Python:
- GJS has no `websocket-client` library — use Gio/Soup for HTTP and WebSocket
- `fetch()` is available in GNOME 45+ via GJS or use Soup.Session for HTTP requests
- Promise-based async fits GJS's pattern well

#### 2. `gnome-ext/src/providers/index.ts`
Factory function matching Python's `get_batch_provider` / `get_streaming_provider`.

#### 3. `gnome-ext/src/providers/deepgram.ts`
- Batch: HTTP POST via `Soup.Session` to Deepgram REST API
- Streaming: WebSocket to Deepgram's real-time API via Soup.WebsocketConnection
- Same auth pattern: `Token {api_key}` header
- Parse Deepgram's JSON response format (nested `results.channels[].alternatives[].transcript`)

#### 4. `gnome-ext/src/providers/groq.ts`
- Batch only: HTTP POST via `Soup.Session` to Groq REST API
- Uses `whisper-large-v3-turbo` model (configurable)
- No streaming support (same as Python)

#### 5. `gnome-ext/src/providers/voxtral.ts`
- Batch: HTTP POST via `Soup.Session` to Mistral API
- Streaming: WebSocket to Mistral's realtime API
- Note: Voxtral streaming in Python uses Mistral SDK's async realtime. GJS equivalent will use raw WebSocket via Soup
- Same model names: `voxtral-mini-latest` (batch), `voxtral-mini-transcribe-realtime-2602` (streaming)

#### 6. `gnome-ext/src/providers/parakeet.ts`
- Batch only: HTTP POST to local `http://localhost:5092`
- No auth needed (local inference server)
- Same API shape as Python

### Verification

#### Automated:
- [ ] `npm run check` passes with all provider types
- [ ] `npm run build` succeeds

#### Manual:
- [ ] Provider factory creates instances without error
- [ ] (Requires API keys) Each provider can be instantiated with valid config

---

## Phase 3: Audio Engine with GStreamer

### Overview
Replace `sounddevice` (PortAudio) with GStreamer pipeline managed in GJS.

### Changes Required:

#### 1. `gnome-ext/src/audio.ts`
GStreamer-based `AudioRecorder` class:

```typescript
import Gst from 'gi://Gst?version=1.0';
import GstBase from 'gi://GstBase?version=1.0';

class AudioRecorder {
  private pipeline: Gst.Pipeline | null;
  
  start(sampleRate?: number): void {
    // Pipeline: autoaudiosrc ! audioconvert ! audioresample ! queue ! wavenc ! filesink
    // Plus a tee to appsink for live level monitoring
  }
  
  stop(): string | null {
    // Send EOS, return file path
  }
  
  getLevel(): number {
    // Read from appsink or level element
  }
}
```

**Pipeline design:**
```
autoaudiosrc name=src !
  audioconvert !
  audioresample !
  capsfilter caps="audio/x-raw,format=S16LE,rate=16000,channels=1" !
  tee name=t
  t. ! queue ! wavenc ! filesink location=/tmp/voice-XXXXXX.wav
  t. ! queue ! appsink name=levelsink max-buffers=1 drop=true
```

**Level calculation:** Read buffer from `appsink`, calculate RMS manually or use `level` GStreamer element.

**Key GStreamer GIR types needed:**
- `@girs/gstreamer-1.0` for `Gst.Pipeline`, `Gst.Element`, `Gst.Bus`, etc.
- `@girs/gst-plugins-base-1.0` for `GstApp.AppSink`

#### 2. `gnome-ext/src/speaker.ts`
Port `SpeakerVolumeManager` from Python:
- `wpctl get-volume @DEFAULT_AUDIO_SINK@` → parse output
- `wpctl set-volume @DEFAULT_AUDIO_SINK@ <value>` → set
- Fallback to `pactl` if `wpctl` not available
- Implement save/decrease/restore lifecycle

#### 3. `gnome-ext/src/bluetooth.ts`
Port from Python's `bluetooth.py`:
- Detect `bluez_card.*` via `pactl list cards`
- Switch to HSP/HFP profile
- Set `bluez_input.*` as default source
- Resume suspended sources

### Verification

#### Automated:
- [ ] `npm run check` passes
- [ ] `npm run build` succeeds

#### Manual:
- [ ] Audio recorder produces valid WAV file
- [ ] Level meter returns meaningful values
- [ ] Speaker volume decrease/restore works
- [ ] BT headset detection + profile switching works

---

## Phase 4: Core Logic

### Overview
Port the remaining core application logic: configuration, hybrid transcriber, recording lifecycle.

### Changes Required:

#### 1. `gnome-ext/src/config.ts`
GSettings wrapper that mirrors Python's `ConfigManager`:
- Read/write to the existing GSettings schema
- Type-safe accessors for all settings (provider, mode, language, etc.)
- Provider config resolution (API key env vars → use `GLib.environ` or `imports.env`)

**API key strategy:** API keys are best read from environment variables. GJS can access env vars via `GLib.getenv()`. The existing schema already stores provider/mode selections.

```typescript
export function getProviderApiKey(provider: string): string | null {
  const envVars: Record<string, string> = {
    deepgram: 'DEEPGRAM_API_KEY',
    groq: 'GROQ_API_KEY',
    voxtral: 'VOXTRAL_API_KEY',
    parakeet: 'PARAKEET_API_KEY',
  };
  const envVar = envVars[provider];
  return envVar ? GLib.getenv(envVar) : null;
}
```

#### 2. `gnome-ext/src/hybrid.ts`
Port `HybridTranscriber`:
- Manages concurrent streaming + batch providers
- Streaming: provides live partial text during recording
- Batch: runs after recording stops for final accurate transcript
- Falls back to streaming result if batch fails

#### 3. Lifecycle integration
The recording lifecycle (already partially in `extension.js`):
- Start → create Recorder → start pipeline → show indicator
- Stop → stop pipeline → transcribe → output text → idle
- Timeout → force stop → cleanup

### Verification

#### Automated:
- [ ] `npm run check` passes
- [ ] `npm run build` succeeds

#### Manual:
- [ ] Hybrid mode produces both streaming text and final accurate text
- [ ] Config reads/writes match GSettings schema
- [ ] API key resolution works for each provider

---

## Phase 5: Extension Integration

### Overview
Convert existing JS files to TypeScript, wire up the new audio/providers/core modules, remove Python subprocess spawning.

### Changes Required:

#### 1. `gnome-ext/src/extension.ts`
Port from `extension.js`:
- Replace `Recorder` (subprocess-based) with direct GStreamer + provider calls
- Remove `_binPath` references
- Keep: indicator management, hotkeys, sleep inhibition, timeout logic, notification display
- Add: direct provider instantiation, audio pipeline management, hybrid mode orchestration

#### 2. `gnome-ext/src/indicator.ts`
Port from `indicator.js`:
- Already uses `GObject.registerClass` — good pattern for TypeScript
- Same UI: icon, spinner, level meter, stop button
- Add type annotations for the GObject class

#### 3. `gnome-ext/src/hotkey.ts`
Port from `hotkey.js`:
- Simple wrapper around `Main.wm.addKeybinding`
- Add proper TypeScript types

#### 4. `gnome-ext/src/typer.ts`
Port from `typer.js`:
- Same dotoolc-based incremental typing
- Keep diff algorithm from nerd-dictation
- Add TypeScript types for `Gio.Subprocess` usage

#### 5. `gnome-ext/src/prefs.ts`
Port from `prefs.js`:
- Already in modern pattern (ES modules, Adw widgets)
- Add TypeScript annotations
- Keep all existing settings UI

#### 6. Remove `gnome-ext/recorder.js`
This file is the Python subprocess wrapper. It gets replaced by direct integration.

### Verification

#### Automated:
- [ ] `npm run check` passes for all files
- [ ] `npm run build` succeeds producing valid GJS modules

#### Manual:
- [ ] Full recording cycle works: hotkey → record → transcribe → output text
- [ ] Indicator shows recording state and level meter
- [ ] Stop button works
- [ ] Preferences dialog shows and saves correctly
- [ ] Sleep inhibition works during recording
- [ ] Timeout recovery works
- [ ] All output methods work: typing (dotoolc), clipboard
- [ ] All transcription modes work: batch, streaming, hybrid
- [ ] All providers work (requires API keys)

---

## Phase 6: Cleanup & Documentation

### Overview
Remove Python code and scripts, update documentation and CI.

### Changes Required:

#### 1. Remove Python source
- Delete `src/voice_to_text/` directory
- Remove `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`
- Remove `scripts/` directory (test audio generator may keep)
- Remove `squashfs-root/` directory

#### 2. Update `README.md`
- Remove Python installation instructions
- Document extension-only installation
- Update requirements (no Python needed)

#### 3. Update `install.sh`
- Simpler: just copy extension files (no Python pip install)

#### 4. Update CI
- `.github/workflows/ci.yml` — remove Python tests, add TypeScript check/build
- `.github/workflows/release.yml` — remove Python build/publish steps

#### 5. Clean up root config files
- Remove `config.yaml` (now handled by GSettings)
- Remove `.pre-commit-config.yaml`, `.ruff_cache/`
- Remove `justfile` (was Python-focused)

#### 6. Keep potentially useful
- `parakeet-v2.sh` — still useful for running Parakeet inference server
- `dotool-quickstart.sh`, `fix-dotoold.sh` — still useful for dotoolc setup
- `docs/dotool.md` — still relevant
- `tests/` — may want to port some test patterns

### Verification

#### Automated:
- [ ] No remaining Python import/execution paths in the extension
- [ ] `npm run build` still succeeds
- [ ] Extension installs cleanly

#### Manual:
- [ ] README accurately reflects new architecture
- [ ] CI passes for TypeScript build
- [ ] No stale Python references in documentation

---

## Testing Strategy

### Per-Phase Verification
Each phase has its own verification criteria (listed above).

### Integration Testing (run-dev.sh --nested)
1. Install extension via `run-dev.sh`
2. Launch nested GNOME Shell: `run-dev.sh --nested`
3. Test full recording cycle
4. Verify indicator UI
5. Test preferences dialog
6. Test different providers (need API keys)
7. Test different modes (batch/streaming/hybrid)
8. Test BT headset integration

### Edge Cases
- No API key configured → graceful error notification
- Recording with no microphone → graceful error
- Very long recording → timeout handling
- Network failure during transcription → retry/fallback
- dotoolc not installed → notification to install
- Provider returns empty transcript → "No speech detected"
- Multiple rapid start/stop → state machine robustness

## Performance Considerations

- GStreamer pipeline adds ~10-20ms latency compared to PortAudio (negligible)
- WebSocket connections should be reused where possible
- WAV file writing to temp directory (same as Python)
- TypeScript bundle size: expect ~100-200KB for provider code + audio
- Memory: streaming buffers ~2MB max (configurable queue sizes)

## Migration Notes

- The existing JS extension can continue working alongside the TS version during development
- Schema changes: no new GSettings keys needed (existing schema is comprehensive)
- The `@girs/gnome-shell` types are for GNOME Shell **50**. The extension's metadata.json claims support back to shell-version 45. TypeScript type checking should target the types we use, but the compiled JS will work on older shells as long as we don't use Shell 50-specific APIs.
- dotoolc remains the typing engine (no replacement needed)
- API keys remain in environment variables (setup via `.profile`/`.bashrc` as before)

## Alternative Approaches Considered

Beyond the TypeScript-in-GJS approach (detailed above), two other architectures were researched:

### Option A: Python DBus Service + Thin GJS Client

**Architecture:**
```
[GNOME Shell Extension (GJS/TS)]
        ↕ Gio.DBusProxy
[Python Background Service (dasbus)]
        ↕
[APIs: Voxtral, Groq, Deepgram, Parakeet]
        ↕
[GStreamer/sounddevice for audio]
```

**How it works:**
- Python app (`voice-to-text`) registers a DBus service on the session bus (e.g. `com.happytomatoe.VoiceToText`)
- The service runs as a systemd --user unit, starting automatically on login
- The gnome extension is minimal: just UI, hotkeys, and DBus proxy calls
- Communication is via DBus method calls and signals
- Extension calls `StartRecording()` on DBus, receives `AudioLevel` signals, gets transcription result

**Available tools:**
- **Python side:** `dasbus` (already available, v1.7), `dbus-python` (v1.4.0), or `pydbus`
- **GJS side:** `Gio.DBusProxy.makeProxyWrapper()` with an XML interface definition
  - Already shown in extension.js's `SessionManagerIface` pattern — the extension already does DBus!
- **Lifecycle:** systemd user service with `Type=dbus` (starts on first bus request, auto-exits on idle)

**Pros:**
- Python code stays as-is (no rewrite)
- Python has mature async/websocket/HTTP libraries
- Service persists even if extension is reloaded (no state loss)
- Provides the service to other consumers (CLI, other extensions)
- Existing `sounddevice` stays — no GStreamer learning curve
- Easier to debug (separate process, can be run standalone)

**Cons:**
- Requires Python + all dependencies installed (no self-contained extension)
- Adds DBus marshalling overhead for every audio level update (~50x/sec)
- More complex deployment (systemd unit, DBus activation file, bus policy)
- Session bus can be unavailable in some contexts (gdm, lock screen)
- Two languages to maintain (Python backend + GJS frontend)
- `voice-to-text` Python binary must discover extension's DBus name — coupling

**DBus marshalling concern:** The existing stdout protocol sends LEVEL lines ~10x/second. Over DBus, each level update requires a signal emission. While DBus is fast enough for this, it adds complexity for real-time data.

---

### Option B: Keep Current Architecture (Python Subprocess + GJS)

**Architecture:**
```
[GNOME Shell Extension (JS)]
        ↕ stdout (line protocol)
[Python CLI Process]
        ↕
[APIs: Voxtral, Groq, Deepgram, Parakeet]
```

**How it works:**
- Exactly as the current codebase works
- Extension spawns Python as a child process per recording session
- Communication via the existing stdout line protocol (START/LEVEL:/TEXT:/ERROR:)
- Python process is ephemeral (spawned per recording, dies after transcription)

**Pros:**
- Zero changes needed to working code
- Python handles HTTP/WebSocket/audio with battle-tested libraries
- Clean process isolation (extension crash doesn't lose recording)
- Existing codebase already works and is tested
- Independent CLI mode still available
- `recorder.js` already handles retries, timeouts, graceful kill

**Cons:**
- Requires Python 3.13+ environment (brittle dependency chain)
- Slow spawn: ~500ms to import Python, load all providers, start audio
- No streaming audio levels until Python sends START token
- Full Python toolchain needed for extension to function
- The existing codebase has startup retry logic (recorder.js) — a symptom of the spawn fragility
- Deployment complexity: `uv`, packages, API keys, path discovery

---

### Comparison Table

| Aspect | A: DBus Service | B: Keep Subprocess (Status Quo) | C: Full GJS TypeScript (this plan) |
|---|---|---|---|
| **Python dependency** | Required | Required | None |
| **Code rewrite** | Minimal (add DBus layer) | None | Full rewrite in TS |
| **Extension install** | Complex (systemd, DBus, pip) | Complex (pip, uv) | Simple (copy files) |
| **Audio quality** | sounddevice (proven) | sounddevice (proven) | GStreamer (needs tuning) |
| **Startup latency** | Instant (daemon runs) | ~500ms per spawn | Instant (in-process) |
| **Provider API calls** | Python libs (mature) | Python libs (mature) | Raw HTTP/WS in GJS (less mature) |
| **Real-time UI** | Via DBus signals (overhead) | Via stdout (proven, fast) | In-process (fastest) |
| **State persistence** | Yes (daemon stays running) | No (process per session) | No (extension lifecycle) |
| **Debugging** | Easy (separate process) | Easy (separate process) | Harder (in-shell, Looking Glass) |
| **Type safety** | None (Python dynamic) | None (Python dynamic) | TypeScript (strong) |
| **GNOME integration** | DBus (standard) | stdin/stdout (hacky) | Native GIR (best) |
| **Maintenance burden** | Two codebases | One codebase (Python) | One codebase (TypeScript) |

### Recommendation for This Project

The **Full GJS TypeScript approach (Option C)** is the right choice given the objectives:
- Eliminates Python entirely → zero dependency chain
- Fully self-contained extension → `run-dev.sh` copies files, that's it
- TypeScript provides type safety against GNOME Shell API changes
- No DBus marshalling overhead for real-time audio levels
- Matches the trend of modern GNOME extensions (rounded-window-corners, etc.)

However, Option A (DBus service) would be the pragmatic choice if:
- You want to keep the Python providers as-is (they work well)
- You need the service to be available outside the extension (CLI, other tools)
- You want to avoid GStreamer complexity in GJS

The plan above pursues **Option C** (full GJS TypeScript).

## References

- Type definitions: `@girs/gnome-shell` (https://github.com/gjsify/gnome-shell)
- Type definitions: `@girs/gjs` (https://github.com/gjsify/types)
- Example TS gnome extension: rounded-window-corners (https://github.com/yilozt/rounded-window-corners)
- GJS documentation: https://gjs.guide/
- GStreamer GIR bindings: https://github.com/gjsify/types
- ts-for-gir examples: https://github.com/gjsify/ts-for-gir/tree/main/examples
- dasbus Python DBus library: https://github.com/rhinstaller/dasbus
- Existing Python providers for API reference: `src/voice_to_text/providers/`
- DBus service pattern in GNOME: Gio.DBusProxy (docs.gtk.org/gio/class.DBusProxy.html)
