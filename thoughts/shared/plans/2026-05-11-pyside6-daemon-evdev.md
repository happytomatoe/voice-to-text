# PySide6 Daemon with evdev Hotkeys - Implementation Plan

## Overview

Transform voice-to-text into a background daemon that listens for global hotkeys via evdev, shows a real-time frequency visualization using PySide6, records audio, transcribes it, and types the result.

## Current State Analysis

- **Python package**: `src/voice_to_text/` with transcription logic, config, audio handling
- **Audio recorder**: FFT computation exists in `main.py` (`get_bar_values()`) and volume tracking
- **Text injection**: `copy_to_clipboard()` exists in `main.py`; no text typing exists
- **UI**: Currently uses curses terminal UI
- **Architecture**: CLI tool + IBus engine (optional)

## Desired End State

Configurable via config.yaml:
- hotkey: "Super+v"
- output.method: "type" | "clipboard" | "both"

```
┌──────────────────────────────────────────────────────┐
│  System Startup                                      │
│  └── voice-daemon (systemd user service)             │
│       ├── evdev hotkey listener (/dev/input/eventX) │
│       ├── PySide6 frequency graph (overlay window)   │
│       ├── Audio recorder (sounddevice + FFT)         │
│       ├── Transcription (Groq/Voxtral API)           │
│       └── Text injection (xdotool > clipboard)       │
└──────────────────────────────────────────────────────┘
```

## What We're NOT Doing

- IBus engine (keep CLI mode separate)
- curses terminal UI
- GNOME Shell extension
- D-Bus service
- CLI mode (daemon only)

## Implementation Approach

Use **evdev** for low-level keyboard capture + **PySide6** for GUI overlay.

## Phase 1: Core Daemon Structure

### Overview
Create the basic systemd user service and entry point.

### Changes Required

#### 1. New package structure
**Directory**: `src/voice_daemon/`

```
src/voice_daemon/
├── __init__.py
├── main.py           # Main daemon entry point
├── hotkey_listener.py   # evdev keyboard capture
├── audio_capture.py     # sounddevice wrapper
├── frequency_widget.py  # PySide6 FFT visualization
├── transcription.py     # Transcription logic (moved/refactored)
├── text_injector.py     # Text injection (refactored)
└── tray.py             # System tray icon
```

#### 2. Dependencies update
**File**: `pyproject.toml` (ADD new dependencies)
```toml
dependencies = [
    ...existing dependencies...,
    "PySide6>=6.6.0",  # NEW
    "evdev>=1.7.0",    # NEW
]
```

#### 3. Main daemon entry
**File**: `src/voice_daemon/main.py`
```python
import sys
import signal
import logging
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from voice_daemon.hotkey_listener import HotkeyListener
from voice_daemon.audio_capture import AudioCapture
from voice_daemon.frequency_widget import FrequencyWindow

LOG_DIR = Path.home() / ".local" / "share" / "voice_daemon"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "daemon.log"),
        logging.StreamHandler(sys.stderr),
    ],
)

class VoiceDaemon:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.freq_window = FrequencyWindow()
        self.audio_capture = AudioCapture(self.freq_window.update_fft)
        self.hotkey = HotkeyListener(self.on_hotkey)

    def on_hotkey(self):
        """Called when hotkey is pressed."""
        if self.audio_capture.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        self.freq_window.show()
        self.audio_capture.start()

    def stop_recording(self):
        self.freq_window.hide()
        audio_data = self.audio_capture.stop()
        self.transcribe_and_inject(audio_data)

    def transcribe_and_inject(self, audio_data):
        # Existing transcription logic
        pass

    def run(self):
        self.hotkey.start()
        self.app.exec()

    def stop(self):
        self.hotkey.stop()
        self.app.quit()

def main():
    daemon = VoiceDaemon()
    signal.signal(signal.SIGINT, lambda *_: daemon.stop())
    signal.signal(signal.SIGTERM, lambda *_: daemon.stop())
    daemon.run()

if __name__ == "__main__":
    main()
```

### Success Criteria

#### Automated Verification:
- [x] `pip install -e .` installs voice-daemon command (add `voice-daemon = "voice_daemon.main:main"` to pyproject.toml scripts)
- [x] `voice-daemon --help` shows usage
- [x] Service starts without errors: `voice-daemon &`

#### Manual Verification:
- [ ] Daemon runs in background
- [ ] No console window appears
- [ ] `killall voice-daemon` stops it cleanly

---

## Phase 2: evdev Hotkey Listener

