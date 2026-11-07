"""Family Camera Controls setup."""
from homeassistant.const import Platform

DOMAIN = "family_camera_control"


async def async_setup_entry(hass, entry):
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.BUTTON])
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.BUTTON])
