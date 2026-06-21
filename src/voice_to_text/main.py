#!/usr/bin/env python3

import argparse
import logging
import os
import select
import signal
import subprocess
import sys
import termios
import threading
import time
import tty
from pathlib import Path

import sounddevice as sd
from dotenv import load_dotenv

from voice_to_text.audio import (
    AudioRecorder,
    SpeakerVolumeManager,
    format_level_bar,
)
from voice_to_text.bluetooth import activate_headset_mic
from voice_to_text.config import ConfigManager
from voice_to_text.hybrid import HybridTranscriber
from voice_to_text.providers import get_batch_provider, get_streaming_provider

DEFAULT_LOG_FILE = Path("/tmp") / "voice-to-text.log"

ALL_PROVIDERS = ["deepgram", "groq", "voxtral", "parakeet"]

logger = logging.getLogger(__name__)


def setup_logging(log_file: Path | None = None, level: int = logging.INFO):
    log_path = log_file if log_file else DEFAULT_LOG_FILE
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stderr),
        ],
    )
    logger.info("Logging initialized, log file: %s, level: %s", log_path, logging.getLevelName(level))


def load_config():
    return ConfigManager()


def copy_to_clipboard(text: str):
    clipboard_commands = [
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ]
    for cmd in clipboard_commands:
        try:
            subprocess.run(cmd, input=text.encode(), check=True)
            return True
        except FileNotFoundError:
            continue
    return False


PROVIDER_ENV_VARS = {
    "deepgram": "DEEPGRAM_API_KEY",
    "groq": "GROQ_API_KEY",
    "voxtral": "VOXTRAL_API_KEY",
}


def detect_shell_rc() -> Path | None:
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    if "fish" in shell:
        return home / ".config" / "fish" / "config.fish"
    elif "zsh" in shell:
        return home / ".zshrc"
    elif "bash" in shell:
        return home / ".bashrc"
    return None


