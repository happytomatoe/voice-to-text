# Plan: Hybrid Real-Time + Batch Transcription

## Goal
Show fast real-time text while recording, then replace with accurate batch text when recording stops.

## How It Works
```
Recording starts
  → Stream audio to Deepgram → Show live text (~150ms latency)
  
Recording stops
  → Send full WAV to Voxtral → Get accurate text
  → Replace live text with batch result
```

**No mid-recording batch.** Streaming provider handles real-time refinement internally. Batch is the "final answer" at the end.

## Current Architecture
```
Record audio → Save WAV → Send to provider → Get text → Show/copy
```
All providers implement `TranscriptionProvider.transcribe_file(audio_path)` (batch only).

## Target Architecture
```
Record audio → Stream chunks to Deepgram → Show live text (fast)
           ↘ Save WAV file
           
Stop recording → Send WAV to Voxtral → Replace live text with accurate text
```

---

## Phase 1: Split Provider Base into Two ABCs

**Files to change:**
- `src/voice_to_text/providers/base.py`

**New interfaces:**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BatchProvider(ABC):
    """Provider that transcribes complete audio files."""

    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        pass

    @abstractmethod
    def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file (batch processing)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

class StreamingProvider(ABC):
    """Provider that transcribes audio in real-time via streaming."""

    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        pass

    @abstractmethod
    def start_stream(self, language: str = "en") -> None:
        """Initialize a streaming session."""
        pass

    @abstractmethod
    def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk for processing."""
        pass

    @abstractmethod
    def get_partial_result(self) -> str | None:
        """Get latest partial transcript (may change)."""
        pass

    @abstractmethod
    def finalize_stream(self) -> str:
        """End stream and return final transcript."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
```

**Providers that support both:**
```python
class DeepgramProvider(BatchProvider, StreamingProvider):
    """Deepgram supports both batch and streaming."""
    # Implement all methods from both ABCs
```

**Verify:** `python -c "from voice_to_text.providers.base import BatchProvider, StreamingProvider"`

---

## Phase 2: Update Existing Providers to Inherit from BatchProvider

**Files to change:**
- `src/voice_to_text/providers/groq.py` — `GroqProvider(BatchProvider)`
- `src/voice_to_text/providers/deepgram.py` — `DeepgramProvider(BatchProvider, StreamingProvider)`
- `src/voice_to_text/providers/voxtral.py` — `VoxtralProvider(BatchProvider)`
- `src/voice_to_text/providers/parakeet.py` — `ParakeetProvider(BatchProvider)`

Keep existing `transcribe_file()` method, just change base class.

**Verify:** All providers instantiate correctly

---

## Phase 3: Implement Deepgram Streaming

**Files to change:**
- `src/voice_to_text/providers/deepgram.py`

`DeepgramProvider` already inherits `BatchProvider`. Add `StreamingProvider` ABC:
```python
class DeepgramProvider(BatchProvider, StreamingProvider):
    # Existing: transcribe_file() from BatchProvider

    def start_stream(self, language: str = "en") -> None:
        # Open WebSocket to wss://api.deepgram.com/v1/listen
        ...

    def send_audio(self, audio_chunk: bytes) -> None:
        # Send PCM chunk over WebSocket
        ...

    def get_partial_result(self) -> str | None:
        # Return latest transcript delta
        ...

    def finalize_stream(self) -> str:
        # Send CloseStream, return final text
        ...
```

**Verify:** Unit test with mock WebSocket

---

## Phase 4: Implement Groq Streaming

**Files to change:**
- `src/voice_to_text/providers/groq.py`

`GroqProvider` becomes `GroqProvider(BatchProvider, StreamingProvider)` with both sets of methods.

**Verify:** Unit test with mock WebSocket

---

## Phase 5: Create HybridTranscriber

**Files to create:**
- `src/voice_to_text/hybrid.py`

```python
from voice_to_text.providers.base import BatchProvider, StreamingProvider

class HybridTranscriber:
    def __init__(self, streaming: StreamingProvider, batch: BatchProvider):
        self.streaming = streaming
        self.batch = batch
        self.partial_text = ""

    def on_audio_chunk(self, chunk: bytes) -> str:
        """Called during recording. Returns live text for display."""
        self.streaming.send_audio(chunk)
        self.partial_text = self.streaming.get_partial_result() or self.partial_text
        return self.partial_text

    def on_recording_stop(self, audio_path: str, language: str) -> str:
        """Called when recording stops. Returns accurate batch text."""
        self.streaming.finalize_stream()  # Clean up streaming
        try:
            return self.batch.transcribe_file(audio_path, language=language)
        except Exception:
            return self.partial_text  # Fallback to streaming text
