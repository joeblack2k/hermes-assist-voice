"""Home Assistant Voice adapter: HTTP POST /voice -> gateway turn -> final answer in the response.

config.yaml platforms.ha_voice.extra keys: host (127.0.0.1), port (8651). Env: HA_VOICE_KEY (required),
HA_VOICE_PORT, HA_VOICE_ALLOW_ALL_USERS.
"""

import asyncio
import logging
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None  # type: ignore[assignment]

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.platforms.event import MessageEvent, MessageType
from gateway.platforms._shared import env_is_connected, get_scoped_secret

logger = logging.getLogger(__name__)

REPLY_TIMEOUT = 90.0
BOT_CHAT_TITLE = "Bot Chat"


def check_requirements() -> bool:
    return AIOHTTP_AVAILABLE


def validate_config(config: PlatformConfig) -> bool:
    return bool(get_scoped_secret("HA_VOICE_KEY", "").strip())


class HAVoiceAdapter(BasePlatformAdapter):
    MAX_MESSAGE_LENGTH = 2000

    def __init__(self, config: PlatformConfig):
        super().__init__(config=config, platform=Platform("ha_voice"))
        extra = config.extra or {}
        self._host: str = extra.get("host") or "127.0.0.1"
        self._port: int = int(extra.get("port") or get_scoped_secret("HA_VOICE_PORT", "8651"))
        self._key: str = get_scoped_secret("HA_VOICE_KEY", "")
        self._runner = None
        self._waiters: Dict[str, "asyncio.Future"] = {}

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not self._key:
            logger.error("[ha_voice] HA_VOICE_KEY not set")
            return False
        app = web.Application()
        app.router.add_post("/voice", self._handle_voice)
        app.router.add_get("/health", self._handle_health)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        try:
            await web.TCPSite(self._runner, self._host, self._port).start()
        except OSError as exc:
            logger.error("[ha_voice] cannot bind %s:%d: %s", self._host, self._port, exc)
            await self._runner.cleanup()
            self._runner = None
            return False
        self._mark_connected()
        self._wire_plugin_handlers(None)
        logger.info("[ha_voice] listening on %s:%d", self._host, self._port)
        return True

    async def disconnect(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        for fut in self._waiters.values():
            if not fut.done():
                fut.cancel()
        self._waiters.clear()
        self._mark_disconnected()

    async def _handle_health(self, request: "web.Request") -> "web.Response":
        return web.json_response({"status": "ok"})

    async def _handle_voice(self, request: "web.Request") -> "web.Response":
        auth = request.headers.get("Authorization", "")
        if not secrets.compare_digest(auth, f"Bearer {self._key}"):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        text = str(body.get("text") or "").strip()
        device = str(body.get("device") or "default").strip() or "default"
        if not text:
            return web.json_response({"error": "text required"}, status=400)
        if device in self._waiters and not self._waiters[device].done():
            self._waiters[device].cancel()
        fut = asyncio.get_running_loop().create_future()
        self._waiters[device] = fut
        source = self.build_source(
            chat_id=device, chat_name=f"Voice {device}", chat_type="dm",
            user_id="voice", user_name="Voice")
        try:
            await asyncio.to_thread(self._pin_bot_chat, source)
        except Exception:
            logger.exception("ha_voice: could not pin Bot Chat session")
        await self.handle_message(MessageEvent(
            text=text, message_type=MessageType.TEXT, source=source,
            message_id=uuid.uuid4().hex[:12], timestamp=datetime.now(),
            channel_prompt=str(body.get("context") or "").strip() or None))
        try:
            reply = await asyncio.wait_for(asyncio.shield(fut), REPLY_TIMEOUT)
        except asyncio.TimeoutError:
            return web.json_response({"error": "timeout"}, status=504)
        except asyncio.CancelledError:
            return web.json_response({"error": "superseded"}, status=409)
        finally:
            if self._waiters.get(device) is fut:
                del self._waiters[device]
        return web.json_response({"text": reply})

    def _pin_bot_chat(self, source) -> None:
        """Route this voice chat into the profile's canonical hidden "Bot Chat" session, so the
        conversation shows up in the app's bot view and continues on other devices."""
        store = getattr(self, "_session_store", None)
        if store is None:
            return
        key = store._generate_session_key(source)
        entry = store.get_or_create_session(source, touch_activity=False)
        db = store._db_for_key(key)
        row = db.get_session_by_title(BOT_CHAT_TITLE)
        if row:
            bot_id = row["id"]
        else:
            bot_id = "bot_chat_" + uuid.uuid4().hex[:12]
            db.create_session(bot_id, "bot_peer_dm")
            db.set_session_title(bot_id, BOT_CHAT_TITLE)
            db.set_session_hidden(bot_id, True)
        tip = store._compression_tip_for_session_id(bot_id) or bot_id
        if entry.session_id not in (bot_id, tip):
            store.switch_session(key, tip)

    async def send(
        self, chat_id: str, content: str, reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        fut = self._waiters.get(chat_id)
        if fut is not None and not fut.done() and (metadata or {}).get("notify"):
            fut.set_result(content)
        return SendResult(success=True, message_id=uuid.uuid4().hex[:12])

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"name": f"Voice {chat_id}", "type": "dm"}


def register(ctx) -> None:
    ctx.register_platform(
        name="ha_voice", label="Home Assistant Voice", adapter_factory=HAVoiceAdapter,
        check_fn=check_requirements, validate_config=validate_config,
        is_connected=env_is_connected("HA_VOICE_KEY"), required_env=["HA_VOICE_KEY"],
        allow_all_env="HA_VOICE_ALLOW_ALL_USERS", max_message_length=HAVoiceAdapter.MAX_MESSAGE_LENGTH,
        emoji="🎙️", allow_update_command=False,
        platform_hint=(
            "Your reply is spoken aloud by a voice assistant: keep it short and conversational, in the "
            "user's language, with no markdown, lists, emoji or debug details."),
    )
