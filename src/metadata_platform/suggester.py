"""Optional AI-suggestion extension point (DISABLED).

This module defines the interface for AI/LLM assisted metadata suggestions but
is intentionally **not** wired into the demo flow. It documents where an
LLM-backed suggester would plug in without generating suggestions or writing
anything back to Unity Catalog.

Enable deliberately, behind the feature flag, once a provider is configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import Asset

# Feature flag: keep AI suggestions off by default. The demo flow never reads
# this; it exists to mark the extension point.
ENABLE_AI_SUGGESTIONS = False


@dataclass(frozen=True)
class Suggestion:
    """A proposed metadata value, carrying provenance for later review."""

    field: str
    value: str
    confidence: float
    source: str = "ai_suggestion"
    status: str = "pending_review"
    approved_by: str | None = None


class MetadataSuggester(Protocol):
    """Provider interface for generating metadata suggestions for an asset."""

    def suggest(self, asset: Asset) -> list[Suggestion]:
        ...


# class LLMSuggester:
#     """Suggest table/column descriptions and a classification via an LLM."""
#
#     def __init__(self, client: object) -> None:
#         self._client = client
#
#     def suggest(self, asset: Asset) -> list[Suggestion]:
#         # Build a prompt from the asset's schema and cryptic column names,
#         # call the provider, and map the response to Suggestion records with a
#         # confidence and status="pending_review". Never write back here.
#         raise NotImplementedError("AI suggestions are disabled in the PoC.")
