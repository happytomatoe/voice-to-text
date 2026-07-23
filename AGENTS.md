# Agent instructions for voice-to-text

## Python imports

- All imports must be at the module level (top of file), never inside functions or methods.
- Local imports inside functions cause `NameError` when module-level functions reference those names.

## Project overview

Voice-to-text converts speech to text on Linux using free cloud/local APIs. It is a two-part project:

- **Python service** (`src/voice_to_text/`): the transcription engine, audio capture, providers, and a D-Bus service that the GNOME extension calls.
- **GNOME Shell extension** (`gnome-ext/`): JS UI (indicator, hotkey, preferences, typer) that talks to the D-Bus service.

Transcription providers: cloud (Voxtral, Groq, Deepgram) and local (Parakeet). API keys come from env vars, the OS keyring, or `config.yaml`.

## Layout

- `src/voice_to_text/` — Python package (engine, audio, bluetooth, config, dbus_service, typer, providers/).
- `gnome-ext/` — GNOME Shell extension JS/JSON/CSS.
- `tests/` — pytest suite (mirrors `src/` modules).
- `service/` — D-Bus service definition.
- `scripts/` — dev/setup helpers.
- `docs/` — design notes.

## Tooling

- Package + environment manager: **uv** (see `pyproject.toml`). Build backend: hatchling.
- Task runner: **just** (see `justfile`). Key recipes:
  - `just test` — run the test suite (`uv run pytest -n auto`).
  - `just run <args>` — run the CLI with `PYTHONPATH=src`.
  - `just service-run` — run the D-Bus service in the foreground.
  - `just service-install` / `service-uninstall` — install/uninstall the user D-Bus service.
  - `just gnome-ext-dev` — install extension and launch a nested GNOME Shell for development.
- Python version: **3.13+** (`requires-python`).

## Linting and type checking

- **ruff** for lint/format: `ruff check .`, `ruff format .` (line-length 120, py313).
- **pyright** for types: `pyright .`.
- **pre-commit** is configured (see `.pre-commit-config.yaml`); run `pre-commit run --all-files`.

## Testing

- Tests use pytest with `pytest-asyncio` (auto mode) and `pytest-xdist` (`-n auto`).
- `testpaths = tests`, `pythonpath = src` (set in `pyproject.toml`).
- Run a single test file with `uv run pytest tests/test_audio.py`.

## Conventions

- Python imports stay at module level (see above).
- Match existing style; ruff/pyright must pass before committing.
- Commit messages follow Conventional Commits (the repo rejects `Co-Authored-By` trailers in pre-commit).

## JavaScript/TypeScript Error Handling (gnome-ext/)

- **Never leave catch blocks empty.** At minimum, log the error: `catch (e) { console.error(e); }`
- **If you must intentionally ignore an error**, add a comment explaining WHY it's safe:
  ```js
  try { await api.call(); } catch { /* ignore: best-effort notification */ }
  ```
- **Use `catch { }` (no parameter)** when intentionally ignoring — signals intent and avoids unused-variable lint errors.
- **Don't just swallow errors** — this makes debugging impossible and hides production failures.
- **Use `finally` for cleanup** (disconnect signals, close connections, release locks).
