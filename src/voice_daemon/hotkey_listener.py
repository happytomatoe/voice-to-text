import select
import logging
import time
from threading import Thread, Event
from evdev import InputDevice, ecodes, list_devices

logger = logging.getLogger(__name__)


class HotkeyListener:
    def __init__(self, callback, key_combo=(ecodes.KEY_V,)):
        """
        callback: function to call when hotkey is pressed
        key_combo: tuple of keys that must all be pressed (mod4 = Super)
        """
        self.callback = callback
        self.key_combo = key_combo
        self.mod_keys = {ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA}
        self.active_keys = set()
        self.running = Event()
        self.thread = None

    def _find_keyboards(self):
        """Find all keyboard devices."""
        devices = []
        for path in list_devices():
            try:
                dev = InputDevice(path)
                if any(cap in dev.capabilities().get(ecodes.EV_KEY, [])
                       for cap in [ecodes.KEY_A, ecodes.KEY_Q]):
                    devices.append(dev)
            except:
                pass
        return devices

    def _listen(self):
        devices = self._find_keyboards()
        if not devices:
            logger.warning("No keyboard devices found")
            return

        logger.info(f"Listening on {len(devices)} keyboard devices")
        for d in devices:
            logger.info(f"  - {d.path}: {d.name}")

        import time
        while self.running.is_set():
            try:
                r, _, _ = select.select(devices, [], [], 0.5)
                if not r:
                    continue
                    
                for dev in r:
                    try:
                        data = list(dev.read())
                        if data:
                            logger.debug(f"Got {len(data)} events from {dev.path}")
                        for event in data:
                            if event.type == ecodes.EV_KEY:
                                key = event.value
                                code = event.code

                                if key == 1:  # key down
                                    key_name = ecodes.KEY.get(code, f"KEY_{code}")
                                    logger.debug(f"Key down: {key_name} ({code})")
                                    if code in self.mod_keys:
                                        self.active_keys.add(code)
                                        logger.debug(f"Super key added, active_keys={self.active_keys}")
                                    if code == ecodes.KEY_V:
                                        self.active_keys.add(code)
                                        logger.debug(f"V pressed, active_keys={self.active_keys}")
                                    if self._check_combo():
                                        if not getattr(self, '_last_triggered', 0) or (time.time() - self._last_triggered) > 0.5:
                                            self._last_triggered = time.time()
                                            logger.info("Hotkey triggered!")
                                            self.callback()

                                elif key == 0:  # key up
                                    if code in self.mod_keys:
                                        self.active_keys.discard(code)
                                    elif code == ecodes.KEY_V:
                                        pass
                    except Exception as e:
                        logger.error(f"Error reading {dev.path}: {e}")
            except Exception as e:
                logger.error(f"Select error: {e}")
                time.sleep(0.1)

    def _check_combo(self):
        """Check if Super+V is pressed."""
        has_mod = any(k in self.active_keys for k in self.mod_keys)
        has_v = ecodes.KEY_V in self.active_keys
        logger.debug(f"check_combo: has_mod={has_mod}, has_v={has_v}, active_keys={self.active_keys}")
        return has_mod and has_v

    def start(self):
        self.running.set()
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()
        logger.info("Hotkey listener started (Super+V)")

    def stop(self):
        self.running.clear()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Hotkey listener stopped")