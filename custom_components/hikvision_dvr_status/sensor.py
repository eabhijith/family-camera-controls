"""Only expose status actually returned by the DVR."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DVRStatus(coordinator, entry, key, label, icon) for key, label, icon in (
        ("camera_count", "camera count", "mdi:cctv"),
        ("storage_status", "storage status", "mdi:harddisk"),
    )])


class DVRStatus(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, key, label, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = f"{entry.title} {label}"
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.unique_id or entry.entry_id)},
            "name": entry.title,
        }

    @property
    def available(self):
        return super().available and self.coordinator.data.get(self._key) is not None

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)