def setup_key_interactive():
    env_provider = os.environ.get("VOICE_TO_TEXT_PROVIDER")
    env_key = os.environ.get("VOICE_TO_TEXT_API_KEY")

    if env_provider and env_key:
        config_mgr = ConfigManager()
        set_provider(config_mgr, env_provider)
        try:
            subprocess.run(
                [
                    "secret-tool",
                    "store",
                    "--label",
                    f"Voice-to-Text {env_provider} API Key",
                    "application",
                    "voice-to-text",
                    "provider",
                    env_provider,
                ],
                input=env_key.encode(),
                check=True,
                capture_output=True,
            )
            print("API key stored securely via secret-tool.")
        except FileNotFoundError:
            print("ERROR: `secret-tool` not found. Install libsecret-tools or similar.")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to store secret: {e.stderr.decode().strip()}")
        return True

    if not sys.stdin.isatty():
        print("Non-interactive session. Skipping interactive setup.")
        return False

    print("voice-to-text API key setup")
    print("=" * 60)

    provider_urls = {
        "deepgram": "https://console.deepgram.com/",
        "groq": "https://console.groq.com/keys",
        "voxtral": "https://console.mistral.ai/api-keys/",
    }

    api_providers = [(name, PROVIDER_ENV_VARS[name]) for name in PROVIDER_ENV_VARS]
    print("Select a provider to configure:")
    for i, (name, env_var) in enumerate(api_providers, 1):
        url = provider_urls.get(name, "")
        print(f"  {i}. {name} ({env_var})")
        if url:
            print(f"     Sign up: {url}")

    choice = input("\nEnter number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(api_providers):
            print("Invalid choice.")
            return False
    except ValueError:
        print("Invalid choice.")
        return False

    provider_name, env_var = api_providers[idx]

    api_key = input(f"Enter {provider_name} API key: ")
    if not api_key:
        print("No key entered. Aborting.")
        return False

    try:
        subprocess.run(
            [
                "secret-tool",
                "store",
                "--label",
                f"Voice-to-Text {provider_name} API Key",
                "application",
                "voice-to-text",
                "provider",
                provider_name,
            ],
            input=api_key.encode(),
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        print("ERROR: `secret-tool` not found. Install libsecret-tools or similar.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to store secret: {e.stderr.decode().strip()}")
        return False

    print("API key stored securely via secret-tool.")

    rc_path = detect_shell_rc()
    if rc_path is None:
        print("WARNING: Unknown shell. Key stored but no environment variable configured.")
        print(
            f"Add this manually:\n"
            f"  export {env_var}=$(secret-tool lookup application voice-to-text provider {provider_name})"
        )
        return False

    lookup_cmd = f"secret-tool lookup application voice-to-text provider {provider_name}"
    fish_line = f"set -x {env_var} ({lookup_cmd})"
    posix_line = f"export {env_var}=$({lookup_cmd})"

    def _shell_line(shell: str) -> str:
        return fish_line if "fish" in shell else posix_line

    def _append_to_file(path: Path, export_line: str | None = None) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text().splitlines() if path.exists() else []
        already = any(env_var in line and "secret-tool lookup" in line for line in existing)
        if not already:
            line = export_line or posix_line
            with path.open("a") as f:
                f.write(f"\n# Voice-to-Text: {provider_name} API key\n{line}\n")
            return True
        return False

    def _rc_shell(path: Path) -> str:
        name = path.name
        if "fish" in name:
            return "fish"
        if "zsh" in name:
            return "zsh"
        return "bash"

    written = []
    if rc_path:
        if _append_to_file(rc_path, _shell_line(_rc_shell(rc_path))):
            written.append(str(rc_path))

    bashrc_path = Path.home() / ".bashrc"
    if bashrc_path.exists() and bashrc_path != rc_path:
        if _append_to_file(bashrc_path, posix_line):
            written.append(str(bashrc_path))

    # Always write to .profile — needed for GNOME Shell / display managers
    profile_path = Path.home() / ".profile"
    if _append_to_file(profile_path, posix_line):
        written.append(str(profile_path))

    if written:
        for path in written:
            print(f"Added to {path}.")
    else:
        print("Environment variable already configured.")

    os.environ[env_var] = api_key
    print("Environment variable set in current shell session.")

    print()
    change = input("Would you like to set this as the default provider? (y/N): ").strip().lower()
    if change in ("y", "yes"):
        config_mgr = ConfigManager()
        set_provider(config_mgr, provider_name)
    return True


def setup_interactive():
    print("voice-to-text setup")
    print("=" * 60)

    env_provider = os.environ.get("VOICE_TO_TEXT_PROVIDER")
    if env_provider:
        config_mgr = load_config()
        set_provider(config_mgr, env_provider)
        return True

    if not sys.stdin.isatty():
        print("Non-interactive session. Skipping interactive setup.")
        return False

    config_mgr = load_config()
    current_provider = config_mgr.get_selected_provider()
    print(f"Current provider: {current_provider}")
    print(f"Config path: {config_mgr.config_path}")
    print()

    set_provider(config_mgr)
    return True


def set_provider(config_mgr, provider: str | None = None) -> bool:
    """Set the default transcription provider in config. If provider is None, prompt interactively."""

    if provider is None:
        print("Choose your transcription provider:")
        print()
        for i, name in enumerate(ALL_PROVIDERS, 1):
            print(f"  {i}. {name}")
        print()

        current = config_mgr.get_selected_provider()
        print(f"Current provider: {current}")
        print()

        choice = input("Enter choice (1-4): ").strip()
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(ALL_PROVIDERS):
                print("Invalid choice. Keeping current provider.")
                return False
            provider = ALL_PROVIDERS[idx]
        except ValueError:
            print("Invalid choice. Keeping current provider.")
            return False
    elif provider not in ALL_PROVIDERS:
        print(f"Unknown provider '{provider}'. Choose from: {', '.join(ALL_PROVIDERS)}")
        return False

    config_mgr.config.setdefault("transcription", {})["provider"] = provider
    if config_mgr.save():
        print(f"Default provider set to: {provider}")
        print(f"Configuration saved to: {config_mgr.config_path}")
        return True
    else:
        print("Failed to save configuration.")
        return False


def maybe_activate_bt_mic(config_mgr, device_override: int | None) -> None:
    """Switch BT headset to HSP/HFP and make its mic the default source.

    Skipped when the user explicitly passed ``--device`` (they are being
    specific), or when ``audio.bluetooth_mic`` is false in config.
    """
    if device_override is not None:
        return
    audio_cfg = config_mgr.get_audio_config() or {}
    if not audio_cfg.get("bluetooth_mic", True):
        return
    try:
        activate_headset_mic()
    except Exception as e:
        logger.debug("BT headset activation failed: %s", e)


def transcribe_audio(audio_path: str, transcriber, language) -> str | None:
    try:
        logger.info("Starting transcription from %s", audio_path)
        start_time = time.time()
        text = transcriber.transcribe_file(audio_path, language=language)
        elapsed = time.time() - start_time
        logger.info("Transcription complete in %.2fs: %s", elapsed, text[:100])
        return text.strip()
    except Exception:
        logger.exception("Transcription failed")
        raise
    finally:
        os.remove(audio_path)


class _LogCollector(logging.Handler):
    """Captures log messages in a list during benchmark."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))


def run_benchmark(args, config_mgr):

    if args.audio_file:
        audio_path = args.audio_file
        print(f"Using audio file: {audio_path}")
    else:
        duration = args.duration
        print(f"Recording for {duration}s...")
        recorder = AudioRecorder(device=args.device)
        recorder.start()
        time.sleep(duration)
        recorder.stop()
        audio_path = recorder.filepath
        frame_count = recorder.frame_count
        print(f"Recorded {frame_count} frames ({duration}s)")

    provider_names = [p.strip() for p in args.providers.split(",")] if args.providers else ALL_PROVIDERS
    providers = []
    for name in provider_names:
        if name not in ALL_PROVIDERS:
            print(f"  {name}: SKIP (unknown provider)")
            continue
        try:
            provider_config = config_mgr.get_provider_config(name)
            p = get_batch_provider(name, provider_config)
            providers.append(p)
        except (ValueError, Exception) as e:
            print(f"  {name}: SKIP ({e})")

    if not providers:
        print("No providers available to benchmark.")
        return

    collector = _LogCollector()
    collector.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log_root = logging.getLogger()
    log_root.addHandler(collector)
    prev_level = log_root.level
    log_root.setLevel(logging.INFO)

    num_runs = args.runs
    print(f"\nBenchmarking {len(providers)} provider(s), {num_runs} run(s) each...")
    results = {}

    for provider in providers:
        runs = []
        print(f"\n  {provider.name}:")
        for i in range(num_runs):
            try:
                start = time.time()
                text = provider.transcribe_file(audio_path)
                elapsed = time.time() - start
                runs.append({"elapsed": elapsed, "text": text, "ok": True})
                print(f'    Run {i + 1}: {elapsed:.2f}s  "{text[:60]}"')
            except Exception as e:
                runs.append({"elapsed": 0.0, "text": f"FAILED: {e}", "ok": False})
                print(f"    Run {i + 1}: FAILED ({e})")
        ok_runs = [r for r in runs if r["ok"]]
        if ok_runs:
            times = [r["elapsed"] for r in ok_runs]
            results[provider.name] = {
                "avg": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
                "runs": runs,
            }

    if not args.audio_file and audio_path and Path(audio_path).exists():
        os.remove(audio_path)

    log_root.removeHandler(collector)
    log_root.setLevel(prev_level)

    sep = "=" * 66
    sorted_results = sorted(results.items(), key=lambda x: x[1]["avg"]) if results else []

    print(sep)
    print("RAW LOGS")
    print(sep)
    for line in collector.records:
        print(f"  {line}")

    if sorted_results:
        fastest = sorted_results[0][0]
        base_avg = sorted_results[0][1]["avg"]
        print(f"\n{sep}")
        print("TIMING")
        print(sep)
        print(f"  {'Provider':<15} {'Avg (s)':<12} {'Min (s)':<12} {'Max (s)':<12}  {'+/-%':<10}")
        print(f"  {'-' * 15} {'-' * 12} {'-' * 12} {'-' * 12}  {'-' * 10}")
        for name, s in sorted_results:
            pct = ((s["avg"] - base_avg) / base_avg) * 100 if base_avg > 0 else 0
            marker = " <- fastest" if name == fastest else ""
            pct_str = f"{('+' if pct > 0 else '')}{pct:<8.1f}%"
            print(f"  {name:<15} {s['avg']:<12.2f} {s['min']:<12.2f} {s['max']:<12.2f}  {pct_str}{marker}")
        print(sep)
        print(f"  Fastest: {fastest} ({sorted_results[0][1]['avg']:.2f}s avg)")

    has_text = any(r["text"] for s in results.values() for r in s["runs"])
    if has_text:
        print(f"\n{sep}")
        print("TEXT")
        print(sep)
        for name, s in sorted_results:
            for i, run in enumerate(s["runs"], 1):
                elapsed_str = f"{run['elapsed']:.2f}s" if run["ok"] else "FAILED"
                print(f"  {name} [{i}/{num_runs}]  {elapsed_str}")
                for line in run["text"].splitlines():
                    print(f"    {line}")
                print()


def run_stdout_mode(args, config_mgr, transcriber, language, duration, hybrid=None, mode="batch"):

    level_interval = 0.1

    logger.info(
        "run_stdout_mode started, duration=%s, device=%s, hybrid=%s, mode=%s",
        duration,
        args.device,
        hybrid is not None,
        mode,
    )

    stop_requested = False

    def handle_sigint(signum, frame):
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, handle_sigint)

    decrease_pct = (
        args.decrease_speaker_volume
        if args.decrease_speaker_volume is not None
        else config_mgr.get_speaker_config().get("decrease_volume", 0)
    )

    recorder = AudioRecorder(device=args.device)

    audio_chunks: list[bytes] = []
    chunk_lock = threading.Lock()

    if hybrid:

        def _on_audio_data(data: bytes):
            logger.debug("Received audio chunk: %d bytes", len(data))
            with chunk_lock:
                audio_chunks.append(data)

        recorder.on_audio_data = _on_audio_data

    with SpeakerVolumeManager.with_decrease(decrease_pct):
        recorder.start()
        print("START", flush=True)
        start_time = time.time()
        last_level_time = time.time()
        level_count = 0
        try:
            if hybrid:
                hybrid.start_stream(language, sample_rate=recorder.sample_rate)

            while not stop_requested:
                if duration > 0 and (time.time() - start_time) > duration:
                    break

                now = time.time()
                if now - last_level_time >= level_interval:
                    if recorder.frame_count:
                        level_count += 1
                        logger.debug("LEVEL[%d]: %.4f", level_count, recorder.smoothed_level)
                        print(f"LEVEL:{recorder.smoothed_level:.4f}", flush=True)
                    last_level_time = now

                if hybrid:
                    with chunk_lock:
                        chunks = audio_chunks[:]
                        audio_chunks.clear()
                    logger.debug("Processing %d audio chunks", len(chunks))
                    for chunk in chunks:
                        logger.debug("Sending chunk to hybrid: %d bytes", len(chunk))
                        partial = hybrid.on_audio_chunk(chunk)
                        if partial:
                            print(f"STREAM:{partial}", flush=True)

                time.sleep(0.02)
        except Exception as e:
            logger.exception("Recording error: %s", e)
            print(f"ERROR:{e}", flush=True)
            sys.exit(1)
        finally:
            recorder.stop()
            logger.info(
                "Audio stream stopped, collected %d frames, %d level readings",
                recorder.frame_count,
                level_count,
            )

    if recorder.frame_count == 0:
        print("ERROR:No audio recorded", flush=True)
        sys.exit(1)

    if recorder.filepath is None:
        print("ERROR:No audio file produced", flush=True)
        sys.exit(1)

    try:
        if mode == "streaming" and hybrid:
            text = hybrid.streaming.finalize_stream()
        elif hybrid:
            text = hybrid.on_recording_stop(recorder.filepath, language)
        else:
            text = transcribe_audio(recorder.filepath, transcriber, language)
        if text:
            logger.info("Final text len=%d: %r", len(text), text)
            print(f"TEXT:{text}", flush=True)
        else:
            print("ERROR:No speech detected", flush=True)
            sys.exit(1)
    except Exception as e:
        logger.exception("Transcription in stdout mode failed: %s", e)
        print(f"ERROR:{e}", flush=True)
        sys.exit(1)
    finally:
        if recorder.filepath and os.path.exists(recorder.filepath):
            try:
                os.unlink(recorder.filepath)
            except OSError:
                logger.debug("Could not remove temp file %s", recorder.filepath)


def _add_record_args(parser_obj):
    parser_obj.add_argument(
        "--duration",
        type=float,
        help="Recording duration in seconds (0 = wait for key)",
    )
    parser_obj.add_argument(
        "--provider",
        type=str,
        choices=["deepgram", "groq", "voxtral", "parakeet"],
        help="Transcription provider to use",
    )
    parser_obj.add_argument(
        "--output",
        type=str,
        choices=["clipboard", "stdout"],
        default="clipboard",
        help="Output method: 'clipboard' or 'stdout' (default: clipboard)",
    )
    parser_obj.add_argument("--model", type=str, help="Whisper model to use")
    parser_obj.add_argument(
        "--decrease-speaker-volume",
        type=int,
        choices=range(0, 101),
        metavar="{0-100}",
        help="Decrease speaker volume by this %% during recording (0=no change, 100=mute)",
    )
    parser_obj.add_argument(
        "--mode",
        type=str,
        choices=["batch", "hybrid", "streaming"],
        help="Transcription mode: 'batch' (default), 'hybrid' (streaming + batch), or 'streaming' (test)",
    )
    parser_obj.add_argument(
        "--streaming-provider",
        type=str,
        choices=["deepgram", "voxtral"],
        help="Streaming provider for hybrid mode (overrides config)",
    )
    parser_obj.add_argument(
        "--batch-provider",
        type=str,
        choices=["deepgram", "groq", "voxtral", "parakeet"],
        help="Batch provider for hybrid mode (overrides config)",
    )


def main():
    parser = argparse.ArgumentParser(description="Voice to Text with Groq Whisper")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("devices", help="List available audio input devices")
    subparsers.add_parser("setup", help="Interactive setup to configure provider")
    subparsers.add_parser("setup-key", help="Securely store an API key and configure it for your shell")

    record_parser = subparsers.add_parser("record", help="Record and transcribe audio")
    _add_record_args(record_parser)

    bench_parser = subparsers.add_parser(
        "benchmark", help="Benchmark provider transcription speed (3 runs each, reports avg)"
    )
    bench_parser.add_argument(
        "--duration", type=float, default=10.0, help="Recording duration in seconds (default: 10)"
    )
    bench_parser.add_argument("--audio-file", type=str, help="Use existing audio file instead of recording")
    bench_parser.add_argument(
        "--runs", type=int, default=3, help="Number of transcription runs per provider (default: 3)"
    )
    bench_parser.add_argument("--device", type=int, help="Audio input device index")
    bench_parser.add_argument(
        "--providers",
        type=str,
        help="Comma-separated providers to test (default: all configured)",
    )

    # Record args also on main parser so they work without "record" subcommand
    _add_record_args(parser)

    parser.add_argument(
        "--language",
        type=str,
        help="Language code for transcription",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Audio input device index (use 'groq-voice devices' to list)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to log file (default: /tmp/voice-to-text.log or config value)",
    )

    # Same general args on record_parser so they work under "record" subcommand
    record_parser.add_argument("--language", type=str, help=argparse.SUPPRESS)
    record_parser.add_argument("--device", type=int, help=argparse.SUPPRESS)
    record_parser.add_argument("--log-file", type=str, help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.command is None:
        args.command = "record"

    config_mgr = load_config()
    log_file_config = config_mgr.get_logging_config().get("file")
    log_level_config = config_mgr.get_logging_config().get("level", "info").upper()
    log_level = getattr(logging, log_level_config, logging.INFO)

    # Override to DEBUG for hybrid/streaming modes to help debug streaming issues
    mode_override = args.mode
    selected_mode = mode_override or config_mgr.config.get("transcription", {}).get("mode", "batch")
    if selected_mode in ("hybrid", "streaming"):
        log_level = logging.DEBUG

    log_file_arg = Path(args.log_file) if args.log_file else None
    log_file = log_file_arg or (Path(log_file_config) if log_file_config else None)
    setup_logging(log_file, log_level)

    if args.command == "devices":
        print("Available audio input devices:")
        print("-" * 60)
        all_devices = sd.query_devices()
        if isinstance(all_devices, dict):
            all_devices = [all_devices]
        for i, dev in enumerate(all_devices):
            if dev["max_input_channels"] > 0:
                print(f"  [{i}] {dev['name']}")
                print(f"      Sample rate: {dev['default_samplerate']} Hz, Channels: {dev['max_input_channels']}")
        print("-" * 60)
        print("Use --device INDEX to select a microphone")
        return

    if args.command == "setup":
        setup_interactive()
        return

    if args.command == "setup-key":
        setup_key_interactive()
        return

    load_dotenv()

    if args.command == "benchmark":
        run_benchmark(args, config_mgr)
        return

    provider_override = args.provider
    language_override = args.language
    mode_override = args.mode
    selected_mode = mode_override or config_mgr.config.get("transcription", {}).get("mode", "batch")
    selected_provider = provider_override or config_mgr.get_selected_provider()
    provider_config = config_mgr.get_provider_config(selected_provider)

    hybrid = None
    transcriber = None
    if selected_mode == "hybrid":
        hybrid_cfg = config_mgr.config.get("transcription", {}).get("hybrid", {})
        streaming_name = getattr(args, "streaming_provider", None) or hybrid_cfg.get("streaming_provider", "deepgram")
        batch_name = getattr(args, "batch_provider", None) or hybrid_cfg.get("batch_provider", "voxtral")
        streaming_config = config_mgr.get_provider_config(streaming_name)
        batch_config = config_mgr.get_provider_config(batch_name)

        try:
            streaming_provider = get_streaming_provider(streaming_name, streaming_config)
            batch_provider = get_batch_provider(batch_name, batch_config)
            hybrid = HybridTranscriber(streaming_provider, batch_provider)
        except ValueError as e:
            logger.error("Hybrid provider initialization failed: %s", e)
            print(f"ERROR:Hybrid provider initialization failed: {e}", file=sys.stdout, flush=True)
            sys.exit(1)
    elif selected_mode == "streaming":
        if args.output != "stdout":
            print("ERROR:streaming mode requires --output stdout", file=sys.stdout, flush=True)
            sys.exit(1)
        hybrid_cfg = config_mgr.config.get("transcription", {}).get("hybrid", {})
        streaming_name = getattr(args, "streaming_provider", None) or hybrid_cfg.get("streaming_provider", "deepgram")
        streaming_config = config_mgr.get_provider_config(streaming_name)

        try:
            streaming_provider = get_streaming_provider(streaming_name, streaming_config)
            hybrid = HybridTranscriber(streaming_provider, streaming_provider)  # type: ignore[arg-type]
        except ValueError as e:
            logger.error("Streaming provider initialization failed: %s", e)
            print(f"ERROR:Streaming provider initialization failed: {e}", file=sys.stdout, flush=True)
            sys.exit(1)
    else:
        try:
            transcriber = get_batch_provider(selected_provider, provider_config)
        except ValueError as e:
            logger.error("Provider initialization failed: %s", e)
            print(f"ERROR:Provider initialization failed: {e}", file=sys.stdout, flush=True)
            sys.exit(1)

    language = language_override or config_mgr.config.get("transcription", {}).get("language", "en")
    audio_config = config_mgr.config.get("audio", {})
    default_duration = audio_config.get("duration", 0)
    duration = args.duration if args.duration is not None else default_duration
    output_mode = args.output

    if output_mode == "stdout":
        maybe_activate_bt_mic(config_mgr, args.device)
        run_stdout_mode(args, config_mgr, transcriber, language, duration, hybrid=hybrid, mode=selected_mode)
        return

    print("Recording... (press ESC or Q to cancel, ENTER to continue)")
    print("-" * 60)

    maybe_activate_bt_mic(config_mgr, args.device)

    decrease_pct = (
        args.decrease_speaker_volume
        if args.decrease_speaker_volume is not None
        else config_mgr.get_speaker_config().get("decrease_volume", 0)
    )

    recorder = AudioRecorder(device=args.device, smooth_factor=0.7)
    with SpeakerVolumeManager.with_decrease(decrease_pct):
        recorder.start()
        start_time = time.time()
        try:
            old_settings = termios.tcgetattr(sys.stdin.fileno())
            try:
                tty.setcbreak(sys.stdin.fileno())
                print("Recording... (ESC/Q to cancel, ENTER to continue)", flush=True)

                while True:
                    if select.select([sys.stdin], [], [], 0.03)[0]:
                        key = sys.stdin.read(1)
                        if key in ("q", "Q") or ord(key) == 27:
                            print("\nExiting without transcription")
                            sys.exit(0)
                        elif key == "\n" or key == "\r":
                            break

                    if duration > 0 and (time.time() - start_time) > duration:
                        break

                    elapsed = time.time() - start_time
                    bar = format_level_bar(recorder.smoothed_level, elapsed)
                    sys.stdout.write(bar)
                    sys.stdout.flush()
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                print()
        finally:
            recorder.stop()

    if recorder.frame_count == 0:
        print("ERROR:No audio recorded")
        sys.exit(1)

    if recorder.filepath is None:
        print("ERROR:No audio file produced")
        sys.exit(1)

    try:
        if hybrid:
            text = hybrid.on_recording_stop(recorder.filepath, language)
        else:
            text = transcribe_audio(recorder.filepath, transcriber, language)
    except Exception as e:
        logger.exception("Transcription failed: %s", e)
        print(f"ERROR:Transcription failed: {e}")
        sys.exit(1)

    if not text:
        logger.warning("No speech detected")
        print("ERROR:No speech detected")
        sys.exit(1)

    if copy_to_clipboard(text):
        logger.info("Copied to clipboard: %s", text[:50])
    else:
        logger.error("Clipboard copy failed")
        print("ERROR:Clipboard copy failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        output_mode = sys.argv and "--output" in sys.argv and "stdout" in sys.argv
        if output_mode:
            print(f"ERROR:{e}", flush=True)
        logger.exception("Unhandled exception: %s", e)
        sys.exit(1)
