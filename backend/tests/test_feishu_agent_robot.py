import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlbot_xpack  # noqa: F401 - initialize the installed wheel before imports
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.compiler import compiles
from sqlmodel import Session, SQLModel

from apps.chat.api import chat as chat_api
from apps.chat.curd import chat as chat_curd
from apps.chat.models.chat_model import Chat, WebChatQuestion
from apps.chat.task import agent
from apps.chat.task import llm as chat_llm
from apps.system.core import robot_manager as robot
from apps.system.models.user import UserPlatformModel


@compiles(postgresql.JSONB, "sqlite")
def _sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


class _User:
    def __init__(self, *, id=2, oid=8, status=1, weight=0, is_admin=False):
        self.id = id
        self.oid = oid
        self.status = status
        self.weight = weight
        self.isAdmin = is_admin
        self.language = "zh-CN"

    def model_copy(self, *, deep=False):
        return _User(
            id=self.id,
            oid=self.oid,
            status=self.status,
            weight=self.weight,
            is_admin=self.isAdmin,
        )


@pytest.mark.parametrize(
    ("mapped_uids", "user", "allowed"),
    [
        ([2], _User(), True),
        ([2, 3], _User(), False),
        ([2], _User(status=0), False),
        ([2], _User(oid=0), False),
        ([2], _User(weight=-1), False),
        ([2], None, False),
    ],
)
def test_resolve_user_requires_unique_active_workspace_mapping(
    monkeypatch, mapped_uids, user, allowed
):
    session = Mock()
    session.exec.return_value.all.return_value = mapped_uids
    lookup = AsyncMock(return_value=user)
    monkeypatch.setattr(robot, "get_user_info", lookup)

    result = asyncio.run(
        robot.FeishuRobotWorker._resolve_user(session, {"open", "union"})
    )

    if allowed:
        assert result.id == 2
        assert result.oid == 8
        assert result is not user
    else:
        assert result is None
    if len(set(mapped_uids)) == 1:
        lookup.assert_awaited_once()
    else:
        lookup.assert_not_awaited()

    params = session.exec.call_args.args[0].compile(dialect=postgresql.dialect()).params
    assert params["origin_1"] == robot.FEISHU_USER_ORIGIN


def test_resolve_user_ignores_unknown_sender_without_user_lookup(monkeypatch):
    session = Mock()
    monkeypatch.setattr(robot, "get_user_info", Mock())

    result = asyncio.run(robot.FeishuRobotWorker._resolve_user(session, set()))

    assert result is None
    session.exec.assert_not_called()
    robot.get_user_info.assert_not_called()


def test_resolve_user_uses_platform_origin_and_rejects_conflicting_ids(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine, tables=[UserPlatformModel.__table__])
    lookup = AsyncMock(side_effect=lambda **kwargs: _User(id=kwargs["user_id"]))
    monkeypatch.setattr(robot, "get_user_info", lookup)
    with Session(engine) as session:
        session.add_all(
            [
                UserPlatformModel(
                    id=1, uid=2, origin=robot.FEISHU_USER_ORIGIN, platform_uid="ou_1"
                ),
                UserPlatformModel(
                    id=2,
                    uid=3,
                    origin=robot.FEISHU_USER_ORIGIN + 1,
                    platform_uid="ou_1",
                ),
                UserPlatformModel(
                    id=3,
                    uid=4,
                    origin=robot.FEISHU_USER_ORIGIN,
                    platform_uid="on_other",
                ),
            ]
        )
        session.commit()

        user = asyncio.run(robot.FeishuRobotWorker._resolve_user(session, {"ou_1"}))
        conflict = asyncio.run(
            robot.FeishuRobotWorker._resolve_user(session, {"ou_1", "on_other"})
        )

    assert user.id == 2
    assert conflict is None
    lookup.assert_awaited_once()


def test_message_routes_group_question_to_sender_open_id_without_group_broadcast():
    worker = robot.FeishuRobotWorker("app", "secret")
    worker._executor.submit = Mock()
    data = SimpleNamespace(
        event=SimpleNamespace(
            sender=SimpleNamespace(
                sender_type="user",
                sender_id=SimpleNamespace(
                    open_id="ou_sender",
                    user_id="u_sender",
                    union_id="on_sender",
                ),
            ),
            message=SimpleNamespace(
                message_type="text",
                message_id="om_1",
                chat_id="oc_group",
                content=json.dumps({"text": "分析任务"}),
                mentions=[],
            ),
        )
    )

    worker._on_message(data)

    assert worker._executor.submit.call_args.args == (
        worker._process,
        "分析任务",
        {"ou_sender", "u_sender", "on_sender"},
        "ou_sender",
    )
    worker._slots.release()


