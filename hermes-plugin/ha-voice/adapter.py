"""Home Assistant Voice adapter: HTTP POST /voice -> gateway turn -> spoken replies.

POST /voice returns the first reply: {"text", "final", "turn"}. If the turn is still running (final=false),
the caller polls GET /voice/next?turn=<id> for further replies until one has final=true. Interim replies are
Hermes' own mid-turn commentary (display.platforms.ha_voice.interim_assistant_messages) or the optional
ack_text sent when nothing has been said after ack_after seconds.

config.yaml platforms.ha_voice.extra keys: host (127.0.0.1), port (8651), ack_text (""), ack_after (6).
Env: HA_VOICE_KEY (required), HA_VOICE_PORT, HA_VOICE_ALLOW_ALL_USERS.
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
        self._ack_text: str = str(extra.get("ack_text") or "").strip()
        self._ack_after: float = float(extra.get("ack_after") or 6)
        self._pending: Dict[str, list] = {}
        self._queues: Dict[str, "asyncio.Queue"] = {}

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not self._key:
            logger.error("[ha_voice] HA_VOICE_KEY not set")
            return False
        app = web.Application()
        app.router.add_post("/voice", self._handle_voice)
        app.router.add_get("/voice/next", self._handle_next)
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
        self._pending.clear()
        self._queues.clear()
        self._mark_disconnected()

    async def _handle_health(self, request: "web.Request") -> "web.Response":
        return web.json_response({"status": "ok"})

    def _authorized(self, request: "web.Request") -> bool:
        return secrets.compare_digest(request.headers.get("Authorization", ""), f"Bearer {self._key}")

    async def _next_reply(self, turn: str, wait: float, on_timeout=None) -> "web.Response":
        queue = self._queues.get(turn)
        if queue is None:
            return web.json_response({"text": "", "final": True, "turn": turn})
        try:
            text, final = await asyncio.wait_for(queue.get(), wait)
        except asyncio.TimeoutError:
            return on_timeout() if on_timeout else web.json_response({"text": "", "final": False, "turn": turn})
        if final:
            self._queues.pop(turn, None)
        return web.json_response({"text": text, "final": final, "turn": turn})

    async def _handle_next(self, request: "web.Request") -> "web.Response":
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            wait = min(float(request.query.get("wait", 20)), 30.0)
        except ValueError:
            wait = 20.0
        return await self._next_reply(request.query.get("turn", ""), wait)

    async def _handle_voice(self, request: "web.Request") -> "web.Response":
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        text = str(body.get("text") or "").strip()
        device = str(body.get("device") or "default").strip() or "default"
        if not text:
            return web.json_response({"error": "text required"}, status=400)
        turn = uuid.uuid4().hex[:12]
        self._queues[turn] = asyncio.Queue()
        self._pending.setdefault(device, []).append(turn)
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
        if self._ack_text:
            return await self._next_reply(
                turn, self._ack_after,
                lambda: web.json_response({"text": self._ack_text, "final": False, "turn": turn}))
        return await self._next_reply(
            turn, REPLY_TIMEOUT, lambda: web.json_response({"error": "timeout"}, status=504))

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
        pending = self._pending.get(chat_id)
        if pending and content.strip():
            final = bool((metadata or {}).get("notify"))
            queue = self._queues.get(pending[0])
            if queue is not None:
                queue.put_nowait((content, final))
            if final:
                pending.pop(0)
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
