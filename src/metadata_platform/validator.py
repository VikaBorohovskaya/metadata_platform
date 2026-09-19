"""Deterministic validation of harvested metadata against policy allowlists.

Validation flags questionable values rather than overwriting them: a value that
is present but outside the approved vocabulary is reported as an issue.

Examples:
    >>> from metadata_platform.config import Policy
    >>> from metadata_platform.models import Asset
    >>> policy = Policy(
    ...     catalog="c", schema="s", warehouse_id=None, host=None,
    ...     table_owner_tag="owner", table_lifecycle_tag="lifecycle",
    ...     table_classification_tag="classification", column_pii_classification="pii",
    ...     allowed_classifications=("public", "internal"),
    ...     allowed_lifecycles=("latest",), weights={"owner": 20}, min_score=100,
    ... )
    >>> validate_asset(Asset("c", "s", "t", classification="secret"), policy)
    ['invalid_classification:secret']
"""

from __future__ import annotations

from .config import Policy
from .models import Asset

PLACEHOLDERS = frozenset({"todo", "tbd", "n/a", "description", "test"})


def validate_description(text: str, object_name: str) -> list[str]:
    """Return basic quality issues for a table or column description."""
    errors: list[str] = []
    normalized = text.strip().lower()
    if len(normalized) < 20:
        errors.append("description_too_short")
    if normalized in PLACEHOLDERS:
        errors.append("placeholder_description")
    if normalized == object_name.lower():
        errors.append("description_repeats_name")
    if "tbd" in normalized or "todo" in normalized:
        errors.append("unfinished_description")
    return errors


def validate_asset(asset: Asset, policy: Policy) -> list[str]:
    """Return validation issues for values outside the approved allowlists.

    A missing value is *not* a validation issue here (that is handled by
    scoring). Only present-but-invalid values are flagged.
    """
    issues: list[str] = []

    classification = (asset.classification or "").strip()
    if classification and classification not in policy.allowed_classifications:
        issues.append(f"invalid_classification:{classification}")

    lifecycle = (asset.lifecycle or "").strip()
    if lifecycle and lifecycle not in policy.allowed_lifecycles:
        issues.append(f"invalid_lifecycle:{lifecycle}")

    if asset.table_comment and asset.table_comment.strip():
        issues.extend(
            f"table_{error}"
            for error in validate_description(asset.table_comment, asset.name)
        )

    for column in asset.columns:
        if column.comment and column.comment.strip():
            issues.extend(
                f"column:{column.name}:{error}"
                for error in validate_description(column.comment, column.name)
            )
        if (
            any(pattern.lower() in column.name.lower() for pattern in policy.pii_column_name_patterns)
            and column.tags.get("classification") != policy.column_pii_classification
        ):
            issues.append(f"missing_pii_tag:{column.name}")

    return issues

 
# DESCRIPTION_RUBRIC_WEIGHTS = {
#     "completeness": 0.20,
#     "semantic_clarity": 0.25,
#     "evidence_consistency": 0.20,
#     "consumer_usefulness": 0.15,
#     "terminology_conformance": 0.10,
#     "freshness": 0.10,
# }
#
# def validate_description_with_llm(
#     client: object,
#     description: str,
#     object_name: str,
#     evidence: dict[str, object],
# ) -> dict[str, object]:
#     """Request a 0-2 rubric scorecard from a LLM provider.
#
#     This is deliberately disabled. Its aggregate score means the description
#     passed this rubric; it does not prove that the description is factually
#     correct. The provider response must be reviewed before any metadata change.
#     """
#     request = {
#         "model": "approved-governance-model",
#         "response_format": {"type": "json_object"},
#         "messages": [
#             {
#                 "role": "system",
#                 "content": (
#                     "Assess metadata descriptions only against supplied evidence. "
#                     "Return JSON with each dimension scored 0, 1, or 2 and a "
#                     "short rationale. Do not claim factual correctness."
#                 ),
#             },
#             {
#                 "role": "user",
#                 "content": {
#                     "object_name": object_name,
#                     "description": description,
#                     "evidence": evidence,
#                     "rubric": {
#                         "completeness": "0 missing or unusable; 1 some context; 2 covers required context",
#                         "semantic_clarity": "0 ambiguous; 1 understandable with effort; 2 clear to target consumers",
#                         "evidence_consistency": "0 contradicts evidence; 1 not fully verified; 2 supported by evidence",
#                         "consumer_usefulness": "0 no usage guidance; 1 basic purpose; 2 includes use, limits, or examples",
#                         "terminology_conformance": "0 inconsistent; 1 partly aligned; 2 uses approved terms",
#                         "freshness": "0 stale; 1 review needed; 2 consistent with current asset",
#                     },
#                 },
#             },
#         ],
#     }
#     response = client.chat.completions.create(**request)
#     return response.choices[0].message.parsed
