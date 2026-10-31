import asyncio
import copy
import sqlite3
from datetime import datetime, timedelta
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import orjson
import pytest
import sqlbot_xpack  # noqa: F401 - initialize the installed wheel before datasource imports
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.compiler import compiles
from sqlmodel import Session, SQLModel

from apps.chat.api import chat as chat_api
from apps.chat.models.chat_model import Chat, ChatRecord, CreateChat, WebChatQuestion
from apps.chat.task import agent
from apps.datasource.models.datasource import CoreDatasource
from apps.db import db as db_module
from common.utils.locale import I18n


@compiles(postgresql.JSONB, "sqlite")
def _sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


def _service(question: str):
    service = agent.WebAgentService.__new__(agent.WebAgentService)
    service.record = SimpleNamespace(id=12, chat_id=3, question=question)
    service.chat_question = SimpleNamespace(
        question=question, engine="SQLite", db_schema=""
    )
    service.ds = CoreDatasource(
        id=5, oid=8, type="sqlite", name="test", configuration="", create_by=1
    )
    service.current_user = SimpleNamespace(id=2)
    service.oid = 8
    service.source_record_id = None
    service.time_zone = "Asia/Shanghai"
    service.local_now = agent.datetime.now(agent.ZoneInfo(service.time_zone))
    service.change_title = False
    service.trans = I18n()(lang="zh-CN")
    service._cancelled = Event()
    service.authorized_columns = Mock(return_value={"tasks": {"id", "status"}})
    service._previous_result = Mock(return_value=None)
    service._pending_identity_question = Mock(return_value=None)
    return service


class _Sessions:
    def __init__(self, session=None):
        self.session = session

    def __call__(self):
        return self.session if self.session is not None else object()

    def remove(self):
        pass


