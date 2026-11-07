"""Separate per-camera bottom-lens button entities with bounded moves."""
import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from .policy import movement_data


async def async_setup_entry(hass, entry, async_add_entities):
    lock = asyncio.Lock()
    async_add_entities([LensButton(entry, direction, lock)
                        for direction in ("up", "down", "left", "right", "stop")])


class LensButton(ButtonEntity):
    _attr_should_poll = False

    def __init__(self, entry, direction, lock):
        self._camera = entry.data["camera_entity"]
        self._direction = direction
        self._lock = lock
        self._attr_unique_id = f"{entry.entry_id}_bottom_{direction}"
        self._attr_name = f"{entry.title} bottom lens {direction}"
        self._attr_icon = "mdi:stop" if direction == "stop" else f"mdi:arrow-{direction}"

    @property
    def available(self):
        state = self.hass.states.get(self._camera)
        return state is not None and state.state not in ("unknown", "unavailable")

    async def async_added_to_hass(self):
        """Refresh button availability when its source camera reconnects."""
        await super().async_added_to_hass()
        self.async_on_remove(async_track_state_change_event(
            self.hass, [self._camera], self._camera_state_changed))

    @callback
    def _camera_state_changed(self, event):
        self.async_write_ha_state()

    async def _send(self, data):
        async with asyncio.timeout(5):
            await self.hass.services.async_call("onvif", "ptz", data,
                target={"entity_id": self._camera}, blocking=True)

    async def async_press(self):
        if not self.available:
            raise HomeAssistantError("Camera is unavailable")
        if self._direction == "stop":
            await self._send(movement_data("stop"))
            return
        # Reject overlapping movements rather than queuing stale taps.
        if self._lock.locked():
            raise HomeAssistantError("A movement is already in progress; press Stop")
        async with self._lock:
            try:
                await self._send(movement_data(self._direction))
            finally:
                await self._send(movement_data("stop"))