def test_message_ignores_bot_sender_and_missing_open_id():
    worker = robot.FeishuRobotWorker("app", "secret")
    worker._executor.submit = Mock()
    base = {
        "message_type": "text",
        "message_id": "om_2",
        "chat_id": "oc_group",
        "content": json.dumps({"text": "查数据"}),
        "mentions": [],
    }

    for sender in (
        SimpleNamespace(sender_type="app", sender_id=SimpleNamespace(open_id="ou_bot")),
        SimpleNamespace(sender_type="user", sender_id=SimpleNamespace(open_id=None)),
    ):
        worker._on_message(
            SimpleNamespace(
                event=SimpleNamespace(sender=sender, message=SimpleNamespace(**base))
            )
        )

    worker._executor.submit.assert_not_called()


def test_feishu_chat_lookup_is_scoped_by_sender_owner_workspace_and_persists():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine, tables=[Chat.__table__])
    worker = robot.FeishuRobotWorker("app", "secret")
    alice = _User(id=2, oid=8)
    bob = _User(id=3, oid=8)
    other_ws = _User(id=2, oid=9)
    with Session(engine) as session:
        session.add_all(
            [
                Chat(
                    id=10,
                    oid=8,
                    create_by=2,
                    create_time=datetime.now(),
                    brief="old chat",
                    engine_type="",
                    origin=robot.FEISHU_CHAT_ORIGIN,
                    external_chat_id="app:8:ou_sender",
                ),
                Chat(
                    id=11,
                    oid=8,
                    create_by=3,
                    create_time=datetime.now(),
                    brief="bob chat",
                    engine_type="",
                    origin=robot.FEISHU_CHAT_ORIGIN,
                    external_chat_id="app:8:ou_sender",
                ),
                Chat(
                    id=12,
                    oid=9,
                    create_by=2,
                    create_time=datetime.now(),
                    brief="other workspace",
                    engine_type="",
                    origin=robot.FEISHU_CHAT_ORIGIN,
                    external_chat_id="app:9:ou_sender",
                ),
            ]
        )
        session.commit()

        alice_chat = worker._chat(session, alice, "ou_sender", new=False)
        bob_chat = worker._chat(session, bob, "ou_sender", new=False)
        workspace_chat = worker._chat(session, other_ws, "ou_sender", new=False)

    with Session(engine) as session:
        bob_again = worker._chat(session, bob, "ou_sender", new=False)

        assert alice_chat.id == 10
        assert alice_chat.create_by == alice.id and alice_chat.oid == alice.oid
        assert bob_chat.id == 11
        assert bob_chat.create_by == bob.id and bob_chat.oid == bob.oid
        assert workspace_chat.id == 12
        assert bob_again.id == bob_chat.id


def test_new_chat_rolls_over_persisted_sender_link(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine, tables=[Chat.__table__])
    worker = robot.FeishuRobotWorker("app", "secret")
    user = _User(id=2, oid=8)

    def create_chat(session, user, options, require_datasource):
        assert options.origin == robot.FEISHU_CHAT_ORIGIN
        assert require_datasource is False
        session.add(
            Chat(
                id=20,
                oid=user.oid,
                create_by=user.id,
                create_time=datetime.now(),
                brief="new chat",
                engine_type="",
                origin=options.origin,
            )
        )
        session.flush()
        return SimpleNamespace(id=20)

    monkeypatch.setattr(chat_curd, "create_chat", create_chat)
    with Session(engine) as session:
        session.add(
            Chat(
                id=10,
                oid=user.oid,
                create_by=user.id,
                create_time=datetime.now(),
                brief="old chat",
                engine_type="",
                origin=robot.FEISHU_CHAT_ORIGIN,
                external_chat_id="app:8:ou_sender",
            )
        )
        session.commit()
        new_chat = worker._chat(session, user, "ou_sender", new=True)
        new_chat_id = new_chat.id

    with Session(engine) as session:
        old_chat = session.get(Chat, 10)
        active = worker._chat(session, user, "ou_sender", new=False)

        assert old_chat.external_chat_id is None
        assert new_chat_id == active.id == 20
        assert active.external_chat_id == "app:8:ou_sender"


@pytest.mark.parametrize(
    ("owner", "origin", "allowed"),
    [
        (2, robot.FEISHU_CHAT_ORIGIN, True),
        (9, robot.FEISHU_CHAT_ORIGIN, False),
        (2, 2, False),
    ],
)
def test_web_agent_allows_own_feishu_chat_only(monkeypatch, owner, origin, allowed):
    session = Mock()
    session.get.return_value = SimpleNamespace(create_by=owner, origin=origin)
    user = SimpleNamespace(id=2)
    question = WebChatQuestion(question="继续分析", chat_id=13, agent_mode=True)
    stream = AsyncMock(return_value="streamed")
    monkeypatch.setattr(chat_api, "stream_agent", stream)

    if allowed:
        result = asyncio.run(
            chat_api.question_answer.__wrapped__(session, user, question, None)
        )
        assert result == "streamed"
        stream.assert_awaited_once()
    else:
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                chat_api.question_answer.__wrapped__(session, user, question, None)
            )
        assert error.value.status_code == 403
        stream.assert_not_awaited()


