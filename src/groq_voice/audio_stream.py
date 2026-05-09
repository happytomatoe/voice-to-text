"""Audio streaming adapter for transcription providers."""
import asyncio
import numpy as np
from typing import AsyncIterator
import logging

logger = logging.getLogger(__name__)

class AudioStreamAdapter:
    """Adapt audio recorder to async stream for transcription providers."""
    
    def __init__(self, audio_recorder, chunk_size=4096):
        self.audio_recorder = audio_recorder
        self.chunk_size = chunk_size
        self._queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
    
    def start(self):
        """Start audio capture and streaming."""
        self.audio_recorder.start()
        self._capture_task = asyncio.create_task(self._capture_audio())
    
    async def _capture_audio(self):
        """Capture audio and push to queue."""
        try:
            while not self._stop_event.is_set():
                if self.audio_recorder.frames:
                    # Get accumulated frames
                    audio_data = self.audio_recorder._get_audio_data()
                    self.audio_recorder.frames = []  # Clear frames
                    
                    # Convert to bytes and chunk
                    audio_bytes = audio_data.tobytes()
                    for i in range(0, len(audio_bytes), self.chunk_size):
                        chunk = audio_bytes[i:i + self.chunk_size]
                        await self._queue.put(chunk)
                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
        except Exception as e:
            logger.exception("Audio capture failed")
        finally:
            self._queue.put_nowait(None)  # Signal end
    
    async def __aiter__(self):
        """Async iterator interface."""
        while True:
            item = await self._queue.get()
            if item is None:  # End signal
                break
            yield item
    
    def stop(self):
        """Stop audio capture."""
        self._stop_event.set()
        self.audio_recorder.stop()
        if hasattr(self, '_capture_task'):
            self._capture_task.cancel()