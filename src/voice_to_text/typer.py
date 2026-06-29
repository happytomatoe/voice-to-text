"""
Continuous dotoolc typing engine for voice-to-text.

Keeps a persistent ``dotoolc`` (client to ``dotoold`` daemon) process open
and feeds it a stream of ``type ...\n`` and ``key backspace\n`` commands
via stdin. The process stays alive for the duration of the recording session.

``dotoolc`` (vs. ``dotool`` direct): ``dotoolc`` is a client to the ``dotoold``
daemon, which keeps virtual input devices registered — lower latency than
``dotool`` which re-registers devices on every invocation. ``dotoold`` is
assumed running (set up by ``dotool-quickstart.sh`` as a systemd user service).

References:
  - dotool docs: https://git.sr.ht/~geb/dotool
  - nerd-dictation diff algorithm: https://github.com/ideasman42/nerd-dictation
"""

import asyncio
import logging
import os
import shutil

logger = logging.getLogger(__name__)


class DotoolcNotFoundError(RuntimeError):
    """Raised when ``dotoolc`` is not found in PATH."""


class ContinuousTyper:
    """Types text via a persistent pipe to the ``dotoolc`` binary.

    Usage::

        typer = ContinuousTyper()
        await typer.start()              # open pipe (once at recording start)
        await typer.stream_type("hello")  # push text immediately
        await typer.stream_backspace(3)   # backspace last 3 chars
        ...
        await typer.stop()                # close pipe (recording done)
    """

    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._dotoolc_path: str | None = None
        self._typed_text: str = ""
        self._usable: bool = True  # set to False after first write failure

    async def start(self) -> None:
        """Start a persistent dotoolc process and keep stdin open."""
        self._dotoolc_path = shutil.which("dotoolc")
        if not self._dotoolc_path:
            # Check ~/.local/bin as fallback
            local_bin = os.path.expanduser("~/.local/bin/dotoolc")
            if os.path.isfile(local_bin) and os.access(local_bin, os.X_OK):
                self._dotoolc_path = local_bin
            else:
                raise DotoolcNotFoundError(
                    "dotoolc not found in PATH or ~/.local/bin. "
                    "Install dotool: https://git.sr.ht/~geb/dotool\n"
                    "dotoolc requires dotoold running (dotool-quickstart.sh)"
                )

        self._process = await asyncio.create_subprocess_exec(
            self._dotoolc_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._typed_text = ""

        # Send initial configuration: zero delays for snappy typing
        assert self._process.stdin is not None
        self._process.stdin.write(b"keydelay 0\ntypedelay 0\n")
        try:
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            # dotoold not running — process started but pipe is dead
            logger.warning("dotoolc pipe broken (dotoold not running?), disabling typing")
            await self.stop()
            self._usable = False
            raise DotoolcNotFoundError(
                "dotoolc pipe broken (dotoold not running?). "
                "Install dotool: https://git.sr.ht/~geb/dotool\n"
                "dotoolc requires dotoold running (dotool-quickstart.sh)"
            )

        logger.info("Continuous dotoolc pipe opened (pid=%d)", self._process.pid)

    async def stream_type(self, text: str) -> None:
        """Push text instantly into the open dotoolc pipe.

        Text is written as ``type <text>\\n`` and flushed immediately.
        Handles newlines by emitting ``key enter`` between lines.
        """
        if not self._usable:
            return
        if not self._process or self._process.returncode is not None:
            logger.warning("dotoolc pipe not open, restarting...")
            await self.start()
        if not self._usable:
            return

        assert self._process is not None
        assert self._process.stdin is not None

        try:
            lines = text.split("\n")
            for i, line in enumerate(lines):
                # dotool interprets backslashes as escape sequences;
                # escape them so literal backslashes are typed
                safe = line.replace("\\", "\\\\")
                cmd = f"type {safe}\n"
                self._process.stdin.write(cmd.encode("utf-8"))
                if i < len(lines) - 1:
                    self._process.stdin.write(b"key enter\n")

            await self._process.stdin.drain()
            self._typed_text += text
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.warning("dotoolc pipe broken, disabling typing: %s", e)
            self._usable = False
        except Exception as e:
            logger.error("Failed to stream text to dotoolc: %s", e)
            self._usable = False

    async def stream_backspace(self, count: int) -> None:
        """Backspace ``count`` characters via the dotoolc pipe."""
        if not self._usable or not self._process or not self._process.stdin:
            return
        if count <= 0:
            return
        try:
            for _ in range(count):
                self._process.stdin.write(b"key backspace\n")
            await self._process.stdin.drain()
            self._typed_text = self._typed_text[:-count]
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.warning("dotoolc pipe broken, disabling typing: %s", e)
            self._usable = False
        except Exception as e:
            logger.error("Failed to stream backspaces to dotoolc: %s", e)
            self._usable = False

    async def stream_diff(self, new_text: str) -> None:
        """Diff ``new_text`` against the previously typed text and send only
        the necessary corrections (backspaces + new suffix).

        This is the nerd-dictation incremental typing algorithm:
        1. Find common prefix length between old and new text.
        2. Backspace the differing suffix.
        3. Type only the new suffix.
        """
        if new_text == self._typed_text:
            return

        old_text = self._typed_text

        # Find common prefix length
        common_len = 0
        min_len = min(len(old_text), len(new_text))
        while common_len < min_len and old_text[common_len] == new_text[common_len]:
            common_len += 1

        backspace_count = len(old_text) - common_len
        new_suffix = new_text[common_len:]

        if backspace_count > 0:
            await self.stream_backspace(backspace_count)
        if new_suffix:
            await self.stream_type(new_suffix)

    async def stop(self) -> None:
        """Close the dotoolc pipe and wait for the process to exit."""
        if self._process and self._process.stdin:
            try:
                self._process.stdin.close()
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except TimeoutError:
                logger.warning("dotoolc did not exit after stdin close; killing")
                self._process.kill()
                await self._process.wait()
            except Exception:
                logger.exception("Failed to close dotoolc cleanly")
            finally:
                logger.info("Continuous dotoolc pipe closed")
                self._process = None
                self._typed_text = ""

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def typed_text(self) -> str:
        return self._typed_text
