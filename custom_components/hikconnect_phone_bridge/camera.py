"""HA-authenticated snapshots only; no stream feature or public image URL."""
from datetime import timedelta
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from . import DOMAIN

SCAN_INTERVAL = timedelta(seconds=4)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([PhoneCamera(hass.data[DOMAIN])], True)


class PhoneCamera(Camera):
    _attr_should_poll = True
    _attr_name = "Hik-Connect selected phone view"
    _attr_unique_id = "hikconnect_phone_bridge_selected_view"
    _attr_supported_features = CameraEntityFeature(0)

    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, DOMAIN + "_updated", self.async_write_ha_state))

    @property
    def available(self):
        return self.bridge.available

    @property
    def extra_state_attributes(self):
        return {k: self.bridge.metadata[k] for k in ("mode", "camera_label", "date", "time", "rate", "view_status")
                if k in self.bridge.metadata}

    async def async_update(self):
        await self.bridge.refresh()

    async def async_camera_image(self, width=None, height=None):
        return await self.bridge.image()