### Overview
Implement global hotkey capture using evdev.

### Design Decisions

| Question | Decision |
|----------|----------|
| Q1: evdev vs python-evdev | Use `evdev` package (python-evdev) |
| Q2: Which device | Listen to all keyboards (`/dev/input/event*`) |
| Q3: Key combination | Super+V (mod4 + KEY_V) |
| Q4: Single key vs combo | Listen for mod4 modifier + V |

### Changes Required

**File**: `src/voice_daemon/hotkey_listener.py`
```python
import select
import logging
from threading import Thread, Event
from evdev import InputDevice, ecodes, list_devices

logger = logging.getLogger(__name__)

class HotkeyListener:
    def __init__(self, callback, key_combo=(ecodes.KEY_V,)):
        """
        callback: function to call when hotkey is pressed
        key_combo: tuple of keys that must all be pressed (mod4 = Super)
        """
        self.callback = callback
        self.key_combo = key_combo
        self.mod_keys = {ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA}  # Super keys
        self.active_keys = set()
        self.running = Event()
        self.thread = None

    def _find_keyboards(self):
        """Find all keyboard devices."""
        devices = []
        for path in list_devices():
            try:
                dev = InputDevice(path)
                if any(cap in dev.capabilities().get(ecodes.EV_KEY, [])
                       for cap in [ecodes.KEY_A, ecodes.KEY_Q]):
                    devices.append(dev)
            except:
                pass
        return devices

    def _listen(self):
        devices = self._find_keyboards()
        logger.info(f"Listening on {len(devices)} keyboard devices")

        while self.running.is_set():
            r, _, _ = select.select(devices, [], [], 0.5)

            for dev in r:
                for event in dev.read():
                    if event.type == ecodes.EV_KEY:
                        key = event.value  # 0=up, 1=down, 2=hold
                        code = event.code

                        if key == 1:  # key down
                            if code in self.mod_keys:
                                self.active_keys.add(code)
                            if self._check_combo():
                                self.callback()

                        elif key == 0:  # key up
                            self.active_keys.discard(code)

    def _check_combo(self):
        """Check if Super+V is pressed."""
        has_mod = any(k in self.active_keys for k in self.mod_keys)
        has_v = ecodes.KEY_V in self.active_keys
        return has_mod and has_v

    def start(self):
        self.running.set()
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()
        logger.info("Hotkey listener started (Super+V)")

    def stop(self):
        self.running.clear()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Hotkey listener stopped")
```

### Success Criteria

#### Automated Verification:
- [x] `python -c "from evdev import list_devices; print(list(list_devices()))"` works
- [x] No permission errors accessing /dev/input/event*

#### Manual Verification:
- [ ] Pressing Super+V triggers callback
- [ ] Works even when no Qt window is focused
- [ ] Multiple keyboards (laptop + USB) both work

---

## Phase 3: PySide6 Frequency Visualization

### Overview
Create the overlay window that shows real-time FFT frequency bars.

### Design Decisions

| Question | Decision |
|----------|----------|
| Q1: Window type | Frameless, always-on-top overlay |
| Q2: Position | Bottom-center of screen |
| Q3: Size | 600x200px |
| Q4: Style | Dark semi-transparent background, gradient bars |
| Q5: Number of bars | 32 (logarithmic frequency spacing) |

### Changes Required

