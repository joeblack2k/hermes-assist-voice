"""Conversation entity that forwards text to the Hermes ha-voice gateway platform."""

from __future__ import annotations

import logging
from typing import Literal

import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_API_KEY, CONF_TIMEOUT, CONF_URL, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([HermesConversationEntity(entry)])


class HermesConversationEntity(conversation.ConversationEntity):
    _attr_supports_streaming = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        data = self._entry.data
        device = user_input.satellite_id or user_input.device_id or "default"
        try:
            async with async_get_clientsession(self.hass).post(
                f"{data[CONF_URL]}/voice",
                headers={"Authorization": f"Bearer {data[CONF_API_KEY]}"},
                json={
                    "text": user_input.text,
                    "device": device.split(".")[-1],
                    "context": f"Current local time: {dt_util.now():%A %d %B %Y, %H:%M} ({dt_util.DEFAULT_TIME_ZONE}).",
                },
                timeout=aiohttp.ClientTimeout(total=data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            ) as resp:
                resp.raise_for_status()
                text = (await resp.json())["text"].strip()
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
            _LOGGER.warning("Hermes request failed: %s", err)
            text = "Sorry, ik kan Hermes nu niet bereiken."

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=self.entity_id, content=text)
        )
        return conversation.async_get_result_from_chat_log(user_input, chat_log)