def _events(
    service,
    monkeypatch,
    *,
    answer_error=False,
    answer_factory=None,
    schema=("tasks(id,status)", ["tasks"]),
    connection_calls=None,
    schema_calls=None,
    session=None,
):
    progress = []
    monkeypatch.setattr(agent, "session_maker", _Sessions(session))
    if "_route" not in vars(service):
        service._route = Mock(return_value=agent.AgentRoute(action="data"))
    if "_recent_history" not in vars(service):
        service._recent_history = Mock(return_value=[])

    def connected(trans, ds, is_raise=False):
        if connection_calls is not None:
            connection_calls.append(ds)
        assert trans is None
        assert ds is service.ds
        assert not is_raise
        return True

    def table_schema(*args, **_kwargs):
        if schema_calls is not None:
            schema_calls.append(args)
        return schema

    monkeypatch.setattr(agent, "check_connection", connected)
    monkeypatch.setattr(agent, "get_table_schema", table_schema)
    monkeypatch.setattr(
        agent,
        "save_agent_progress",
        lambda *args, **kwargs: progress.append(copy.deepcopy(kwargs)),
    )
    monkeypatch.setattr(agent, "save_chart", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent, "finish_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent, "save_error_message", lambda *args, **kwargs: None)
    if answer_factory:
        service._answer = answer_factory
    else:
        service._answer = Mock(
            side_effect=RuntimeError("model unavailable") if answer_error else None,
            return_value=iter(["共 2 条任务。"]),
        )
    service._chart = Mock(return_value=({"type": "table", "columns": []}, None))
    events = [
        orjson.loads(chunk.removeprefix("data:")) for chunk in service.run_agent()
    ]
    return events, progress


def test_greeting_replies_without_datasource_or_sql(monkeypatch):
    service = _service("你好")
    service.ds = None
    history = [{"question": "早上好", "answer": "早上好！"}]
    service._recent_history = Mock(return_value=history)
    service._route = Mock(return_value=agent.AgentRoute(action="chat", reply="你好！"))
    service.select_datasource = Mock()
    service._decide = Mock()
    service._execute_step = Mock()
    connection_calls = []
    schema_calls = []

    events, progress = _events(
        service,
        monkeypatch,
        connection_calls=connection_calls,
        schema_calls=schema_calls,
    )

    service._route.assert_called_once_with(history)
    service.select_datasource.assert_not_called()
    service.authorized_columns.assert_not_called()
    service._decide.assert_not_called()
    service._execute_step.assert_not_called()
    assert connection_calls == schema_calls == []
    assert [event["type"] for event in events] == [
        "id",
        "question",
        "answer-result",
        "finish",
    ]
    assert events[2]["content"] == progress[-1]["answer"] == "你好！"
    assert progress[-1]["steps"] == []


def test_data_question_without_datasource_asks_for_configuration(monkeypatch):
    service = _service("查询订单")
    service.ds = None
    service.select_datasource = Mock()
    service._decide = Mock()
    service._execute_step = Mock()
    session = Mock()
    session.execute.return_value.first.return_value = None

    events, progress = _events(service, monkeypatch, session=session)

    session.execute.assert_called_once()
    service.select_datasource.assert_not_called()
    service._decide.assert_not_called()
    service._execute_step.assert_not_called()
    service.authorized_columns.assert_not_called()
    assert [event["type"] for event in events] == [
        "id",
        "question",
        "answer-result",
        "finish",
    ]
    assert events[2]["content"] == progress[-1]["answer"]
    assert "数据源" in progress[-1]["answer"]


@pytest.mark.parametrize(
    ("table", "columns", "create_sql", "rows", "question", "sql"),
    [
        (
            "orders",
            {"customer", "amount"},
            "CREATE TABLE orders (customer TEXT, amount INTEGER)",
            [("A", 10), ("A", 20), ("B", 5)],
            "按客户统计订单金额",
            "SELECT customer, SUM(amount) AS total FROM orders GROUP BY customer",
        ),
        (
            "inventory",
            {"sku", "quantity"},
            "CREATE TABLE inventory (sku TEXT, quantity INTEGER)",
            [("P1", 8), ("P2", 3)],
            "查看库存明细",
            "SELECT sku, quantity FROM inventory",
        ),
    ],
)
def test_query_works_with_unrelated_datasource_schemas(
    monkeypatch, table, columns, create_sql, rows, question, sql
):
    service = _service(question)
    service.authorized_columns = Mock(return_value={table: columns})
    service._decide = Mock(
        side_effect=[
            agent.AgentDecision(action="query", sql=sql),
            agent.AgentDecision(action="finish", display="table"),
        ]
    )
    connection = sqlite3.connect(":memory:")
    connection.execute(create_sql)
    connection.executemany(f"INSERT INTO {table} VALUES (?, ?)", rows)

    def execute(query):
        cursor = connection.execute(query)
        fields = [column[0] for column in cursor.description]
        return {
            "fields": fields,
            "fields_info": [],
            "data": [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()],
        }

    service.execute_sql = execute
    monkeypatch.setattr(agent, "get_row_permission_filters", lambda *args, **kwargs: [])
    monkeypatch.setattr(agent, "save_sql", lambda *args: None)
    monkeypatch.setattr(agent, "save_sql_exec_data", lambda *args: None)
    events, progress = _events(
        service, monkeypatch, schema=(f"{table}({','.join(sorted(columns))})", [table])
    )

    assert [event["type"] for event in events].count("agent-step") == 1
    assert progress[-1]["steps"][0]["row_count"] == 2
    assert table.upper() in progress[-1]["steps"][0]["sql"].upper()
    assert service._decide.call_count == 2


@pytest.mark.parametrize(
    "invalid",
    [
        {"chat_id": 4},
        {"create_by": 9},
        {"datasource": 6},
        {"finish": False},
        {"error": "failed"},
        {"first_chat": True},
        {"question": ""},
        {"answer": ""},
    ],
)
def test_recent_history_is_scoped_and_bounded(invalid):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine, tables=[ChatRecord.__table__])
    service = _service("那上周呢")
    service.record.id = 7
    start = datetime(2026, 10, 31, 9)
    with Session(engine) as session:
        session.add_all(
            [
                ChatRecord(
                    id=record_id,
                    chat_id=3,
                    create_by=2,
                    datasource=None if record_id == 3 else 5,
                    create_time=start + timedelta(minutes=record_id),
                    question="Q" * 501 if record_id == 5 else f"q{record_id}",
                    answer="A" * 501 if record_id == 5 else f"a{record_id}",
                    finish=True,
                )
                for record_id in range(1, 6)
            ]
        )
        excluded = {
            "id": 6,
            "chat_id": 3,
            "create_by": 2,
            "datasource": 5,
            "create_time": start + timedelta(minutes=6),
            "question": "excluded",
            "answer": "excluded",
            "finish": True,
        }
        excluded.update(invalid)
        session.add(ChatRecord(**excluded))
        session.commit()

        history = agent.WebAgentService._recent_history(service, session)

    assert history == [
        {"question": "q2", "answer": "a2"},
        {"question": "q3", "answer": "a3"},
        {"question": "q4", "answer": "a4"},
        {
            "question": "Q" * agent.HISTORY_TEXT_CHARS,
            "answer": "A" * agent.HISTORY_TEXT_CHARS,
        },
    ]


