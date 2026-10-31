import sqlite3

import pytest

from apps.chat.task.safe_query import apply_row_filters, prepare_safe_query

FIELDS = {
    "tasks": {"id", "status", "owner_id"},
    "owners": {"id", "name"},
}


def test_authorized_columns_cte_and_database_limit():
    sql, tables = prepare_safe_query(
        "WITH counts AS (SELECT status, COUNT(*) AS n FROM tasks GROUP BY status) "
        "SELECT status, n FROM counts",
        FIELDS,
        ds_type="sqlite",
        row_limit=20,
    )
    assert tables == {"tasks"}
    assert sql.endswith("LIMIT 20")

    sql, tables = prepare_safe_query(
        "SELECT t.status, o.name FROM tasks AS t JOIN owners AS o ON t.owner_id = o.id LIMIT 3",
        FIELDS,
        row_limit=20,
    )
    assert tables == {"tasks", "owners"}
    assert sql.endswith("LIMIT 3")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT secret FROM tasks",
        "SELECT t.secret FROM tasks AS t",
        "SELECT status FROM tasks WHERE secret = 1",
        "SELECT * FROM tasks",
        "SELECT t.* FROM tasks AS t",
        "SELECT id FROM tasks JOIN owners ON tasks.owner_id = owners.id",
        "SELECT id FROM other.tasks",
        "SELECT status FROM tasks UNION SELECT secret FROM owners",
        "WITH x AS (SELECT secret FROM tasks) SELECT secret FROM x",
        "SELECT status FROM tasks; DELETE FROM tasks",
        "UPDATE tasks SET status = 'done'",
        "SELECT status INTO copied_tasks FROM tasks",
        "SELECT status FROM tasks FOR UPDATE",
        "SELECT status FROM tasks LIMIT ?",
        "SELECT id FROM tasks NATURAL JOIN owners",
        "SELECT tasks FROM tasks",
        "SELECT ROW_TO_JSON(tasks) FROM tasks",
        "SELECT TO_JSONB(t) FROM tasks AS t",
    ],
)
def test_reject_unsafe_or_unauthorized_query(sql):
    with pytest.raises(ValueError):
        prepare_safe_query(sql, FIELDS, row_limit=20)


def test_schema_qualified_table_requires_exact_authorization():
    sql, tables = prepare_safe_query(
        "SELECT t.status FROM reporting.tasks AS t",
        {"reporting.tasks": FIELDS["tasks"]},
        row_limit=10,
    )
    assert tables == {"tasks"}
    assert sql.endswith("LIMIT 10")


def test_sql_server_limit_uses_top_and_caps_existing_limit():
    sql, _ = prepare_safe_query(
        "SELECT TOP 500 status FROM tasks", FIELDS, ds_type="sqlServer", row_limit=10
    )
    assert "TOP 10" in sql


def test_none_row_limit_validates_without_changing_limit():
    sql, tables = prepare_safe_query(
        "SELECT id FROM tasks", FIELDS, ds_type="sqlite", row_limit=None
    )
    assert sql == "SELECT id FROM tasks"
    assert tables == {"tasks"}

    sql, _ = prepare_safe_query(
        "SELECT id FROM tasks LIMIT 50", FIELDS, ds_type="sqlite", row_limit=None
    )
    assert sql.endswith("LIMIT 50")
    with pytest.raises(ValueError):
        prepare_safe_query(
            "SELECT secret FROM tasks", FIELDS, ds_type="sqlite", row_limit=None
        )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT TOP 10 PERCENT status FROM tasks",
        "SELECT TOP 10 WITH TIES status FROM tasks ORDER BY status",
    ],
)
def test_reject_sql_server_limits_that_can_exceed_cap(sql):
    with pytest.raises(ValueError):
        prepare_safe_query(sql, FIELDS, ds_type="sqlServer", row_limit=10)


def test_row_filters_apply_to_every_self_join_and_cte_occurrence():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE tasks(id INTEGER, owner_id INTEGER, status TEXT);"
        "INSERT INTO tasks VALUES (1, 1, 'open'), (2, 1, 'hidden'), (3, 2, 'open');"
    )
    query, _ = prepare_safe_query(
        "WITH visible AS (SELECT id, owner_id FROM tasks) "
        "SELECT a.id, b.id FROM visible a JOIN tasks b ON a.owner_id = b.owner_id",
        FIELDS,
        ds_type="sqlite",
        row_limit=20,
    )
    filtered = apply_row_filters(
        query, [{"table": "tasks", "filter": "status = 'open'"}], ds_type="sqlite"
    )
    assert filtered.count("WHERE status = 'open'") == 2
    assert "status = 'open' AND status = 'open'" not in filtered
    assert conn.execute(filtered).fetchall() == [(1, 1), (3, 3)]


def test_row_filter_preserves_left_join_and_qualified_reference():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE tasks(id INTEGER, owner_id INTEGER, status TEXT);"
        "CREATE TABLE owners(id INTEGER, name TEXT);"
        "INSERT INTO tasks VALUES (1, 1, 'open'), (2, 2, 'hidden');"
        "INSERT INTO owners VALUES (1, 'Alice'), (2, 'Bob');"
    )
    query, _ = prepare_safe_query(
        "SELECT o.name, t.id FROM owners o LEFT JOIN tasks t ON o.id = t.owner_id",
        FIELDS,
        ds_type="sqlite",
        row_limit=20,
    )
    filtered = apply_row_filters(
        query, [{"table": "tasks", "filter": "status = 'open'"}], ds_type="sqlite"
    )
    assert conn.execute(filtered).fetchall() == [("Alice", 1), ("Bob", None)]
    with pytest.raises(ValueError, match="not found"):
        apply_row_filters(query, [{"table": "missing", "filter": "id = 1"}])


