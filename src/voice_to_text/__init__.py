__version__ = "0.1.0"

_SOURCE_HASH = None


def source_hash() -> str | None:
    global _SOURCE_HASH
    if _SOURCE_HASH is not None:
        return _SOURCE_HASH
    try:
        from voice_to_text._build_info import SOURCE_HASH  # type: ignore
        _SOURCE_HASH = SOURCE_HASH
    except ImportError:
        _SOURCE_HASH = ""
    return _SOURCE_HASH or None