def test_task_details_query_once_and_persist_answer(monkeypatch):
    service = _service("查询任务明细，给我表格")
    service._decide = Mock(
        side_effect=[
            agent.AgentDecision(
                action="query",
                sql="SELECT id, status FROM tasks",
                question="task details",
            ),
            agent.AgentDecision(action="finish", display="table"),
        ]
    )
    service._execute_step = Mock(
        return_value=(
            "SELECT id, status FROM tasks LIMIT 1000",
            {
                "fields": ["id", "status"],
                "data": [{"id": 1, "status": "open"}, {"id": 2, "status": "done"}],
            },
        )
    )

    events, progress = _events(service, monkeypatch)

    assert service._execute_step.call_count == 1
    assert [event["type"] for event in events].count("agent-step") == 1
    assert next(event for event in events if event["type"] == "chart")["content"]
    assert progress[-1]["answer"] == "共 2 条任务。"
    assert progress[-1]["steps"][0]["row_count"] == 2
    assert progress[-1]["steps"][0]["result"]["rows"] == [
        {"id": "1", "status": "open"},
        {"id": "2", "status": "done"},
    ]


def test_followup_passes_same_chat_history_to_data_decision(monkeypatch):
    service = _service("那上周呢")
    history = [{"question": "本周订单有多少？", "answer": "本周有 20 单。"}]
    service._recent_history = Mock(return_value=history)
    service._route = Mock(return_value=agent.AgentRoute(action="data"))
    structured = Mock()
    structured.invoke.return_value = agent.AgentDecision(action="finish")
    service.llm = Mock()
    service.llm.with_structured_output.return_value = structured

    events, progress = _events(service, monkeypatch)

    service._route.assert_called_once_with(history)
    messages = structured.invoke.call_args.args[0]
    assert orjson.loads(messages[1].content)["history"] == history
    assert progress[-1]["answer"]
    assert not any(event["type"] in {"sql", "chart"} for event in events)


def test_why_question_stops_after_four_queries(monkeypatch):
    service = _service("为什么未完成任务增多")
    service._decide = Mock(
        return_value=agent.AgentDecision(
            action="query",
            sql="SELECT status FROM tasks",
            question="compare",
            investigate=True,
        )
    )
    service._execute_step = Mock(
        return_value=(
            "SELECT status FROM tasks LIMIT 1000",
            {"fields": ["status"], "data": [{"status": "open"}]},
        )
    )

    events, progress = _events(service, monkeypatch)

    assert service._execute_step.call_count == agent.MAX_QUERIES
    assert service._decide.call_count == agent.MAX_QUERIES
    assert [event["type"] for event in events].count("agent-step") == agent.MAX_QUERIES
    assert len(progress[-1]["steps"]) == agent.MAX_QUERIES


