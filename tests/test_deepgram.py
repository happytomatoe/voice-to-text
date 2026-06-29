"""Tests for Deepgram provider."""

import pytest

from voice_to_text.providers import get_batch_provider
from voice_to_text.providers.deepgram import DeepgramProvider


class TestDeepgramProvider:
    def test_get_deepgram_provider(self):
        config = {"api_key": "test_key"}
        provider = get_batch_provider("deepgram", config)
        assert isinstance(provider, DeepgramProvider)
        assert provider.name == "deepgram"

    def test_initialization(self):
        config = {"api_key": "test_key"}
        provider = DeepgramProvider(config)
        assert provider.model == "nova-3"
        assert provider.api_url == "https://api.deepgram.com"

    def test_missing_api_key(self):
        import os

        old_key = os.environ.pop("DEEPGRAM_API_KEY", None)
        try:
            with pytest.raises(ValueError):
                DeepgramProvider({})
        finally:
            if old_key is not None:
                os.environ["DEEPGRAM_API_KEY"] = old_key

    @pytest.mark.asyncio
    async def test_transcribe_file_request_format(self):
        """Test that transcribe_file sends properly formatted request."""
        from unittest.mock import Mock, patch

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": {"channels": [{"alternatives": [{"transcript": "hello world"}]}]}}

        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            config = {"api_key": "test_key"}
            provider = DeepgramProvider(config)

            import os
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(b"RIFF....WAVEfmt ")
                tmp_path = tmp.name

            try:
                result = await provider.transcribe_file(tmp_path)

                assert mock_post.called
                call_args = mock_post.call_args
                url = call_args[0][0]
                assert url == "https://api.deepgram.com/v1/listen"

                params = call_args[1]["params"]
                assert params["model"] == "nova-3"
                assert params["language"] == "en"

                headers = call_args[1]["headers"]
                assert headers["Authorization"] == "Token test_key"
                assert headers["Content-Type"] == "audio/wav"

                content = call_args[1]["content"]
                assert content is not None

                assert result == "hello world"
            finally:
                os.unlink(tmp_path)
