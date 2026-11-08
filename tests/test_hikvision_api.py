"""Synthetic ISAPI fixtures; these do not claim authenticated household results."""
import importlib.util
import pathlib
import unittest
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

path = pathlib.Path(__file__).parents[1] / "custom_components/hikvision_dvr_status/api.py"
spec = importlib.util.spec_from_file_location("hik_api", path)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class DVRTest(unittest.TestCase):
    def test_streams_are_not_cameras(self):
        root = api.parse_xml(b'<StreamingChannelList xmlns="urn:test"><StreamingChannel><Video><videoInputChannelID>1</videoInputChannelID></Video></StreamingChannel><StreamingChannel><Video><videoInputChannelID>1</videoInputChannelID></Video></StreamingChannel><StreamingChannel><Video><videoInputChannelID>2</videoInputChannelID></Video></StreamingChannel></StreamingChannelList>')
        self.assertEqual(api.channel_count(root), 2)

    def test_missing_inventory_is_unknown(self):
        self.assertIsNone(api.channel_count(api.parse_xml(b'<StreamingChannelList/>')))

    def test_storage_namespace(self):
        root = api.parse_xml(b'<storage xmlns="urn:test"><hddList><hdd><status>ok</status></hdd><hdd><status>error</status></hdd></hddList></storage>')
        self.assertEqual(api.storage_status(root), "error, ok")

    def test_wrong_xml_rejected(self):
        with self.assertRaises(api.DeviceError):
            api.device_info(api.parse_xml(b'<ResponseStatus/>'))

    def test_xml_entity_rejected(self):
        with self.assertRaises(api.DeviceError):
            api.parse_xml(b'<!DOCTYPE x [<!ENTITY test SYSTEM "file:///etc/passwd">]><x/>')

    def test_encoded_dtd_rejected(self):
        with self.assertRaises(api.DeviceError):
            api.parse_xml('<!DOCTYPE x [<!ENTITY test "example">]><x/>'.encode('utf-16'))

    def test_oversize_rejected(self):
        with self.assertRaises(api.DeviceError):
            api.parse_xml(b'x' * (api.MAX_RESPONSE + 1))

    def test_host_validation(self):
        for host in ("http://example.org", "example.org/path", "user@host", "host:80", "host#fragment", ""):
            with self.assertRaises(ValueError):
                api.validate_host(host)
        self.assertEqual(api.validate_host("DVR.local"), "dvr.local")

    def test_no_write_endpoint(self):
        client = api.DVRClient("dvr.local", "user", "secret")
        with self.assertRaises(ValueError):
            client.get("/ISAPI/System/reboot")

    def test_no_redirects(self):
        with self.assertRaises(api.DeviceError):
            api.NoRedirect().redirect_request(None, None, 302, "", {}, "http://other.local")

    def test_partial_support(self):
        client = api.DVRClient("dvr.local", "user", "secret")
        client.get = Mock(side_effect=[api.DeviceError("unsupported"), api.parse_xml(b'<storage><status>ok</status></storage>')])
        self.assertEqual(client.status(), {"camera_count": None, "storage_status": "ok"})

    def test_auth_is_not_swallowed(self):
        client = api.DVRClient("dvr.local", "user", "secret")
        client.get = Mock(side_effect=api.AuthenticationError())
        with self.assertRaises(api.AuthenticationError):
            client.status()

    def test_digest_get_transport(self):
        observations = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                authorization = self.headers.get("Authorization", "")
                observations.append((self.command, self.path, authorization.startswith("Digest ")))
                if not authorization:
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Digest realm="test", nonce="testnonce", qop="auth", algorithm=MD5')
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'<DeviceInfo><model>Fixture DVR</model></DeviceInfo>')

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = api.DVRClient("127.0.0.1", "fixture-user", "fixture-password", port=server.server_port)
            self.assertEqual(client.identify()["model"], "Fixture DVR")
            self.assertEqual(observations, [("GET", "/ISAPI/System/deviceInfo", False),
                                           ("GET", "/ISAPI/System/deviceInfo", True)])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
