"""Audio recording for IBus Cloud Speech engine."""

import numpy as np
import sounddevice as sd
import logging

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BLOCK_SIZE = 2048


class AudioRecorder:
    """Audio recorder for voice input."""

    def __init__(self, device=None, callback=None):
        self._device = device
        self._callback = callback
        self._stream = None
        self._recording = False
        self._recorded_frames = []
        self._last_level = 0.0

    def start_recording(self):
        """Start audio recording."""
        if self._recording:
            return

        self._recording = True
        self._recorded_frames = []

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning("Audio callback status: %s", status)

            float_data = indata[:, 0].astype(np.float32) / 32768.0
            self._recorded_frames.append(indata.copy())

            if self._callback:
                rms = np.sqrt(np.mean(float_data ** 2))
                level = min(rms * 5, 1.0)
                self._last_level = level
                self._callback(level)

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=BLOCK_SIZE,
                dtype="int16",
                callback=audio_callback,
                device=self._device,
            )
            self._stream.start()
            logger.info("Audio recording started")
        except Exception as e:
            logger.error("Failed to start audio recording: %s", e)
            self._recording = False
            raise

    def stop_recording(self):
        """Stop recording and return audio data."""
        if not self._recording:
            return None

        self._recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning("Error stopping stream: %s", e)
            self._stream = None

        if not self._recorded_frames:
            logger.warning("No audio frames recorded")
            return None

        audio_data = np.concatenate(self._recorded_frames, axis=0)
        logger.info("Recording stopped, captured %d frames", len(self._recorded_frames))
        return audio_data

    def get_audio_level(self):
        """Get current audio level (0-1)."""
        return self._last_level

    @staticmethod
    def list_devices():
        """List available audio input devices."""
        try:
            devices = sd.query_devices()
            if isinstance(devices, dict):
                return [devices]
            return devices
        except Exception as e:
            logger.error("Failed to query audio devices: %s", e)
            return []