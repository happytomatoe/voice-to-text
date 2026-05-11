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
        self._block_count = 0

    def _callback(self, indata, frames, time_info, status):
        if self.is_recording:
            float_data = indata[:, 0].astype(np.float32) / 32768.0
            with self._lock:
                self.frames.append(indata.copy())

            self._block_count += 1
            if self.fft_callback and self._block_count % 3 == 0:
                import gi
                gi.require_version('Gtk', '3.0')
                from gi.repository import GLib
                GLib.idle_add(self.fft_callback, float_data.copy())

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

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            with wave.open(f.name, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            return f.name