"""Mocked transport/capture checks; no attached device is accessed."""
import argparse
import io
import json
import shlex
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from test_phone_bridge_policy import helper, fixture


class HelperTest(unittest.TestCase):
    def test_claim_persisted_before_any_action(self):
        bridge = self.bridge()
        with tempfile.TemporaryDirectory() as root:
            bridge.state_path = str(Path(root) / "state.json")
            command_id = str(uuid.uuid4())
            self.assertTrue(bridge.claim(command_id))
            self.assertEqual(json.loads(Path(bridge.state_path).read_text())["seen"], [command_id])
            self.assertFalse(bridge.claim(command_id))
            self.assertEqual(Path(bridge.state_path).stat().st_mode & 0o777, 0o600)

    def test_no_recording_keeps_safe_mode_controls_without_frame(self):
        xml = fixture().replace('</hierarchy>', '<node package="com.connect.enduser" resource-id="com.connect.enduser:id/play_view_status_tv" text="Loading"/></hierarchy>')
        view, _, _ = helper.parse_view(xml, require_video=False)
        self.assertEqual(view["mode"], "Playback")
        with self.assertRaises(helper.UnsafeView):
            helper.parse_view(xml)

    def test_hidden_or_zero_rate_still_mirrors_paused_app_view(self):
        view, _, _ = helper.parse_view(fixture().replace("197KB/s", "0KB/s"))
        self.assertEqual(view['mode'], 'Playback')

    def test_real_app_duplicate_nodes_and_today(self):
        xml = fixture().replace("2026/11/07", "Today")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
        for node in list(root):
            if node.get("resource-id", "").endswith(("/play_view", "/play_mode_tv")):
                root.append(ET.fromstring(ET.tostring(node)))
        view, crop, _ = helper.parse_view(ET.tostring(root), today="2026/11/08")
        self.assertEqual(view["date"], "2026/11/08")
        self.assertEqual(crop, (0, 223, 1080, 831))

    def bridge(self):
        bridge = helper.Bridge.__new__(helper.Bridge)
        bridge.args = argparse.Namespace(adb="adb", utmctl="utmctl", vm="explicit-vm")
        bridge.serial = "test-only"
        bridge.seen = set()
        bridge.ack = {}
        return bridge

    def test_crop_in_memory_and_rate_changes(self):
        from PIL import Image
        raw = io.BytesIO()
        Image.new("RGB", (1080, 1200), "red").save(raw, "PNG")
        bridge = self.bridge()
        before = helper.parse_view(fixture())
        after = helper.parse_view(fixture().replace("197KB/s", "198KB/s"))
        bridge.view = Mock(side_effect=[before, after])
        bridge.guard = Mock()
        bridge.adb = Mock(return_value=raw.getvalue())
        bridge.publish = Mock()
        bridge.capture()
        metadata, jpeg = bridge.publish.call_args.args
        self.assertTrue(metadata["available"])
        self.assertLessEqual(len(jpeg), helper.MAX_JPEG)
        with Image.open(io.BytesIO(jpeg)) as image:
            self.assertEqual(image.size, (1080, 608))
        bridge.adb.assert_called_once_with("exec-out", "screencap", "-p")

    def test_locked_no_capture(self):
        bridge = self.bridge()
        bridge.adb = Mock(side_effect=[b"showing=true", b"mCurrentFocus=Window{a com.connect.enduser/.Main}"])
        bridge.publish = Mock()
        with self.assertRaises(helper.UnsafeView):
            bridge.capture()
        self.assertEqual(bridge.adb.call_count, 2)
        bridge.publish.assert_not_called()

    def test_guest_python_atomic_private_publication(self):
        bridge = self.bridge()
        bridge.run = Mock(return_value=b"")
        bridge.publish({"available": True, "mode": "Live"}, b"\xff\xd8test")
        argv = bridge.run.call_args.args[0]
        self.assertEqual(argv[:6], ["utmctl", "exec", "explicit-vm", "--cmd", "/bin/sh", "-c"])
        docker = shlex.split(argv[-1])
        self.assertEqual(docker[:5], ["docker", "exec", "homeassistant", "python3", "-c"])
        code = docker[-1]
        compile(code, "guest-publication", "exec")
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root).resolve() / "phone_camera_bridge"
            exec(code.replace("/config/phone_camera_bridge", str(directory)), {})
            self.assertEqual((directory / "frame.jpg").read_bytes(), b"\xff\xd8test")
            self.assertTrue(json.loads((directory / "metadata.json").read_text())["available"])
            self.assertEqual((directory / "frame.jpg").stat().st_mode & 0o777, 0o600)
            self.assertFalse(list(directory.glob(".incoming-*")))

    def test_verified_date_action_ack_and_dedup(self):
        bridge = self.bridge()
        command_id = str(uuid.uuid4())
        command = {"command_id": command_id, "action": "previous_day", "timestamp": time.time()}
        bridge.run = Mock(return_value=json.dumps(command).encode())
        before = helper.parse_view(fixture())
        after = helper.parse_view(fixture().replace("2026/11/07", "2026/11/06"))
        bridge.view = Mock(side_effect=[before, after])
        bridge.guard = Mock()
        bridge.adb = Mock()
        bridge.commands()
        self.assertEqual(bridge.ack, {"command_id": command_id, "status": "success"})
        bridge.adb.assert_called_once_with("shell", "input", "tap", "50", "125")
        bridge.commands()
        self.assertEqual(bridge.adb.call_count, 1)

    def test_stale_command_never_taps(self):
        bridge = self.bridge()
        command = {"command_id": str(uuid.uuid4()), "action": "live", "timestamp": time.time()-21}
        bridge.run = Mock(return_value=json.dumps(command).encode())
        bridge.view = Mock()
        bridge.adb = Mock()
        bridge.commands()
        self.assertEqual(bridge.ack["status"], "error")
        bridge.view.assert_not_called()
        bridge.adb.assert_not_called()


if __name__ == "__main__":
    unittest.main()
