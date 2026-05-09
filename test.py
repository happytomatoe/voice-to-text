#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, GLib
import subprocess
import time
import os
import signal


class TypeInPreviousWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Type to Previous Window")
        self.set_default_size(400, 200)

        # Layout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        self.set_child(box)

        label = Gtk.Label(label="Text to type in previous window:")
        box.append(label)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Type your text here...")
        box.append(self.entry)

        self.delay_label = Gtk.Label(label="Delay before typing (seconds): 1.0")
        box.append(self.delay_label)

        self.delay_slider = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.5, 5.0, 0.5
        )
        self.delay_slider.set_value(1.0)
        self.delay_slider.connect("value-changed", self.on_delay_changed)
        box.append(self.delay_slider)

        btn = Gtk.Button(label="Send & Close")
        btn.connect("clicked", self.on_send_clicked)
        box.append(btn)

        # Connect Enter key
        self.entry.connect("activate", self.on_send_clicked)

    def on_delay_changed(self, slider):
        val = slider.get_value()
        self.delay_label.set_text(f"Delay before typing (seconds): {val:.1f}")

    def on_send_clicked(self, _):
        text = self.entry.get_text()
        delay = self.delay_slider.get_value()
        if text:
            self.schedule_type_and_close(text, delay)

    def schedule_type_and_close(self, text, delay):
        """Close the window, wait for focus to return, then type."""
        self.get_application().quit()

        def do_type():
            time.sleep(delay)
            subprocess.run(["wtype", text])

        import threading

        t = threading.Thread(target=do_type, daemon=True)
        t.start()


class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.typeprevious")

    def do_activate(self):
        win = TypeInPreviousWindow(self)
        win.present()


if __name__ == "__main__":
    app = MyApp()
    app.run()
