"""Config flow for Hermes Agent."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
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


class HermesAgentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
