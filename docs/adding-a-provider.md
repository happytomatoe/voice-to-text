# Adding a New Transcription Provider

This guide walks through adding a new speech-to-text provider to voice-to-text.
It uses the **ElevenLabs Scribe** provider (batch-only) as the reference
implementation, since it exercises every step below.

## Overview

Providers live in `src/voice_to_text/providers/` and are wired into a central
factory (`src/voice_to_text/providers/__init__.py`). A provider is one of:

- **Batch** (`BatchProvider`) — transcribes a complete audio file in one call.
  Most cloud providers (Groq, Deepgram, Voxtral, Parakeet, ElevenLabs) are batch.
- **Streaming** (`StreamingProvider` / `WebSocketStreamingProvider`) —
  transcribes audio in real time. Only Deepgram and Voxtral support streaming.

A provider can be batch-only, streaming-only, or both (Deepgram/Voxtral are
both). **A batch-only provider must NOT be added to the streaming dropdown** —
`tests/test_gnome_providers.py` enforces this and will fail otherwise.

## 1. Create the provider module

Create `src/voice_to_text/providers/<provider>.py`. Implement `BatchProvider`
(or `StreamingProvider`):

```python
"""<Provider> transcription provider."""

import logging
from pathlib import Path
from typing import Any

import httpx  # or the provider SDK

from .base import BatchProvider, resolve_api_key

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "..."


class MyProvider(BatchProvider):
    def __init__(self, config: dict[str, Any]):
        # provider_name is REQUIRED so the keyring backend can resolve the key
        self.api_key = resolve_api_key(
            config, "MYPROVIDER_API_KEY", provider_name="myprovider"
        )
        self.model = config.get("model", DEFAULT_MODEL)
        self.api_url = config.get("api_url", "https://api.example.com")

    async def transcribe_file(self, audio_path: str, language: str = "en") -> str:
        logger.info("Transcribing %s with %s", audio_path, self.model)
        # ... perform the transcription request ...
        return text

    async def close(self) -> None:
        """Release persistent resources. No-op if you use a per-call client."""
        # e.g. await self.client.close() — or just `pass` when there is none

    @property
    def name(self) -> str:
        return "myprovider"
```

### Contract details (keyring refactor, #51)

- **`close()` is abstract and required.** Even batch providers must implement
  it. Use `pass` when there is no persistent connection (e.g. you create the
  HTTP client per call inside `transcribe_file`).
- **Always pass `provider_name` to `resolve_api_key`.** It maps to the keyring
  entry `service=voice-to-text username=<provider>`. Without it,
  `api_key_source: "keyring"` cannot find the key.
- **All imports must be at module level** (project rule in `AGENTS.md`).

## 2. Register in the factory

Edit `src/voice_to_text/providers/__init__.py`:

```python
from .myprovider import MyProvider
...
_BATCH_PROVIDERS = {
    ...
    "myprovider": MyProvider,
}
```

- Add the import in isort/alphabetical order.
- Batch-only providers go **only** in `_BATCH_PROVIDERS`. Add to
  `_STREAMING_PROVIDERS` only if the provider supports streaming.
- The provider key (`"myprovider"`) is what users set in `config.yaml`
  (`transcription.provider`) and select in the GNOME dropdown.

## 3. Add configuration

In `config.yaml`, add a provider block:

```yaml
myprovider:
  api_key_env: "MYPROVIDER_API_KEY"
  model: "default-model"
```

Update the `transcription.provider` comment to list the new option.

### API keys / keyring

Keys are resolved at runtime by `resolve_api_key` (step 1). Store them in the
OS keyring:

```bash
secret-tool store --label="MyProvider API Key" service voice-to-text username myprovider
# or
python3 -c "import keyring, getpass; keyring.set_password('voice-to-text', 'myprovider', getpass.getpass('Key: '))"
```

Enable the keyring backend globally or per-provider:

```yaml
transcription:
  api_key_source: "keyring"   # or set `api_key_source` under the provider block
```

> The legacy `service/voice-to-text-dbus-wrapper` that exported keys via
> `secret-tool lookup` was removed in #51; key loading now happens in Python
> inside `resolve_api_key`.

## 4. Surface in the GNOME extension

Edit `gnome-ext/prefs.js`:

```js
providerCombo.append('myprovider', 'MyProvider');
// and, for batch providers, also:
batchProviderCombo.append('myprovider', 'MyProvider');
// DO NOT add batch-only providers to streamingProviderCombo
```

Update the summary text in
`gnome-ext/schemas/org.gnome.shell.extensions.voice-to-text.gschema.xml`
(the `provider` and/or `batch-provider` keys) to mention the new option. The
key type is `type="s"` (open string), so no enum change is needed.

> **Regression guard:** `tests/test_gnome_providers.py` parses `prefs.js`
> combos and asserts every entry resolves to a registered Python provider.
> Every combo entry MUST have a matching factory registration, or the test
> fails.

## 5. Tests

Mirror `tests/test_elevenlabs.py` / `tests/test_deepgram.py`:

- factory lookup returns the right class and `.name`
- `__init__` defaults (model, api_url, etc.)
- missing API key raises `ValueError`
- a mocked HTTP/SK call verifying the request shape (URL, headers, body fields,
  `text` extraction)

Also add a factory + missing-key case to `tests/test_providers.py` for
completeness.

## 6. Documentation

Update `README.md`:

- add the provider under **Providers** (Cloud / Local)
- add an API-key requirement bullet under **Requirements**
- add the `secret-tool store` command under **API Keys**

## 7. Validate

```bash
uv run ruff check src/voice_to_text/providers/<provider>.py
uv run pyright src/voice_to_text/providers/<provider>.py
uv run pytest            # includes test_gnome_providers.py and the new tests
```

All checks must pass before opening a PR.
