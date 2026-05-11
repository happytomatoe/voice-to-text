#!/usr/bin/env python3

import sys
import signal
import logging
import os
from pathlib import Path

LOG_DIR = Path.home() / ".local" / "share" / "voice_daemon"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "daemon.log"),
        logging.StreamHandler(sys.stderr),
    ],
)

logger = logging.getLogger(__name__)


class VoiceDaemon:
    def __init__(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, GLib
        self._glib = GLib

        Gtk.init_check()

        from voice_daemon.frequency_widget import FrequencyWindow
        from voice_daemon.audio_capture import AudioCapture
        from voice_daemon.hotkey_listener import HotkeyListener

        self.freq_window = FrequencyWindow()
        self.audio_capture = AudioCapture(self.freq_window.update_fft)
        self.hotkey = HotkeyListener(self.on_hotkey)

        from voice_daemon.tray import TrayIcon
        self.tray = TrayIcon(self.stop)

        self._main_loop = GLib.MainLoop()

        logger.info("VoiceDaemon initialized")

    def on_hotkey(self):
        """Called when hotkey is pressed."""
        logger.info(f"on_hotkey called, is_recording={self.audio_capture.is_recording}")
        if self.audio_capture.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        logger.info("Starting recording")
        self._glib.idle_add(self.freq_window.show_all)
        self.audio_capture.start()

    def stop_recording(self):
        logger.info("Stopping recording")
        self._glib.idle_add(self.freq_window.hide)
        audio_path = self.audio_capture.stop()
        if audio_path:
            self.transcribe_and_inject(audio_path)

    def transcribe_and_inject(self, audio_path):
        from voice_to_text.providers import get_provider
        from voice_to_text.config import ConfigManager
        from voice_daemon.text_injector import inject_text

        config = ConfigManager()
        provider_name = config.get_selected_provider()
        provider = get_provider(provider_name, config.get_provider_config(provider_name))

        language = config.config.get("transcription", {}).get("language", "en")

        try:
            logger.info("Starting transcription")
            text = provider.transcribe_file(audio_path, language=language)
            logger.info("Transcription complete: %s", text[:50] if text else "empty")

            output_method = config.get_output_config().get("method", "type")
            inject_text(text, method=output_method)
        except Exception as e:
            logger.exception("Transcription failed: %s", e)
        finally:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)

    def run(self):
        self.hotkey.start()
        logger.info("VoiceDaemon running - press Super+V to record")
        self._main_loop.run()

    def stop(self):
        logger.info("Stopping VoiceDaemon")
        self.hotkey.stop()
        self._main_loop.quit()


def main():
    daemon = VoiceDaemon()

    def shutdown():
        logger.info("Shutting down...")
        daemon.hotkey.stop()

    def handle_signal(signum, frame):
        logger.info(f"Signal {signum} received, exiting immediately...")
        daemon.hotkey.stop()
        os._exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    daemon.run()
    logger.info("VoiceDaemon exited")


if __name__ == "__main__":
    main()