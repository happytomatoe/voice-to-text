"""End-to-end tests for voice-to-text CLI."""
import subprocess
import pytest
import os
import tempfile
import wave
import struct


def create_test_wav(duration_ms=100, sample_rate=16000):
    """Create a minimal WAV file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
        
    num_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(wav_path, 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        # Write silence
        wav.writeframes(struct.pack('<' + 'h' * num_samples, *([0] * num_samples)))
    
    return wav_path


class TestCLIHelp:
    """Test CLI help and basic commands."""
    
    def test_help_exits_zero(self):
        result = subprocess.run(
            ['python', '-m', 'voice_to_text.main', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        assert 'Voice to Text' in result.stdout or 'voice-to-text' in result.stdout
    
    def test_record_help(self):
        result = subprocess.run(
            ['python', '-m', 'voice_to_text.main', 'record', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        assert '--mode' in result.stdout
        assert '--provider' in result.stdout
    
    def test_devices_command(self):
        result = subprocess.run(
            ['python', '-m', 'voice_to_text.main', 'devices'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        assert 'Available audio input devices' in result.stdout


class TestModeArgument:
    """Test --mode argument parsing."""
    
    def test_mode_batch(self):
        result = subprocess.run(
            ['python', '-m', 'voice_to_text.main', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert 'batch' in result.stdout
    
    def test_mode_hybrid(self):
        result = subprocess.run(
            ['python', '-m', 'voice_to_text.main', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert 'hybrid' in result.stdout

    def test_mode_streaming(self):
        result = subprocess.run(
            ['python', '-m', 'voice_to_text.main', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert 'streaming' in result.stdout


class TestRecordHelp:
    """Test record subcommand help."""

    def test_record_help_has_streaming_provider(self):
        result = subprocess.run(
            ['python', '-m', 'voice_to_text.main', 'record', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert '--streaming-provider' in result.stdout

    def test_record_help_has_batch_provider(self):
        result = subprocess.run(
            ['python', '-m', 'voice_to_text.main', 'record', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert '--batch-provider' in result.stdout


class TestProviderImports:
    """Test that all providers can be imported."""
    
    def test_import_batch_providers(self):
        from voice_to_text.providers import get_batch_provider
        from voice_to_text.providers.groq import GroqProvider
        from voice_to_text.providers.deepgram import DeepgramProvider
        from voice_to_text.providers.voxtral import VoxtralProvider
        from voice_to_text.providers.parakeet import ParakeetProvider
        
        assert GroqProvider is not None
        assert DeepgramProvider is not None
        assert VoxtralProvider is not None
        assert ParakeetProvider is not None
    
    def test_import_streaming_providers(self):
        from voice_to_text.providers import get_streaming_provider
        from voice_to_text.providers.groq import GroqProvider
        from voice_to_text.providers.deepgram import DeepgramProvider
        
        assert GroqProvider is not None
        assert DeepgramProvider is not None
    
    def test_import_hybrid_transcriber(self):
        from voice_to_text.hybrid import HybridTranscriber
        assert HybridTranscriber is not None


class TestProviderABCs:
    """Test that providers implement correct ABCs."""
    
    def test_groq_is_batch_provider(self):
        from voice_to_text.providers.base import BatchProvider
        from voice_to_text.providers.groq import GroqProvider
        assert issubclass(GroqProvider, BatchProvider)
    
    def test_deepgram_is_batch_and_streaming(self):
        from voice_to_text.providers.base import BatchProvider, StreamingProvider
        from voice_to_text.providers.deepgram import DeepgramProvider
        assert issubclass(DeepgramProvider, BatchProvider)
        assert issubclass(DeepgramProvider, StreamingProvider)
    
    def test_voxtral_is_batch_provider(self):
        from voice_to_text.providers.base import BatchProvider
        from voice_to_text.providers.voxtral import VoxtralProvider
        assert issubclass(VoxtralProvider, BatchProvider)
    
    def test_parakeet_is_batch_provider(self):
        from voice_to_text.providers.base import BatchProvider
        from voice_to_text.providers.parakeet import ParakeetProvider
        assert issubclass(ParakeetProvider, BatchProvider)


class TestHybridTranscriber:
    """Test HybridTranscriber functionality."""
    
    def test_hybrid_transcriber_initialization(self):
        from voice_to_text.hybrid import HybridTranscriber
        from voice_to_text.providers.deepgram import DeepgramProvider
        from voice_to_text.providers.voxtral import VoxtralProvider
        
        # Mock configs
        deepgram_config = {'api_key': 'test_key'}
        voxtral_config = {'api_key': 'test_key'}
        
        streaming = DeepgramProvider(deepgram_config)
        batch = VoxtralProvider(voxtral_config)
        
        hybrid = HybridTranscriber(streaming, batch)
        assert hybrid.streaming is streaming
        assert hybrid.batch is batch
        assert hybrid.partial_text == ""


class TestConfigLoading:
    """Test configuration loading."""
    
    def test_config_loads(self):
        from voice_to_text.config import ConfigManager
        config_mgr = ConfigManager()
        assert config_mgr.config is not None
    
    def test_config_has_hybrid_mode(self):
        from voice_to_text.config import ConfigManager
        config_mgr = ConfigManager()
        mode = config_mgr.config.get('transcription', {}).get('mode', 'batch')
        assert mode in ['batch', 'hybrid']


class TestGNOMESchema:
    """Test GNOME extension schema."""
    
    def test_schema_file_exists(self):
        schema_path = 'gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml'
        assert os.path.exists(schema_path)
    
    def test_schema_has_mode_key(self):
        schema_path = 'gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml'
        with open(schema_path, 'r') as f:
            content = f.read()
        assert 'name="mode"' in content
        assert '"batch"' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
