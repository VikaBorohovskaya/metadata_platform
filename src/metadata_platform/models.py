"""Data models for assets and their metadata scores.

Examples:
    >>> asset = Asset(
    ...     catalog="c", schema="s", name="t",
    ...     table_comment="Orders", owner="team", lifecycle="latest",
    ...     classification="internal", last_altered="2026-09-19T08:00:00Z",
    ...     columns=[Column("id", "BIGINT", "Identifier")],
    ... )
    >>> asset.full_name
    'c.s.t'
    >>> asset.column_description_coverage
    1.0
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The six required metadata fields the PoC scores, in report order.
REQUIRED_FIELDS: tuple[str, ...] = (
    "table_description",
    "column_descriptions",
    "owner",
    "lifecycle",
    "last_update",
    "classification",
)


@dataclass(frozen=True)
class Column:
    """A single column and its description."""

    name: str
    data_type: str | None = None
    comment: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def is_described(self) -> bool:
        """Whether the column has a non-empty comment."""
        return bool(self.comment and self.comment.strip())


@dataclass
class Asset:
    """A table asset and the metadata harvested for it."""

    catalog: str
    schema: str
    name: str
    table_comment: str | None = None
    owner: str | None = None
    lifecycle: str | None = None
    classification: str | None = None
    last_altered: str | None = None
    columns: list[Column] = field(default_factory=list)
    harvested_at: str | None = None

    @property
    def full_name(self) -> str:
        """Stable ``catalog.schema.table`` identifier."""
        return f"{self.catalog}.{self.schema}.{self.name}"

    @property
    def column_description_coverage(self) -> float:
        """Fraction of columns that have a description (0.0 when no columns)."""
        if not self.columns:
            return 0.0
        described = sum(1 for column in self.columns if column.is_described)
        return described / len(self.columns)


@dataclass(frozen=True)
class Provenance:
    """Origin stamp for a single metadata value.

    The PoC only reads existing catalog metadata, so harvested values are stamped
    ``source="observed"``. The ``confidence``, ``status`` and ``approved_by``
    fields are the slots an AI suggestion (``source="ai_suggestion"``,
    ``status="pending_review"``) would populate through the disabled extension.
    """

    source: str = "observed"
    status: str = "observed"
    generated_at: str | None = None
    confidence: float | None = None
    approved_by: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize to a plain, JSON-friendly dictionary."""
        return {
            "source": self.source,
            "status": self.status,
            "generated_at": self.generated_at,
            "confidence": self.confidence,
            "approved_by": self.approved_by,
        }


@dataclass(frozen=True)
class FieldResult:
    """Outcome for a single required field on one asset."""

    name: str
    present: bool
    weight: int
    earned: float
    issue: str | None = None
    value: object | None = None
    provenance: Provenance | None = None


@dataclass
class AssetScore:
    """Completeness score and issues for one asset."""

    asset: str
    score: float
    fields: list[FieldResult]
    issues: list[str]

    @property
    def missing_fields(self) -> list[str]:
        """Names of required fields that are absent or invalid."""
        return [result.name for result in self.fields if not result.present]

    def to_dict(self) -> dict[str, object]:
        """Serialize to a plain, JSON-friendly dictionary."""
        return {
            "asset": self.asset,
            "score": self.score,
            "issues": list(self.issues),
            "fields": [
                {
                    "name": result.name,
                    "present": result.present,
                    "weight": result.weight,
                    "earned": round(result.earned, 2),
                    "issue": result.issue,
                    "value": result.value,
                    "provenance": result.provenance.to_dict() if result.provenance else None,
                }
                for result in self.fields
            ],
        }