def test_cancelled_investigation_preserves_first_result(monkeypatch):
    service = _service("为什么未完成任务增多")
    service._decide = Mock(
        return_value=agent.AgentDecision(
            action="query", sql="SELECT status FROM tasks", investigate=True
        )
    )

    def execute(_session, _sql, _allowed):
        service._cancelled.set()
        return "SELECT status FROM tasks LIMIT 1000", {
            "fields": ["status"],
            "data": [{"status": "open"}],
        }

    service._execute_step = Mock(side_effect=execute)
    events, progress = _events(service, monkeypatch)

    assert service._execute_step.call_count == 1
    assert "open" in progress[-1]["answer"]
    assert [event["type"] for event in events].count("chart") == 1


def test_model_failure_keeps_evidence_and_table(monkeypatch):
    service = _service("分析未完成任务")
    service._decide = Mock(
        side_effect=[
            agent.AgentDecision(
                action="query", sql="SELECT status FROM tasks", investigate=True
            ),
            agent.AgentDecision(action="finish"),
        ]
    )
    service._execute_step = Mock(
        return_value=(
            "SELECT status FROM tasks LIMIT 1000",
            {"fields": ["status"], "data": [{"status": "open"}]},
        )
    )

    events, progress = _events(service, monkeypatch, answer_error=True)

    assert "open" in progress[-1]["answer"]
    assert [event["type"] for event in events].count("chart") == 1
    assert events[-1]["type"] == "finish"


def test_my_tasks_requires_identity_without_query(monkeypatch):
    service = _service("帮我看看今天做的任务")
    service._decide = Mock()

    events, progress = _events(service, monkeypatch)

    service._decide.assert_not_called()
    assert "具体人员" in progress[-1]["answer"]
    assert any(event["type"] == "finish" for event in events)


def test_my_tasks_with_named_person_can_be_queried():
    assert agent._identity_unknown("我是张三，请查询我的任务") is False
    assert agent._identity_unknown("我的任务") is True
    assert agent._identity_unknown("我是经理，我的任务") is True
    assert agent._identity_unknown("我是项目经理，我的任务") is True
    assert agent._identity_unknown("我是负责人，我的任务") is True


def test_identity_reply_resumes_the_original_question(monkeypatch):
    service = _service("张三")
    service._pending_identity_question.return_value = "帮我看看今天做的任务"
    service._decide = Mock(
        side_effect=[
            agent.AgentDecision(action="query", sql="SELECT id, status FROM tasks"),
            agent.AgentDecision(action="finish"),
        ]
    )
    service._execute_step = Mock(
        return_value=(
            "SELECT id, status FROM tasks LIMIT 1000",
            {"fields": ["id", "status"], "data": [{"id": 1, "status": "open"}]},
        )
    )

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine, tables=[ChatRecord.__table__])
    with Session(engine) as session:
        session.add(ChatRecord(id=12, chat_id=3, create_by=2, question="张三"))
        session.commit()

        events, _ = _events(service, monkeypatch, session=session)
        session.expire_all()
        saved_question = session.get(ChatRecord, 12).question

    service._execute_step.assert_called_once()
    assert "今天做的任务" in saved_question
    assert "张三" in saved_question
    assert service.chat_question.question == service.record.question == saved_question
    assert (
        next(event for event in events if event["type"] == "question")["question"]
        == saved_question
    )


def test_role_reply_still_needs_a_person(monkeypatch):
    service = _service("我是经理")
    service._pending_identity_question.return_value = "我的任务"
    service._decide = Mock()

    _events(service, monkeypatch)

    service._decide.assert_not_called()
    assert agent._identity_unknown(service.chat_question.question)


