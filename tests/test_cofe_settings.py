"""Verified serializer shape tests, not a working native transport test."""
from copy import deepcopy
import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).parents[1] / "custom_components/family_camera_control/cofe_settings.py"
spec = importlib.util.spec_from_file_location("cofe_settings", path)
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.light = {"WorkMode": "Auto", "Brightness": 70,
                      "MoveTrigLight": {"Level": 4, "Duration": 30, "Other": 99},
                      "WorkPeriod": {"existing": True}, "Unknown": "preserve"}
        self.alert = {"Enable": True, "Duration": 10,
                      "EventHandler": {"AlarmOutEnable": True},
                      "RemoteEnable": [False], "RemoteDuration": [5]}

    def test_indexed_object_and_preservation(self):
        original = deepcopy(self.light)
        packet = settings.white_light_update(self.light, session_id="fixture-session", channel=0,
                                             mode="Intelligent", sensitivity="high", duration=60)
        self.assertEqual(packet["Name"], "Camera.WhiteLight.[0]")
        self.assertIsInstance(packet[packet["Name"]], dict)
        result = packet[packet["Name"]]
        self.assertEqual(result["MoveTrigLight"], {"Level": 6, "Duration": 60, "Other": 99})
        self.assertEqual(result["Brightness"], 70)
        self.assertEqual(result["WorkPeriod"], original["WorkPeriod"])
        self.assertEqual(result["Unknown"], "preserve")
        self.assertEqual(self.light, original)

    def test_unindexed_name(self):
        result = settings.white_light_update(self.light, session_id="fixture", mode="Close")
        self.assertEqual(result["Name"], "Camera.WhiteLight")

    def test_alert_preserves_remote_and_event_fields(self):
        packet = settings.intelligent_alert_update(self.alert, session_id="fixture", enabled=False, duration=20)
        name = "Alarm.IntellAlertAlarm"
        self.assertEqual(packet["Name"], name)
        self.assertFalse(packet[name]["Enable"])
        self.assertEqual(packet[name]["EventHandler"], self.alert["EventHandler"])
        self.assertEqual(packet[name]["RemoteDuration"], [5])
        self.assertTrue(self.alert["Enable"])

    def test_light_and_alert_durations_not_interchangeable(self):
        with self.assertRaises(ValueError):
            settings.white_light_update(self.light, session_id="fixture", duration=20)
        with self.assertRaises(ValueError):
            settings.intelligent_alert_update(self.alert, session_id="fixture", duration=60)

    def test_night_vision_picker_is_not_workmode(self):
        for value in (0, "0", "full_color", True):
            with self.assertRaises(ValueError):
                settings.white_light_update(self.light, session_id="fixture", mode=value)

    def test_missing_configuration_not_defaulted(self):
        for existing in ({}, {"Brightness": 1}, []):
            with self.assertRaises(ValueError):
                settings.white_light_update(existing, session_id="fixture", mode="Auto")

    def test_invalid_channels(self):
        for channel in (True, -1, 32, "0"):
            with self.assertRaises(ValueError):
                settings.white_light_update(self.light, session_id="fixture", channel=channel, mode="Auto")

    def test_boolean_is_not_integer_duration(self):
        with self.assertRaises(ValueError):
            settings.intelligent_alert_update(self.alert, session_id="fixture", duration=True)

    def test_no_change_rejected(self):
        with self.assertRaises(ValueError):
            settings.white_light_update(self.light, session_id="fixture")

    def test_session_syntax_not_authentication(self):
        with self.assertRaises(ValueError):
            settings.intelligent_alert_update(self.alert, session_id="", enabled=True)
