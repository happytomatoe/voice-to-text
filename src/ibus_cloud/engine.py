"""IBus Cloud Speech engine implementation."""

import gi
import logging
import threading
import asyncio

LOG_FILE = "/tmp/ibus-cloud.log"
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler(LOG_FILE),
    ]
)

import sys
def log_exceptions(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = log_exceptions

gi.require_version('IBus', '1.0')
from gi.repository import IBus, GObject

from ibus_cloud.audio import AudioRecorder
from ibus_cloud.config import ConfigManager

logger = logging.getLogger(__name__)

GDK_q = 0x71
IBUS_SUPER_MASK = 0x2000


class CloudSpeechEngine(IBus.Engine):
    __gtype_name__ = 'CloudSpeechEngine'

    def __init__(self, bus, object_path):
        super().__init__(connection=bus.get_connection(),
                         object_path=object_path)
        logger.info("CloudSpeechEngine created")
        self._recording = False
        self._transcribing = False
        self._audio_recorder = None
        self._config = ConfigManager()
        self._loop = None
        self._thread = None

    def do_enable(self):
        """Called when engine is enabled."""
        logger.info("=== CloudSpeech engine do_enable() called ===")
        self.register_properties(IBus.PropList.new())
        logger.info("Properties registered")
        self.update_preedit_text(
            IBus.Text.new_from_string("Cloud: Press Super+Q to record"), 0, True
        )
        logger.info("Preedit text set")

    def do_disable(self):
        """Called when engine is disabled."""
        logger.info("CloudSpeech engine disabled")
        self.stop_recording()

    def do_process_key_event(self, keyval, keycode, state):
        """Handle key events - Super+Q toggles recording."""
        if keyval == GDK_q and (state & IBUS_SUPER_MASK):
            if self._transcribing:
                return True

            if self._recording:
                self.stop_recording_and_transcribe()
            else:
                self.start_recording()
            return True

        return False

    def start_recording(self):
        """Start audio recording."""
        logger.info("Starting recording")
        self._recording = True
        self._audio_recorder = AudioRecorder(
            device=self._config.get_audio_device(),
            callback=self._on_audio_level
        )
        self._audio_recorder.start_recording()
        self.update_preedit_text(
            IBus.Text.new_from_string("● Recording... (press Super+Q to stop)"), 0, True
        )

    def stop_recording_and_transcribe(self):
        """Stop recording and start transcription."""
        logger.info("Stopping recording and transcribing")
        self._recording = False
        self._transcribing = True

        audio_data = None
        if self._audio_recorder:
            audio_data = self._audio_recorder.stop_recording()
            self._audio_recorder = None

        self.update_preedit_text(
            IBus.Text.new_from_string("◐ Transcribing..."), 0, True
        )

        if audio_data is not None and len(audio_data) > 0:
            self._transcribe_async(audio_data)
        else:
            self._transcribing = False
            self.update_preedit_text(
                IBus.Text.new_from_string("No audio recorded"), 0, True
            )
            GObject.timeout_add(2000, self._clear_preedit)

    def _transcribe_async(self, audio_data):
        """Run transcription in a background thread."""
        def run_transcription():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                text = loop.run_until_complete(self._do_transcribe(audio_data))
                loop.close()

                if text and text.strip():
                    self.commit_text(IBus.Text.new_from_string(text))
                    self._show_notification("Voice Input", f"Transcribed: {text[:50]}...")
                else:
                    self.update_preedit_text(
                        IBus.Text.new_from_string("No speech detected"), 0, True
                    )
                    GObject.timeout_add(2000, self._clear_preedit)

            except Exception as e:
                logger.exception("Transcription failed: %s", e)
                self.update_preedit_text(
                    IBus.Text.new_from_string(f"Error: {e}"), 0, True
                )
                GObject.timeout_add(3000, self._clear_preedit)
            finally:
                self._transcribing = False

        thread = threading.Thread(target=run_transcription, daemon=True)
        thread.start()

    async def _do_transcribe(self, audio_data):
        """Perform actual transcription."""
        from voice_to_text.providers import get_provider
        from voice_to_text.config import ConfigManager

        config_mgr = ConfigManager()
        provider_name = config_mgr.get_selected_provider()
        provider_config = config_mgr.get_provider_config(provider_name)
        transcriber = get_provider(provider_name, provider_config)

        language = config_mgr.config.get("transcription", {}).get("language", "en")

        import tempfile
        import wave
        import os

        SAMPLE_RATE = 16000
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            with wave.open(f.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data.tobytes())

            try:
                text = transcriber.transcribe_file(f.name, language=language)
                return text
            finally:
                os.remove(f.name)

    def _on_audio_level(self, level):
        """Callback for audio level updates."""
        if self._recording:
            filled = int(level * 10)
            bars = "█" * filled + "░" * (10 - filled)
            text = f"● Recording... {bars}"
            self.update_preedit_text(IBus.Text.new_from_string(text), 0, True)

    def _clear_preedit(self):
        """Clear the preedit text."""
        self.update_preedit_text(IBus.Text.new_from_string(""), 0, False)
        return False

    def _show_notification(self, title, body):
        """Show a desktop notification."""
        import subprocess
        try:
            subprocess.run(
                ["notify-send", "-u", "normal", title, body],
                check=True,
                capture_output=True,
            )
        except Exception as e:
            logger.warning("Failed to show notification: %s", e)

    def stop_recording(self):
        """Stop any ongoing recording."""
        if self._recording and self._audio_recorder:
            self._audio_recorder.stop_recording()
            self._audio_recorder = None
        self._recording = False
        self._transcribing = False

    def do_focus_in(self):
        """Called when input context gains focus."""
        pass

    def do_focus_out(self):
        """Called when input context loses focus."""
        if self._recording:
            self.stop_recording_and_transcribe()

    def do_reset(self):
        """Reset engine state."""
        self.stop_recording()


class CloudSpeechEngineFactory(GObject.Object):
    """Factory for creating CloudSpeechEngine instances."""

    def __init__(self):
        super().__init__()

    def create_engine(self, engine_name):
        """Create a new engine instance."""
        if engine_name == "com.cloud-voice.CloudSpeech":
            return CloudSpeechEngine()
        return None