@pytest.mark.parametrize(
    "change",
    [
        {"chat_id": 4},
        {"create_by": 9},
        {"datasource": 6},
        {"finish": False},
        {"error": "failed"},
        {"data": "{}"},
        {"answer": "other answer"},
        {"question": "查询任务"},
    ],
)
def test_identity_context_requires_immediate_matching_record(change):
    service = _service("张三")
    prior = {
        "id": 11,
        "chat_id": 3,
        "create_by": 2,
        "datasource": 5,
        "question": "我的任务",
        "answer": service.trans("i18n_chat.agent_identity_needed"),
        "finish": True,
        "error": None,
        "sql": None,
        "data": None,
    }
    prior.update(change)
    session = Mock()
    session.execute.return_value.scalars.return_value.first.return_value = (
        SimpleNamespace(**prior)
    )

    assert agent.WebAgentService._pending_identity_question(service, session) is None


def test_identity_context_reads_latest_record_only():
    service = _service("张三")
    session = Mock()
    session.execute.return_value.scalars.return_value.first.return_value = (
        SimpleNamespace(
            id=11,
            chat_id=3,
            create_by=2,
            datasource=5,
            question="我的任务",
            answer=service.trans("i18n_chat.agent_identity_needed"),
            finish=True,
            error=None,
            sql=None,
            data=None,
        )
    )

    assert (
        agent.WebAgentService._pending_identity_question(service, session) == "我的任务"
    )
    statement = session.execute.call_args.args[0]
    compiled = statement.compile()
    assert "chat_record.id <" in str(compiled)
    assert "ORDER BY chat_record.id DESC" in str(compiled)
    service.source_record_id = 9
    session.reset_mock()
    assert agent.WebAgentService._pending_identity_question(service, session) is None
    session.execute.assert_not_called()


def test_identity_context_reads_persisted_records():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine, tables=[ChatRecord.__table__])
    service = _service("张三")
    with Session(engine) as session:
        session.add_all(
            [
                ChatRecord(
                    id=11,
                    chat_id=3,
                    create_by=2,
                    datasource=5,
                    question="我的任务",
                    answer=service.trans("i18n_chat.agent_identity_needed"),
                    finish=True,
                ),
                ChatRecord(id=12, chat_id=3, create_by=2, datasource=5),
            ]
        )
        session.commit()
        assert (
            agent.WebAgentService._pending_identity_question(service, session)
            == "我的任务"
        )

        session.add_all(
            [
                ChatRecord(
                    id=13, chat_id=3, create_by=2, datasource=5, question="查询任务"
                ),
                ChatRecord(id=14, chat_id=3, create_by=2, datasource=5),
            ]
        )
        session.commit()
        service.record.id = 14
        assert (
            agent.WebAgentService._pending_identity_question(service, session) is None
        )


def test_row_filter_is_applied_before_execution(monkeypatch):
    service = _service("查询任务")
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE tasks (id INTEGER, status TEXT, owner_id INTEGER)")
    connection.executemany(
        "INSERT INTO tasks VALUES (?, ?, ?)", [(1, "open", 7), (2, "done", 9)]
    )
    executed = []

    def execute(sql):
        executed.append(sql)
        rows = connection.execute(sql).fetchall()
        return {
            "fields": ["id", "status"],
            "fields_info": [],
            "data": [dict(zip(["id", "status"], row, strict=True)) for row in rows],
        }

    service.execute_sql = execute
    monkeypatch.setattr(
        agent,
        "get_row_permission_filters",
        lambda *args, **kwargs: [{"table": "tasks", "filter": "owner_id = 7"}],
    )
    monkeypatch.setattr(agent, "save_sql", lambda *args: None)
    monkeypatch.setattr(agent, "save_sql_exec_data", lambda *args: None)

    sql, result = service._execute_step(
        object(), "SELECT id, status FROM tasks", {"tasks": {"id", "status"}}
    )

    assert "owner_id" in sql
    assert executed == [sql]
    assert result["data"] == [{"id": 1, "status": "open"}]
    with pytest.raises(ValueError, match="Unauthorized SQL table"):
        service._execute_step(
            object(), "SELECT id FROM secrets", {"tasks": {"id", "status"}}
        )
    assert len(executed) == 1


