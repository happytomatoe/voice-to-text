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
from pathlib import Path

import sounddevice as sd
import yaml
from dotenv import load_dotenv

from voice_to_text import default_db_path, source_hash
from voice_to_text.providers import get_provider
from voice_to_text.config import ConfigManager
from voice_to_text.usage_db import UsageDB
from voice_to_text.stats_reporter import show_stats
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

    choice = input("Enter your choice (1-2): ").strip()

    if choice == "1":
        provider = "voxtral"
    elif choice == "2":
        provider = "groq"
    else:
        print("Invalid choice. Keeping current provider.")
        return

    config_mgr.config.setdefault("transcription", {})["provider"] = provider

    try:
        with open(config_mgr.config_path, "w") as f:
            yaml.dump(config_mgr.config, f)
        print(f"Provider set to: {provider}")
        print(f"Configuration saved to: {config_mgr.config_path}")
        print("Configuration saved successfully!")
    except Exception as e:
        print(f"Failed to save configuration: {e}")


def transcribe_audio(audio_path: str, transcriber, language) -> tuple[str | None, float]:
    try:
        logger.info("Starting transcription from %s", audio_path)
        start_time = time.time()
        text = transcriber.transcribe_file(audio_path, language=language)
        elapsed = time.time() - start_time
        logger.info("Transcription complete in %.2fs: %s", elapsed, text[:100])
        return text.strip(), elapsed
    except Exception as e:
        logger.exception("Transcription failed")
        raise
    finally:
        os.remove(audio_path)


def _get_model_name(transcriber) -> str | None:
    return getattr(transcriber, "model", None) or getattr(transcriber, "model_name", None)


def _record_usage(
    usage_db: UsageDB | None,
    text: str,
    provider: str,
    transcriber,
    language: str,
    recording_duration: float,
    api_response_time: float,
):
    if usage_db is None:
        return
    usage_db.record_session(
        provider=provider,
        model=_get_model_name(transcriber),
        language=language,
        recording_duration_seconds=recording_duration,
        api_response_time_seconds=api_response_time,
        word_count=len(text.split()),
        character_count=len(text),
    )


def run_stdout_mode(args, config_mgr, usage_db, transcriber, language, duration):
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

    recording_duration = time.time() - start_time

    if recorder.frame_count == 0:
        print("ERROR:No audio recorded", flush=True)
        sys.exit(1)

    try:
        text, api_response_time = transcribe_audio(recorder.filepath, transcriber, language)
        _record_usage(
            usage_db,
            text=text,
            provider=transcriber.name,
            transcriber=transcriber,
            language=language,
            recording_duration=recording_duration,
            api_response_time=api_response_time,
        )
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
        choices=["groq", "voxtral", "parakeet"],
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

    stats_parser = subparsers.add_parser("stats", help="Show usage statistics")
    stats_parser.add_argument(
        "--daily", action="store_true", help="Show daily breakdown"
    )
    stats_parser.add_argument(
        "--weekly", action="store_true", help="Show weekly breakdown"
    )
    stats_parser.add_argument(
        "--monthly", action="store_true", help="Show monthly breakdown"
    )
    stats_parser.add_argument(
        "--by-provider",
        action="store_true",
        help="Show breakdown by provider",
    )
    stats_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    stats_parser.add_argument(
        "--since",
        type=str,
        help="Start date (YYYY-MM-DD) for stats period",
    )
    stats_parser.add_argument(
        "--until",
        type=str,
        help="End date (YYYY-MM-DD) for stats period",
    )
    stats_parser.add_argument(
        "--db-path",
        type=str,
        help="Path to usage database",
    )

    record_parser = subparsers.add_parser("record", help="Record and transcribe audio")
    _add_record_args(record_parser)

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

    if args.command == "stats":
        usage_tracking_config = config_mgr.get_usage_tracking_config()
        db_path = args.db_path or usage_tracking_config.get("db_path")
        if db_path:
            db_path = str(Path(db_path).expanduser())
        else:
            db_path = str(default_db_path())
        usage_db = UsageDB(db_path)
        print(show_stats(usage_db, args))
        usage_db.close()
        return

    load_dotenv()

    usage_tracking_config = config_mgr.get_usage_tracking_config()
    if usage_tracking_config.get("enabled", True):
        db_path = usage_tracking_config.get("db_path")
        if db_path:
            db_path = str(Path(db_path).expanduser())
        else:
            db_path = str(default_db_path())
        usage_db = UsageDB(db_path)
        logger.info("Usage tracking enabled, db: %s", db_path)
    else:
        usage_db = None

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
        run_stdout_mode(args, config_mgr, usage_db, transcriber, language, duration)
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

    recording_duration = time.time() - start_time

    if recorder.frame_count == 0:
        print("ERROR:No audio recorded")
        sys.exit(1)

    try:
        text, api_response_time = transcribe_audio(recorder.filepath, transcriber, language)
    except Exception as e:
        logger.exception("Transcription failed: %s", e)
        print(f"ERROR:Transcription failed: {e}")
        sys.exit(1)

    if not text:
        logger.warning("No speech detected")
        print("ERROR:No speech detected")
        sys.exit(1)

    _record_usage(
        usage_db,
        text=text,
        provider=transcriber.name,
        transcriber=transcriber,
        language=language,
        recording_duration=recording_duration,
        api_response_time=api_response_time,
    )

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
