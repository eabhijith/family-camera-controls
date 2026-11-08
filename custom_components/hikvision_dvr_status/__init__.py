"""Local read-only Hikvision DVR status integration."""
from datetime import timedelta
import logging
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import AuthenticationError, DeviceError, DVRClient

DOMAIN = "hikvision_dvr_status"


async def async_setup_entry(hass, entry):
    client = DVRClient(**entry.data)

    async def update():
        try:
            return await hass.async_add_executor_job(client.status)
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except DeviceError as error:
            raise UpdateFailed(str(error)) from error

    coordinator = DataUpdateCoordinator(hass, logging.getLogger(__name__),
        name=DOMAIN, update_method=update, update_interval=timedelta(seconds=60))
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
