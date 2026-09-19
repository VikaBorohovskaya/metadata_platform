"""Tests for classification and lifecycle allowlist validation."""

from __future__ import annotations

from metadata_platform.models import Asset, Column
from metadata_platform.validator import validate_asset, validate_description


def test_valid_values_have_no_issues(policy) -> None:
    asset = Asset(
        catalog="c",
        schema="s",
        name="t",
        classification="confidential",
        lifecycle="latest",
    )
    assert validate_asset(asset, policy) == []


def test_invalid_classification_flagged(policy) -> None:
    asset = Asset(catalog="c", schema="s", name="t", classification="secret")
    assert validate_asset(asset, policy) == ["invalid_classification:secret"]


def test_invalid_lifecycle_flagged(policy) -> None:
    asset = Asset(catalog="c", schema="s", name="t", lifecycle="archived")
    assert validate_asset(asset, policy) == ["invalid_lifecycle:archived"]


def test_missing_values_are_not_validation_issues(policy) -> None:
    # Absent values are handled by scoring, not validation.
    asset = Asset(catalog="c", schema="s", name="t")
    assert validate_asset(asset, policy) == []


def test_description_validation_flags_basic_quality_problems() -> None:
    assert validate_description("todo", "orders") == [
        "description_too_short",
        "placeholder_description",
        "unfinished_description",
    ]
    assert validate_description("orders", "orders") == [
        "description_too_short",
        "description_repeats_name",
    ]


def test_asset_validation_identifies_table_and_column_description_issues(policy) -> None:
    asset = Asset(
        catalog="c",
        schema="s",
        name="orders",
        table_comment="TBD",
        columns=[Column("customer_id", "BIGINT", "description")],
    )
    assert validate_asset(asset, policy) == [
        "table_description_too_short",
        "table_placeholder_description",
        "table_unfinished_description",
        "column:customer_id:description_too_short",
        "column:customer_id:placeholder_description",
    ]


def test_email_column_requires_pii_tag(policy) -> None:
    asset = Asset(
        catalog="c",
        schema="s",
        name="customers",
        columns=[Column("email", "STRING")],
    )
    assert validate_asset(asset, policy) == ["missing_pii_tag:email"]


def test_email_column_with_pii_tag_is_valid(policy) -> None:
    asset = Asset(
        catalog="c",
        schema="s",
        name="customers",
        columns=[Column("primary_email", "STRING", tags={"classification": "pii"})],
    )
    assert validate_asset(asset, policy) == []


def test_configured_pii_column_pattern_requires_pii_tag(policy) -> None:
    asset = Asset(
        catalog="c",
        schema="s",
        name="customers",
        columns=[Column("contact_phone", "STRING")],
    )
    assert validate_asset(asset, policy) == ["missing_pii_tag:contact_phone"]
