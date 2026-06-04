#!/usr/bin/env python3

import argparse
import select
import signal
import termios
import time
import tty
import subprocess
import sys
import os
import logging
import getpass
from pathlib import Path

import sounddevice as sd
from dotenv import load_dotenv

from voice_to_text import source_hash
from voice_to_text.providers import get_provider
from voice_to_text.config import ConfigManager
from voice_to_text.audio import (
    AudioRecorder,
    SpeakerVolumeManager,
    format_level_bar,
)

DEFAULT_LOG_FILE = Path("/tmp") / "voice-to-text.log"

logger = logging.getLogger(__name__)


def setup_logging(log_file: Path | None = None):
    log_path = log_file if log_file else DEFAULT_LOG_FILE
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stderr),
        ],
    )
    logger.info("Logging initialized, log file: %s", log_path)


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
    import subprocess as _subprocess

    print("voice-to-text API key setup")
    print("=" * 60)

    api_providers = [
        (name, PROVIDER_ENV_VARS[name])
        for name in PROVIDER_ENV_VARS
    ]

    env_provider = os.environ.get("VOICE_TO_TEXT_PROVIDER", "").strip().lower()
    if env_provider in PROVIDER_ENV_VARS:
        provider_name, env_var = env_provider, PROVIDER_ENV_VARS[env_provider]
    else:
        if not sys.stdin.isatty():
            print("ERROR: Non-interactive run and VOICE_TO_TEXT_PROVIDER is unset or invalid.")
            print(f"Set it to one of: {', '.join(PROVIDER_ENV_VARS)}")
            return
        print("Select a provider to configure:")
        for i, (name, env_var) in enumerate(api_providers, 1):
            print(f"  {i}. {name} ({env_var})")

        choice = input("\nEnter number: ").strip()
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(api_providers):
                print("Invalid choice.")
                return
        except ValueError:
            print("Invalid choice.")
            return

        provider_name, env_var = api_providers[idx]

    api_key = os.environ.get("VOICE_TO_TEXT_API_KEY", "").strip()
    if not api_key:
        if not sys.stdin.isatty():
            print("ERROR: Non-interactive run and VOICE_TO_TEXT_API_KEY is unset.")
            return
        api_key = getpass.getpass(f"Enter {provider_name} API key: ")
    if not api_key:
        print("No key entered. Aborting.")
        return

    try:
        _subprocess.run(
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
        return
    except _subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to store secret: {e.stderr.decode().strip()}")
        return

    print(f"API key stored securely via secret-tool.")

    config_mgr = load_config()
    config_mgr.config.setdefault("transcription", {})["provider"] = provider_name
    if not config_mgr.save():
        print(f"WARNING: Failed to persist provider '{provider_name}' to {config_mgr.config_path}.")
    else:
        print(f"Default provider set to '{provider_name}'.")

    rc_path = detect_shell_rc()
    if rc_path is None:
        print("WARNING: Unknown shell. Key stored but no environment variable configured.")
        print(f"Add this manually:\n  export {env_var}=$(secret-tool lookup application voice-to-text provider {provider_name})")
        return

    lookup_cmd = f"secret-tool lookup application voice-to-text provider {provider_name}"
    if "fish" in os.environ.get("SHELL", ""):
        export_line = f"set -x {env_var} ({lookup_cmd})"
    else:
        export_line = f"export {env_var}=$({lookup_cmd})"

    rc_path.parent.mkdir(parents=True, exist_ok=True)
    existing = rc_path.read_text().splitlines() if rc_path.exists() else []
    already_present = any(env_var in line and "secret-tool lookup" in line for line in existing)

    if already_present:
        print(f"Environment variable already configured in {rc_path}.")
    else:
        with rc_path.open("a") as f:
            f.write(f"\n# Voice-to-Text: {provider_name} API key\n{export_line}\n")
        print(f"Added to {rc_path}.")
        print(f"Restart your shell or run:\n  source {rc_path}")


def setup_interactive():
    print("groq-voice setup")
    print("=" * 60)
    print("Choose your transcription provider:")
    print()
    print("1. Voxtral (default)  - Uses Voxtral API for transcription")
    print("2. Groq - Uses Groq API for transcription")
    print()

    config_mgr = load_config()
    current_provider = config_mgr.get_selected_provider()
    print(f"Current provider: {current_provider}")
    print(f"Config path: {config_mgr.config_path}")
    print()

    env_provider = os.environ.get("VOICE_TO_TEXT_PROVIDER", "").strip().lower()
    if env_provider in ("voxtral", "groq"):
        provider = env_provider
    else:
        if not sys.stdin.isatty():
            print("ERROR: Non-interactive run and VOICE_TO_TEXT_PROVIDER is unset or invalid.")
            print("Set it to one of: voxtral, groq")
            return
        choice = input("Enter your choice (1-2): ").strip()
        if choice == "1":
            provider = "voxtral"
        elif choice == "2":
            provider = "groq"
        else:
            print("Invalid choice. Keeping current provider.")
            return

    config_mgr.config.setdefault("transcription", {})["provider"] = provider

    if config_mgr.save():
        print(f"Provider set to: {provider}")
        print(f"Configuration saved to: {config_mgr.config_path}")
        print("Configuration saved successfully!")
    else:
        print(f"Failed to save configuration to: {config_mgr.config_path}")


def transcribe_audio(audio_path: str, transcriber, language) -> str | None:
    try:
        logger.info("Starting transcription from %s", audio_path)
        start_time = time.time()
        text = transcriber.transcribe_file(audio_path, language=language)
        elapsed = time.time() - start_time
        logger.info("Transcription complete in %.2fs: %s", elapsed, text[:100])
        return text.strip()
    except Exception as e:
        logger.exception("Transcription failed")
        raise
    finally:
        os.remove(audio_path)


def run_benchmark(args, config_mgr):
    from voice_to_text.providers import get_provider

    ALL_PROVIDERS = ["deepgram", "groq", "voxtral", "parakeet"]

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
            p = get_provider(name, provider_config)
            providers.append(p)
        except (ValueError, Exception) as e:
            print(f"  {name}: SKIP ({e})")

    if not providers:
        print("No providers available to benchmark.")
        return

    num_runs = args.runs
    print(f"\nBenchmarking {len(providers)} provider(s), {num_runs} run(s) each...")
    results = {}

    for provider in providers:
        times = []
        print(f"\n  {provider.name}:")
        for i in range(num_runs):
            try:
                start = time.time()
                text = provider.transcribe_file(audio_path)
                elapsed = time.time() - start
                times.append(elapsed)
                print(f"    Run {i+1}: {elapsed:.2f}s  \"{text[:60]}\"")
            except Exception as e:
                print(f"    Run {i+1}: FAILED ({e})")
        if times:
            avg = sum(times) / len(times)
            results[provider.name] = {
                "avg": avg, "min": min(times), "max": max(times), "times": times
            }

    if results:
        fastest = min(results.items(), key=lambda x: x[1]["avg"])[0]
        print()
        print(f"{'='*66}")
        print(f"{'Provider':<15} {'Avg (s)':<12} {'Min (s)':<12} {'Max (s)':<12}  {'+/-%':<10}")
        print(f"{'-'*15} {'-'*12} {'-'*12} {'-'*12}  {'-'*10}")
        sorted_results = sorted(results.items(), key=lambda x: x[1]["avg"])
        base_avg = sorted_results[0][1]["avg"]
        for name, s in sorted_results:
            pct = ((s["avg"] - base_avg) / base_avg) * 100 if base_avg > 0 else 0
            marker = " <- fastest" if name == fastest else ""
            spread = (s["max"] - s["min"]) / s["avg"] * 100 if s["avg"] > 0 else 0
            print(f"{name:<15} {s['avg']:<12.2f} {s['min']:<12.2f} {s['max']:<12.2f}  {'+' if pct > 0 else ''}{pct:<8.1f}%{marker}")
        print(f"{'='*66}")
        print(f"Fastest: {fastest} ({sorted_results[0][1]['avg']:.2f}s avg)")

    if not args.audio_file and audio_path and Path(audio_path).exists():
        os.remove(audio_path)


def run_stdout_mode(args, config_mgr, transcriber, language, duration):
    LEVEL_INTERVAL = 0.1

    logger.info(
        "run_stdout_mode started, duration=%s, device=%s", duration, args.device
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

    with SpeakerVolumeManager.with_decrease(decrease_pct):
        recorder.start()
        start_time = time.time()
        last_level_time = time.time()
        level_count = 0
        try:
            while not stop_requested:
                if duration > 0 and (time.time() - start_time) > duration:
                    break

                now = time.time()
                if now - last_level_time >= LEVEL_INTERVAL:
                    if recorder.frame_count:
                        level_count += 1
                        logger.debug("LEVEL[%d]: %.4f", level_count, recorder.smoothed_level)
                        print(f"LEVEL:{recorder.smoothed_level:.4f}", flush=True)
                    last_level_time = now

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

    try:
        text = transcribe_audio(recorder.filepath, transcriber, language)
        if text:
            print(f"TEXT:{text}", flush=True)
        else:
            print("ERROR:No speech detected", flush=True)
            sys.exit(1)
    except Exception as e:
        logger.exception("Transcription in stdout mode failed: %s", e)
        print(f"ERROR:{e}", flush=True)
        sys.exit(1)


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


def main():
    parser = argparse.ArgumentParser(description="Voice to Text with Groq Whisper")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("devices", help="List available audio input devices")
    subparsers.add_parser("setup", help="Interactive setup to configure provider")
    subparsers.add_parser("setup-key", help="Securely store an API key and configure it for your shell")

    record_parser = subparsers.add_parser("record", help="Record and transcribe audio")
    _add_record_args(record_parser)

    bench_parser = subparsers.add_parser("benchmark", help="Benchmark provider transcription speed (3 runs each, reports avg)")
    bench_parser.add_argument(
        "--duration", type=float, default=10.0, help="Recording duration in seconds (default: 10)"
    )
    bench_parser.add_argument(
        "--audio-file", type=str, help="Use existing audio file instead of recording"
    )
    bench_parser.add_argument(
        "--runs", type=int, default=3, help="Number of transcription runs per provider (default: 3)"
    )
    bench_parser.add_argument(
        "--device", type=int, help="Audio input device index"
    )
    bench_parser.add_argument(
        "--providers",
        type=str,
        help="Comma-separated providers to test (default: all configured)",
    )

    # Record args also on main parser so they work without "record" subcommand
    _add_record_args(parser)

    parser.add_argument(
        "--source-hash",
        action="store_true",
        help="Print the source hash embedded in this binary",
    )
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

    if args.source_hash:
        h = source_hash()
        print(h if h else "no-source-hash")
        return

    config_mgr = load_config()
    log_file_config = config_mgr.get_logging_config().get("file")
    log_file_arg = Path(args.log_file) if args.log_file else None
    log_file = log_file_arg or (Path(log_file_config) if log_file_config else None)
    setup_logging(log_file)

    if args.command == "devices":
        print("Available audio input devices:")
        print("-" * 60)
        all_devices = sd.query_devices()
        if isinstance(all_devices, dict):
            all_devices = [all_devices]
        for i, dev in enumerate(all_devices):
            if dev["max_input_channels"] > 0:
                print(f"  [{i}] {dev['name']}")
                print(
                    f"      Sample rate: {dev['default_samplerate']} Hz, Channels: {dev['max_input_channels']}"
                )
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
    selected_provider = provider_override or config_mgr.get_selected_provider()
    provider_config = config_mgr.get_provider_config(selected_provider)

    try:
        transcriber = get_provider(selected_provider, provider_config)
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
        run_stdout_mode(args, config_mgr, transcriber, language, duration)
        return

    print("Recording... (press ESC or Q to cancel, ENTER to continue)")
    print("-" * 60)

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

    try:
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
        output_mode = (
            sys.argv
            and "--output" in sys.argv
            and "stdout" in sys.argv
        )
        if output_mode:
            print(f"ERROR:{e}", flush=True)
        logger.exception("Unhandled exception: %s", e)
        sys.exit(1)
