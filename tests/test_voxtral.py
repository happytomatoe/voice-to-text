"""Tests for Voxtral provider."""

import pytest

from voice_to_text.providers import get_provider
from voice_to_text.providers.voxtral import VoxtralProvider


class TestVoxtralProvider:
    def test_get_voxtral_provider(self):
        config = {"api_key": "test_key", "model": "voxtral-mini-latest"}
        provider = get_provider("voxtral", config)
        assert isinstance(provider, VoxtralProvider)
        assert provider.name == "voxtral"

    def test_initialization(self):
        config = {"api_key": "test_key"}
        provider = VoxtralProvider(config)
        assert provider.model == "voxtral-mini-latest"
        assert provider.api_url == "https://api.mistral.ai"

    def test_missing_api_key(self):
        # Unset the environment variable for this test
        import os

        old_key = os.environ.pop("VOXTRAL_API_KEY", None)
        try:
            with pytest.raises(ValueError):
                VoxtralProvider({})
        finally:
            if old_key is not None:
                os.environ["VOXTRAL_API_KEY"] = old_key

    def test_transcribe_file_request_format(self):
        """Test that transcribe_file sends properly formatted request."""
        from unittest.mock import Mock, patch

        # Mock the requests.post method
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"text": "test transcription"}

        with patch("requests.post", return_value=mock_response) as mock_post:
            config = {"api_key": "test_key"}
            provider = VoxtralProvider(config)

            # Create a temporary audio file for testing
            import os
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(b"RIFF....WAVEfmt ")  # Minimal WAV header
                tmp_path = tmp.name

            try:
                result = provider.transcribe_file(tmp_path)

                # Verify the request was made correctly
                assert mock_post.called
                call_args = mock_post.call_args

                # Check URL
                assert call_args[0][0] == "https://api.mistral.ai/v1/audio/transcriptions"

                # Check headers
                headers = call_args[1]["headers"]
                assert headers["Authorization"] == "Bearer test_key"

                # Check files parameter
                files = call_args[1]["files"]
                assert "file" in files
                file_tuple = files["file"]
                assert len(file_tuple) == 2  # Should be (filename, file_object)
                assert file_tuple[0] == os.path.basename(tmp_path)

                # Check data parameter
                data = call_args[1]["data"]
                assert data["model"] == "voxtral-mini-latest"
                assert data["language"] == "en"

                # Check result
                assert result == "test transcription"

            finally:
                os.unlink(tmp_path)