**File**: `src/voice_daemon/frequency_widget.py`
```python
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QGradient
from PySide6.QtWidgets import QWidget

NUM_BARS = 32
BLOCK_SIZE = 2048
SAMPLE_RATE = 16000

class FrequencyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_AlwaysStackOnTop)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self.bar_values = np.zeros(NUM_BARS)
        self.smoothed = np.zeros(NUM_BARS)

        # Position at bottom-center
        self.resize(600, 200)
        screen = self.screen()
        if screen:
            geo = screen.geometry()
            self.move((geo.width() - self.width()) // 2, geo.height() - self.height() - 50)

        # Timer for smooth updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(30)  # ~33 FPS

    def update_fft(self, audio_buffer: np.ndarray):
        """Called from audio thread with float32 samples."""
        freqs = np.fft.rfftfreq(BLOCK_SIZE, d=1/SAMPLE_RATE)
        windowed = audio_buffer * np.hanning(BLOCK_SIZE)
        fft_mag = np.abs(np.fft.rfft(windowed))
        fft_db = 20 * np.log10(fft_mag + 1e-10)
        fft_db = np.clip((fft_db + 60) / 60, 0, 1)

        # Logarithmic frequency bins
        freq_bins = np.logspace(np.log10(20), np.log10(SAMPLE_RATE//2), NUM_BARS + 1)

        for i in range(NUM_BARS):
            lo = np.searchsorted(freqs, freq_bins[i])
            hi = max(np.searchsorted(freqs, freq_bins[i + 1]), lo + 1)
            hi = min(hi, len(fft_db))
            self.bar_values[i] = np.max(fft_db[lo:hi]) if hi > lo else 0

        # Smooth
        self.smoothed = 0.7 * self.smoothed + 0.3 * self.bar_values

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 10
        bar_width = (w - 2*margin) / NUM_BARS

        # Background
        painter.fillRect(0, 0, w, h, QColor(20, 20, 30, 200))

        # Bars
        for i, val in enumerate(self.smoothed):
            x = margin + i * bar_width
            bar_h = int(val * (h - 2*margin))
            y = h - margin - bar_h

            # Color gradient: green -> yellow -> red
            if val < 0.5:
                color = QColor(50, 200, 50)  # green
            elif val < 0.8:
                color = QColor(200, 200, 50)  # yellow
            else:
                color = QColor(200, 50, 50)  # red

            painter.fillRect(int(x), y, int(bar_width - 2), bar_h, color)
```

### Success Criteria

#### Automated Verification:
- [ ] Window appears without errors
- [ ] Frameless and transparent background works

#### Manual Verification:
- [ ] Frequency bars animate during recording
- [ ] Window stays on top of other apps
- [ ] Window positioned at bottom-center
- [ ] Semi-transparent background visible

---

## Phase 4: Audio Capture Integration

### Overview
Wire up sounddevice to provide FFT data to the frequency widget during recording.

### Changes Required

**File**: `src/voice_daemon/audio_capture.py`
```python
import numpy as np
import sounddevice as sd
import threading
import tempfile
import wave
from typing import Optional, Callable

class AudioCapture:
    def __init__(self, fft_callback: Optional[Callable] = None, sample_rate=16000):
        self.sample_rate = sample_rate
        self.fft_callback = fft_callback
        self.block_size = 2048
        self.frames = []
        self.stream = None
        self.is_recording = False
        self._start_time = None
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        if self.is_recording:
            float_data = indata[:, 0].astype(np.float32) / 32768.0
            with self._lock:
                self.frames.append(indata.copy())

            if self.fft_callback:
                self.fft_callback(float_data)

    def start(self):
        self.frames = []
        self.is_recording = True
        self._start_time = threading.Event()

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.block_size,
            dtype='int16',
            callback=self._callback,
        )
        self.stream.start()
        self._start_time.set()

    def stop(self) -> Optional[str]:
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        with self._lock:
            if not self.frames:
                return None
            audio_data = np.concatenate(self.frames, axis=0)

        # Save to temp WAV
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            with wave.open(f.name, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            return f.name
```

### Success Criteria

#### Automated Verification:
- [ ] `python -c "import sounddevice as sd; print(sd.query_devices())"` lists microphones
- [ ] Recording creates WAV file

#### Manual Verification:
- [ ] Pressing Super+V shows frequency window
- [ ] FFT bars respond to audio input
- [ ] Releasing hotkey stops recording

---

## Phase 5: Text Injection & Transcription

### Overview
Integrate existing transcription and text injection logic.

### Changes Required

**File**: `src/voice_daemon/main.py` (update)
```python
def transcribe_and_inject(self, audio_path):
    from voice_to_text.providers import get_provider
    from voice_to_text.config import ConfigManager

    config = ConfigManager()
    provider_name = config.get_selected_provider()
    provider = get_provider(provider_name, config.get_provider_config(provider_name))

    text = provider.transcribe_file(audio_path)

    from voice_daemon.text_injector import inject_text
    inject_text(text)

    os.remove(audio_path)
```

### Success Criteria

#### Automated Verification:
- [ ] Transcription completes without error
- [ ] Text injection method called

#### Manual Verification:
- [ ] Transcribed text appears in focused application
- [ ] Works on both X11 and Wayland

---

## Phase 6: System Tray & Auto-start

### Overview
Add system tray icon and systemd user service for auto-start on login.

### Changes Required

#### 1. System tray icon
**File**: `src/voice_daemon/tray.py`
```python
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QCoreApplication

class TrayIcon:
    def __init__(self, on_quit):
        self.tray = QSystemTrayIcon()
        self.tray.setToolTip("Voice to Text")

        menu = QMenu()
        menu.addAction("Quit", on_quit)
        self.tray.setContextMenu(menu)

        self.tray.show()

    def show_message(self, title, msg):
        self.tray.showMessage(title, msg)
```