def test_synthetic_task_analysis_uses_followup_numbers(monkeypatch):
    service = _service("为什么今天未完成任务增多")
    service._decide = Mock(
        side_effect=[
            agent.AgentDecision(
                action="query",
                sql="SELECT COUNT(id) AS n FROM tasks WHERE status = 'open' AND day = '2026-10-30'",
                investigate=True,
            ),
            agent.AgentDecision(
                action="query",
                sql="SELECT COUNT(id) AS n FROM tasks WHERE status = 'open' AND day = '2026-10-29'",
                investigate=True,
            ),
            agent.AgentDecision(action="finish", display="table"),
        ]
    )
    service.authorized_columns = Mock(return_value={"tasks": {"id", "status", "day"}})
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE tasks (id INTEGER, status TEXT, day TEXT)")
    connection.executemany(
        "INSERT INTO tasks VALUES (?, ?, ?)",
        [
            (1, "open", "2026-10-29"),
            (2, "open", "2026-10-30"),
            (3, "open", "2026-10-30"),
            (4, "open", "2026-10-30"),
        ],
    )
    executed = []

    def execute(sql):
        executed.append(sql)
        n = connection.execute(sql).fetchone()[0]
        return {
            "fields": ["n"],
            "fields_info": [{"name": "n", "is_numeric": True}],
            "data": [{"n": n}],
        }

    service.execute_sql = execute
    monkeypatch.setattr(agent, "get_row_permission_filters", lambda *args, **kwargs: [])
    monkeypatch.setattr(agent, "save_sql", lambda *args: None)
    monkeypatch.setattr(agent, "save_sql_exec_data", lambda *args: None)

    def answer(evidence):
        counts = [int(item["result"]["rows"][0]["n"]) for item in evidence]
        yield f"未完成任务从 {counts[1]} 增至 {counts[0]}；这些数据尚不能证明原因。"

    events, progress = _events(service, monkeypatch, answer_factory=answer)

    assert len(executed) == 2
    assert [event["type"] for event in events].count("agent-step") == 2
    assert "从 1 增至 3" in progress[-1]["answer"]
    assert "不能证明原因" in progress[-1]["answer"]
    assert [step["result"]["rows"][0]["n"] for step in progress[-1]["steps"]] == [
        "3",
        "1",
    ]


def test_explicit_bar_uses_real_aggregate_fields():
    service = _service("按状态画柱状图")
    service.chat_question.chart_sys_question = lambda: {
        "system": "chart",
        "rules": "fields",
    }
    service.generate_chart = lambda *args: iter(
        [
            {
                "content": '{"type":"bar","axis":{"x":{"value":"status"},"y":[{"value":"n"}]}}'
            }
        ]
    )
    result = {
        "fields": ["status", "n"],
        "fields_info": [{"name": "n", "is_numeric": True}],
        "data": [{"status": "open", "n": 3}, {"status": "done", "n": 1}],
    }

    chart, reason = service._chart(object(), result, "chart", "bar")

    assert reason is None
    assert chart["type"] == "bar"
    assert chart["axis"]["x"]["value"] == "status"
    assert chart["axis"]["y"][0]["value"] == "n"


def test_web_agent_rejects_another_users_chat():
    session = Mock()
    session.get.return_value = SimpleNamespace(create_by=9, origin=0)
    user = SimpleNamespace(id=2)
    question = WebChatQuestion(question="tasks", chat_id=3, agent_mode=True)

    with pytest.raises(HTTPException) as error:
        asyncio.run(chat_api.question_answer.__wrapped__(session, user, question, None))

    assert error.value.status_code == 403


