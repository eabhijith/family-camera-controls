"""Buttons wait for actual phone acknowledgement."""
from datetime import timedelta
from homeassistant.components.button import ButtonEntity
from . import DOMAIN, ACTIONS

SCAN_INTERVAL = timedelta(seconds=4)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([PhoneButton(hass.data[DOMAIN], action) for action in ACTIONS], True)


class PhoneButton(ButtonEntity):
    _attr_should_poll = True

    def __init__(self, bridge, action):
        self.bridge = bridge
        self.action = action
        self._attr_name = "Hik-Connect " + action.replace("_", " ")
        self._attr_unique_id = "hikconnect_phone_bridge_" + action

    @property
    def available(self):
        return (self.bridge.control_available and not self.bridge.lock.locked()
                and (self.action not in ("previous_day", "next_day")
                     or self.bridge.metadata.get("mode") == "Playback"))

    async def async_update(self):
        await self.bridge.refresh()

    async def async_press(self):
        await self.bridge.command(self.action)
