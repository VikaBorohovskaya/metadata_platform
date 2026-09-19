"""Transparent, rules-based metadata completeness scoring.

Each of the six required fields contributes its configured weight when present
and valid. Column descriptions contribute proportionally to their coverage. The
result carries an explicit, human-readable list of issues per asset.

Examples:
    >>> from metadata_platform.config import Policy
    >>> from metadata_platform.models import Asset, Column
    >>> policy = Policy(
    ...     catalog="c", schema="s", warehouse_id=None, host=None,
    ...     table_owner_tag="owner", table_lifecycle_tag="lifecycle",
    ...     table_classification_tag="classification", column_pii_classification="pii",
    ...     allowed_classifications=("internal",), allowed_lifecycles=("latest",),
    ...     weights={
    ...         "table_description": 20, "column_descriptions": 20, "owner": 20,
    ...         "lifecycle": 15, "last_update": 10, "classification": 15,
    ...     },
    ...     min_score=100,
    ... )
    >>> asset = Asset(
    ...     "c", "s", "t", table_comment="Orders", owner="team",
    ...     lifecycle="latest", classification="internal",
    ...     last_altered="2026-09-19", columns=[Column("id", "BIGINT", "Id")],
    ... )
    >>> score_asset(asset, policy).score
    100.0
"""

from __future__ import annotations

from dataclasses import replace

from .config import Policy
from .models import Asset, AssetScore, FieldResult, Provenance
from .validator import validate_asset


def _field(name: str, present: bool, weight: int, earned: float, issue: str | None) -> FieldResult:
    return FieldResult(name=name, present=present, weight=weight, earned=earned, issue=issue)


def score_asset(asset: Asset, policy: Policy) -> AssetScore:
    """Score a single asset across the six required fields.

    Args:
        asset: The harvested asset.
        policy: The active policy providing weights and allowlists.

    Returns:
        An :class:`AssetScore` with per-field results and an issue list.
    """
    weights = policy.weights
    validation_issues = validate_asset(asset, policy)
    invalid_classification = any(i.startswith("invalid_classification") for i in validation_issues)
    invalid_lifecycle = any(i.startswith("invalid_lifecycle") for i in validation_issues)
    invalid_table_description = any(
        issue.startswith("table_description_")
        or issue == "table_placeholder_description"
        or issue == "table_unfinished_description"
        for issue in validation_issues
    )
    invalid_column_descriptions = {
        issue.split(":", 2)[1]
        for issue in validation_issues
        if issue.startswith("column:")
    }

    results: list[FieldResult] = []

    # 1. Table description.
    weight = weights.get("table_description", 0)
    present = bool(asset.table_comment and asset.table_comment.strip()) and not invalid_table_description
    results.append(
        _field(
            "table_description",
            present,
            weight,
            weight if present else 0.0,
            None if present else "invalid_table_description" if asset.table_comment else "missing_table_description",
        )
    )

    # 2. Column descriptions (coverage-weighted).
    weight = weights.get("column_descriptions", 0)
    valid_columns = [
        column
        for column in asset.columns
        if column.is_described and column.name not in invalid_column_descriptions
    ]
    coverage = len(valid_columns) / len(asset.columns) if asset.columns else 0.0
    present = bool(asset.columns) and coverage >= 1.0
    if not asset.columns:
        issue: str | None = "no_columns"
    elif not present:
        issue = "missing_column_descriptions"
    else:
        issue = None
    results.append(_field("column_descriptions", present, weight, weight * coverage, issue))

    # 3. Owner.
    weight = weights.get("owner", 0)
    present = bool(asset.owner and asset.owner.strip())
    results.append(
        _field("owner", present, weight, weight if present else 0.0, None if present else "missing_owner")
    )

    # 4. Lifecycle (present requires a value that is also in the allowlist).
    weight = weights.get("lifecycle", 0)
    has_value = bool(asset.lifecycle and asset.lifecycle.strip())
    present = has_value and not invalid_lifecycle
    issue = None
    if not present:
        issue = "invalid_lifecycle" if invalid_lifecycle else "missing_lifecycle"
    results.append(_field("lifecycle", present, weight, weight if present else 0.0, issue))

    # 5. Last successful update.
    weight = weights.get("last_update", 0)
    present = bool(asset.last_altered and str(asset.last_altered).strip())
    results.append(
        _field(
            "last_update",
            present,
            weight,
            weight if present else 0.0,
            None if present else "missing_last_update",
        )
    )

    # 6. Data classification (present requires a value that is also valid).
    weight = weights.get("classification", 0)
    has_value = bool(asset.classification and asset.classification.strip())
    present = has_value and not invalid_classification
    issue = None
    if not present:
        issue = "invalid_classification" if invalid_classification else "missing_classification"
    results.append(_field("classification", present, weight, weight if present else 0.0, issue))

    # Stamp each field with its observed value and provenance. The PoC only reads
    # existing catalog metadata, so every value is source="observed".
    observed_values: dict[str, object | None] = {
        "table_description": asset.table_comment,
        "column_descriptions": round(asset.column_description_coverage, 2),
        "owner": asset.owner,
        "lifecycle": asset.lifecycle,
        "last_update": asset.last_altered,
        "classification": asset.classification,
    }
    provenance = Provenance(generated_at=asset.harvested_at)
    results = [
        replace(result, value=observed_values.get(result.name), provenance=provenance)
        for result in results
    ]

    score = round(sum(result.earned for result in results), 2)
    issues = [result.issue for result in results if result.issue]
    return AssetScore(asset=asset.full_name, score=score, fields=results, issues=issues)


def score_assets(assets: list[Asset], policy: Policy) -> list[AssetScore]:
    """Score every asset, preserving input order."""
    return [score_asset(asset, policy) for asset in assets]
