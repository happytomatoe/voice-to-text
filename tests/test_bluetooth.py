"""Tests for Bluetooth headset detection."""

from unittest.mock import patch

from voice_to_text.bluetooth import detect_headset


class TestDetectHeadset:
    def test_prefers_default_bluez_source(self):
        default = "bluez_input.AA_BB_CC_DD_EE_FF"
        other = "bluez_input.11_22_33_44_55_66"
        card = "bluez_card.AA_BB_CC_DD_EE_FF"

        with (
            patch("voice_to_text.bluetooth.get_default_source", return_value=default),
            patch("voice_to_text.bluetooth.list_inputs", return_value=[other, default]),
            patch(
                "voice_to_text.bluetooth.find_headset_for_source", side_effect=lambda s: card if s == default else None
            ),
            patch("voice_to_text.bluetooth.get_card_profile", return_value="a2dp-sink"),
            patch("voice_to_text.bluetooth.get_source_description", return_value="My Headset"),
        ):
            headset = detect_headset()

        assert headset is not None
        assert headset.source_name == default
        assert headset.source_desc == "My Headset"

    def test_falls_back_to_first_available_input(self):
        source = "bluez_input.AA_BB_CC_DD_EE_FF"
        card = "bluez_card.AA_BB_CC_DD_EE_FF"

        with (
            patch("voice_to_text.bluetooth.get_default_source", return_value="alsa_input.pci"),
            patch("voice_to_text.bluetooth.list_inputs", return_value=[source]),
            patch("voice_to_text.bluetooth.find_headset_for_source", return_value=card),
            patch("voice_to_text.bluetooth.get_card_profile", return_value="headset-head-unit"),
            patch("voice_to_text.bluetooth.get_source_description", return_value="Fallback Headset"),
        ):
            headset = detect_headset()

        assert headset is not None
        assert headset.source_name == source
