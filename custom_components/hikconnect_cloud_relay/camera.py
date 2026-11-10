"""Native HA camera: no custom public media routes or credential attributes."""
from __future__ import annotations

import queue
from datetime import timedelta
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HikConnectCamera(entry, hass.data[DOMAIN][entry.entry_id])])


class HikConnectCamera(Camera):
    _attr_should_poll = True
    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_extra_state_attributes = {"cloud_provider": DOMAIN}

    def __init__(self, entry, runtime):
        super().__init__()
        self._runtime = runtime
        data = entry.data
        serial, channel = data["device_serial"], data["channel"]
        self._attr_unique_id = f"{DOMAIN}_{serial}_{channel}"
        self._attr_name = data.get("channel_name", f"Channel {channel}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)}, manufacturer="Hikvision",
            name=data.get("device_name", serial), model=data.get("device_model"),
        )

    @property
    def available(self):
        relay = self._runtime["relay"]
        return relay.status == "streaming" and bool(relay.healthy)

    async def async_update(self):
        """Refresh entity availability from thread-safe relay health properties."""

    async def async_camera_image(self, width=None, height=None):
        try:
            return await self.hass.async_add_executor_job(self._runtime["relay"].snapshot, 15.0)
        except queue.Empty:
            return None

    async def stream_source(self):
        # Internal FFmpeg input, not a URL published as entity state.
        return self._runtime["feed"].source
