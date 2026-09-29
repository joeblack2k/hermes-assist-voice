"""Config flow for Hermes Agent."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_SPEAKER,
    CONF_TIMEOUT,
    CONF_URL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,
    }
)


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SPEAKER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player")
        )
    }
)


class HermesOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )


class HermesAgentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> HermesOptionsFlow:
        return HermesOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = user_input[CONF_URL].rstrip("/")
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            try:
                async with async_get_clientsession(self.hass).get(
                    f"{user_input[CONF_URL]}/health",
                    headers={"Authorization": f"Bearer {user_input[CONF_API_KEY]}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status in (401, 403):
                        errors["base"] = "invalid_auth"
                    elif resp.status >= 400:
                        errors["base"] = "cannot_connect"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(title="Hermes Agent", data=user_input)
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)
