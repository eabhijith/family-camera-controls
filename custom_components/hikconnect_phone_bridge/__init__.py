"""One selected authenticated Android app view, not a native DVR stream."""
import asyncio
import time
import uuid
from datetime import timedelta

import voluptuous as vol
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.exceptions import HomeAssistantError

from .policy import load_metadata, private_directory, snapshot, valid_metadata, valid_controls, write_command

DOMAIN = "hikconnect_phone_bridge"
ACTIONS = ("live", "recordings", "previous_day", "next_day")
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Any(None, vol.Schema({}))}, extra=vol.ALLOW_EXTRA)


class Bridge:
    def __init__(self, hass, directory):
        self.hass = hass
        self.directory = directory
        self.metadata = {}
        self.lock = asyncio.Lock()

    @property
    def available(self):
        return valid_metadata(self.metadata)

    @property
    def control_available(self):
        return valid_controls(self.metadata)

    async def refresh(self):
        try:
            self.metadata = await self.hass.async_add_executor_job(load_metadata, self.directory)
        except (OSError, ValueError):
            self.metadata = {}
        async_dispatcher_send(self.hass, DOMAIN + "_updated")

    async def image(self):
        try:
            return await self.hass.async_add_executor_job(snapshot, self.directory)
        except (OSError, ValueError):
            return None

    async def command(self, action):
        if action not in ACTIONS:
            raise HomeAssistantError("Unsupported phone bridge action")
        if self.lock.locked():
            raise HomeAssistantError("Phone bridge command already pending")
        async with self.lock:
            await self.refresh()
            if not self.control_available:
                raise HomeAssistantError("Phone bridge unavailable or stale")
            command_id = str(uuid.uuid4())
            command = {"command_id": command_id, "action": action, "timestamp": time.time()}
            await self.hass.async_add_executor_job(write_command, self.directory, command)
            deadline = asyncio.get_running_loop().time() + 45
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.5)
                await self.refresh()
                if self.metadata.get("command_id") != command_id:
                    continue
                status = self.metadata.get("status")
                if status == "success" and self.control_available:
                    return
                if status == "error":
                    raise HomeAssistantError("Phone bridge could not verify requested action")
            raise HomeAssistantError("Phone bridge acknowledgement timed out")


async def async_setup(hass, config):
    directory = await hass.async_add_executor_job(private_directory, hass.config.config_dir)
    bridge = Bridge(hass, directory)
    hass.data[DOMAIN] = bridge
    await bridge.refresh()

    async def refresh_view(_now):
        await bridge.refresh()

    cancel_refresh = async_track_time_interval(hass, refresh_view, timedelta(seconds=3))
    hass.bus.async_listen_once("homeassistant_stop", lambda event: cancel_refresh())

    async def action_service(call):
        await bridge.command(call.data["action"])

    hass.services.async_register(DOMAIN, "action", action_service,
                                 schema=vol.Schema({vol.Required("action"): vol.In(ACTIONS)}))
    for platform in ("camera", "button"):
        await discovery.async_load_platform(hass, platform, DOMAIN, {}, config)
    return True
