import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import orjson
import pytest
import sqlbot_xpack  # noqa: F401 - initialize the installed wheel before CRUD imports
from sqlalchemy import create_engine, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.compiler import compiles
from sqlmodel import Session, SQLModel

from apps.chat.curd.chat import get_chat_with_records, get_chat_with_records_with_data
from apps.chat.models.chat_model import (
    Chat,
    ChatLog,
    ChatQuestionBase,
    ChatRecord,
    ChatRecordResult,
    McpQuestion,
    WebChatQuestion,
)
from apps.chat.task.agent import WebAgentService


@compiles(postgresql.JSONB, "sqlite")
def _sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


def _save_agent_progress():
    source = Path(__file__).resolve().parents[1] / "apps/chat/curd/chat.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "save_agent_progress"
    )
    scope = {"SessionDep": object, "ChatRecord": ChatRecord, "update": update}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"),
        scope,
    )
    return scope["save_agent_progress"]


def test_agent_fields_are_optional_in_model_and_response():
    assert ChatRecord.__table__.columns["answer"].nullable
    assert isinstance(
        ChatRecord.__table__.columns["agent_steps"].type, postgresql.JSONB
    )
    assert ChatRecord.__table__.columns["source_record_id"].nullable
    assert ChatRecordResult(answer="Done", agent_steps=[]).agent_steps == []
    assert WebChatQuestion(question="Tasks", chat_id=1).agent_mode is False
    assert "agent_mode" not in McpQuestion.model_fields
    assert "agent_mode" not in ChatQuestionBase.model_fields


def test_progress_update_preserves_omitted_fields_and_accepts_empty_values():
    save = _save_agent_progress()
    session = Mock()
    session.get.return_value = ChatRecord(id=7, chat_id=1)

    save(session, 7, answer="", steps=[])
    statement = session.execute.call_args.args[0]
    assert statement.compile(dialect=postgresql.dialect()).params == {
        "id_1": 7,
        "answer": "",
        "agent_steps": [],
    }

    session.reset_mock()
    save(session, 7, steps=[{"sql": "SELECT 1"}])
    params = (
        session.execute.call_args.args[0].compile(dialect=postgresql.dialect()).params
    )
    assert params["agent_steps"] == [{"sql": "SELECT 1"}]
    assert "answer" not in params

    session.reset_mock()
    save(session, 7)
    session.execute.assert_not_called()


def test_both_history_views_restore_answer_and_steps():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine, tables=[Chat.__table__, ChatRecord.__table__, ChatLog.__table__]
    )
    steps = [
        {"question": "task status", "sql": "SELECT status FROM tasks", "row_count": 2}
    ]
    with Session(engine) as session:
        session.add(
            Chat(
                id=1,
                oid=1,
                create_by=2,
                create_time=datetime.now(),
                brief="tasks",
                engine_type="SQLite",
                origin=0,
            )
        )
        session.add(
            ChatRecord(
                id=7,
                chat_id=1,
                create_by=2,
                create_time=datetime.now(),
                datasource=5,
                question="原始任务查询",
                data=orjson.dumps(
                    {"fields": ["status"], "data": [{"status": "open"}]}
                ).decode(),
                finish=True,
            )
        )
        session.add(
            ChatRecord(
                id=8,
                chat_id=1,
                create_by=2,
                create_time=datetime.now(),
                datasource=5,
                question="tasks",
                answer="共 2 条任务",
                agent_steps=steps,
                source_record_id=7,
                finish=True,
            )
        )
        session.commit()
        user = SimpleNamespace(id=2)

        compact = get_chat_with_records(session, 1, user, None).records[-1]
        full = get_chat_with_records_with_data(session, 1, user, None).records[-1]

    assert compact["answer"] == full["answer"] == "共 2 条任务"
    assert compact["agent_steps"] == full["agent_steps"] == steps
    assert compact["source_record_id"] == full["source_record_id"] == 7


def test_text_only_reply_restores_without_sql_or_chart():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine, tables=[Chat.__table__, ChatRecord.__table__, ChatLog.__table__]
    )
    with Session(engine) as session:
        session.add(
            Chat(
                id=1,
                oid=1,
                create_by=2,
                create_time=datetime.now(),
                brief="chat",
                engine_type="SQLite",
                origin=0,
            )
        )
        session.add(
            ChatRecord(
                id=7,
                chat_id=1,
                create_by=2,
                create_time=datetime.now(),
                question="你好",
                answer="你好！",
                agent_steps=[],
                finish=True,
            )
        )
        session.commit()
        user = SimpleNamespace(id=2)

        compact = get_chat_with_records(session, 1, user, None).records[0]
        full = get_chat_with_records_with_data(session, 1, user, None).records[0]

    for record in (compact, full):
        assert record["answer"] == "你好！"
        assert record["agent_steps"] == []
        assert record["sql"] is None
        assert record["chart"] is None
        assert record.get("data") is None


def test_source_result_is_persisted_only_after_ownership_and_datasource_check():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine, tables=[ChatRecord.__table__])
    result = orjson.dumps({"fields": ["status"], "data": [{"status": "open"}]}).decode()
    with Session(engine) as session:
        session.add_all(
            [
                ChatRecord(
                    id=7, chat_id=1, create_by=2, datasource=5, data=result, finish=True
                ),
                ChatRecord(id=8, chat_id=1, create_by=2, datasource=5),
                ChatRecord(
                    id=9, chat_id=1, create_by=2, datasource=6, data=result, finish=True
                ),
                ChatRecord(
                    id=10,
                    chat_id=1,
                    create_by=2,
                    datasource=5,
                    data=result,
                    finish=False,
                ),
                ChatRecord(
                    id=11,
                    chat_id=1,
                    create_by=2,
                    datasource=5,
                    data=orjson.dumps(
                        {"fields": ["status"], "data": [{"status": "future"}]}
                    ).decode(),
                    create_time=datetime.now(),
                    finish=True,
                ),
            ]
        )
        session.commit()

        service = WebAgentService.__new__(WebAgentService)
        service.record = SimpleNamespace(id=8, chat_id=1)
        service.current_user = SimpleNamespace(id=2)
        service.ds = SimpleNamespace(id=5)
        service.source_record_id = 9
        with pytest.raises(ValueError, match="Source result does not belong"):
            service._previous_result(session)
        assert session.get(ChatRecord, 8).source_record_id is None

        service.source_record_id = 10
        with pytest.raises(ValueError, match="Source result does not belong"):
            service._previous_result(session)
        assert session.get(ChatRecord, 8).source_record_id is None

        service.source_record_id = 11
        with pytest.raises(ValueError, match="Source result does not belong"):
            service._previous_result(session)
        assert session.get(ChatRecord, 8).source_record_id is None

        service.source_record_id = None
        assert service._previous_result(session)["result"]["rows"] == [
            {"status": "open"}
        ]
        assert session.get(ChatRecord, 8).source_record_id is None

        service.source_record_id = 7
        assert service._previous_result(session)["question"] is None
        session.expire_all()
        assert session.get(ChatRecord, 8).source_record_id == 7
