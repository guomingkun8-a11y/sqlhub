"""Feishu WebSocket bot backed by the ordinary web chat agent."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateImageRequest,
    CreateImageRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as WsClient
from sqlmodel import Session, select

from apps.chat.models.chat_model import Chat, ChatQuestion, CreateChat
from apps.system.crud.robot_manage import get_app_secret, get_config
from apps.system.crud.user import get_user_info
from apps.system.models.user import UserPlatformModel
from common.core.config import settings
from common.core.db import engine
from common.utils.locale import I18n

logger = logging.getLogger(__name__)
i18n = I18n()
FEISHU_USER_ORIGIN = 8
FEISHU_CHAT_ORIGIN = 3
MAX_PREVIEW_ROWS = 10


def _table_preview(data: dict, trans) -> str:
    fields = [field for field in data.get("fields", []) if isinstance(field, str)][:8]
    rows = data.get("data") or []
    if not rows:
        return trans("i18n_robot.no_result")
    lines = []
    for index, row in enumerate(rows[:MAX_PREVIEW_ROWS], 1):
        if not isinstance(row, dict):
            continue
        cells = [
            f"{field}: {str(row.get(field, ''))[:100].replace(chr(10), ' ')}"
            for field in fields
        ]
        lines.append(f"{index}. " + "；".join(cells))
    if len(rows) > MAX_PREVIEW_ROWS:
        lines.append(trans("i18n_robot.more_rows", count=MAX_PREVIEW_ROWS))
    return "\n".join(lines)


class FeishuRobotWorker:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._client: WsClient | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_error = ""
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="feishu-agent"
        )
        self._slots = threading.BoundedSemaphore(8)
        self._seen_lock = threading.Lock()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._chat_lock = threading.Lock()

    @staticmethod
    async def _resolve_user(session: Session, sender_ids: set[str]):
        if not sender_ids:
            return None
        uids = set(
            session.exec(
                select(UserPlatformModel.uid).where(
                    UserPlatformModel.origin == FEISHU_USER_ORIGIN,
                    UserPlatformModel.platform_uid.in_(sender_ids),
                )
            ).all()
        )
        if len(uids) != 1:
            return None
        user = await get_user_info(session=session, user_id=uids.pop())
        if (
            not user
            or user.status != 1
            or not user.oid
            or (not user.isAdmin and user.weight < 0)
        ):
            return None
        return user.model_copy(deep=True)

    def _chat(self, session: Session, user, open_id: str, new: bool) -> Chat:
        from apps.chat.curd.chat import create_chat

        external_id = f"{self.app_id}:{user.oid}:{open_id}"
        with self._chat_lock:
            chats = session.exec(
                select(Chat)
                .where(
                    Chat.origin == FEISHU_CHAT_ORIGIN,
                    Chat.external_chat_id == external_id,
                    Chat.create_by == user.id,
                    Chat.oid == user.oid,
                )
                .order_by(Chat.id.desc())
            ).all()
            if chats and not new:
                return chats[0]
            for previous in chats:
                previous.external_chat_id = None
                session.add(previous)
            session.flush()
            created = create_chat(
                session,
                user,
                CreateChat(
                    question="Feishu", origin=FEISHU_CHAT_ORIGIN, agent_mode=True
                ),
                require_datasource=False,
            )
            chat = session.get(Chat, created.id)
            chat.external_chat_id = external_id
            session.commit()
            return chat

    async def _answer(self, question: str, open_id: str, sender_ids: set[str]):
        from apps.chat.task.agent import WebAgentService

        with Session(engine) as session:
            user = await self._resolve_user(session, sender_ids)
            if user is None:
                return i18n(lang="zh-CN")("i18n_robot.user_not_linked"), None
            trans = i18n(lang=user.language)
            if question.strip().lower() == "/new":
                self._chat(session, user, open_id, new=True)
                return trans("i18n_robot.new_chat"), None
            chat = self._chat(session, user, open_id, new=False)
            if chat.create_by != user.id or chat.oid != user.oid:
                return trans("i18n_robot.user_disabled"), None
            service = await WebAgentService.create(
                session,
                user,
                ChatQuestion(chat_id=chat.id, question=question),
                None,
                time_zone="Asia/Shanghai",
            )
            record = service.init_record(session)
            for _ in service.run_agent():
                pass
            session.refresh(record)
            if record.error or not record.answer:
                return trans("i18n_robot.agent_error"), None
            data = json.loads(record.data) if record.data else None
            chart = json.loads(record.chart) if record.chart else None
            answer = record.answer.strip()
            if data and (not chart or chart.get("type") == "table"):
                answer += "\n\n" + _table_preview(data, trans)
            return answer[:12000], (record.chat_id, record.id, chart, data, trans)

    def _api_client(self):
        return (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )

    def _reply(self, open_id: str, message_type: str, content: dict) -> bool:
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("open_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(open_id)
                .msg_type(message_type)
                .content(json.dumps(content, ensure_ascii=False))
                .build()
            )
            .build()
        )
        response = self._api_client().im.v1.message.create(request)
        if not response.success():
            logger.warning("Feishu reply failed: code=%s", response.code)
            return False
        return True

    def _send_chart(self, open_id: str, record_info) -> None:
        from apps.chat.task.llm import request_picture

        chat_id, record_id, chart, data, _ = record_info
        if not chart or chart.get("type") == "table" or not data:
            return
        _, error = request_picture(chat_id, record_id, chart, data)
        if error:
            raise error
        image_path = Path(settings.MCP_IMAGE_PATH) / f"c_{chat_id}_r_{record_id}.png"
        with image_path.open("rb") as image:
            request = (
                CreateImageRequest.builder()
                .request_body(
                    CreateImageRequestBody.builder()
                    .image_type("message")
                    .image(image)
                    .build()
                )
                .build()
            )
            response = self._api_client().im.v1.image.create(request)
        if not response.success() or not response.data or not response.data.image_key:
            raise RuntimeError("Feishu image upload failed")
        if not self._reply(open_id, "image", {"image_key": response.data.image_key}):
            raise RuntimeError("Feishu image reply failed")

    def _process(self, question: str, sender_ids: set[str], open_id: str) -> None:
        try:
            answer, record_info = asyncio.run(
                self._answer(question, open_id, sender_ids)
            )
            if not self._reply(open_id, "text", {"text": answer}):
                return
            if record_info and record_info[2] and record_info[2].get("type") != "table":
                try:
                    self._send_chart(open_id, record_info)
                except Exception:
                    logger.exception("Feishu chart delivery failed")
                    preview = _table_preview(record_info[3], record_info[4])
                    self._reply(open_id, "text", {"text": preview})
        except Exception:
            logger.exception("Feishu agent request failed")
            self._reply(
                open_id, "text", {"text": i18n(lang="zh-CN")("i18n_robot.agent_error")}
            )
        finally:
            self._slots.release()

    def _on_message(self, data: P2ImMessageReceiveV1) -> None:
        event = getattr(data, "event", None)
        msg = getattr(event, "message", None)
        sender = getattr(getattr(event, "sender", None), "sender_id", None)
        open_id = getattr(sender, "open_id", None)
        if not msg or msg.message_type != "text" or not open_id or not msg.chat_id:
            return
        if getattr(event.sender, "sender_type", "user") != "user":
            return
        try:
            question = json.loads(msg.content).get("text", "")
        except (TypeError, ValueError):
            return
        if not isinstance(question, str):
            return
        for mention in msg.mentions or []:
            key = getattr(mention, "key", None)
            if key:
                question = question.replace(f"@{key}", "")
        question = question.strip()
        if not question:
            return
        message_id = getattr(msg, "message_id", None)
        if message_id:
            with self._seen_lock:
                now = time.monotonic()
                if message_id in self._seen and now - self._seen[message_id] < 600:
                    return
                self._seen[message_id] = now
                while len(self._seen) > 1024:
                    self._seen.popitem(last=False)
        sender_ids = {
            value
            for value in (
                getattr(sender, "user_id", None),
                open_id,
                getattr(sender, "union_id", None),
            )
            if isinstance(value, str) and 0 < len(value) <= 255
        }
        if not self._slots.acquire(blocking=False):
            self._reply(
                open_id, "text", {"text": i18n(lang="zh-CN")("i18n_robot.busy")}
            )
            return
        try:
            self._executor.submit(self._process, question, sender_ids, open_id)
        except RuntimeError:
            self._slots.release()

    def start(self) -> None:
        if self._running:
            return
        handler: EventDispatcherHandler = (
            EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._on_message)
            .build()
        )
        client = WsClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.INFO,
        )
        self._client = client
        self._running = True
        self._last_error = ""

        def run():
            try:
                client.start()
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("Feishu WebSocket stopped")
            finally:
                self._running = False

        self._thread = threading.Thread(target=run, name="feishu-robot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._client is not None:
            self._client.stop()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._client = None


class RobotManager:
    _instance: RobotManager | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._worker: FeishuRobotWorker | None = None
        self._platform = "feishu"

    @classmethod
    def get_instance(cls) -> RobotManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker._running

    def status(self) -> dict:
        return {
            "platform": self._platform,
            "running": self.running,
            "last_error": self._worker._last_error if self._worker else "",
        }

    def start(self, session, platform: str = "feishu") -> dict:
        config = get_config(session, platform)
        if config is None or not config.app_id:
            return {"ok": False, "message": "尚未配置 App ID，请先在页面填写。"}
        secret = get_app_secret(session, platform)
        if not secret:
            return {"ok": False, "message": "尚未配置 App Secret，请先在页面填写。"}
        if self.running and self._worker.app_id == config.app_id:
            return {"ok": True, "message": "机器人已在运行中。"}
        self.stop()
        self._platform = platform
        self._worker = FeishuRobotWorker(config.app_id, secret)
        self._worker.start()
        return {"ok": True, "message": "机器人已启动。"}

    def stop(self) -> dict:
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
        return {"ok": True, "message": "机器人已停止。"}


robot_manager = RobotManager.get_instance()
