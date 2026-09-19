"""Tests for the rules-based scorer."""

from __future__ import annotations

from metadata_platform.models import Asset, Column
from metadata_platform.scorer import score_asset


def _complete_asset() -> Asset:
    return Asset(
        catalog="example_catalog",
        schema="example_schema",
        name="demo_orders_complete",
        table_comment="Customer orders with one row for each completed purchase transaction.",
        owner="data-commerce",
        lifecycle="latest",
        classification="internal",
        last_altered="2026-09-19T08:00:00Z",
        columns=[
            Column("order_id", "BIGINT", "Unique identifier assigned to each customer order record"),
            Column("order_total", "DECIMAL", "Total monetary value recorded for the customer order"),
        ],
    )


def test_complete_asset_scores_full(policy) -> None:
    score = score_asset(_complete_asset(), policy)
    assert score.score == 100.0
    assert score.issues == []
    assert score.missing_fields == []


def test_missing_owner_is_flagged(policy) -> None:
    asset = _complete_asset()
    asset.owner = None
    score = score_asset(asset, policy)
    assert "missing_owner" in score.issues
    assert "owner" in score.missing_fields
    assert score.score == 80.0  # 100 - owner weight (20)


def test_partial_column_descriptions_are_proportional(policy) -> None:
    asset = _complete_asset()
    asset.columns = [
        Column("order_id", "BIGINT", "Unique identifier assigned to each customer order record"),
        Column("c_seg", "STRING", None),  # cryptic, undescribed
    ]
    score = score_asset(asset, policy)
    column_field = next(f for f in score.fields if f.name == "column_descriptions")
    assert column_field.present is False
    assert column_field.earned == 10.0  # 20 weight * 0.5 coverage
    assert "missing_column_descriptions" in score.issues


def test_invalid_classification_does_not_earn_points(policy) -> None:
    asset = _complete_asset()
    asset.classification = "secret"  # not in allowlist
    score = score_asset(asset, policy)
    classification_field = next(f for f in score.fields if f.name == "classification")
    assert classification_field.present is False
    assert classification_field.earned == 0.0
    assert "invalid_classification" in score.issues


def test_missing_table_description_and_classification(policy) -> None:
    asset = Asset(
        catalog="example_catalog",
        schema="example_schema",
        name="demo_payments_sparse",
        table_comment=None,
        owner="data-finance",
        lifecycle="prerelease",
        classification=None,
        last_altered="2026-09-19T08:00:00Z",
        columns=[Column("pmt_id", "BIGINT", None)],
    )
    score = score_asset(asset, policy)
    assert "missing_table_description" in score.issues
    assert "missing_classification" in score.issues
    assert score.score < 100.0


def test_fields_carry_observed_provenance(policy) -> None:
    asset = _complete_asset()
    asset.harvested_at = "2026-09-19T08:00:00+00:00"
    score = score_asset(asset, policy)

    owner_field = next(f for f in score.fields if f.name == "owner")
    assert owner_field.value == "data-commerce"
    assert owner_field.provenance is not None
    assert owner_field.provenance.source == "observed"
    assert owner_field.provenance.generated_at == "2026-09-19T08:00:00+00:00"

    serialized = score.to_dict()["fields"][0]
    assert serialized["provenance"]["source"] == "observed"
    assert serialized["provenance"]["approved_by"] is None

