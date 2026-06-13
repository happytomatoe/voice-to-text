"""Bluetooth headset helpers: auto-switch to HSP/HFP and set default source.

Bluetooth headsets such as the Sony WH-1000XM3 default to A2DP for high-quality
playback, which leaves the microphone inactive. When the microphone is needed we
must switch the card profile to HSP/HFP (HSP/HFP enables capture) and make the
resulting ``bluez_input`` source the PipeWire/PulseAudio default so sounddevice's
``InputStream(device=None)`` actually reads the headset mic.

This uses ``pactl`` because it works for both PipeWire (via ``pipewire-pulse``)
and PulseAudio. A udev rule or WirePlumber script could also automate this on
device-connect, but tying it to the recording trigger keeps the behavior
contained to the app and works regardless of system policy configuration.
"""

import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

HSP_HFP_PROFILES = ("headset-head-unit", "headset-head-unit-cvsd", "hands-free", "hands-free-ag")
PROFILE_SWITCH_DELAY = 1.0

CARDS_RE = re.compile(r"Name: (?P<name>bluez_card\.[0-9A-Fa-f:]+)")
PROFILE_RE = re.compile(r"Active Profile:\s*(?P<profile>\S+)")
SOURCE_NAME_RE = re.compile(r"Name:\s*(?P<name>bluez_input\.[0-9A-Fa-f:]+)")
SOURCE_DESC_RE = re.compile(r"Description:\s*(?P<desc>.+)")
DEFAULT_SOURCE_RE = re.compile(r"Default Source:\s*(?P<name>\S+)")


@dataclass
class BluetoothHeadset:
    card_name: str
    active_profile: str
    source_name: str
    source_desc: str


def _run(cmd: list[str], timeout: float = 5.0) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.debug("Command %s failed: %s", cmd, e)
        return None
    if result.returncode != 0:
        logger.debug("Command %s exited %s: %s", cmd, result.returncode, result.stderr.strip())
        return None
    return result.stdout


def list_cards() -> list[str]:
    """Return all bluez card names visible to pactl."""
    out = _run(["pactl", "list", "cards", "short"])
    if not out:
        return []
    names = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].startswith("bluez_card."):
            names.append(parts[1])
    return names


def list_inputs() -> list[str]:
    """Return all bluez input source names visible to pactl."""
    out = _run(["pactl", "list", "short", "sources"])
    if not out:
        return []
    names = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].startswith("bluez_input."):
            names.append(parts[1])
    return names


def get_source_description(source: str) -> str:
    """Return the human-readable description for a pulse source."""
    out = _run(["pactl", "list", "sources"])
    if not out:
        return source
    in_block = False
    for line in out.splitlines():
        if line.strip() == f"Name: {source}":
            in_block = True
            continue
        if in_block:
            m = SOURCE_DESC_RE.search(line)
            if m:
                return m.group("desc").strip()
            if not line.strip():
                break
    return source


def _headset_for_source(source: str, card: str) -> BluetoothHeadset:
    return BluetoothHeadset(
        card_name=card,
        active_profile=get_card_profile(card) or "",
        source_name=source,
        source_desc=get_source_description(source),
    )


def get_card_profile(card: str) -> str | None:
    out = _run(["pactl", "list", "cards"])
    if not out:
        return None
    in_block = False
    for line in out.splitlines():
        if line.strip() == f"Name: {card}":
            in_block = True
            continue
        if not in_block:
            continue
        m = PROFILE_RE.search(line)
        if m:
            return m.group("profile")
        if not line.strip():
            break
    return None


def get_default_source() -> str | None:
    out = _run(["pactl", "info"])
    if not out:
        return None
    m = DEFAULT_SOURCE_RE.search(out)
    return m.group("name") if m else None


def find_headset_for_source(source_name: str) -> str | None:
    """Given a bluez_input source name, return the matching bluez_card name."""
    addr = source_name.removeprefix("bluez_input.").replace(":", "_").lower()
    for card in list_cards():
        if card.removeprefix("bluez_card.").lower() == addr:
            return card
    return None


def set_card_profile(card: str, profile: str) -> bool:
    out = _run(["pactl", "set-card-profile", card, profile])
    return out is not None


def set_default_source(source: str) -> bool:
    out = _run(["pactl", "set-default-source", source])
    return out is not None


def resume_source(source: str) -> bool:
    """Resume a suspended source (WirePlumber suspends idle BT inputs)."""
    out = _run(["pactl", "suspend-source", source, "0"])
    return out is not None


def pick_hsp_profile(card: str) -> str | None:
    """Choose the best available HSP/HFP profile on the given card."""
    out = _run(["pactl", "list", "cards"])
    if not out:
        return None
    in_block = False
    available: list[tuple[int, str]] = []
    for line in out.splitlines():
        if line.strip() == f"Name: {card}":
            in_block = True
            continue
        if in_block:
            if not line.strip():
                break
            stripped = line.strip()
            if stripped.startswith("off:"):
                continue
            m = re.match(r"([\w-]+):", stripped)
            if not m:
                continue
            profile = m.group(1)
            if profile in HSP_HFP_PROFILES and "available: yes" in line:
                priority_m = re.search(r"priority:\s*(\d+)", line)
                priority = int(priority_m.group(1)) if priority_m else 0
                available.append((priority, profile))
    if not available:
        return None
    available.sort(reverse=True)
    return available[0][1]


def detect_headset() -> BluetoothHeadset | None:
    """Return a connected BT headset that has a capture source available.

    Prefers the current default source when it is a Bluetooth headset input.
    """
    default = get_default_source()
    if default and default.startswith("bluez_input."):
        card = find_headset_for_source(default)
        if card:
            return _headset_for_source(default, card)

    for source in list_inputs():
        card = find_headset_for_source(source)
        if card:
            return _headset_for_source(source, card)
    return None


def activate_headset_mic(force: bool = False) -> bool:
    """Make the connected BT headset's microphone the system default.

    Switches the card profile from A2DP/``off`` to HSP/HFP and sets the
    resulting ``bluez_input`` source as the PulseAudio default. Returns
    True if a change was actually applied, False otherwise.
    """
    if not shutil.which("pactl"):
        logger.debug("pactl not available, skipping BT headset setup")
        return False

    headset = detect_headset()
    if not headset:
        return False

    current_default = get_default_source()
    needs_source_swap = current_default != headset.source_name
    needs_profile_switch = headset.active_profile not in HSP_HFP_PROFILES

    if not needs_profile_switch and not needs_source_swap and not force:
        return False

    if needs_profile_switch:
        target = pick_hsp_profile(headset.card_name)
        if not target:
            logger.info(
                "BT headset %s has no HSP/HFP profile available; mic may not work",
                headset.source_desc,
            )
            return False
        logger.info(
            "Switching BT headset %s profile: %s -> %s",
            headset.source_desc,
            headset.active_profile,
            target,
        )
        if not set_card_profile(headset.card_name, target):
            logger.warning("Failed to switch BT headset profile to %s", target)
            return False
        time.sleep(PROFILE_SWITCH_DELAY)

    if needs_source_swap or needs_profile_switch:
        if not set_default_source(headset.source_name):
            logger.warning("Failed to set default source to %s", headset.source_name)
            return False
        logger.info(
            "Set default audio source to %s (%s)",
            headset.source_name,
            headset.source_desc,
        )

    if resume_source(headset.source_name):
        logger.debug("Resumed suspended source %s", headset.source_name)

    return True
