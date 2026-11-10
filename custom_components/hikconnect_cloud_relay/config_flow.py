"""Private HA account sign-in and one actual API channel per config entry."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .cloud import HikConnectClient, HikConnectAuthError, HikConnectChallengeError
from .const import DOMAIN

USER_SCHEMA = vol.Schema({
    vol.Required("username"): str,
    vol.Required("password"): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
})


def _discover(credentials, serial=None):
    client = HikConnectClient(credentials["username"], credentials["password"])
    try:
        client.login()
        return client.get_channels(serial) if serial else client.get_devices()
    finally:
        client.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._credentials = {}
        self._devices = {}
        self._channels = {}
        self._device = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                devices = await self.hass.async_add_executor_job(_discover, user_input)
                if devices:
                    self._credentials = {key: user_input[key] for key in ("username", "password")}
                    self._devices = {device.serial: device for device in devices}
                    return await self.async_step_device()
                errors["base"] = "no_devices"
            except HikConnectChallengeError:
                errors["base"] = "challenge_required"
            except HikConnectAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_device(self, user_input=None):
        schema = vol.Schema({vol.Required("device_serial"): vol.In({
            serial: f"{item.name} ({item.model})" for serial, item in self._devices.items()
        })})
        errors = {}
        if user_input is not None:
            self._device = self._devices[user_input["device_serial"]]
            try:
                channels = await self.hass.async_add_executor_job(
                    _discover, self._credentials, self._device.serial)
                # Do not apply intercom-only linked/signal heuristics to DVR rows.
                self._channels = {row.channel: row for row in channels}
                if channels:
                    return await self.async_step_channel()
                errors["base"] = "no_channels"
            except HikConnectChallengeError:
                errors["base"] = "challenge_required"
            except HikConnectAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="device", data_schema=schema, errors=errors)

    async def async_step_channel(self, user_input=None):
        schema = vol.Schema({vol.Required("channel"): vol.In({
            number: f"{number}: {item.name}" for number, item in self._channels.items()
        }), vol.Required("allow_unencrypted_transport", default=False): bool})
        errors = {}
        if user_input is not None:
            if user_input.get("allow_unencrypted_transport") is not True:
                return self.async_show_form(step_id="channel", data_schema=schema,
                    errors={"base": "transport_consent_required"})
            row = self._channels[int(user_input["channel"])]
            await self.async_set_unique_id(f"{row.serial}:{row.channel}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=row.name, data={
                **self._credentials, "device_serial": row.serial, "channel": row.channel,
                "channel_name": row.name, "device_name": self._device.name,
                "device_model": self._device.model,
                "allow_unencrypted_transport": True,
            })
        return self.async_show_form(step_id="channel", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                entry = self._get_reauth_entry()
                # Verify account access to this channel before replacing credentials.
                rows = await self.hass.async_add_executor_job(
                    _discover, user_input, entry.data["device_serial"])
                if not any(row.channel == entry.data["channel"] for row in rows):
                    errors["base"] = "no_channels"
                else:
                    return self.async_update_reload_and_abort(entry, data_updates=user_input)
            except HikConnectChallengeError:
                errors["base"] = "challenge_required"
            except HikConnectAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="reauth_confirm", data_schema=USER_SCHEMA,
                                    errors=errors)
