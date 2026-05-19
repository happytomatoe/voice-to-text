#!/usr/bin/env python3

import argparse
import math
import select
import signal
import termios
import time
import tempfile
import tty
import subprocess
import sys
import os
import logging
import wave
from pathlib import Path

import numpy as np
import collections
import sounddevice as sd
import yaml
from dotenv import load_dotenv

from voice_to_text.providers import get_provider
from voice_to_text.config import ConfigManager

DEFAULT_LOG_FILE = Path("/tmp") / "voice-to-text.log"

SAMPLE_RATE = 16000
BLOCK_SIZE = 2048

MAX_RECORDED_FRAMES_LEN = int(SAMPLE_RATE * 5)

METER_WIDTH = 50
GREY = "\033[90m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"
BLOCK = "\u2588"

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


def transcribe_audio(recorded_frames, sample_rate, transcriber, language):
    if not recorded_frames:
        return None

    audio_data = np.concatenate(recorded_frames, axis=0)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        with wave.open(f.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())
        audio_path = f.name

        try:
            logger.info("Starting transcription")
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


def compute_rms(indata):
    samples = indata[:, 0].astype(np.float64)
    rms = math.sqrt(np.mean(samples**2))
    return min(rms / 32768.0, 1.0)


def run_stdout_mode(args, config_mgr, transcriber, language, duration):
    SAMPLE_RATE = 16000
    BLOCK_SIZE = 2048
    LEVEL_INTERVAL = 0.1

    logger.info(
        "run_stdout_mode started, duration=%s, device=%s", duration, args.device
    )

    stop_requested = False

    def handle_sigint(signum, frame):
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, handle_sigint)

    recorded_frames = collections.deque(maxlen=MAX_RECORDED_FRAMES_LEN)
    start_time = time.time()

    def audio_callback(indata, frames, time_info, status):
        recorded_frames.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        callback=audio_callback,
        device=args.device,
    )
    stream.start()

    last_level_time = time.time()
    level_count = 0

    try:
        while not stop_requested:
            if duration > 0 and (time.time() - start_time) > duration:
                break

            now = time.time()
            if now - last_level_time >= LEVEL_INTERVAL:
                if recorded_frames:
                    latest = recorded_frames[-1]
                    rms = compute_rms(latest)
                    level_count += 1
                    logger.debug("LEVEL[%d]: %.4f", level_count, rms)
                    print(f"LEVEL:{rms:.4f}", flush=True)
                last_level_time = now

            time.sleep(0.02)
    except Exception as e:
        logger.exception("Recording error: %s", e)
        print(f"ERROR:{e}", flush=True)
        sys.exit(1)
    finally:
        stream.stop()
        stream.close()
        logger.info(
            "Audio stream stopped, collected %d frames, %d level readings",
            len(recorded_frames),
            level_count,
        )

    try:
        text = transcribe_audio(recorded_frames, SAMPLE_RATE, transcriber, language)
        if text:
            print(f"TEXT:{text}", flush=True)
        else:
            print("ERROR:No speech detected", flush=True)
            sys.exit(1)
    except Exception as e:
        logger.exception("Transcription in stdout mode failed: %s", e)
        print(f"ERROR:{e}", flush=True)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Voice to Text with Groq Whisper")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("devices", help="List available audio input devices")
    subparsers.add_parser("setup", help="Interactive setup to configure provider")

    record_parser = subparsers.add_parser("record", help="Record and transcribe audio")
    record_parser.add_argument(
        "--duration",
        type=float,
        help="Recording duration in seconds (0 = wait for key)",
    )
    record_parser.add_argument("--model", type=str, help="Whisper model to use")

    parser.add_argument(
        "--duration",
        type=float,
        help="Recording duration in seconds (0 = wait for key)",
    )
    parser.add_argument("--model", type=str, help="Whisper model to use")
    parser.add_argument(
        "--provider",
        type=str,
        choices=["groq", "voxtral", "parakeet"],
        help="Transcription provider to use",
    )
    parser.add_argument(
        "--language",
        type=str,
        help="Language code for transcription",
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["clipboard", "stdout"],
        default="clipboard",
        help="Output method: 'clipboard' or 'stdout' (default: clipboard)",
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

    args = parser.parse_args()

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

    load_dotenv()

    provider_override = (
        args.provider if hasattr(args, "provider") and args.provider else None
    )
    language_override = (
        args.language if hasattr(args, "language") and args.language else None
    )
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

    output_mode = (
        args.output if hasattr(args, "output") and args.output else "clipboard"
    )

    if output_mode == "stdout":
        run_stdout_mode(args, config_mgr, transcriber, language, duration)
        return

    print("Recording... (press ESC or Q to cancel, ENTER to continue)")
    print("-" * 60)

    SMOOTH = 0.7

    smoothed_level = 0.0
    recorded_frames = collections.deque(maxlen=MAX_RECORDED_FRAMES_LEN)
    start_time = time.time()

    def audio_callback(indata, frames, time_info, status):
        nonlocal smoothed_level
        float_data = indata[:, 0].astype(np.float32) / 32768.0
        recorded_frames.append(indata.copy())
        rms = math.sqrt(np.mean(float_data**2))
        smoothed_level = SMOOTH * smoothed_level + (1 - SMOOTH) * rms

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        callback=audio_callback,
        device=args.device,
    )
    stream.start()
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

            level = min(1.0, smoothed_level)
            filled = int(level * METER_WIDTH)

            if level < 0.13:
                color = GREY
            elif level < 0.5:
                color = GREEN
            elif level < 0.7:
                color = YELLOW
            else:
                color = RED

            bar = BLOCK * filled + " " * (METER_WIDTH - filled)
            elapsed = time.time() - start_time
            sys.stdout.write(f"\r[{color}{bar}{RESET}] {elapsed:.1f}s   ")
            sys.stdout.flush()
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print()
    stream.stop()
    stream.close()

    if not recorded_frames:
        print("ERROR:No audio recorded")
        sys.exit(1)

    try:
        text = transcribe_audio(recorded_frames, SAMPLE_RATE, transcriber, language)
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
        print(f"ERROR:Clipboard copy failed")


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