def test_row_filter_can_use_hidden_column_without_exposing_it():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE tasks(id INTEGER, status TEXT);"
        "INSERT INTO tasks VALUES (1, 'open'), (2, 'hidden');"
    )
    query, _ = prepare_safe_query(
        "SELECT id FROM tasks", {"tasks": {"id"}}, ds_type="sqlite", row_limit=10
    )
    filtered = apply_row_filters(
        query, [{"table": "tasks", "filter": "status = 'open'"}], ds_type="sqlite"
    )
    assert conn.execute(filtered).fetchall() == [(1,)]


def test_row_filter_rewrite_rechecks_serialized_query(monkeypatch):
    import sqlglot

    query, _ = prepare_safe_query(
        "SELECT id FROM tasks", {"tasks": {"id"}}, ds_type="sqlite"
    )
    real_parse_one = sqlglot.parse_one

    def tamper_final_query(sql, *args, **kwargs):
        if sql.startswith("SELECT id FROM (SELECT * FROM tasks"):
            return real_parse_one("SELECT secret FROM tasks")
        return real_parse_one(sql, *args, **kwargs)

    monkeypatch.setattr(
        sqlglot,
        "parse_one",
        tamper_final_query,
    )

    with pytest.raises(ValueError, match="rewrite changed"):
        apply_row_filters(
            query, [{"table": "tasks", "filter": "owner_id = 7"}], ds_type="sqlite"
        )


def test_row_filter_on_schema_qualified_table_rewrites_column_qualifier():
    conn = sqlite3.connect(":memory:")
    conn.execute("ATTACH DATABASE ':memory:' AS reporting")
    conn.executescript(
        "CREATE TABLE reporting.tasks(id INTEGER, status TEXT);"
        "INSERT INTO reporting.tasks VALUES (1, 'open'), (2, 'hidden');"
    )
    query, _ = prepare_safe_query(
        "SELECT reporting.tasks.id FROM reporting.tasks",
        {"reporting.tasks": {"id"}},
        ds_type="sqlite",
        row_limit=10,
    )
    filtered = apply_row_filters(
        query, [{"table": "tasks", "filter": "status = 'open'"}], ds_type="sqlite"
    )
    assert conn.execute(filtered).fetchall() == [(1,)]


@pytest.mark.parametrize(
    "ds_type, query, allowed, filter_table, predicate, expected",
    [
        (
            "sqlServer",
            "SELECT [dbo].[Tasks].[Id] FROM [dbo].[Tasks]",
            {"dbo.Tasks": {"Id"}},
            "Tasks",
            "[Status] = N'open'",
            "[dbo].[Tasks] WHERE [Status] = N'open'",
        ),
        (
            "pg",
            'SELECT "Reporting"."Tasks"."Id" FROM "Reporting"."Tasks"',
            {"Reporting.Tasks": {"Id"}},
            "Tasks",
            "\"Status\" = 'open'",
            '"Reporting"."Tasks" WHERE "Status" = \'open\'',
        ),
        (
            "oracle",
            "SELECT APP.TASKS.ID FROM APP.TASKS",
            {"APP.TASKS": {"ID"}},
            "TASKS",
            "STATUS = 'open'",
            "APP.TASKS WHERE STATUS = 'open'",
        ),
    ],
)
def test_row_filters_keep_qualified_identifier_case(
    ds_type, query, allowed, filter_table, predicate, expected
):
    safe_sql, _ = prepare_safe_query(query, allowed, ds_type=ds_type, row_limit=10)
    filtered = apply_row_filters(
        safe_sql, [{"table": filter_table, "filter": predicate}], ds_type=ds_type
    )
    assert expected in filtered


def test_sql_server_distinct_case_is_not_authorized_by_folding():
    with pytest.raises(ValueError, match="Unauthorized SQL table"):
        prepare_safe_query(
            "SELECT [Id] FROM [dbo].[tasks]",
            {"dbo.Tasks": {"Id"}},
            ds_type="sqlServer",
        )
    with pytest.raises(ValueError, match="Unauthorized SQL column"):
        prepare_safe_query(
            "SELECT [Secret] FROM [dbo].[Tasks]",
            {"dbo.Tasks": {"secret"}},
            ds_type="sqlServer",
        )
    with pytest.raises(ValueError, match="Unauthorized SQL column"):
        prepare_safe_query(
            "WITH visible AS (SELECT [Id] FROM [dbo].[Tasks]) "
            "SELECT t.[Secret] FROM [dbo].[Tasks] t JOIN visible v ON t.[Id] = v.[Id]",
            {"dbo.Tasks": {"Id", "secret"}},
            ds_type="sqlServer",
        )


def test_postgres_quoted_unqualified_column_uses_authorized_case():
    sql, _ = prepare_safe_query(
        'SELECT "Id" FROM "Reporting"."Tasks"',
        {"Reporting.Tasks": {"Id"}},
        ds_type="pg",
        row_limit=None,
    )
    assert sql == 'SELECT "Id" FROM "Reporting"."Tasks"'
