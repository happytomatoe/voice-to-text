"""Base provider interface for transcription services."""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import keyring as keyring_lib

logger = logging.getLogger(__name__)


class BatchProvider(ABC):
    """Provider that transcribes complete audio files."""

    @abstractmethod
    def __init__(self, config: dict[str, Any]):
        pass

    @abstractmethod
    async def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file (batch processing)."""

    @abstractmethod
    async def close(self) -> None:
        """Close provider resources (e.g. HTTP clients)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class StreamingProvider(ABC):
    """Provider that transcribes audio in real-time via streaming."""

    @abstractmethod
    def __init__(self, config: dict[str, Any]):
        pass

    @abstractmethod
    async def start_stream(self, language: str = "en", sample_rate: int = 16000) -> None:
        """Initialize a streaming session."""
        pass

    @abstractmethod
    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send an audio chunk for processing."""
        pass

    @abstractmethod
    async def get_partial_result(self) -> str | None:
        """Get latest partial transcript (may change)."""
        pass

    @abstractmethod
    async def finalize_stream(self) -> str:
        """End stream and return final transcript."""

    @abstractmethod
    async def close(self) -> None:
        """Close provider resources (e.g. HTTP clients)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


# Keyring lookups block on a D-Bus round-trip to the secret service. When
# that service is unreachable (e.g. inside the isolated dbus-run-session used
# by `just gnome-ext-dev`), the call can hang for tens of seconds and, if
# invoked on the asyncio event loop, freeze recording startup. Bound it.
_KEYRING_TIMEOUT = 3.0


def _keyring_get_password(service: str, provider: str, timeout: float = _KEYRING_TIMEOUT) -> str | None:
    """Return the keyring password, or raise on timeout / error.

    Runs the blocking ``keyring.get_password`` in a worker thread and fails
    fast (default 3s) so an unreachable secret service cannot hang startup.
    The worker thread is intentionally not joined on timeout, so the lingering
    keyring call cannot re-block the caller.
    """
    import concurrent.futures

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = ex.submit(keyring_lib.get_password, service, provider)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as e:
            raise RuntimeError(
                f"keyring lookup timed out after {timeout}s (is the secret service reachable on this session bus?)"
            ) from e
    finally:
        ex.shutdown(wait=False)


def resolve_api_key(
    config: dict[str, Any],
    default_env: str,
    extra_envs: tuple[str, ...] = (),
    provider_name: str | None = None,
) -> str:
    """Resolve API key from environment variable, config, or keyring.

    Resolution order (env > config > keyring):
    1. Environment variable (via api_key_env or default_env)
    2. Config file api_key field (plain value only)
    3. Keyring (if api_key_source == "keyring") — may incur ~3s timeout
       on systems without a reachable Secret Service (CI, containers).

    Raises ValueError if not found.
    """
    api_key_source = config.get("api_key_source", "keyring")
    source_used = "none"

    # 1. Environment variable
    env_var = config.get("api_key_env", default_env)
    key = os.getenv(env_var)
    if not key:
        for env in extra_envs:
            key = os.getenv(env)
            if key:
                break
    if key:
        source_used = f"env:{env_var or extra_envs}"

    # 2. Config file
    if not key:
        key = config.get("api_key")
        if key:
            source_used = "config:api_key"

    # 3. Keyring (fallback, may be slow without Secret Service)
    if not key and api_key_source == "keyring" and provider_name:
        try:
            key = _keyring_get_password("voice-to-text", provider_name)
            if key:
                source_used = f"keyring:{provider_name}"
                logger.debug("Resolved API key for %s from keyring", provider_name)
            else:
                logger.debug("No keyring entry for %s", provider_name)
        except Exception as e:
            logger.warning(
                "Keyring lookup failed for %s: %s",
                provider_name,
                e,
            )

    if not key:
        all_vars = (config.get("api_key_env", default_env),) + extra_envs
        raise ValueError(f"No API key found in environment ({all_vars}), config, or keyring")

    # Log key fingerprint for debugging (first 6 + last 4 chars)
    if len(key) > 10:
        fingerprint = f"{key[:6]}...{key[-4:]}"
    else:
        fingerprint = f"{key[:3]}...{key[-2:]}"
    logger.info("API key resolved: provider=%s source=%s fingerprint=%s", provider_name, source_used, fingerprint)

    return key


