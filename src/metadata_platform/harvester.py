"""Harvest metadata for the target assets from Unity Catalog.

Reads real technical and governed metadata from ``system.information_schema``
through a pluggable SQL executor, then normalizes the rows into :class:`Asset`
records keyed by ``catalog.schema.table``.

The :class:`SqlExecutor` protocol keeps the harvest layer testable offline: the
Databricks implementation is only constructed when running against a live
warehouse, while tests inject a fake executor returning canned rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from .config import Policy
from .models import Asset, Column

_TABLES_SQL = """
SELECT table_catalog, table_schema, table_name, comment, table_owner, last_altered
FROM system.information_schema.tables
WHERE table_catalog = '{catalog}' AND table_schema = '{schema}'
"""

_COLUMNS_SQL = """
SELECT table_catalog, table_schema, table_name, column_name, full_data_type, comment, ordinal_position
FROM system.information_schema.columns
WHERE table_catalog = '{catalog}' AND table_schema = '{schema}'
ORDER BY table_name, ordinal_position
"""

_TAGS_SQL = """
SELECT catalog_name, schema_name, table_name, tag_name, tag_value
FROM system.information_schema.table_tags
WHERE catalog_name = '{catalog}' AND schema_name = '{schema}'
"""

_COLUMN_TAGS_SQL = """
SELECT catalog_name, schema_name, table_name, column_name, tag_name, tag_value
FROM system.information_schema.column_tags
WHERE catalog_name = '{catalog}' AND schema_name = '{schema}'
"""


@runtime_checkable
class SqlExecutor(Protocol):
    """Runs a SQL statement and returns rows as dictionaries."""

    def execute(self, sql: str) -> list[dict[str, Any]]:
        ...


class DatabricksSqlExecutor:
    """SQL executor backed by the Databricks Statement Execution API.

    Uses ``WorkspaceClient().statement_execution.execute_statement`` with the
    ambient Databricks profile; no credentials are read or stored here. An
    optional ``host`` overrides the workspace URL resolved from the profile.
    """

    def __init__(
        self,
        warehouse_id: str,
        client: Any | None = None,
        host: str | None = None,
    ) -> None:
        if client is None:
            from databricks.sdk import WorkspaceClient  # imported lazily

            client = WorkspaceClient(host=host) if host else WorkspaceClient()
        self._client = client
        self._warehouse_id = warehouse_id

    def execute(self, sql: str) -> list[dict[str, Any]]:
        """Execute a statement and return its rows (empty for DDL)."""
        from databricks.sdk.service.sql import StatementState

        response = self._client.statement_execution.execute_statement(
            warehouse_id=self._warehouse_id,
            statement=sql,
            wait_timeout="30s",
        )
        state = response.status.state
        if state != StatementState.SUCCEEDED:
            error = getattr(response.status.error, "message", response.status.error)
            raise RuntimeError(f"statement failed: state={state} error={error}")
        return _rows_to_dicts(response)


def _rows_to_dicts(response: Any) -> list[dict[str, Any]]:
    """Convert a statement-execution response into a list of row dicts."""
    manifest = getattr(response, "manifest", None)
    result = getattr(response, "result", None)
    if manifest is None or result is None:
        return []
    columns = [column.name for column in manifest.schema.columns]
    data = getattr(result, "data_array", None) or []
    return [dict(zip(columns, row)) for row in data]


def harvest(executor: SqlExecutor, policy: Policy) -> list[Asset]:
    """Harvest and normalize assets in the policy's target scope.

    Args:
        executor: SQL executor used to read ``system.information_schema``.
        policy: Active policy providing the target catalog/schema and tag names.

    Returns:
        Assets sorted by name, each populated with the six required fields.
    """
    scope = {"catalog": policy.catalog, "schema": policy.schema}
    harvested_at = datetime.now(timezone.utc).isoformat()
    table_rows = executor.execute(_TABLES_SQL.format(**scope))
    column_rows = executor.execute(_COLUMNS_SQL.format(**scope))
    tag_rows = executor.execute(_TAGS_SQL.format(**scope))
    column_tag_rows = executor.execute(_COLUMN_TAGS_SQL.format(**scope))

    tags_by_column: dict[tuple[str, str], dict[str, str]] = {}
    for row in column_tag_rows:
        key = (row["table_name"], row["column_name"])
        tags_by_column.setdefault(key, {})[row["tag_name"]] = row["tag_value"]

    columns_by_table: dict[str, list[Column]] = {}
    for row in column_rows:
        columns_by_table.setdefault(row["table_name"], []).append(
            Column(
                name=row["column_name"],
                data_type=row.get("full_data_type"),
                comment=row.get("comment"),
                tags=tags_by_column.get((row["table_name"], row["column_name"]), {}),
            )
        )

    tags_by_table: dict[str, dict[str, str]] = {}
    for row in tag_rows:
        tags_by_table.setdefault(row["table_name"], {})[row["tag_name"]] = row["tag_value"]

    assets: list[Asset] = []
    for row in table_rows:
        name = row["table_name"]
        tags = tags_by_table.get(name, {})
        # Governed owner tag takes precedence; fall back to the table owner.
        owner = tags.get(policy.table_owner_tag) or row.get("table_owner")
        assets.append(
            Asset(
                catalog=row["table_catalog"],
                schema=row["table_schema"],
                name=name,
                table_comment=row.get("comment"),
                owner=owner,
                lifecycle=tags.get(policy.table_lifecycle_tag),
                classification=tags.get(policy.table_classification_tag),
                last_altered=row.get("last_altered"),
                columns=columns_by_table.get(name, []),
                harvested_at=harvested_at,
            )
        )

    return sorted(assets, key=lambda asset: asset.name)
