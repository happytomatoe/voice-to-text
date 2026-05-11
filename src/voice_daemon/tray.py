import logging
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3

logger = logging.getLogger(__name__)


class TrayIcon:
    def __init__(self, on_quit):
        self.indicator = AppIndicator3.Indicator.new(
            "voice-to-text",
            "audio-x-generic",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_title("Voice to Text")
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", on_quit)
        menu.append(quit_item)
        menu.show_all()

        self.indicator.set_menu(menu)
        logger.info("System tray icon created")

    def show_message(self, title, msg):
        self.indicator.set_title(f"{title}\n{msg}")