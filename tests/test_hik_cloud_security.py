"""Offline security regressions; no HA install or vendor access required."""
import asyncio
import ast
import importlib.util
from enum import IntFlag
import json
from pathlib import Path
import queue
import sys
import threading
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/hikconnect_cloud_relay"
PACKAGE = "_hik_cloud_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(SOURCE)]
sys.modules[PACKAGE] = package


def load(name):
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.{name}", SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cloud = load("cloud")
relay = load("relay")
vtm = sys.modules[f"{PACKAGE}.vtm"]


class CloudSecurity(unittest.TestCase):
    def test_cached_frame_expires_and_clears(self):
        frames = relay.FrameBuffer()
        with patch.object(relay.time, "monotonic", return_value=10):
            frames.publish(b"synthetic-image")
            self.assertTrue(frames.fresh)
        with patch.object(relay.time, "monotonic", return_value=30):
            self.assertFalse(frames.fresh)
            with self.assertRaises(queue.Empty):
                frames.snapshot(timeout=0)
        frames.clear()
        self.assertFalse(frames.fresh)

    def test_unsupported_encryption_does_not_repeat_logins(self):
        worker = relay.CloudRelay("fake", "fake", cloud.DEFAULT_API_HOST, "fake", 1, 1, 0, 5)
        worker._run_once = Mock(side_effect=vtm.UnsupportedVtmStream())
        worker._run()
        self.assertEqual(worker._run_once.call_count, 1)
        self.assertEqual(worker.status, "unsupported")

    def test_api_host_allowlist(self):
        for value in ["http://api.hik-connect.com", "https://evil.test", "https://hik-connect.com.evil.test",
                      "https://x.hik-connect.com@evil.test", "https://api.hik-connect.com/path",
                      "https://api.hik-connect.com:444", "https://127.0.0.1"]:
            with self.subTest(value=value), self.assertRaises(cloud.HikConnectError):
                cloud.HikConnectClient("fake", "fake", value)
        client = cloud.HikConnectClient("fake", "fake", "https://ieu.hik-connect.com")
        client.close()

    def test_redaction_discards_values(self):
        secret = "secret-123"
        self.assertNotIn(secret, cloud._redact(f"password={secret}&token={secret}"))

    def test_no_http_redirects_or_auth_retry(self):
        client = cloud.HikConnectClient("fake", "fake")
        response = Mock(status_code=302)
        client._session.request = Mock(return_value=response)
        with self.assertRaises(cloud.HikConnectError):
            client.login()
        self.assertEqual(client._session.request.call_count, 1)
        self.assertFalse(client._session.request.call_args.kwargs["allow_redirects"])
        client.close()

    def test_bad_password_stops(self):
        client = cloud.HikConnectClient("fake", "fake")
        client._raw = Mock(return_value={"meta": {"code": 1013}})
        with self.assertRaises(cloud.HikConnectAuthError):
            client.login()
        self.assertEqual(client._raw.call_count, 1)
        client.close()

    def test_password_rate_limit_is_not_retried(self):
        client = cloud.HikConnectClient("fake", "fake")
        client._session.request = Mock(return_value=Mock(status_code=429, headers={}))
        with self.assertRaises(cloud.HikConnectError):
            client.login()
        self.assertEqual(client._session.request.call_count, 1)
        client.close()

    def test_session_expiry_does_not_resubmit_password(self):
        client = cloud.HikConnectClient("fake", "fake")
        client.session_id = "fake-session"
        client._raw = Mock(return_value={"meta": {"code": 401}})
        client.login = Mock()
        with self.assertRaises(cloud.HikConnectAuthError):
            client.get_devices()
        client.login.assert_not_called()
        client.close()

    def test_trusted_region_redirect_is_bounded(self):
        client = cloud.HikConnectClient("fake", "fake")
        client._raw = Mock(side_effect=[
            {"meta": {"code": 1100}, "loginArea": {"apiDomain": "ieu.hik-connect.com"}},
            {"loginSession": {"sessionId": "fake-session"}}, {},
        ])
        client.login()
        self.assertEqual(client.base_url, "https://ieu.hik-connect.com")
        self.assertEqual(client._raw.call_count, 3)
        client.close()

    def test_region_redirect_checked_before_second_post(self):
        for target in ["http://api.hik-connect.com", "https://evil.test"]:
            client = cloud.HikConnectClient("fake", "fake")
            client._raw = Mock(return_value={"meta": {"code": 1100}, "loginArea": {"apiDomain": target}})
            with self.assertRaises(cloud.HikConnectError):
                client.login()
            self.assertEqual(client._raw.call_count, 1)
            client.close()

    def test_challenge_is_not_bypassed(self):
        client = cloud.HikConnectClient("fake", "fake")
        client._raw = Mock(return_value={"meta": {"code": 1015}})
        with self.assertRaises(cloud.HikConnectChallengeError):
            client.login()
        self.assertEqual(client._raw.call_count, 1)
        client.close()

    def test_worker_stops_on_auth_failure(self):
        callback = Mock()
        worker = relay.CloudRelay("fake", "fake", cloud.DEFAULT_API_HOST, "fake", 1, 1, 0, 5,
                                  on_auth_failed=callback)
        worker._run_once = Mock(side_effect=cloud.HikConnectAuthError("secret"))
        worker._run()
        self.assertEqual(worker._run_once.call_count, 1)
        self.assertEqual(worker.status, "auth_failed")
        callback.assert_called_once()
        self.assertNotIn("secret", str(worker.stats()))

    def test_vtm_private_endpoint_rejected(self):
        client = vtm.VtmStreamClient("ysproto://127.0.0.1:8554/live")
        with patch.object(vtm.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 8554))]), \
             patch.object(vtm.socket, "create_connection") as connect:
            with self.assertRaises(vtm.VtmError):
                client.connect()
            connect.assert_not_called()

    def test_metadata_and_no_public_routes(self):
        manifest = json.loads((SOURCE / "manifest.json").read_text())
        self.assertTrue(manifest["config_flow"])
        self.assertIn("stream", manifest["dependencies"])
        self.assertIn("requests>=2.32.5,<3", manifest["requirements"])
        text = (SOURCE / "__init__.py").read_text() + (SOURCE / "media_view.py").read_text()
        self.assertNotIn("register_view(", text)
        self.assertNotIn("requires_auth = False", text)
        camera = (SOURCE / "camera.py").read_text()
        self.assertIn("_attr_supported_features = CameraEntityFeature.STREAM", camera)
        self.assertIn('_attr_extra_state_attributes = {"cloud_provider": DOMAIN}', camera)
        flow = (SOURCE / "config_flow.py").read_text()
        self.assertIn("TextSelectorType.PASSWORD", flow)
        self.assertNotIn("if channel.linked", flow)


class PrivateFeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_unencrypted_transport_requires_explicit_acceptance(self):
        tree = ast.parse((SOURCE / "config_flow.py").read_text())
        flow_class = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        method = next(node for node in flow_class.body
                      if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_step_channel")
        vol = types.SimpleNamespace(Schema=lambda value: value,
                                    Required=lambda key, **kwargs: key, In=lambda value: value)
        namespace = {"vol": vol}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "config_flow.py", "exec"), namespace)
        flow = Mock()
        flow._channels = {1: Mock(name="channel")}
        for data in ({"channel": 1}, {"channel": 1, "allow_unencrypted_transport": False}):
            await namespace["async_step_channel"](flow, data)
            self.assertEqual(flow.async_show_form.call_args.kwargs["errors"],
                             {"base": "transport_consent_required"})
        flow.async_create_entry.assert_not_called()

    async def test_first_config_form_never_authenticates(self):
        tree = ast.parse((SOURCE / "config_flow.py").read_text())
        flow_class = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        method = next(node for node in flow_class.body
                      if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_step_user")
        # Execute the actual method without importing HA; all side effects mocked.
        namespace = {"USER_SCHEMA": object()}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "config_flow.py", "exec"), namespace)
        flow = Mock()
        flow.hass.async_add_executor_job = AsyncMock()
        result = await namespace["async_step_user"](flow, None)
        self.assertIs(result, flow.async_show_form.return_value)
        flow.hass.async_add_executor_job.assert_not_called()
        self.assertEqual(flow.async_show_form.call_args.kwargs["step_id"], "user")

    async def test_native_camera_contract_with_mock_ha(self):
        class CameraEntityFeature(IntFlag):
            STREAM = 2

        class Camera:
            pass

        modules = {}
        for name in ["homeassistant", "homeassistant.components", "homeassistant.components.camera",
                     "homeassistant.helpers", "homeassistant.helpers.entity"]:
            modules[name] = types.ModuleType(name)
        modules["homeassistant.components.camera"].Camera = Camera
        modules["homeassistant.components.camera"].CameraEntityFeature = CameraEntityFeature
        modules["homeassistant.helpers.entity"].DeviceInfo = dict
        with patch.dict(sys.modules, modules):
            camera = load("camera")
        worker = Mock(status="streaming")
        worker.snapshot.return_value = b"jpeg"
        runtime = {"relay": worker, "feed": Mock(source="http://127.0.0.1:45678/stream.ts")}
        entity = camera.HikConnectCamera(Mock(data={"device_serial": "fake", "channel": 2}), runtime)
        self.assertIsInstance(entity._attr_supported_features, CameraEntityFeature)
        self.assertIn(CameraEntityFeature.STREAM, entity._attr_supported_features)
        self.assertEqual(entity._attr_extra_state_attributes,
                         {"cloud_provider": "hikconnect_cloud_relay"})
        self.assertEqual(await entity.stream_source(), runtime["feed"].source)

        async def executor(function, *args):
            return function(*args)

        entity.hass = Mock(async_add_executor_job=executor)
        self.assertEqual(await entity.async_camera_image(), b"jpeg")
        worker.status = "auth_failed"
        self.assertFalse(entity.available)

    async def test_real_listener_binds_only_loopback(self):
        media = load("media_view")
        hass = Mock()
        worker = Mock()
        feed = media.PrivateMediaFeed(hass, worker)
        try:
            await feed.start()
            self.assertTrue(feed.source.startswith("http://127.0.0.1:"))
            self.assertTrue(all(address[0] == "127.0.0.1" for address in feed.runner.addresses))
            self.assertNotEqual(feed.runner.addresses[0][1], 8123)
            hass.http.register_view.assert_not_called()
        finally:
            await feed.stop()


if __name__ == "__main__":
    unittest.main()
