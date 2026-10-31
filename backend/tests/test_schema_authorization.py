from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlbot_xpack  # noqa: F401 - initialize installed wheel before datasource imports

from apps.chat.task import llm
from apps.chat.task.safe_query import prepare_safe_query
from apps.datasource.crud import datasource


@pytest.mark.parametrize(
    "ds_type,schema,table,column,bare_sql,qualified_sql",
    [
        (
            "pg",
            "reporting",
            "tasks",
            "id",
            "SELECT id FROM tasks",
            "SELECT id FROM reporting.tasks",
        ),
        (
            "sqlServer",
            "reporting",
            "tasks",
            "id",
            "SELECT id FROM tasks",
            "SELECT id FROM reporting.tasks",
        ),
        (
            "oracle",
            "REPORTING",
            "TASKS",
            "ID",
            "SELECT ID FROM TASKS",
            "SELECT ID FROM REPORTING.TASKS",
        ),
        (
            "redshift",
            "reporting",
            "tasks",
            "id",
            "SELECT id FROM tasks",
            "SELECT id FROM reporting.tasks",
        ),
        (
            "kingbase",
            "reporting",
            "tasks",
            "id",
            "SELECT id FROM tasks",
            "SELECT id FROM reporting.tasks",
        ),
        (
            "dm",
            "REPORTING",
            "TASKS",
            "ID",
            "SELECT ID FROM TASKS",
            "SELECT ID FROM REPORTING.TASKS",
        ),
    ],
)
def test_schema_scoped_datasource_rejects_default_schema_table(
    monkeypatch, ds_type, schema, table, column, bare_sql, qualified_sql
):
    monkeypatch.setattr(
        llm,
        "get_table_obj_by_ds",
        lambda *args: [
            SimpleNamespace(
                schema=schema,
                table=SimpleNamespace(table_name=table),
                fields=[SimpleNamespace(field_name=column)],
            )
        ],
    )
    service = llm.LLMService.__new__(llm.LLMService)
    service.ds = SimpleNamespace(type=ds_type)
    service.current_user = SimpleNamespace(id=2)

    allowed = service.authorized_columns(None)

    assert allowed == {f"{schema}.{table}": {column}}
    with pytest.raises(ValueError, match="Unauthorized SQL table"):
        prepare_safe_query(bare_sql, allowed, ds_type=ds_type)
    assert prepare_safe_query(qualified_sql, allowed, ds_type=ds_type)[1] == {table}


@pytest.mark.parametrize("ds_type", ["sqlite", "mysql", "excel"])
def test_database_scoped_datasource_keeps_unqualified_tables(monkeypatch, ds_type):
    monkeypatch.setattr(
        llm,
        "get_table_obj_by_ds",
        lambda *args: [
            SimpleNamespace(
                schema="public",
                table=SimpleNamespace(table_name="tasks"),
                fields=[SimpleNamespace(field_name="id")],
            )
        ],
    )
    service = llm.LLMService.__new__(llm.LLMService)
    service.ds = SimpleNamespace(type=ds_type)
    service.current_user = SimpleNamespace(id=2)

    allowed = service.authorized_columns(None)

    assert allowed["tasks"] == {"id"}
    assert prepare_safe_query("SELECT id FROM tasks", allowed, ds_type=ds_type)[1] == {
        "tasks"
    }


def test_missing_configured_schema_does_not_use_service_name(monkeypatch):
    monkeypatch.setattr(
        datasource,
        "aes_decrypt",
        lambda value: '{"database":"service_db","dbSchema":""}',
    )
    session = MagicMock()
    session.query.return_value.filter.return_value.all.side_effect = [
        [SimpleNamespace(id=1, table_name="TASKS")],
        [SimpleNamespace(table_id=1, field_name="ID")],
    ]
    session.query.return_value.all.return_value = []
    ds = SimpleNamespace(id=5, type="oracle", configuration="cipher")

    items = datasource.get_table_obj_by_ds(session, SimpleNamespace(id=1), ds)

    assert items[0].schema is None

    service = llm.LLMService.__new__(llm.LLMService)
    service.ds = ds
    service.current_user = SimpleNamespace(id=1)
    monkeypatch.setattr(llm, "get_table_obj_by_ds", lambda *args: items)
    assert service.authorized_columns(session) == {}


def test_schema_scoped_sample_does_not_query_when_schema_missing(monkeypatch):
    queries = []
    monkeypatch.setattr(
        datasource,
        "exec_sql",
        lambda ds, sql, origin_column: queries.append(sql),
    )

    sample = datasource.get_table_sample_data(
        SimpleNamespace(type="oracle"),
        "TASKS",
        [SimpleNamespace(field_name="ID")],
    )

    assert sample == ""
    assert queries == []


@pytest.mark.parametrize(
    "ds_type,schema,table,expected",
    [
        ("pg", "reporting", "tasks", '"reporting"."tasks"'),
        ("sqlServer", "reporting", "tasks", "[reporting].[tasks]"),
        ("oracle", "REPORTING", "TASKS", '"REPORTING"."TASKS"'),
        ("redshift", "reporting", "tasks", '"reporting"."tasks"'),
        ("kingbase", "reporting", "tasks", '"reporting"."tasks"'),
        ("dm", "REPORTING", "TASKS", '"REPORTING"."TASKS"'),
    ],
)
def test_model_sample_uses_configured_schema(
    monkeypatch, ds_type, schema, table, expected
):
    queries = []
    monkeypatch.setattr(
        datasource,
        "get_table_obj_by_ds",
        lambda **kwargs: [
            SimpleNamespace(
                schema=schema,
                table=SimpleNamespace(table_name=table),
                fields=[SimpleNamespace(field_name="id")],
            )
        ],
    )
    monkeypatch.setattr(
        datasource,
        "exec_sql",
        lambda ds, sql, origin_column: queries.append(sql) or {"data": []},
    )

    datasource.get_tables_sample_data(
        session=None,
        current_user=SimpleNamespace(id=1),
        ds=SimpleNamespace(type=ds_type),
        table_list=[table],
    )

    assert len(queries) == 1
    assert f"FROM {expected}" in queries[0]


@pytest.mark.parametrize("ds_type", ["sqlite", "excel"])
def test_model_sample_keeps_existing_unqualified_tables(monkeypatch, ds_type):
    queries = []
    monkeypatch.setattr(
        datasource,
        "exec_sql",
        lambda ds, sql, origin_column: queries.append(sql) or {"data": []},
    )

    datasource.get_table_sample_data(
        SimpleNamespace(type=ds_type),
        "tasks",
        [SimpleNamespace(field_name="id")],
        schema="public",
    )

    assert 'FROM "tasks"' in queries[0]
