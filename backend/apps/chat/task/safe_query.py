"""Validate generated queries against the visible datasource schema before execution."""

from collections import Counter
from collections.abc import Collection, Mapping

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope
from sqlglot.schema import MappingSchema

_DIALECTS = {
    "ck": "clickhouse",
    "dm": "oracle",
    "doris": "mysql",
    "es": None,
    "excel": "postgres",
    "hive": "hive",
    "kingbase": "postgres",
    "mysql": "mysql",
    "oracle": "oracle",
    "pg": "postgres",
    "redshift": "redshift",
    "sqlite": "sqlite",
    "sqlserver": "tsql",
    "starrocks": "mysql",
}

SCHEMA_SCOPED_DATASOURCES = frozenset(
    {"dm", "kingbase", "oracle", "pg", "redshift", "sqlserver"}
)


def _table_key(table: exp.Table) -> str:
    parts = tuple(part for part in (table.catalog, table.db, table.name) if part)
    if any("." in part for part in parts):
        raise ValueError(
            "Dots inside SQL identifiers require unambiguous metadata keys"
        )
    return ".".join(parts)


def _physical_source(scope: Scope, alias: str) -> exp.Table | None:
    current: Scope | None = scope
    while current is not None:
        selected = current.selected_sources.get(alias)
        if selected:
            source = selected[1]
            return source if isinstance(source, exp.Table) else None
        current = current.parent
    raise ValueError(f"Unknown SQL source: {alias}")


def prepare_safe_query(
    sql: str,
    allowed_columns: Mapping[str, Collection[str]],
    *,
    ds_type: str | None = None,
    dialect: str | None = None,
    row_limit: int | None = 1000,
) -> tuple[str, set[str]]:
    """Return an authorized SELECT and its real tables; optionally cap its rows.

    ``allowed_columns`` uses physical table names, including schema/catalog for
    qualified references. Apply row filters after this validation.
    """
    if row_limit is not None and row_limit < 1:
        raise ValueError("SQL row limit must be positive")
    if ds_type:
        try:
            dialect = dialect or _DIALECTS[ds_type.lower()]
        except KeyError as exc:
            raise ValueError(f"Unsupported datasource type: {ds_type}") from exc

    try:
        statements = sqlglot.parse(sql, read=dialect)
        if len(statements) != 1 or not isinstance(
            statements[0], (exp.Select, exp.SetOperation)
        ):
            raise ValueError("Only one SELECT statement is allowed")
        query = statements[0]
        if next(query.find_all(exp.DML, exp.DDL, exp.Into, exp.Lock), None):
            raise ValueError("SQL contains a write or locking operation")
        if any(
            join.args.get("method") == "NATURAL" for join in query.find_all(exp.Join)
        ):
            raise ValueError("Natural joins can use unauthorized columns")
        if any(
            not isinstance(star.parent, exp.Count) for star in query.find_all(exp.Star)
        ):
            raise ValueError("SQL wildcard columns are not allowed")
        if any(
            options and (options.args.get("percent") or options.args.get("with_ties"))
            for limit in query.find_all(exp.Limit)
            if (options := limit.args.get("limit_options")) is not None
        ):
            raise ValueError("Percentage and tied SQL limits cannot enforce a row cap")

        # Preserve physical spelling for case-sensitive databases. Qualification
        # runs on a separate normalized copy to resolve aliases and CTE columns.
        scopes = traverse_scope(query.copy())
        tables: set[str] = set()
        schema: dict[str, dict[str, str]] = {}
        normalized_allowed: dict[str, set[str]] = {}
        normalized_keys: dict[str, str] = {}
        for scope in scopes:
            physical_sources = [
                source
                for _, source in scope.selected_sources.values()
                if isinstance(source, exp.Table)
            ]
            for column in scope.columns:
                if column.table:
                    continue
                current_scope: Scope | None = scope
                while current_scope is not None:
                    if column.name in current_scope.selected_sources:
                        raise ValueError(
                            "SQL whole-row source references are not allowed"
                        )
                    current_scope = current_scope.parent
            for _, source in scope.selected_sources.values():
                if isinstance(source, Scope):
                    continue
                if not isinstance(source, exp.Table) or not source.name:
                    raise ValueError("Unsupported SQL table source")
                key = _table_key(source)
                if key not in allowed_columns:
                    raise ValueError(f"Unauthorized SQL table: {key}")
                tables.add(source.name)
                normalized_source = normalize_identifiers(
                    source.copy(), dialect=dialect
                )
                normalized_key = _table_key(normalized_source)
                if (
                    normalized_key in normalized_keys
                    and normalized_keys[normalized_key] != key
                ):
                    raise ValueError(
                        "SQL table names collide after dialect normalization"
                    )
                normalized_keys[normalized_key] = key
                normalized_allowed[normalized_key] = {
                    normalize_identifiers(
                        exp.to_identifier(name, quoted=True), dialect=dialect
                    ).name
                    for name in allowed_columns[key]
                }
                schema.setdefault(normalized_source.name, {}).update(
                    dict.fromkeys(normalized_allowed[normalized_key], "UNKNOWN")
                )
            if dialect == "tsql":
                for column in scope.columns:
                    if column.table:
                        source = _physical_source(scope, column.table)
                        candidates = [source] if source else []
                    elif len(physical_sources) == len(scope.selected_sources):
                        candidates = physical_sources
                    else:
                        candidates = []
                    if candidates and not any(
                        column.name in allowed_columns[_table_key(source)]
                        for source in candidates
                    ):
                        raise ValueError(f"Unauthorized SQL column: {column.name}")
        if not tables:
            raise ValueError("SQL does not reference an authorized table")

        qualified = qualify(
            query.copy(),
            dialect=dialect,
            schema=MappingSchema(schema, dialect=dialect, normalize=False),
            identify=False,
        )
        for scope in traverse_scope(qualified):
            for column in scope.columns:
                if not column.table:
                    raise ValueError(f"Ambiguous SQL column: {column.name}")
                source = _physical_source(scope, column.table)
                if source and column.name not in normalized_allowed[_table_key(source)]:
                    raise ValueError(f"Unauthorized SQL column: {column.name}")

        existing_limit = query.args.get("limit")
        if existing_limit:
            literal = existing_limit.expression
            if not isinstance(literal, exp.Literal) or not literal.is_int:
                raise ValueError("SQL limit must be an integer literal")
            if row_limit is None or 0 <= int(literal.this) <= row_limit:
                return query.sql(dialect=dialect), tables
        if row_limit is None:
            return query.sql(dialect=dialect), tables
        return query.limit(row_limit).sql(dialect=dialect), tables
    except (sqlglot.errors.SqlglotError, KeyError, AttributeError) as exc:
        raise ValueError(f"Invalid or unauthorized SQL: {exc}") from exc


