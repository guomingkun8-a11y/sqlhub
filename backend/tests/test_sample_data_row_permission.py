import sqlite3
from types import SimpleNamespace

import pytest
import sqlbot_xpack  # noqa: F401 - initialize installed wheel before datasource imports

from apps.datasource.crud import datasource


def test_sample_data_respects_row_permission_before_model_context(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        "CREATE TABLE tasks (id INTEGER, owner_id INTEGER);"
        "INSERT INTO tasks VALUES (1, 7), (2, 9);"
    )
    monkeypatch.setattr(
        datasource,
        "get_table_obj_by_ds",
        lambda **kwargs: [
            SimpleNamespace(
                schema=None,
                table=SimpleNamespace(table_name="tasks"),
                fields=[SimpleNamespace(field_name="id")],
            )
        ],
    )
    monkeypatch.setattr(
        datasource,
        "get_row_permission_filters",
        lambda **kwargs: [{"table": "tasks", "filter": "owner_id = 7"}],
    )
    queries = []

    def execute(ds, sql, origin_column):
        assert ds.type == "sqlite"
        assert origin_column is True
        queries.append(sql)
        return {"data": [{"id": row[0]} for row in connection.execute(sql)]}

    monkeypatch.setattr(datasource, "exec_sql", execute)
    sample = datasource.get_tables_sample_data(
        session=None,
        current_user=SimpleNamespace(id=2),
        ds=SimpleNamespace(type="sqlite"),
        table_list=["tasks"],
    )

    assert "owner_id = 7" in queries[0]
    assert '"id": 1' in sample
    assert '"id": 2' not in sample


@pytest.mark.parametrize("ds_type", ["sqlServer", "oracle", "mysql", "sqlite"])
def test_sample_filter_rewrite_preserves_dialect_row_limit(monkeypatch, ds_type):
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
        [{"table": "tasks", "filter": "owner_id = 7"}],
        schema="reporting",
    )

    assert len(queries) == 1
    assert "owner_id = 7" in queries[0]
    if ds_type == "sqlServer":
        assert "SELECT TOP 3" in queries[0]
    if ds_type == "oracle":
        assert "ROWNUM <= 3" in queries[0]
