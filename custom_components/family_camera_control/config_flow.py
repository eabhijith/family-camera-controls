"""Configure an existing ONVIF camera, without duplicating its credentials."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector, entity_registry as er
from . import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            registry = er.async_get(self.hass)
            entity = registry.async_get(user_input["camera_entity"])
            if entity is None or entity.platform != "onvif":
                errors["base"] = "not_onvif"
            else:
                await self.async_set_unique_id(entity.id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input["room"], data=user_input)
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required("camera_entity"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="camera", integration="onvif")),
            vol.Required("room"): str,
        }))
