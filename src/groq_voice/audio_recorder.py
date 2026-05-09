"""Audio recording module using sounddevice."""
from __future__ import annotations
import sounddevice as sd
import numpy as np
import tempfile
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(self, sample_rate=16000, channels=1, max_duration=30, device=None):
        self.channels = channels
        self.max_duration = max_duration
        self.device = device
        if device is not None:
            props = sd.query_devices(device)
            self.sample_rate = int(props['default_samplerate'])
        else:
            self.sample_rate = sample_rate
        self.frames = []
        self.recording = False
        self._start_time = None
        self._fft_size = 2048

    def get_volume(self):
        """Return current RMS volume (0-1) from accumulated frames."""
        if not self.frames:
            return 0.0
        audio = np.concatenate(self.frames, axis=0).flatten().astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(audio ** 2)))

    def get_frequency_data(self):
        """Return frequency bins (amplitude per frequency) from accumulated frames."""
        if not self.frames:
            return np.array([])
        audio = np.concatenate(self.frames, axis=0).flatten().astype(np.float32) / 32768.0
        fft = np.abs(np.fft.rfft(audio, n=self._fft_size))
        return fft

    def _get_audio_data(self):
        """Return current accumulated audio data."""
        if not self.frames:
            return np.array([], dtype=np.int16)
        return np.concatenate(self.frames, axis=0)

    def start(self):
        """Start recording."""
        self.frames = []
        self.recording = True
        self._start_time = time.time()
        device_idx = self.device if self.device is not None else sd.query_devices(None, 'input')['index']
        props = sd.query_devices(device_idx)
        logger.info(f"Recording using device [{device_idx}] '{props['name']}' at {self.sample_rate} Hz, {props['max_input_channels']} channels")
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            device=self.device,
            callback=self._callback
        )
        self.stream.start()

    @property
    def elapsed(self):
        """Return elapsed recording time in seconds."""
        if self._start_time is None:
            return 0
        return time.time() - self._start_time

    def _callback(self, indata, frames, time, status):
        """Callback for audio input."""
        if self.recording:
            self.frames.append(indata.copy())

    def stop(self) -> Optional[str]:
        """Stop recording and return path to WAV file."""
        self.recording = False
        self.stream.stop()
        self.stream.close()

        if not self.frames:
            return None

        audio_data = np.concatenate(self.frames, axis=0)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            self._write_wav(f.name, audio_data)
            return f.name

    def _write_wav(self, path, audio_data):
        """Write numpy array to WAV file."""
        import wave
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())