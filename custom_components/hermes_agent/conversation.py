"""Conversation entity that forwards text to the Hermes ha-voice gateway platform."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_API_KEY, CONF_TIMEOUT, CONF_URL, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

FOLLOW_UP_TIMEOUT = 600
POLL_WAIT = 20


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

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._entry.data[CONF_API_KEY]}"}

    async def _poll(self, turn: str) -> dict[str, Any]:
        async with async_get_clientsession(self.hass).get(
            f"{self._entry.data[CONF_URL]}/voice/next",
            headers=self._headers,
            params={"turn": turn, "wait": POLL_WAIT},
            timeout=aiohttp.ClientTimeout(total=POLL_WAIT + 15),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _announce(self, satellite: str, message: str) -> None:
        for _ in range(60):
            state = self.hass.states.get(satellite)
            if state is None or state.state == "idle":
                break
            await asyncio.sleep(0.5)
        try:
            await self.hass.services.async_call(
                "assist_satellite",
                "announce",
                {"entity_id": satellite, "message": message, "preannounce": False},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Hermes announcement on %s failed: %s", satellite, err)

    async def _follow_up(self, turn: str, satellite: str | None) -> str:
        """Speak later replies on the satellite; without one, return the final reply."""
        deadline = time.monotonic() + FOLLOW_UP_TIMEOUT
        while time.monotonic() < deadline:
            try:
                reply = await self._poll(turn)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                _LOGGER.warning("Hermes follow-up failed: %s", err)
                break
            text = (reply.get("text") or "").strip()
            if reply.get("final"):
                if satellite and text:
                    await self._announce(satellite, text)
                return text
            if satellite and text:
                await self._announce(satellite, text)
        return ""

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        data = self._entry.data
        satellite = user_input.satellite_id
        device = (satellite or user_input.device_id or "default").split(".")[-1]
        try:
            async with async_get_clientsession(self.hass).post(
                f"{data[CONF_URL]}/voice",
                headers=self._headers,
                json={
                    "text": user_input.text,
                    "device": device,
                    "context": f"Current local time: {dt_util.now():%A %d %B %Y, %H:%M} ({dt_util.DEFAULT_TIME_ZONE}).",
                },
                timeout=aiohttp.ClientTimeout(total=data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            ) as resp:
                resp.raise_for_status()
                reply = await resp.json()
            text = reply["text"].strip()
            if not reply.get("final", True):
                if satellite:
                    self.hass.async_create_background_task(
                        self._follow_up(reply["turn"], satellite), "hermes_agent_follow_up"
                    )
                else:
                    text = await self._follow_up(reply["turn"], None) or text
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
            _LOGGER.warning("Hermes request failed: %s", err)
            text = "Sorry, ik kan Hermes nu niet bereiken."

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=self.entity_id, content=text)
        )
        return conversation.async_get_result_from_chat_log(user_input, chat_log)
