"""Phone-free cloud live video; adapted from ijtan's MIT integration."""
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, ConfigEntryError
from homeassistant.helpers import config_validation as cv
from .cloud import HikConnectClient, HikConnectAuthError, HikConnectError
from .const import DOMAIN, DEFAULT_API_HOST
from .media_view import PrivateMediaFeed
from .relay import CloudRelay

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.CAMERA]


def _validate_account(data):
    client = HikConnectClient(data["username"], data["password"])
    try:
        client.login()
    finally:
        client.close()


async def async_setup_entry(hass, entry):
    if entry.data.get("allow_unencrypted_transport") is not True:
        raise ConfigEntryError("Explicit acceptance of experimental unencrypted cloud transport is required")
    try:
        await hass.async_add_executor_job(_validate_account, entry.data)
    except HikConnectAuthError:
        raise ConfigEntryAuthFailed("Cloud account sign-in required") from None
    except HikConnectError:
        raise ConfigEntryNotReady("Cloud service unavailable") from None

    def auth_failed():
        # Called from relay thread; schedule reauth on HA's event loop.
        hass.loop.call_soon_threadsafe(entry.async_start_reauth, hass)

    data = entry.data
    relay = CloudRelay(data["username"], data["password"], DEFAULT_API_HOST,
                       data["device_serial"], int(data["channel"]), 1, 0.0, 5,
                       on_auth_failed=auth_failed)
    feed = PrivateMediaFeed(hass, relay)
    await feed.start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"relay": relay, "feed": feed}
    try:
        await hass.async_add_executor_job(relay.start)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await hass.async_add_executor_job(relay.stop)
        await feed.stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise

    async def stop_on_shutdown(event):
        await hass.async_add_executor_job(relay.stop)
        await feed.stop()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_on_shutdown))
    return True


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime = hass.data[DOMAIN].pop(entry.entry_id)
    await hass.async_add_executor_job(runtime["relay"].stop)
    await runtime["feed"].stop()
    return True
