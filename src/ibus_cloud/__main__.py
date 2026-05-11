#!/usr/bin/env python3
"""IBus Cloud Speech engine entry point."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import gi
gi.require_version('IBus', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import IBus, GLib


def main():
    factory = CloudSpeechEngineFactory()
    IBus.init()
    bus = IBus.Bus()
    bus.connect("disconnected", lambda _: GLib.main_quit())
    service = IBus.Service(bus, "com.cloud-voice.CloudSpeech")
    service.register()
    GLib.main()


if __name__ == '__main__':
    main()