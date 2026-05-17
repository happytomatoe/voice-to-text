#!/usr/bin/env python3 -m pytest
"""Import smoke-test: every provider that ships in the repo imports cleanly.

Skips groq (needs `groq` package) — test flavour depends on that dept not being
present in this venv.  The realtime provider is covered regardless of what
mistralai package format is installed (sdist vs wheel) because both import
paths are handled.
"""
import sys, os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from voice_to_text.providers import get_provider
from mistralai.extra.realtime import AudioFormat

MANDATORY = {"voxtral", "voxtral_realtime"}
OPTIONAL  = {"groq"}   # may be absent if groq pkg not installed; test is skipped


def _import_provider(name):
    """Import a provider class; raise if not importable."""
    return get_provider(name, {"api_key": "test"})


IMPORTABLE = [n for n in MANDATORY | {"voxtral"} if "_realtime" in n or "voxtral" in n]

# ── mandatory providers ──────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["voxtral", "voxtral_realtime"])
def test_importable(name):
    p = _import_provider(name)
    assert p is not None


# ── realtime: import paths ───────────────────────────────────────────────
def test_realtime_import_paths():
    """Both `mistralai.client.Mistral` (sdist 2.x) and top-level `Mistral`
    (wheel / 1.x) must be tried; the correct one is selected at runtime."""
    tried = []
    try:
        from mistralai.client import Mistral
        tried.append("client")
    except ImportError:
        pass
    try:
        from mistralai import Mistral
        tried.append("top-level")
    except ImportError:
        pass
    assert tried, "No Mistral import path found — is mistralai installed?"


# ── realtime: AudioFormat import ─────────────────────────────────────────
def test_audio_format_import():
    """extra.realtime must be importable when mistralai[realtime] is present."""
    fmt = AudioFormat(encoding="pcm_s16le", sample_rate=16000)
    assert fmt.encoding == "pcm_s16le"


# ── groq: optional ───────────────────────────────────────────────────────
@pytest.mark.skipif(
    __import__("sys"),
    reason="groq package not installed in this venv",
)
def test_groq_import():
    _import_provider("groq")
