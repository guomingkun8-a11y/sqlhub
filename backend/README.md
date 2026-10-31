# SQLHub Backend

FastAPI backend for SQLHub. The service provides chat and analysis workflows, configured datasource access, account and workspace permissions, MCP endpoints, and database migrations.

## Requirements

- Python 3.11
- PostgreSQL
- Model and datasource configuration for the features being used

## Run Locally

Configure the required settings for the local environment, then run:

```powershell
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

## Tests and Migrations

```powershell
uv run pytest -q
uv run alembic heads
uv run alembic history
```

See [`../docs/agents/backend.md`](../docs/agents/backend.md) and [`../docs/agents/testing.md`](../docs/agents/testing.md) for repository conventions.
