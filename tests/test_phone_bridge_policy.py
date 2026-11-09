"""Offline policy checks; no phone, credentials, UTM, or HA required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load("phone_helper", "tools/hik_phone_bridge.py")
policy = load("phone_policy", "custom_components/hikconnect_phone_bridge/policy.py")


def fixture(mode="Live View", overlay=""):
    def node(resource, text="", cls="android.widget.TextView", rect="[0,100][100,150]"):
        return ('<node package="com.connect.enduser" resource-id="com.connect.enduser:id/'
                + resource + '" text="' + text + '" class="' + cls + '" bounds="'
                + rect + '" enabled="true" clickable="true"/>')
    return ('<hierarchy>' + node("play_view", cls="android.view.TextureView", rect="[0,223][1080,831]")
            + node("play_mode_tv", mode) + node("title_tv", "Camera01")
            + node("record_date_tv", "2026/11/07") + node("rate_text", "197KB/s")
            + node("playSwitchBtn") + node("record_date_subtract_iv")
            + node("record_date_add_iv") + overlay + '</hierarchy>')


class PhonePolicyTest(unittest.TestCase):
    def test_exact_crop_and_mode(self):
        view, crop, _ = helper.parse_view(fixture())
        self.assertEqual(crop, (0, 223, 1080, 831))
        self.assertEqual(view["mode"], "Playback")
        self.assertNotIn("device_id", view)
        live, _, _ = helper.parse_view(fixture("Playback"))
        self.assertEqual(live["mode"], "Live")

    def test_overlays(self):
        system = '<node package="com.android.systemui" bounds="[0,0][1080,80]"/>'
        helper.parse_view(fixture(overlay=system))
        for overlay in (system.replace("[0,0][1080,80]", "[0,300][1080,400]"),
                        system.replace("com.android.systemui", "com.other.app")):
            with self.assertRaises(helper.UnsafeView):
                helper.parse_view(fixture(overlay=overlay))

    def test_reject_unstable_or_wrong_view(self):
        for xml in (fixture().replace('</hierarchy>', '<node package="com.connect.enduser" resource-id="com.connect.enduser:id/play_view_status_tv" text="Failed"/></hierarchy>'),
                    fixture().replace("android.view.TextureView", "android.widget.ImageView"),
                    fixture().replace("Live View", "Unknown")):
            with self.assertRaises(helper.UnsafeView):
                helper.parse_view(xml)

    def test_lock_and_focus(self):
        self.assertTrue(helper.unlocked("mShowingLockscreen=false\nshowing=false"))
        self.assertFalse(helper.unlocked("showing=true"))
        self.assertFalse(helper.unlocked("unrecognized output"))
        self.assertFalse(helper.unlocked("mShowingLockscreen=false\nshowing=true"))
        self.assertTrue(helper.foreground_is_app("mCurrentFocus=Window{123 u0 com.connect.enduser/.Main}"))
        self.assertFalse(helper.foreground_is_app("mCurrentFocus=Window{123 u0 com.other/.Main}"))

    def test_mode_and_dates(self):
        view, _, _ = helper.parse_view(fixture())
        self.assertEqual(helper.action_target("previous_day", view),
                         ("record_date_subtract_iv", "Playback", "2026/11/06"))
        self.assertEqual(helper.action_target("next_day", view)[2], "2026/11/08")
        self.assertEqual(helper.action_target("live", view)[:2], ("playSwitchBtn", "Live"))
        self.assertEqual(helper.action_target("recordings", view)[0], None)
        view["mode"] = "Live"
        with self.assertRaises(helper.UnsafeView):
            helper.action_target("previous_day", view)
        with self.assertRaises(helper.UnsafeView):
            helper.action_target("operation_btn", view)

    def test_fresh_private_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            directory = policy.private_directory(root)
            metadata = {"available": True, "source": helper.APP, "mode": "Live", "timestamp": time.time()}
            (directory / "metadata.json").write_text(json.dumps(metadata))
            (directory / "frame.jpg").write_bytes(b"\xff\xd8snapshot")
            self.assertEqual(policy.snapshot(directory), b"\xff\xd8snapshot")
            metadata["timestamp"] -= 21
            (directory / "metadata.json").write_text(json.dumps(metadata))
            self.assertIsNone(policy.snapshot(directory))
            metadata["timestamp"] = time.time() + 100
            self.assertFalse(policy.valid_metadata(metadata))
            metadata["timestamp"] = time.time()
            metadata["mode"] = "Settings"
            self.assertFalse(policy.valid_metadata(metadata))

    def test_symlink_rejection_and_atomic_command(self):
        with tempfile.TemporaryDirectory() as root:
            directory = policy.private_directory(root)
            command = {"command_id": "test-uuid", "action": "live"}
            policy.write_command(directory, command)
            self.assertEqual(json.loads(policy.read_private(directory, "command.json", 8192)), command)
            (directory / "frame.jpg").symlink_to(directory / "command.json")
            with self.assertRaises(OSError):
                policy.read_private(directory, "frame.jpg", 65536)
            (directory / "command.json").unlink()
            (directory / "command.json").symlink_to(directory / "frame.jpg")
            with self.assertRaises(ValueError):
                policy.write_command(directory, command)


if __name__ == "__main__":
    unittest.main()
