"""Read-only local ISAPI client. No cloud tokens, writes or playback commands."""
import ipaddress
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

MAX_RESPONSE = 1024 * 1024
PATHS = frozenset({"/ISAPI/System/deviceInfo", "/ISAPI/ContentMgmt/Storage",
                   "/ISAPI/Streaming/channels"})


class AuthenticationError(Exception):
    """The DVR rejected local credentials."""


class DeviceError(Exception):
    """The DVR is unreachable or returned an invalid response."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DeviceError("DVR redirects are not allowed")


def validate_host(host):
    """Accept a bare host only; never accept credentials, paths or URL fragments."""
    if not isinstance(host, str) or not host or len(host) > 253:
        raise ValueError("Enter a host name or IP address")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                   for label in host.split(".")):
            raise ValueError("Enter a bare host name or IP address") from None
    return host.lower()


def parse_xml(payload):
    if (len(payload) > MAX_RESPONSE or b"\x00" in payload
            or b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper()):
        raise DeviceError("Unsafe or oversized DVR XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        raise DeviceError("Invalid DVR XML") from None
    # Hikvision firmware varies in namespace URI. Match the local names only.
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    return root


def device_info(root):
    if root.tag != "DeviceInfo":
        raise DeviceError("Not an ISAPI device-information response")
    return {key: root.findtext(key) for key in ("model", "firmwareVersion", "serialNumber")}


def channel_count(root):
    if root.tag != "StreamingChannelList":
        raise DeviceError("Not an ISAPI streaming-channel response")
    # Main/substreams must not be counted as different cameras.
    sources = set()
    for channel in root.findall("StreamingChannel"):
        source = channel.findtext("Video/videoInputChannelID")
        if source and source.isdecimal():
            sources.add(int(source))
    # Missing source identity is unknown, not zero or a guessed ID convention.
    return len(sources) if sources else None


def storage_status(root):
    if root.tag not in {"storage", "Storage", "hddList", "HDDList"}:
        raise DeviceError("Not an ISAPI storage response")
    states = [node.text.strip() for node in root.iter("status") if node.text and node.text.strip()]
    return ", ".join(sorted(set(states))) if states else None


class DVRClient:
    def __init__(self, host, username, password, port=80, use_https=False):
        host = validate_host(host)
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid DVR port")
        address = f"[{host}]" if ":" in host else host
        self.base = f"{'https' if use_https else 'http'}://{address}:{port}"
        manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(None, self.base, username, password)
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
            urllib.request.HTTPDigestAuthHandler(manager))

    def get(self, path):
        if path not in PATHS:
            raise ValueError("Only approved read-only ISAPI endpoints are allowed")
        request = urllib.request.Request(self.base + path, headers={"Accept": "application/xml"}, method="GET")
        try:
            with self._opener.open(request, timeout=8) as response:
                return parse_xml(response.read(MAX_RESPONSE + 1))
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise AuthenticationError("Local DVR credentials rejected") from None
            raise DeviceError(f"DVR returned HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise DeviceError("Could not connect to DVR") from None

    def identify(self):
        return device_info(self.get("/ISAPI/System/deviceInfo"))

    def status(self):
        result = {}
        for name, path, parser in (
            ("camera_count", "/ISAPI/Streaming/channels", channel_count),
            ("storage_status", "/ISAPI/ContentMgmt/Storage", storage_status),
        ):
            try:
                result[name] = parser(self.get(path))
            except AuthenticationError:
                raise
            except DeviceError:
                # Unsupported endpoint must not prevent the other sensor working.
                result[name] = None
        if all(value is None for value in result.values()):
            raise DeviceError("No supported DVR status endpoints are available")
        return result