```

**Flow:**
1. During recording: `on_audio_chunk()` called repeatedly → returns live text
2. After recording: `on_recording_stop()` called once → returns accurate batch text
3. Caller replaces live text with batch text

**Verify:** Test with mock providers

---

## Phase 6: Update Config for Hybrid Mode

**Files to change:**
- `config.yaml`

```yaml
transcription:
  mode: "batch"           # "batch" or "hybrid"
  provider: "parakeet"
  hybrid:
    streaming_provider: "deepgram"
    batch_provider: "voxtral"
    language: "en"
```

**Verify:** Config loads correctly

---

## Phase 7: Update Provider Registry

**Files to change:**
- `src/voice_to_text/providers/__init__.py`

```python
from .base import BatchProvider, StreamingProvider
from .groq import GroqProvider
from .deepgram import DeepgramProvider
from .voxtral import VoxtralProvider
from .parakeet import ParakeetProvider

_BATCH_PROVIDERS = {
    "groq": GroqProvider,
    "deepgram": DeepgramProvider,
    "voxtral": VoxtralProvider,
    "parakeet": ParakeetProvider,
}

_STREAMING_PROVIDERS = {
    "groq": GroqProvider,
    "deepgram": DeepgramProvider,
}

def get_batch_provider(name: str, config: Dict) -> BatchProvider:
    ...

def get_streaming_provider(name: str, config: Dict) -> StreamingProvider:
    ...
```

**Verify:** Import works, providers instantiate

---

## Phase 8: Update Main to Support Hybrid Mode

**Files to change:**
- `src/voice_to_text/main.py`

1. Add `--mode` argument (`batch` / `hybrid`)
2. In recording flow, check mode:
   - `batch`: Current behavior (record → send file → get text)
   - `hybrid`: 
     - Start streaming provider
     - On each audio callback: send chunk to streaming, display live text
     - On stop: send WAV to batch provider, replace live text with batch result
3. Text replacement: **Backspace + retype** (track displayed text length, erase with backspaces, type new text)

**Text replacement helper:**
```python
class TextDisplay:
    def __init__(self):
        self.displayed = ""
    
    def update(self, new_text: str):
        """Replace displayed text with new text."""
        # Erase old text
        if self.displayed:
            subprocess.run(["ydotool", "type", "-d", "1", "\b" * len(self.displayed)])
        # Type new text
        if new_text:
            subprocess.run(["ydotool", "type", "-d", "1", new_text])
        self.displayed = new_text
```

**Hybrid flow in code:**
```python
# During recording loop
hybrid = HybridTranscriber(deepgram, voxtral)
display = TextDisplay()
hybrid.start_stream(language)

for chunk in audio_stream:
    live_text = hybrid.on_audio_chunk(chunk)
    display.update(live_text)  # Show live text

# After recording stops
final_text = hybrid.on_recording_stop(audio_path, language)
display.update(final_text)  # Replace with accurate batch text
```

**Verify:** `voice-to-text record --mode hybrid` works end-to-end

---

## Verification Checklist

- [ ] `voice-to-text record` (batch) — no regression
- [ ] `voice-to-text record --mode hybrid` — live text during recording
- [ ] After recording stops, live text replaced with batch result
- [ ] Clipboard copy uses batch result (accurate)
- [ ] `config.yaml mode: hybrid` works without CLI flag
- [ ] Falls back to streaming-only if batch provider fails
- [ ] Falls back to batch-only if streaming provider fails
- [ ] All existing tests pass
- [ ] New tests pass

---

## Optional Enhancement: LocalAgreement Policy

To reduce text flicker during streaming, only display text confirmed in 2+ consecutive updates:

```python
class StableTextFilter:
    def __init__(self):
        self.history = []
    
    def update(self, text: str) -> str:
        self.history.append(text)
        if len(self.history) < 2:
            return ""
        # Return longest common prefix of last 2 updates
        return longest_common_prefix(self.history[-2], self.history[-1])
```

This is what Whisper-Streaming uses. Can be added later if flicker is a problem.

---

## Provider ABCs

| Provider | ABCs | Notes |
|----------|------|-------|
| Groq | `BatchProvider, StreamingProvider` | Fast Whisper, WebSocket |
| Deepgram | `BatchProvider, StreamingProvider` | Nova-3, WebSocket |
| Voxtral | `BatchProvider` | Cloud, batch only |
| Parakeet | `BatchProvider` | Local HTTP, batch only |

**Recommended hybrid combos:**
- `streaming: deepgram` + `batch: voxtral` (your choice)
- `streaming: deepgram` + `batch: parakeet` (fast + free/local)
