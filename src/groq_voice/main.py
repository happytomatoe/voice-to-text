#!/usr/bin/env python3
"""Voice to Text using Groq Whisper - Gnome hotkey integration."""

import argparse
import time
import tempfile
import subprocess
import sys
import tty
import termios
import os
import logging
import threading
import curses
from pathlib import Path
import yaml
from dotenv import load_dotenv

from groq_voice.providers import get_provider
from groq_voice.config import ConfigManager

LOG_DIR = Path.home() / ".local" / "share" / "groq_voice"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "groq_voice.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration using ConfigManager."""
    return ConfigManager()

















def copy_to_clipboard(text: str):
    """Copy text to system clipboard using xclip."""
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard"], input=text.encode(), check=True
        )
        return True
    except FileNotFoundError:
        try:
            subprocess.run(
                ["xsel", "--clipboard", "--input"], input=text.encode(), check=True
            )
            return True
        except FileNotFoundError:
            pass
    return False


def show_notification(title: str, body: str):
    """Show a desktop notification."""
    try:
        subprocess.run(
            ["notify-send", "-u", "normal", title, body],
            check=True,
            capture_output=True,
        )
    except Exception:
        pass


def setup_interactive():
    """Interactive setup to configure the transcription provider."""
    print("groq-voice setup")
    print("=" * 60)
    print("Choose your transcription provider:")
    print()
    print("1. Groq (default) - Uses Groq API for transcription")
    print("2. Voxtral - Uses Voxtral API for transcription")
    print()
    
    config_mgr = load_config()
    current_provider = config_mgr.get_selected_provider()
    print(f"Current provider: {current_provider}")
    print(f"Config path: {config_mgr.config_path}")
    print()
    
    choice = input("Enter your choice (1-2): ").strip()
    
    if choice == "1":
        provider = "groq"
    elif choice == "2":
        provider = "voxtral"
    else:
        print("Invalid choice. Keeping current provider.")
        return
    
    # Update the config
    config_mgr.config.setdefault("transcription", {})["provider"] = provider
    
    # Save the updated config
    try:
        with open(config_mgr.config_path, "w") as f:
            yaml.dump(config_mgr.config, f)
        print(f"Provider set to: {provider}")
        print(f"Configuration saved to: {config_mgr.config_path}")
        print("Configuration saved successfully!")
    except Exception as e:
        print(f"Failed to save configuration: {e}")