@pytest.mark.parametrize(
    ("agent_mode", "origin", "allowed"),
    [(True, 0, True), (False, 0, False), (True, 1, False), (True, 2, False)],
)
def test_start_chat_without_datasource_requires_web_agent_opt_in(
    agent_mode, origin, allowed
):
    session = Mock()
    session.refresh.side_effect = lambda chat: setattr(chat, "id", 17)
    user = SimpleNamespace(id=2, oid=8)
    request = CreateChat(agent_mode=agent_mode, origin=origin)
    endpoint = next(
        route.endpoint
        for route in chat_api.router.routes
        if route.path == "/chat/start"
    )
    handler = endpoint.__wrapped__.__wrapped__
    if allowed:
        created = asyncio.run(handler(session, user, request))
        assert created.id == 17
        assert created.records == []
        chat = session.add.call_args.args[0]
        assert isinstance(chat, Chat)
        assert chat.datasource is None
        assert chat.origin == 0
        session.commit.assert_called_once()
    else:
        with pytest.raises(HTTPException, match="Datasource cannot be None"):
            asyncio.run(handler(session, user, request))
        session.add.assert_not_called()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT NEXTVAL('task_id_seq') FROM tasks",
        "SELECT SETVAL('task_id_seq', 9) FROM tasks",
        "SELECT DBLINK_EXEC('conn', 'DELETE FROM tasks') FROM tasks",
        "SELECT PG_READ_FILE('/etc/passwd') FROM tasks",
        "SELECT PG_SLEEP(100) FROM tasks",
        "SELECT PG_ADVISORY_LOCK(1) FROM tasks",
        "SELECT PG_NOTIFY('audit', id::text) FROM tasks",
    ],
)
def test_postgres_select_functions_with_side_effects_are_rejected(sql):
    safe, reason = db_module.check_sql_read(sql, SimpleNamespace(type="pg"))
    assert safe is False
    assert "dangerous function" in reason


def test_postgres_execution_sets_read_only_and_statement_timeout(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    session.bind.dialect.name = "postgresql"
    result = MagicMock()
    result.__enter__.return_value = result
    result.keys.return_value._keys = ["id"]
    result.fetchall.return_value = [(1,)]
    session.execute.side_effect = [None, None, result]
    monkeypatch.setattr(db_module, "get_session", lambda _ds: session)
    monkeypatch.setattr(db_module, "aes_decrypt", lambda _value: '{"timeout": 2}')
    ds = CoreDatasource(id=5, oid=8, type="pg", configuration="encrypted")

    query = db_module.exec_sql(ds, "SELECT id FROM tasks")

    assert query["data"] == [{"id": 1}]
    statements = [str(call.args[0]) for call in session.execute.call_args_list]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert "statement_timeout" in statements[1]
    assert session.execute.call_args_list[1].args[1] == {"value": "2s"}


def test_datasource_selection_rejects_foreign_id_before_chat_mutation():
    service = agent.WebAgentService.__new__(agent.WebAgentService)
    service.current_assistant = None
    service.oid = 8
    service.record = SimpleNamespace(id=12, chat_id=3)
    service.ds = None
    service.chat_question = SimpleNamespace(
        datasource_sys_question=lambda: "select source"
    )
    session = Mock()
    session.exec.return_value = [SimpleNamespace(id=5, name="local", description="")]
    chat = SimpleNamespace(datasource=None)
    foreign = CoreDatasource(id=5, oid=9, type="sqlite", configuration="")
    session.get.side_effect = [chat, foreign]

    with pytest.raises(Exception, match="Datasource does not belong"):
        list(service.select_datasource(session))

    assert chat.datasource is None
    session.commit.assert_not_called()
