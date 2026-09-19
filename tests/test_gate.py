"""Tests for the CI gate over a mocked harvest layer (no live warehouse)."""

from __future__ import annotations

from metadata_platform.gate import evaluate_gate
from metadata_platform.harvester import harvest
from metadata_platform.scorer import score_assets

from .conftest import FakeExecutor


def _table_row(name: str, comment: str | None, owner: str, altered: str) -> dict:
    return {
        "table_catalog": "example_catalog",
        "table_schema": "example_schema",
        "table_name": name,
        "comment": comment,
        "table_owner": owner,
        "last_altered": altered,
    }


def _column_row(table: str, column: str, comment: str | None, position: int) -> dict:
    return {
        "table_catalog": "example_catalog",
        "table_schema": "example_schema",
        "table_name": table,
        "column_name": column,
        "full_data_type": "STRING",
        "comment": comment,
        "ordinal_position": position,
    }


def _tag_row(table: str, tag: str, value: str) -> dict:
    return {
        "catalog_name": "example_catalog",
        "schema_name": "example_schema",
        "table_name": table,
        "tag_name": tag,
        "tag_value": value,
    }


def _executor(*, include_incomplete: bool) -> FakeExecutor:
    tables = [
        _table_row(
            "demo_orders_complete",
            "Customer orders with one row for each completed purchase transaction.",
            "sp",
            "2026-09-19T08:00:00Z",
        )
    ]
    columns = [
        _column_row(
            "demo_orders_complete",
            "order_id",
            "Unique identifier assigned to each customer order record.",
            1,
        )
    ]
    tags = [
        _tag_row("demo_orders_complete", "owner", "data-commerce"),
        _tag_row("demo_orders_complete", "lifecycle", "latest"),
        _tag_row("demo_orders_complete", "classification", "internal"),
    ]

    if include_incomplete:
        tables.append(_table_row("demo_payments_sparse", None, "sp", "2026-09-19T08:00:00Z"))
        columns.append(_column_row("demo_payments_sparse", "amt", None, 1))
        tags.extend(
            [
                _tag_row("demo_payments_sparse", "owner", "data-finance"),
                _tag_row("demo_payments_sparse", "lifecycle", "prerelease"),
            ]
        )

    return FakeExecutor(
        {
            "information_schema.tables": tables,
            "information_schema.columns": columns,
            "information_schema.table_tags": tags,
        }
    )


def test_gate_passes_when_all_complete(policy) -> None:
    assets = harvest(_executor(include_incomplete=False), policy)
    scores = score_assets(assets, policy)
    result = evaluate_gate(scores, policy.min_score)
    assert result.passed is True
    assert result.failures == []


def test_gate_fails_on_missing_metadata(policy) -> None:
    assets = harvest(_executor(include_incomplete=True), policy)
    scores = score_assets(assets, policy)
    result = evaluate_gate(scores, policy.min_score)
    assert result.passed is False
    failed_assets = {failure.asset for failure in result.failures}
    assert "example_catalog.example_schema.demo_payments_sparse" in failed_assets
    report = result.format_report()
    assert "missing_table_description" in report
    assert "missing_classification" in report


def test_harvest_prefers_governed_owner_tag(policy) -> None:
    assets = harvest(_executor(include_incomplete=False), policy)
    asset = assets[0]
    # Owner tag "data-commerce" wins over the table_owner "sp".
    assert asset.owner == "data-commerce"