def main():
    import numpy as np
    import sounddevice as sd

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
    record_parser.add_argument(
        "--provider",
        type=str,
        choices=["groq", "voxtral"],
        help="Transcription provider to use"
    )
    record_parser.add_argument(
        "--output",
        type=str,
        choices=["clipboard"],
        default="clipboard",
        help="Output method: 'clipboard' (default: clipboard)",
    )

    parser.add_argument(
        "--duration",
        type=float,
        help="Recording duration in seconds (0 = wait for key)",
    )
    parser.add_argument("--model", type=str, help="Whisper model to use")
    parser.add_argument(
        "--output",
        type=str,
        choices=["type", "clipboard"],
        default="type",
        help="Output method: 'type' or 'clipboard' (default: type)",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Audio input device index (use 'groq-voice devices' to list)",
    )

    args = parser.parse_args()

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

    config = load_config()
    load_dotenv()

    config_mgr = load_config()
    
    # Handle provider override from CLI
    provider_override = args.provider if hasattr(args, 'provider') and args.provider else None
    selected_provider = provider_override or config_mgr.get_selected_provider()
    provider_config = config_mgr.get_provider_config(selected_provider)
    transcriber = get_provider(selected_provider, provider_config)

    def should_use_streaming(transcriber) -> bool:
        """Determine if we should use streaming based on provider capabilities."""
        # For now, only use streaming if explicitly requested
        # Could add --stream flag or auto-detect based on provider
        return False  # Start with batch mode for compatibility
    
    model = args.model or config_mgr.config.get("transcription", {}).get(
        "model", "whisper-large-v3-turbo"
    )
    language = config_mgr.config.get("transcription", {}).get("language", "en")
    audio_config = config_mgr.config.get("audio", {})
    default_duration = audio_config.get("duration", 0)
    duration = args.duration if args.duration is not None else default_duration

    print("Recording... (press ESC or q to stop)")
    print("-" * 60)

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 2048
    SMOOTH = 0.7

    # fix 1: explicit float32 buffer for correct FFT scaling
    audio_buffer = np.zeros(BLOCK_SIZE, dtype=np.float32)
    smoothed = None
    stop = False
    recorded_frames = []
    start_time = time.time()

    def audio_callback(indata, frames, time_info, status):
        # fix 1: normalize int16 → float32 so FFT magnitudes are in [-1, 1]
        float_data = indata[:, 0].astype(np.float32) / 32768.0
        num_samples = min(frames, BLOCK_SIZE)
        audio_buffer[:num_samples] = float_data[:num_samples]
        if num_samples < BLOCK_SIZE:
            audio_buffer[num_samples:] = 0
        recorded_frames.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        callback=audio_callback,
        device=args.device,  # fix 3: pass --device to the stream
    )
    stream.start()

    def get_bar_values(num_bars):
        nonlocal smoothed
        if smoothed is None or len(smoothed) != num_bars:
            smoothed = np.zeros(num_bars)
        max_freq = SAMPLE_RATE // 2
        freq_bins = np.logspace(np.log10(20), np.log10(max_freq), num_bars + 1)
        freqs = np.fft.rfftfreq(BLOCK_SIZE, d=1 / SAMPLE_RATE)
        windowed = audio_buffer * np.hanning(BLOCK_SIZE)
        fft_mag = np.abs(np.fft.rfft(windowed))
        fft_db = 20 * np.log10(fft_mag + 1e-10)
        fft_db = np.clip((fft_db + 60) / 60, 0, 1)
        bar_vals = np.zeros(num_bars)
        for i in range(num_bars):
            lo = np.searchsorted(freqs, freq_bins[i])
            hi = max(np.searchsorted(freqs, freq_bins[i + 1]), lo + 1)
            hi = min(hi, len(fft_db))
            slice_ = fft_db[lo:hi]
            bar_vals[i] = np.max(slice_) if len(slice_) > 0 else 0
        smoothed = SMOOTH * smoothed + (1 - SMOOTH) * bar_vals
        return smoothed

    def curses_loop(stdscr):
        nonlocal stop
        curses.curs_set(0)
        stdscr.nodelay(True)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)

        while not stop:
            try:
                key = stdscr.getch()
                if key in (ord("q"), ord("Q"), 27, 10):
                    stop = True
                    break
            except Exception:
                pass

            # fix 2: use elapsed wall-clock time instead of broken stream.time
            if duration > 0 and (time.time() - start_time) > duration:
                stop = True
                break

            height, width = stdscr.getmaxyx()
            num_bars = width - 2
            bar_height = height - 2

            bar_vals = get_bar_values(num_bars)
            stdscr.erase()

            for x, val in enumerate(bar_vals):
                filled = int(val * bar_height)
                for y in range(filled):
                    row = height - 2 - y
                    frac = y / bar_height if bar_height > 0 else 0
                    if frac < 0.5:
                        color = curses.color_pair(3)
                    elif frac < 0.8:
                        color = curses.color_pair(2)
                    else:
                        color = curses.color_pair(1)
                    try:
                        stdscr.addch(row, x + 1, "█", color)
                    except curses.error:
                        pass

            elapsed = time.time() - start_time
            stdscr.addstr(
                height - 1,
                1,
                f"Recording... (ESC/q/ENTER to stop) Elapsed: {elapsed:.1f}s",
                curses.A_DIM,
            )
            stdscr.refresh()
            time.sleep(0.03)

    curses.wrapper(curses_loop)
    stream.stop()
    stream.close()

    if not recorded_frames:
        print("No audio recorded")
        show_notification("Voice to Text", "No audio recorded")
        sys.exit(1)

    audio_data = np.concatenate(recorded_frames, axis=0)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        import wave

        with wave.open(f.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        audio_path = f.name

    if not audio_path:
        print("No audio recorded")
        show_notification("Voice to Text", "No audio recorded")
        sys.exit(1)

    try:
        if should_use_streaming(transcriber) and transcriber.supports_streaming:
            print("\nStreaming transcription...")
            logger.info("Starting streaming transcription")
            
            # Create audio stream adapter
            from groq_voice.audio_stream import AudioStreamAdapter
            stream_adapter = AudioStreamAdapter(audio_recorder)
            stream_adapter.start()
            
            # Run async transcription
            try:
                import asyncio
                text_parts = []
                async def run_streaming():
                    async for text_delta in transcriber.transcribe_stream(stream_adapter, language=language):
                        text_parts.append(text_delta)
                        # Could show realtime updates here if desired
                asyncio.run(run_streaming())
                text = ''.join(text_parts).strip()
            except Exception as e:
                logger.exception("Streaming transcription failed")
                raise
            finally:
                stream_adapter.stop()
        else:
            # Fall back to batch processing
            print("\nTranscribing...")
            logger.info("Starting transcription")
            text = transcriber.transcribe_file(audio_path, language=language)
        logger.info("Transcription complete: %s", text[:100])
    except Exception as e:
        logger.exception("Transcription failed")
        print(f"Error: {e}")
        show_notification("Voice to Text", f"Error: {e}")
        sys.exit(1)
    finally:
        os.remove(audio_path)

    if not text.strip():
        logger.warning("No speech detected")
        print("No speech detected")
        show_notification("Voice to Text", "No speech detected")
        sys.exit(1)

    if copy_to_clipboard(text):
        logger.info("Copied to clipboard: %s", text[:50])
        print(f"Copied to clipboard: {text[:50]}...")
        show_notification("Voice to Text", f"Copied: {text[:50]}...")
    else:
        logger.error("Clipboard copy failed")
        print(f"Transcription: {text}")
        show_notification("Voice to Text", text[:50])


if __name__ == "__main__":
    main()
