"""End-to-end tests for voice-to-text CLI."""

import os
import struct
import subprocess
import sys
import tempfile
import wave

import pytest

from voice_to_text.config import ConfigManager
from voice_to_text.hybrid import HybridTranscriber
from voice_to_text.providers.base import BatchProvider, StreamingProvider
from voice_to_text.providers.deepgram import DeepgramProvider
from voice_to_text.providers.groq import GroqProvider
from voice_to_text.providers.parakeet import ParakeetProvider
from voice_to_text.providers.voxtral import VoxtralProvider


@pytest.fixture
def create_test_wav(duration_ms=100, sample_rate=16000):
    """Create a minimal WAV file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    num_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(wav_path, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        # Write silence
        wav.writeframes(struct.pack("<" + "h" * num_samples, *([0] * num_samples)))

    yield wav_path

    if os.path.exists(wav_path):
        os.unlink(wav_path)


class TestCLIHelp:
    """Test CLI help and basic commands."""

    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "-m", "voice_to_text.main", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "Voice to Text" in result.stdout or "voice-to-text" in result.stdout

    def test_record_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "voice_to_text.main", "record", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "--mode" in result.stdout
        assert "--provider" in result.stdout

    def test_devices_command(self):
        result = subprocess.run(
            [sys.executable, "-m", "voice_to_text.main", "devices"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "Available audio input devices" in result.stdout


class TestModeArgument:
    """Test --mode argument parsing."""

    def test_mode_batch(self):
        result = subprocess.run(
            [sys.executable, "-m", "voice_to_text.main", "--help"], capture_output=True, text=True, timeout=10
        )
        assert "batch" in result.stdout

    def test_mode_hybrid(self):
        result = subprocess.run(
            [sys.executable, "-m", "voice_to_text.main", "--help"], capture_output=True, text=True, timeout=10
        )
        assert "hybrid" in result.stdout

    def test_mode_streaming(self):
        result = subprocess.run(
            [sys.executable, "-m", "voice_to_text.main", "--help"], capture_output=True, text=True, timeout=10
        )
        assert "streaming" in result.stdout


class TestRecordHelp:
    """Test record subcommand help."""

    def test_record_help_has_streaming_provider(self):
        result = subprocess.run(
            [sys.executable, "-m", "voice_to_text.main", "record", "--help"], capture_output=True, text=True, timeout=10
        )
        assert "--streaming-provider" in result.stdout

    def test_record_help_has_batch_provider(self):
        result = subprocess.run(
            [sys.executable, "-m", "voice_to_text.main", "record", "--help"], capture_output=True, text=True, timeout=10
        )
        assert "--batch-provider" in result.stdout


class TestProviderImports:
    """Test that all providers can be imported."""

    def test_import_batch_providers(self):
        assert GroqProvider is not None
        assert DeepgramProvider is not None
        assert VoxtralProvider is not None
        assert ParakeetProvider is not None

    def test_import_streaming_providers(self):
        assert GroqProvider is not None
        assert DeepgramProvider is not None

    def test_import_hybrid_transcriber(self):
        assert HybridTranscriber is not None


class TestProviderABCs:
    """Test that providers implement correct ABCs."""

    def test_groq_is_batch_provider(self):
        assert issubclass(GroqProvider, BatchProvider)

    def test_deepgram_is_batch_and_streaming(self):
        assert issubclass(DeepgramProvider, BatchProvider)
        assert issubclass(DeepgramProvider, StreamingProvider)

    def test_voxtral_is_batch_provider(self):
        assert issubclass(VoxtralProvider, BatchProvider)

    def test_voxtral_is_streaming_provider(self):
        assert issubclass(VoxtralProvider, StreamingProvider)

    def test_parakeet_is_batch_provider(self):
        assert issubclass(ParakeetProvider, BatchProvider)


class TestHybridTranscriber:
    """Test HybridTranscriber functionality."""

    def test_hybrid_transcriber_initialization(self):
        # Mock configs
        deepgram_config = {"api_key": "test_key"}
        voxtral_config = {"api_key": "test_key"}

        streaming = DeepgramProvider(deepgram_config)
        batch = VoxtralProvider(voxtral_config)

        hybrid = HybridTranscriber(streaming, batch)
        assert hybrid.streaming is streaming
        assert hybrid.batch is batch
        assert hybrid.partial_text == ""


class TestConfigLoading:
    """Test configuration loading."""

    def test_config_loads(self):
        config_mgr = ConfigManager()
        assert config_mgr.config is not None

    def test_config_has_hybrid_mode(self):
        config_mgr = ConfigManager()
        mode = config_mgr.config.get("transcription", {}).get("mode", "batch")
        assert mode in ["batch", "hybrid", "streaming"]


class TestGNOMESchema:
    """Test GNOME extension schema."""

    def test_schema_file_exists(self):
        schema_path = "gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml"
        assert os.path.exists(schema_path)

    def test_schema_has_mode_key(self):
        schema_path = "gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml"
        with open(schema_path) as f:
            content = f.read()
        assert 'name="mode"' in content
        assert '"batch"' in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
