"""Tests for audio recording and level metering."""
import os
import wave
from unittest.mock import patch

import numpy as np

from voice_to_text.audio import AudioRecorder, SAMPLE_RATE, BLOCK_SIZE


class TestAudioRecorder:
    def test_records_audio_to_wav(self):
        with patch("voice_to_text.audio.sd.InputStream"):
            recorder = AudioRecorder()
            recorder.start()

            cb = recorder._callback
            chunk = np.zeros((BLOCK_SIZE, 1), dtype=np.int16)
            cb(chunk, BLOCK_SIZE, None, None)

            chunk = (np.ones((BLOCK_SIZE, 1), dtype=np.int16) * 1000)
            cb(chunk, BLOCK_SIZE, None, None)

            filepath = recorder.stop()

        with wave.open(filepath, "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == SAMPLE_RATE
            assert wav.getnframes() == BLOCK_SIZE * 2

        os.unlink(filepath)

    def test_frame_count(self):
        with patch("voice_to_text.audio.sd.InputStream"):
            recorder = AudioRecorder()
            recorder.start()

            cb = recorder._callback
            for _ in range(5):
                cb(np.zeros((BLOCK_SIZE, 1), dtype=np.int16), BLOCK_SIZE, None, None)

            recorder.stop()
            assert recorder.frame_count == 5

        os.unlink(recorder.filepath)

    def test_smoothed_level(self):
        with patch("voice_to_text.audio.sd.InputStream"):
            recorder = AudioRecorder()
            recorder.start()

            cb = recorder._callback
            cb(np.zeros((BLOCK_SIZE, 1), dtype=np.int16), BLOCK_SIZE, None, None)

            first = recorder.smoothed_level
            cb(np.ones((BLOCK_SIZE, 1), dtype=np.int16) * 30000, BLOCK_SIZE, None, None)

            recorder.stop()
            assert first < recorder.smoothed_level

        os.unlink(recorder.filepath)