def test_table_preview_is_bounded_and_includes_result_rows():
    def trans(key, **kwargs):
        return f"{key}:{kwargs.get('count', '')}"

    data = {
        "fields": [f"c{i}" for i in range(9)],
        "data": [{f"c{i}": i for i in range(9)} for _ in range(12)],
    }

    preview = robot._table_preview(data, trans)

    assert "1. c0: 0；c1: 1；c2: 2；c3: 3；c4: 4；c5: 5；c6: 6；c7: 7" in preview
    assert "11." not in preview
    assert "i18n_robot.more_rows:10" in preview


def test_chart_delivery_failure_falls_back_to_table_preview(monkeypatch):
    worker = robot.FeishuRobotWorker("app", "secret")

    def trans(key, **_kwargs):
        return key

    record_info = (
        4,
        7,
        {"type": "bar"},
        {"fields": ["status"], "data": [{"status": "open"}]},
        trans,
    )
    monkeypatch.setattr(
        worker, "_answer", AsyncMock(return_value=("Analysis", record_info))
    )
    worker._reply = Mock(return_value=True)
    worker._send_chart = Mock(side_effect=RuntimeError("render failure"))
    assert worker._slots.acquire()

    worker._process("analyze", {"ou_1"}, "ou_1")

    assert worker._reply.call_count == 2
    assert worker._reply.call_args_list[0].args == (
        "ou_1",
        "text",
        {"text": "Analysis"},
    )
    fallback = worker._reply.call_args_list[1].args[2]["text"]
    assert "1. status: open" in fallback
    assert worker._slots.acquire()
    worker._slots.release()


def test_chart_image_upload_and_private_reply(monkeypatch, tmp_path):
    worker = robot.FeishuRobotWorker("app", "secret")
    png = tmp_path / "c_4_r_7.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(robot.settings, "MCP_IMAGE_PATH", str(tmp_path))
    render = Mock(return_value=("unused", None))
    monkeypatch.setattr(chat_llm, "request_picture", render)
    client = Mock()
    client.im.v1.image.create.return_value = SimpleNamespace(
        success=lambda: True, data=SimpleNamespace(image_key="img_7")
    )
    worker._api_client = Mock(return_value=client)
    worker._reply = Mock(return_value=True)
    chart = {"type": "bar", "axis": {"x": {"value": "status"}}}
    data = {"fields": ["status"], "data": [{"status": "open"}]}

    worker._send_chart("ou_sender", (4, 7, chart, data, None))

    render.assert_called_once_with(4, 7, chart, data)
    client.im.v1.image.create.assert_called_once()
    worker._reply.assert_called_once_with("ou_sender", "image", {"image_key": "img_7"})


def test_answer_uses_web_agent_and_never_calls_legacy_mcp(monkeypatch):
    user = _User()
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    chat = SimpleNamespace(id=13, create_by=user.id, oid=user.oid)
    record = SimpleNamespace(
        id=17,
        chat_id=13,
        error=None,
        answer="共 1 项",
        data=json.dumps({"fields": ["status"], "data": [{"status": "open"}]}),
        chart=json.dumps({"type": "table"}),
    )
    service = SimpleNamespace(
        init_record=Mock(return_value=record), run_agent=Mock(return_value=iter(()))
    )
    create = AsyncMock(return_value=service)
    monkeypatch.setattr(robot, "Session", Mock(return_value=session))
    monkeypatch.setattr(robot, "engine", object())
    monkeypatch.setattr(
        robot.FeishuRobotWorker, "_resolve_user", AsyncMock(return_value=user)
    )
    monkeypatch.setattr(robot.FeishuRobotWorker, "_chat", Mock(return_value=chat))
    monkeypatch.setattr(agent.WebAgentService, "create", create)
    worker = robot.FeishuRobotWorker("app", "secret")

    answer, info = asyncio.run(worker._answer("查询任务", "ou_1", {"ou_1"}))

    assert "共 1 项" in answer
    assert "status: open" in answer
    assert info[:3] == (13, 17, {"type": "table"})
    create.assert_called_once()
    service.init_record.assert_called_once_with(session)
    service.run_agent.assert_called_once_with()
    assert not hasattr(robot, "SqlHubClient")
