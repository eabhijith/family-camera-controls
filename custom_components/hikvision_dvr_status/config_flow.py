"""Validate local DVR credentials without changing device configuration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from . import DOMAIN
from .api import AuthenticationError, DeviceError, DVRClient


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_reauth(self, entry_data):
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = {**self._reauth_entry.data, **user_input}
            try:
                client = DVRClient(**data)
                info = await self.hass.async_add_executor_job(client.identify)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (DeviceError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                identity = info.get("serialNumber") or client.base
                if identity != self._reauth_entry.unique_id:
                    errors["base"] = "wrong_device"
                else:
                    return self.async_update_reload_and_abort(self._reauth_entry, data_updates=user_input)
        return self.async_show_form(step_id="reauth_confirm", errors=errors, data_schema=vol.Schema({
            vol.Required("username", default=self._reauth_entry.data["username"]): str,
            vol.Required("password"): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }))

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                client = DVRClient(**user_input)
                info = await self.hass.async_add_executor_job(client.identify)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (DeviceError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                identity = info.get("serialNumber") or client.base
                await self.async_set_unique_id(identity)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.get("model") or "Hikvision DVR", data=user_input)
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required("host"): str,
            vol.Required("username"): str,
            vol.Required("password"): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required("port", default=80): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required("use_https", default=False): bool,
        }))
