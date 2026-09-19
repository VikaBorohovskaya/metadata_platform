"""Shared test fixtures: an in-memory SQL executor and a base policy."""

from __future__ import annotations

from typing import Any

import pytest

from metadata_platform.config import Policy


class FakeExecutor:
    """In-memory ``SqlExecutor`` that returns canned rows by matching SQL.

    Rows are keyed by a substring expected to appear in the statement (e.g.
    ``information_schema.tables``). DDL statements return an empty list and are
    recorded in :attr:`executed`.
    """

    def __init__(self, rows_by_marker: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._rows = rows_by_marker or {}
        self.executed: list[str] = []

    def execute(self, sql: str) -> list[dict[str, Any]]:
        self.executed.append(sql)
        for marker, rows in self._rows.items():
            if marker in sql:
                return rows
        return []


@pytest.fixture
def policy() -> Policy:
    """A minimal, valid policy with the standard weights and allowlists."""
    return Policy(
        catalog="example_catalog",
        schema="example_schema",
        warehouse_id="wh-123",
        host=None,
        table_owner_tag="owner",
        table_lifecycle_tag="lifecycle",
        table_classification_tag="classification",
        column_pii_classification="pii",
        pii_column_name_patterns=("email", "phone"),
        allowed_classifications=("public", "internal", "confidential", "strictly_confidential"),
        allowed_lifecycles=("latest", "prerelease", "decommissioned"),
        weights={
            "table_description": 20,
            "column_descriptions": 20,
            "owner": 20,
            "lifecycle": 15,
            "last_update": 10,
            "classification": 15,
        },
        min_score=100,
    )
