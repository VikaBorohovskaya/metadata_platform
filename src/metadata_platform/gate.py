"""CI gate: decide whether a set of asset scores meets the required bar.

Examples:
    >>> from metadata_platform.models import AssetScore
    >>> good = AssetScore("c.s.good", 100.0, [], [])
    >>> bad = AssetScore("c.s.bad", 60.0, [], ["missing_owner"])
    >>> evaluate_gate([good, bad], min_score=100).passed
    False
    >>> evaluate_gate([good], min_score=100).passed
    True
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import AssetScore


@dataclass(frozen=True)
class GateResult:
    """Outcome of applying the CI gate to a set of scores."""

    passed: bool
    min_score: float
    failures: list[AssetScore]

    def format_report(self) -> str:
        """Human-readable, actionable summary of any failures."""
        if self.passed:
            return f"PASS: all assets meet the metadata bar (min_score={self.min_score:g})."
        lines = [f"FAIL: {len(self.failures)} asset(s) below the metadata bar (min_score={self.min_score:g}):"]
        for score in self.failures:
            issues = ", ".join(score.issues) if score.issues else "score below threshold"
            lines.append(f"  - {score.asset} (score={score.score:g}): {issues}")
        return "\n".join(lines)


def evaluate_gate(scores: list[AssetScore], min_score: float) -> GateResult:
    """Fail any asset scoring below ``min_score`` or carrying open issues."""
    failures = [score for score in scores if score.score < min_score or score.issues]
    return GateResult(passed=not failures, min_score=min_score, failures=failures)
