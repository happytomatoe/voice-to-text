from pathlib import Path

__version__ = "0.1.0"

_SOURCE_HASH = None

try:
    from voice_to_text._build_info import SOURCE_HASH  # type: ignore
    _SOURCE_HASH = SOURCE_HASH
except ImportError:
    pass


def source_hash() -> str | None:
    return _SOURCE_HASH or None


def default_db_path() -> Path:
    return Path.home() / ".local" / "share" / "voice-to-text" / "usage.db"

