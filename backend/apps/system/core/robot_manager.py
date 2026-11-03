"""群机器人（飞书 / 钉钉 / 企业微信）—— 统一走网页端同一个问答 Agent。

三个平台都采用「长连接」模式，服务端主动外连，无需公网回调地址：

* 飞书：企业自建应用 + WebSocket 长连接（lark-oapi）
* 钉钉：企业内部应用机器人 + Stream 模式（dingtalk-stream）
* 企业微信：智能机器人 API 模式 + 长连接（wecom-aibot-sdk）

用户身份通过 ``sys_user_platform``（origin 6/7/8）关联到站内账号，
群里的提问会落到提问者自己的会话里，答案与图表私聊回给提问者。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests
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

PLATFORM_FEISHU = "feishu"
PLATFORM_DINGTALK = "dingtalk"
PLATFORM_WECOM = "wecom"
SUPPORTED_PLATFORMS = (PLATFORM_FEISHU, PLATFORM_DINGTALK, PLATFORM_WECOM)

# sys_user_platform.origin：6=企业微信 7=钉钉 8=飞书（与用户管理页的来源枚举一致）
PLATFORM_USER_ORIGIN = {PLATFORM_FEISHU: 8, PLATFORM_DINGTALK: 7, PLATFORM_WECOM: 6}
# chat.origin：0=页面 1=MCP 2=小助手 3=飞书 4=钉钉 5=企业微信
PLATFORM_CHAT_ORIGIN = {PLATFORM_FEISHU: 3, PLATFORM_DINGTALK: 4, PLATFORM_WECOM: 5}
PLATFORM_TITLE = {
    PLATFORM_FEISHU: "Feishu",
    PLATFORM_DINGTALK: "DingTalk",
    PLATFORM_WECOM: "WeCom",
}

# 兼容旧引用/单测
FEISHU_USER_ORIGIN = PLATFORM_USER_ORIGIN[PLATFORM_FEISHU]
FEISHU_CHAT_ORIGIN = PLATFORM_CHAT_ORIGIN[PLATFORM_FEISHU]
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


class BaseRobotWorker:
    """平台无关的部分：并发槽、消息去重、用户映射、会话复用、Agent 调用。"""

    platform = ""
    chat_title = ""
    user_origin = 0
    chat_origin = 0
    max_answer_chars = 12000

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._running = False
        self._last_error = ""
        self._client = None
        self._thread = None
        self._loop = None
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix=f"{self.platform or 'bot'}-agent"
        )
        self._slots = threading.BoundedSemaphore(8)
        self._seen_lock = threading.Lock()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._chat_lock = threading.Lock()

    # ---------------------------------------------------------------- 身份与会话
    @classmethod
    async def _resolve_user(cls, session: Session, sender_ids: set[str]):
        if not sender_ids:
            return None
        uids = set(
            session.exec(
                select(UserPlatformModel.uid).where(
                    UserPlatformModel.origin == cls.user_origin,
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

    def _external_id(self, user, sender_key: str) -> str:
        return f"{self.app_id}:{user.oid}:{sender_key}"

    def _chat(self, session: Session, user, sender_key: str, new: bool) -> Chat:
        from apps.chat.curd.chat import create_chat

        external_id = self._external_id(user, sender_key)
        with self._chat_lock:
            chats = session.exec(
                select(Chat)
                .where(
                    Chat.origin == self.chat_origin,
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
                    question=self.chat_title,
                    origin=self.chat_origin,
                    agent_mode=True,
                ),
                require_datasource=False,
            )
            chat = session.get(Chat, created.id)
            chat.external_chat_id = external_id
            session.commit()
            return chat

    async def _answer(self, question: str, sender_key: str, sender_ids: set[str]):
        from apps.chat.task.agent import WebAgentService

        with Session(engine) as session:
            user = await self._resolve_user(session, sender_ids)
            if user is None:
                return (
                    i18n(lang="zh-CN")(
                        "i18n_robot.user_not_linked",
                        platform=PLATFORM_TITLE.get(self.platform, self.platform),
                    ),
                    None,
                )
            trans = i18n(lang=user.language)
            if question.strip().lower() == "/new":
                self._chat(session, user, sender_key, new=True)
                return trans("i18n_robot.new_chat"), None
            chat = self._chat(session, user, sender_key, new=False)
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
            return answer[: self.max_answer_chars], (
                record.chat_id,
                record.id,
                chart,
                data,
                trans,
            )

    # ---------------------------------------------------------------- 公共工具
    def _already_seen(self, message_id: str | None) -> bool:
        if not message_id:
            return False
        with self._seen_lock:
            now = time.monotonic()
            seen_at = self._seen.get(message_id)
            if seen_at is not None and now - seen_at < 600:
                return True
            self._seen[message_id] = now
            while len(self._seen) > 1024:
                self._seen.popitem(last=False)
        return False

    def _started(self) -> bool:
        return self._running

    def start(self) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def _shutdown_common(self) -> None:
        self._running = False
        self._executor.shutdown(wait=False, cancel_futures=True)


class FeishuRobotWorker(BaseRobotWorker):
    platform = PLATFORM_FEISHU
    chat_title = "Feishu"
    user_origin = PLATFORM_USER_ORIGIN[PLATFORM_FEISHU]
    chat_origin = PLATFORM_CHAT_ORIGIN[PLATFORM_FEISHU]

    def _api_client(self):
        import lark_oapi as lark

        return (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )

    def _reply(self, open_id: str, message_type: str, content: dict) -> bool:
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

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
        from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody

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

    def _on_message(self, data) -> None:
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
        if self._already_seen(getattr(msg, "message_id", None)):
            return
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
        self._running = True
        self._last_error = ""

        def run():
            # lark_oapi.ws.client 在模块导入时就绑定了全局事件循环，
            # 必须在工作线程内导入并把该循环换成线程自己的循环，
            # 否则会拿到主线程正在运行的 loop，启动直接报
            # "This event loop is already running"。
            import sys

            import lark_oapi as lark
            from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
            from lark_oapi.ws import Client as WsClient

            ws_module = sys.modules.get("lark_oapi.ws.client")
            if ws_module is not None:
                loop = asyncio.new_event_loop()
                ws_module.loop = loop
                asyncio.set_event_loop(loop)
                self._loop = loop
            try:
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
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                logger.debug("Feishu loop stop skipped", exc_info=True)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3)
            self._thread = None
        self._client = None
        self._loop = None
        self._shutdown_common()


class DingTalkRobotWorker(BaseRobotWorker):
    """钉钉企业内部应用机器人（Stream 模式，出站 WebSocket）。"""

    platform = PLATFORM_DINGTALK
    chat_title = "DingTalk"
    user_origin = PLATFORM_USER_ORIGIN[PLATFORM_DINGTALK]
    chat_origin = PLATFORM_CHAT_ORIGIN[PLATFORM_DINGTALK]
    max_answer_chars = 12000

    def _external_id(self, user, sender_key: str) -> str:
        return f"dingtalk:{self.app_id}:{user.oid}:{sender_key}"

    # ------------------------------------------------------------ 私聊发送
    def _send_private(self, msg, msg_key: str, params: dict[str, Any]) -> bool:
        user_id = getattr(msg, "sender_staff_id", None)
        client = self._client
        if not user_id or client is None:
            return False
        try:
            token = client.get_access_token()
            if not token:
                return False
            response = requests.post(
                "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend",
                headers={"x-acs-dingtalk-access-token": token},
                json={
                    "robotCode": getattr(msg, "robot_code", None) or self.app_id,
                    "userIds": [user_id],
                    "msgKey": msg_key,
                    "msgParam": json.dumps(params, ensure_ascii=False),
                },
                timeout=10,
            )
            response.raise_for_status()
            body = response.json()
        except Exception:
            logger.exception("DingTalk private message failed")
            return False
        if isinstance(body, dict) and body.get("code") not in (None, "", 0, "0"):
            logger.warning("DingTalk private message rejected: %s", body.get("message"))
            return False
        return True

    def _reply_text(self, msg, text: str) -> bool:
        return self._send_private(msg, "sampleText", {"content": text})

    def _send_chart(self, msg, record_info) -> None:
        from apps.chat.task.llm import request_picture

        chat_id, record_id, chart, data, _ = record_info
        if not chart or chart.get("type") == "table" or not data:
            return
        image_url, error = request_picture(chat_id, record_id, chart, data)
        if error:
            raise error
        if not image_url or not self._send_private(
            msg, "sampleImageMsg", {"photoURL": image_url}
        ):
            raise RuntimeError("DingTalk private chart delivery failed")

    def _process(self, question: str, sender_ids: set[str], msg) -> None:
        sender_key = (
            getattr(msg, "sender_staff_id", None)
            or getattr(msg, "sender_id", None)
            or ""
        )
        try:
            answer, record_info = asyncio.run(
                self._answer(question, sender_key, sender_ids)
            )
            if not self._reply_text(msg, answer):
                return
            if record_info and record_info[2] and record_info[2].get("type") != "table":
                try:
                    self._send_chart(msg, record_info)
                except Exception:
                    logger.exception("DingTalk chart delivery failed")
                    self._reply_text(
                        msg, _table_preview(record_info[3], record_info[4])
                    )
        except Exception:
            logger.exception("DingTalk agent request failed")
            self._reply_text(msg, i18n(lang="zh-CN")("i18n_robot.agent_error"))
        finally:
            self._slots.release()

    def _on_message(self, data: dict) -> None:
        from dingtalk_stream import ChatbotMessage

        if not isinstance(data, dict):
            return
        try:
            msg = ChatbotMessage.from_dict(data)
        except Exception:
            logger.warning("DingTalk callback payload not understood", exc_info=True)
            return
        if getattr(msg, "message_type", None) != "text" or not msg.text:
            return
        if not getattr(msg, "conversation_id", None):
            return
        if not getattr(msg, "sender_staff_id", None):
            return
        sender_id = getattr(msg, "sender_id", "") or ""
        # 机器人/系统的消息以 $ 开头，直接忽略，避免自问自答
        if isinstance(sender_id, str) and sender_id.startswith("$"):
            return
        question = (getattr(msg.text, "content", "") or "").strip()
        if not question:
            return
        if self._already_seen(getattr(msg, "message_id", None)):
            return
        sender_ids = {
            value
            for value in (
                getattr(msg, "sender_staff_id", None),
                sender_id or None,
            )
            if isinstance(value, str) and 0 < len(value) <= 255
        }
        if not self._slots.acquire(blocking=False):
            self._reply_text(msg, i18n(lang="zh-CN")("i18n_robot.busy"))
            return
        try:
            self._executor.submit(self._process, question, sender_ids, msg)
        except RuntimeError:
            self._slots.release()

    # ------------------------------------------------------------ 生命周期
    def start(self) -> None:
        if self._running:
            return
        import dingtalk_stream

        credential = dingtalk_stream.Credential(self.app_id, self.app_secret)
        client = dingtalk_stream.DingTalkStreamClient(credential)

        worker = self
        original_open = client.open_connection

        def guarded_open():
            if not worker._running:
                raise SystemExit
            worker._loop = asyncio.get_running_loop()
            return original_open()

        client.open_connection = guarded_open

        class _Handler(dingtalk_stream.ChatbotHandler):
            async def process(self, callback):
                try:
                    worker._on_message(callback.data)
                except Exception:
                    logger.exception("DingTalk message dispatch failed")
                return dingtalk_stream.AckMessage.STATUS_OK, "OK"

        client.register_callback_handler(
            dingtalk_stream.chatbot.ChatbotMessage.TOPIC, _Handler()
        )
        self._client = client
        self._running = True
        self._last_error = ""

        def run():
            try:
                client.start_forever()
            except SystemExit:
                pass
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("DingTalk Stream stopped")
            finally:
                self._running = False

        self._thread = threading.Thread(target=run, name="dingtalk-robot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        client = self._client
        websocket = getattr(client, "websocket", None) if client else None
        loop = self._loop
        if websocket is not None and loop is not None and not loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(websocket.close(), loop).result(
                    timeout=5
                )
            except Exception:
                logger.debug("DingTalk websocket close skipped", exc_info=True)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
            self._thread = None
        self._client = None
        self._loop = None
        self._shutdown_common()


class WeComRobotWorker(BaseRobotWorker):
    """企业微信智能机器人（API 模式 + 长连接）。"""

    platform = PLATFORM_WECOM
    chat_title = "WeCom"
    user_origin = PLATFORM_USER_ORIGIN[PLATFORM_WECOM]
    chat_origin = PLATFORM_CHAT_ORIGIN[PLATFORM_WECOM]
    max_answer_chars = 8000

    def _external_id(self, user, sender_key: str) -> str:
        return f"wecom:{self.app_id}:{user.oid}:{sender_key}"

    def _submit(self, coro):
        loop = getattr(self, "_loop", None)
        if loop is None or loop.is_closed():
            raise RuntimeError("WeCom event loop is not running")
        return asyncio.run_coroutine_threadsafe(coro, loop)

    async def _deliver(self, userid: str, answer: str, record_info) -> None:
        if not answer:
            return
        await self._client.send_message(
            userid, {"msgtype": "markdown", "markdown": {"content": answer}}
        )
        if record_info and record_info[2] and record_info[2].get("type") != "table":
            try:
                await self._send_chart(userid, record_info)
            except Exception:
                logger.exception("WeCom chart delivery failed")
                await self._client.send_message(
                    userid,
                    {
                        "msgtype": "markdown",
                        "markdown": {
                            "content": _table_preview(record_info[3], record_info[4])
                        },
                    },
                )

    async def _send_chart(self, userid: str, record_info) -> None:
        """Render the chart and send its media to the requester's private chat."""
        from apps.chat.task.llm import request_picture

        chat_id, record_id, chart, data, _ = record_info
        _, error = await asyncio.to_thread(
            request_picture, chat_id, record_id, chart, data
        )
        if error:
            raise error
        image_path = Path(settings.MCP_IMAGE_PATH) / f"c_{chat_id}_r_{record_id}.png"
        raw = image_path.read_bytes()
        uploaded = await self._client.upload_media(
            raw, type="image", filename=image_path.name
        )
        await self._client.send_media_message(userid, "image", uploaded["media_id"])

    def _process(self, question: str, sender_ids: set[str], frame: dict) -> None:
        userid = ((frame.get("body") or {}).get("from") or {}).get("userid") or ""
        try:
            answer, record_info = asyncio.run(
                self._answer(question, userid, sender_ids)
            )
            self._submit(self._deliver(userid, answer, record_info)).result(timeout=60)
        except Exception:
            logger.exception("WeCom agent request failed")
            try:
                self._submit(
                    self._client.send_message(
                        userid,
                        {
                            "msgtype": "markdown",
                            "markdown": {
                                "content": i18n(lang="zh-CN")("i18n_robot.agent_error")
                            },
                        },
                    )
                ).result(timeout=30)
            except Exception:
                logger.debug("WeCom error reply failed", exc_info=True)
        finally:
            self._slots.release()

    async def _on_frame(self, frame: dict) -> None:
        body = frame.get("body") or {}
        if body.get("msgtype") != "text":
            return
        userid = (body.get("from") or {}).get("userid") or ""
        if not userid:
            return
        question = ((body.get("text") or {}).get("content") or "").strip()
        if not question:
            return
        if self._already_seen(body.get("msgid")):
            return
        if not self._slots.acquire(blocking=False):
            try:
                await self._client.send_message(
                    userid,
                    {
                        "msgtype": "markdown",
                        "markdown": {"content": i18n(lang="zh-CN")("i18n_robot.busy")},
                    },
                )
            except Exception:
                logger.debug("WeCom busy reply failed", exc_info=True)
            return
        try:
            self._executor.submit(self._process, question, {userid}, frame)
        except RuntimeError:
            self._slots.release()

    # ------------------------------------------------------------ 生命周期
    def start(self) -> None:
        if self._running:
            return
        from wecom_aibot_sdk import WSClient

        self._running = True
        self._last_error = ""

        async def serve():
            client = WSClient(bot_id=self.app_id, secret=self.app_secret)
            client.on("message.text", self._on_frame)
            self._client = client
            self._loop = asyncio.get_running_loop()
            await client.connect()
            # connect() 建立连接后立即返回，随后需要保持事件循环存活
            try:
                while self._running:
                    await asyncio.sleep(0.5)
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    logger.debug("WeCom disconnect failed", exc_info=True)

        def run():
            try:
                asyncio.run(serve())
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("WeCom long connection stopped")
            finally:
                self._running = False

        self._thread = threading.Thread(target=run, name="wecom-robot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        thread = getattr(self, "_thread", None)
        if thread is not None:
            thread.join(timeout=5)
            self._thread = None
        self._client = None
        self._shutdown_common()


WORKER_CLASSES = {
    PLATFORM_FEISHU: FeishuRobotWorker,
    PLATFORM_DINGTALK: DingTalkRobotWorker,
    PLATFORM_WECOM: WeComRobotWorker,
}


class RobotManager:
    """按平台管理多个常驻 worker，允许三个平台同时在线。"""

    _instance: RobotManager | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._workers: dict[str, BaseRobotWorker] = {}
        self._meta: dict[str, dict[str, str]] = {}
        self._manager_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> RobotManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def running(self) -> bool:
        return any(worker._running for worker in self._workers.values())

    def is_running(self, platform: str) -> bool:
        worker = self._workers.get(platform)
        return bool(worker and worker._running)

    def status(self, platform: str = PLATFORM_FEISHU) -> dict:
        worker = self._workers.get(platform)
        return {
            "platform": platform,
            "running": bool(worker and worker._running),
            "last_error": worker._last_error if worker else "",
        }

    def statuses(self) -> list[dict]:
        return [self.status(platform) for platform in SUPPORTED_PLATFORMS]

    def start(self, session, platform: str = PLATFORM_FEISHU) -> dict:
        platform = (platform or PLATFORM_FEISHU).lower()
        if platform not in WORKER_CLASSES:
            return {"ok": False, "message": f"暂不支持的平台：{platform}"}
        config = get_config(session, platform)
        if config is None or not config.app_id:
            return {"ok": False, "message": "尚未配置应用标识，请先在页面填写。"}
        secret = get_app_secret(session, platform)
        if not secret:
            return {"ok": False, "message": "尚未配置应用密钥，请先在页面填写。"}
        with self._manager_lock:
            worker = self._workers.get(platform)
            if (
                worker is not None
                and worker._running
                and worker.app_id == config.app_id
            ):
                return {
                    "ok": True,
                    "message": f"{PLATFORM_TITLE[platform]} 机器人已在运行中。",
                }
            if worker is not None:
                try:
                    worker.stop()
                except Exception:
                    logger.warning(
                        "Stopping previous %s worker failed", platform, exc_info=True
                    )
                self._workers.pop(platform, None)
            worker = WORKER_CLASSES[platform](config.app_id, secret)
            self._workers[platform] = worker
            try:
                worker.start()
            except Exception as exc:
                logger.exception("Starting %s worker failed", platform)
                self._workers.pop(platform, None)
                return {"ok": False, "message": f"启动失败：{exc}"}
        return {"ok": True, "message": f"{PLATFORM_TITLE[platform]} 机器人已启动。"}

    def stop(self, platform: str | None = None) -> dict:
        with self._manager_lock:
            targets = [platform.lower()] if platform else list(self._workers.keys())
            for name in targets:
                worker = self._workers.pop(name, None)
                if worker is None:
                    continue
                try:
                    worker.stop()
                except Exception:
                    logger.warning("Stopping %s worker failed", name, exc_info=True)
        label = PLATFORM_TITLE.get((platform or "").lower(), "")
        return {
            "ok": True,
            "message": f"{label} 机器人已停止。" if label else "机器人已停止。",
        }


robot_manager = RobotManager.get_instance()