class WebSocketStreamingProvider(StreamingProvider):
    """Shared WebSocket streaming logic for providers using the Deepgram-compatible protocol.

    Subclasses implement: __init__, transcribe_file, start_stream (URL/headers), name.

    Uses the ``websockets`` async library (replaces legacy websocket-client).
    """

    _partial_result: str | None
    _finalized_text: str
    _ws: Any  # websockets.WebSocketClientProtocol | None

    def _init_ws_state(self) -> None:
        self._partial_result = None
        self._finalized_text = ""
        self._ws = None

    async def _connect_ws(self, ws_url: str, headers: dict[str, str]) -> None:
        """Open a persistent WebSocket connection."""
        import time as _time

        import websockets

        _t0 = _time.monotonic()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        ws_headers = list(headers.items())
        self._ws = await websockets.connect(ws_url, additional_headers=ws_headers)
        self._partial_result = None
        self._finalized_text = ""
        logger.info("[PROFIL] WS connect to %s: %.3fs", ws_url.split("?")[0], _time.monotonic() - _t0)

    async def send_audio(self, audio_chunk: bytes) -> None:
        if self._ws is None:
            raise RuntimeError("Stream not started. Call start_stream() first.")
        try:
            await self._ws.send(audio_chunk)
            await self._process_messages()
        except Exception as e:
            logger.warning("Error sending audio to %s stream: %s", self.name, e)
            self._ws = None
            raise RuntimeError("Streaming connection lost") from e

    async def get_partial_result(self) -> str | None:
        if self._partial_result:
            return (
                (self._finalized_text + " " + self._partial_result).strip()
                if self._finalized_text
                else self._partial_result
            )
        return self._finalized_text or None

    async def finalize_stream(self) -> str:
        if self._ws is None:
            result = (
                (self._finalized_text + " " + self._partial_result).strip()
                if self._partial_result
                else self._finalized_text
            )
            self._partial_result = None
            self._finalized_text = ""
            return result

        try:
            await self._ws.send(json.dumps({"type": "CloseStream"}))
            try:
                async with asyncio.timeout(2.0):
                    while True:
                        msg = await self._ws.recv()
                        if isinstance(msg, str):
                            data = json.loads(msg)
                            msg_type = data.get("type", "")
                            if msg_type == "Results":
                                channel = data.get("channel", {})
                                alternatives = channel.get("alternatives", [{}])
                                transcript = alternatives[0].get("transcript", "") if alternatives else ""
                                if transcript:
                                    self._finalized_text = (self._finalized_text + " " + transcript).strip()
            except TimeoutError:
                pass
        except Exception as e:
            logger.warning("Error closing %s stream: %s", self.name, e)
        finally:
            if self._ws is not None:
                try:
                    await self._ws.close()
                except Exception:
                    pass

        result = self._finalized_text
        self._ws = None
        self._partial_result = None
        self._finalized_text = ""
        return result

    async def _process_messages(self) -> None:
        if self._ws is None:
            return

        try:
            async with asyncio.timeout(0.01):
                while True:
                    msg = await self._ws.recv()
                    if isinstance(msg, str):
                        data = json.loads(msg)
                        msg_type = data.get("type", "unknown")
                        if msg_type == "Results":
                            logger.debug("Deepgram Results: %s", msg)
                            channel = data.get("channel", {})
                            alternatives = channel.get("alternatives", [{}])
                            transcript = alternatives[0].get("transcript", "") if alternatives else ""
                            is_final = data.get("is_final", False)
                            if is_final and transcript:
                                self._finalized_text = (self._finalized_text + " " + transcript).strip()
                                self._partial_result = None
                            elif transcript:
                                self._partial_result = transcript
                        elif msg_type == "Error":
                            logger.error("%s stream error: %s", self.name, data.get("message"))
        except (TimeoutError, asyncio.CancelledError):  # noqa: UP041
            pass
        except Exception as e:
            logger.warning("Error processing %s messages: %s", self.name, e)
            self._ws = None