#### 2. Systemd user service
**File**: `service/voice-daemon.service`
```ini
[Unit]
Description=Voice to Text Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/voice-daemon  # requires adding to pyproject.toml scripts
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

#### 3. Install script
**File**: `justfile`
```makefile
install-daemon:
    pip install -e .
    mkdir -p ~/.config/systemd/user/
    cp service/voice-daemon.service ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable voice-daemon.service
    systemctl --user start voice-daemon.service

uninstall-daemon:
    systemctl --user stop voice-daemon.service
    systemctl --user disable voice-daemon.service
    rm ~/.config/systemd/user/voice-daemon.service
```

### Success Criteria

#### Automated Verification:
- [ ] Service file is valid: `systemd-analyze verify service/voice-daemon.service`
- [ ] pip install works

#### Manual Verification:
- [ ] Tray icon appears after launch
- [ ] Right-click shows menu with Quit option
- [ ] Reboot: daemon starts automatically
- [ ] Tray icon click: shows/hides settings

---

## Phase 7: Configuration

### Overview
Add configuration for hotkey, provider, output method.

### Changes Required

**File**: `config.yaml` (update/add)
```yaml
daemon:
  hotkey: "Super+v"  # Super+v, Ctrl+Alt+v, etc.
  auto_start: true

audio:
  sample_rate: 16000
  device: null  # null = default microphone

transcription:
  provider: "groq"

output:
  method: "type"      # "type" = inject text, "clipboard" = copy only, "both" = type + clipboard
```

### Config loading
**File**: `src/voice_daemon/config.py`
```python
import yaml
from pathlib import Path

class DaemonConfig:
    def __init__(self):
        self.path = Path.home() / ".config" / "voice-daemon" / "config.yaml"
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                self.data = yaml.safe_load(f) or {}
        else:
            self.data = {}
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            yaml.dump(self.data, f)

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.data
        for k in keys:
            val = val.get(k, default)
        return val

    @property
    def hotkey(self):
        return self.get('daemon.hotkey', 'Super+v')

    @property
    def output_method(self):
        return self.get('output.method', 'type')
```

### Text injection
**File**: `src/voice_daemon/text_injector.py` (NEW - does not exist yet)

This module needs to be created. Existing codebase has `copy_to_clipboard()` in `voice_to_text/main.py` but no typing/injection.

```python
def inject_text(text, method='type'):
    if method in ('type', 'both'):
        if inject_text_direct(text):
            return True
    if method in ('clipboard', 'both'):
        if inject_text_clipboard(text):
            return True
    return False
```

### Success Criteria

#### Automated Verification:
- [ ] Config file parsed correctly
- [ ] Hotkey changeable via config

#### Manual Verification:
- [ ] Different hotkey triggers recording
- [ ] Provider setting respected

### Unit Tests:
- Hotkey listener key detection
- Audio capture callback
- FFT computation accuracy

### Integration Tests:
- Full recording → transcription → injection flow
- System tray functionality

### Manual Testing Steps:
1. Install: `pip install -e .`
2. Start daemon: `voice-daemon &`
3. Press Super+V in any application
4. Speak into microphone
5. Release key → text appears
6. Check tray icon
7. Reboot and verify auto-start

---

## Performance Considerations

| Component | Resource |
|-----------|----------|
| evdev listener | ~0% CPU (event-driven) |
| PySide6 GUI | ~2-5% CPU when visible |
| Audio capture | ~1% CPU |
| FFT computation | ~1% CPU |
| Transcription | Network-bound |

**Total expected**: <10% CPU when active, <1% when idle

---

## Dependencies

New dependencies to add:
```toml
dependencies = [
    "PySide6>=6.6.0",
    "evdev>=1.7.0",
]
```

Existing dependencies (already in pyproject.toml):
- sounddevice~=0.5.5
- numpy~=2.4.4
- groq~=1.2.0
- python-dotenv~=1.2.2
- pyyaml~=6.0.3

---

## References

- Existing audio/FFT handling: `src/voice_to_text/main.py` (lines 243-323)
- Existing transcription: `src/voice_to_text/providers/` (get_provider in `__init__.py`)
- Existing ConfigManager: `src/voice_to_text/config.py`
- Existing clipboard: `src/voice_to_text/main.py` (`copy_to_clipboard()`)
- IBus engine (separate): `src/ibus_cloud/engine.py`