def apply_row_filters(
    sql: str,
    filters: list[dict[str, str]],
    *,
    ds_type: str | None = None,
    dialect: str | None = None,
) -> str:
    """Apply trusted row-permission conditions to every physical table source.

    Call after ``prepare_safe_query``. A filtered subquery preserves outer-join
    semantics; each filter is parsed as a condition, never spliced into SQL.
    """
    if not filters:
        return sql
    if ds_type:
        try:
            dialect = dialect or _DIALECTS[ds_type.lower()]
        except KeyError as exc:
            raise ValueError(f"Unsupported datasource type: {ds_type}") from exc

    try:
        statements = sqlglot.parse(sql, read=dialect)
        if len(statements) != 1 or not isinstance(
            statements[0], (exp.Select, exp.SetOperation)
        ):
            raise ValueError("Only one SELECT statement is allowed")
        query = statements[0]
        if next(query.find_all(exp.DML, exp.DDL, exp.Into, exp.Lock), None):
            raise ValueError("SQL contains a write or locking operation")

        parsed_filters: dict[str, list[exp.Expression]] = {}
        for item in filters:
            name, predicate = item["table"], item["filter"]
            if not name or not predicate:
                raise ValueError("Row filter needs a table and condition")
            parsed = sqlglot.parse(f"SELECT 1 WHERE {predicate}", read=dialect)
            if len(parsed) != 1 or not isinstance(parsed[0], exp.Select):
                raise ValueError("Invalid row filter")
            where = parsed[0].args.get("where")
            if where is None or next(
                where.find_all(
                    exp.Query, exp.Table, exp.DML, exp.DDL, exp.Command, exp.Func
                ),
                None,
            ):
                raise ValueError("Unsafe row filter")
            if any(column.table for column in where.find_all(exp.Column)):
                raise ValueError("Row filter columns must be unqualified")
            parsed_filters.setdefault(name, []).append(where.this)

        sources: list[exp.Table] = []
        for scope in traverse_scope(query):
            for _, source in scope.selected_sources.values():
                if isinstance(source, exp.Table):
                    sources.append(source)
        before = Counter(_table_key(source) for source in sources)
        matched: set[str] = set()
        for source in sources:
            names = dict.fromkeys((source.name, _table_key(source)))
            conditions = []
            for name in names:
                if name in parsed_filters:
                    matched.add(name)
                    conditions.extend(parsed_filters[name])
            if not conditions:
                continue

            alias = source.alias_or_name
            if not source.alias and source.db:
                for column in query.find_all(exp.Column):
                    if column.table == source.name and column.db == source.db:
                        column.set("db", None)
                        column.set("catalog", None)
            inner_table = source.copy()
            inner_table.set("alias", None)
            condition = conditions[0].copy()
            for extra in conditions[1:]:
                condition = exp.and_(condition, extra.copy())
            wrapped = (
                exp.select("*")
                .from_(inner_table)
                .where(condition)
                .subquery(alias=alias)
            )
            source.replace(wrapped)

        if matched != set(parsed_filters):
            raise ValueError(
                f"Row filter tables not found: {set(parsed_filters) - matched}"
            )
        rewritten = query.sql(dialect=dialect)
        reparsed = sqlglot.parse_one(rewritten, read=dialect)
        if reparsed != query:
            raise ValueError("Row filter rewrite changed the validated query")
        after = Counter(
            _table_key(source)
            for scope in traverse_scope(reparsed)
            for _, source in scope.selected_sources.values()
            if isinstance(source, exp.Table)
        )
        if before != after:
            raise ValueError("Row filter rewrite changed physical tables")
        return rewritten
    except (sqlglot.errors.SqlglotError, KeyError, AttributeError) as exc:
        raise ValueError(f"Invalid row filter or SQL: {exc}") from exc
