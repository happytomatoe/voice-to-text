"""Tests for Parakeet provider."""

from unittest.mock import Mock, patch

from voice_to_text.providers.parakeet import ParakeetProvider


class TestParakeetProvider:
    def test_transcribe_file_sends_language(self):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"text": "hello"}

        provider = ParakeetProvider({})

        with patch("voice_to_text.providers.parakeet.requests.post", return_value=mock_response) as mock_post:
            with patch("builtins.open", create=True):
                provider.transcribe_file("/tmp/test.wav", language="de")

        _, kwargs = mock_post.call_args
        assert kwargs["data"]["language"] == "de"
        assert kwargs["data"]["model"] == provider.model_name
