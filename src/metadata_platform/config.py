"""Policy configuration loading and validation.

The policy defines the target scope, governed tag names, allowlists, scoring
weights, and the CI gate threshold. Values may be overridden by environment
variables so the same config file works across environments and repositories.

Examples:
    >>> import io, os
    >>> policy = Policy.load(  # doctest: +SKIP
    ...     "config/metadata_policy.yml", env=os.environ
    ... )
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class Policy:
    """Resolved metadata policy for a single run."""

    catalog: str
    schema: str
    warehouse_id: str | None
    host: str | None
    table_owner_tag: str
    table_lifecycle_tag: str
    table_classification_tag: str
    column_pii_classification: str
    pii_column_name_patterns: tuple[str, ...]
    allowed_classifications: tuple[str, ...]
    allowed_lifecycles: tuple[str, ...]
    weights: dict[str, int]
    min_score: float

    @classmethod
    def load(
        cls,
        path: str | Path,
        env: Mapping[str, str] | None = None,
    ) -> "Policy":
        """Load a policy from YAML, applying environment overrides.

        Environment overrides:
            ``METADATA_CATALOG``, ``METADATA_SCHEMA``, ``METADATA_WAREHOUSE_ID``,
            ``METADATA_HOST`` (falls back to ``DATABRICKS_HOST``).
        """
        env = os.environ if env is None else env
        raw: dict[str, Any] = yaml.safe_load(Path(path).read_text()) or {}

        target = raw.get("target", {})
        tags = raw.get("tags", {})
        table_tags = tags.get("table", {})
        column_tags = tags.get("column", {})
        gate = raw.get("gate", {})

        catalog = env.get("METADATA_CATALOG") or target.get("catalog")
        schema = env.get("METADATA_SCHEMA") or target.get("schema")
        warehouse_id = env.get("METADATA_WAREHOUSE_ID") or target.get("warehouse_id")
        host = (
            env.get("METADATA_HOST")
            or env.get("DATABRICKS_HOST")
            or target.get("host")
        )

        policy = cls(
            catalog=str(catalog) if catalog else "",
            schema=str(schema) if schema else "",
            warehouse_id=str(warehouse_id) if warehouse_id else None,
            host=str(host) if host else None,
            table_owner_tag=table_tags.get("owner", "owner"),
            table_lifecycle_tag=table_tags.get("lifecycle", "lifecycle"),
            table_classification_tag=table_tags.get("classification", "classification"),
            column_pii_classification=column_tags.get("classification", "pii"),
            pii_column_name_patterns=tuple(raw.get("pii_column_name_patterns", [])),
            allowed_classifications=tuple(raw.get("allowed_classifications", [])),
            allowed_lifecycles=tuple(raw.get("allowed_lifecycles", [])),
            weights=dict(raw.get("weights", {})),
            min_score=float(gate.get("min_score", 100)),
        )
        policy._validate()
        return policy

    def _validate(self) -> None:
        """Reject malformed identifiers and empty required settings."""
        if not self.catalog or not _IDENTIFIER.match(self.catalog):
            raise ValueError(f"invalid catalog identifier: {self.catalog!r}")
        if not self.schema or not _IDENTIFIER.match(self.schema):
            raise ValueError(f"invalid schema identifier: {self.schema!r}")
        if not self.weights:
            raise ValueError("policy weights must not be empty")
        if any(not pattern.strip() for pattern in self.pii_column_name_patterns):
            raise ValueError("PII column-name patterns must not be empty")

    def require_warehouse(self) -> str:
        """Return the warehouse id or raise a clear error when missing."""
        if not self.warehouse_id:
            raise ValueError(
                "No SQL warehouse configured. Set METADATA_WAREHOUSE_ID or "
                "target.warehouse_id in the policy file."
            )
        return self.warehouse_id
