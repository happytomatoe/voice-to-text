import numpy as np
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, cairo, GLib

NUM_BARS = 32
BLOCK_SIZE = 2048
SAMPLE_RATE = 16000


class FrequencyWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_decorated(False)
        self.set_default_size(600, 200)

        screen = self.get_screen()
        if screen:
            display = screen.get_display()
            monitor = display.get_primary_monitor()
            if monitor:
                geo = monitor.get_geometry()
                self.move(geo.width // 2 - 300, geo.height - 250)

        self.bar_values = np.zeros(NUM_BARS)
        self.smoothed = np.zeros(NUM_BARS)
        self._lock = threading.Lock()

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(600, 200)
        self.drawing_area.connect("draw", self._on_draw)
        self.add(self.drawing_area)

        self.timeout_id = None

    def _on_timeout(self):
        if self.get_visible():
            self.queue_draw()
        return True

    def show(self):
        self.show_all()
        self.present()
        if self.timeout_id is None:
            self.timeout_id = GLib.timeout_add(33, self._on_timeout)

    def hide(self):
        Gtk.Window.hide(self)
        if self.timeout_id is not None:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None

    def update_fft(self, audio_buffer: np.ndarray):
        freqs = np.fft.rfftfreq(BLOCK_SIZE, d=1/SAMPLE_RATE)
        windowed = audio_buffer * np.hanning(BLOCK_SIZE)
        fft_mag = np.abs(np.fft.rfft(windowed))
        fft_db = 20 * np.log10(fft_mag + 1e-10)
        fft_db = np.clip((fft_db + 60) / 60, 0, 1)

        freq_bins = np.logspace(np.log10(20), np.log10(SAMPLE_RATE//2), NUM_BARS + 1)

        with self._lock:
            for i in range(NUM_BARS):
                lo = np.searchsorted(freqs, freq_bins[i])
                hi = max(np.searchsorted(freqs, freq_bins[i + 1]), lo + 1)
                hi = min(hi, len(fft_db))
                self.bar_values[i] = np.max(fft_db[lo:hi]) if hi > lo else 0

            self.smoothed = 0.7 * self.smoothed + 0.3 * self.bar_values

    def _on_draw(self, widget, cr):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        margin = 10
        bar_width = (width - 2 * margin) / NUM_BARS

        cr.set_source_rgb(0.078, 0.078, 0.118)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        with self._lock:
            smoothed = self.smoothed.copy()

        for i, val in enumerate(smoothed):
            x = margin + i * bar_width
            bar_h = max(1, int(val * (height - 2 * margin)))
            y = height - margin - bar_h

            if val < 0.5:
                cr.set_source_rgb(0.196, 0.784, 0.196)
            elif val < 0.8:
                cr.set_source_rgb(0.784, 0.784, 0.196)
            else:
                cr.set_source_rgb(0.784, 0.196, 0.196)

            cr.rectangle(x, y, bar_width - 2, bar_h)
            cr.fill()