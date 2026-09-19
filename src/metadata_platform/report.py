"""Build inspectable scorecards from asset scores.

Produces two artifacts:

    * a per-asset scorecard (JSON) with field-level detail and issues, and
    * an aggregate summary (per-field completeness and overall average),

plus a Markdown rendering for quick human review.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import REQUIRED_FIELDS, AssetScore


def aggregate(scores: list[AssetScore]) -> dict[str, object]:
    """Compute per-field completeness and the overall average score."""
    total = len(scores)
    field_present = {name: 0 for name in REQUIRED_FIELDS}
    for score in scores:
        for result in score.fields:
            if result.present:
                field_present[result.name] += 1

    field_coverage = {
        name: round(field_present[name] / total, 3) if total else 0.0 for name in REQUIRED_FIELDS
    }
    overall = round(sum(score.score for score in scores) / total, 2) if total else 0.0
    return {
        "asset_count": total,
        "overall_average_score": overall,
        "field_coverage": field_coverage,
    }


def build_report(scores: list[AssetScore]) -> dict[str, object]:
    """Assemble the full report payload."""
    return {
        "summary": aggregate(scores),
        "assets": [score.to_dict() for score in scores],
    }


def render_markdown(report: dict[str, object]) -> str:
    """Render the report as a compact Markdown scorecard."""
    summary = report["summary"]
    assets = report["assets"]
    lines = ["# Metadata Scorecard", ""]
    lines.append(f"- Assets scored: **{summary['asset_count']}**")
    lines.append(f"- Overall average score: **{summary['overall_average_score']}/100**")
    lines.append("")
    lines.append("## Field coverage")
    lines.append("")
    lines.append("| Field | Coverage |")
    lines.append("| --- | --- |")
    for name, coverage in summary["field_coverage"].items():
        lines.append(f"| {name} | {coverage * 100:.0f}% |")
    lines.append("")
    lines.append("## Assets")
    lines.append("")
    lines.append("| Asset | Score | Issues |")
    lines.append("| --- | --- | --- |")
    for asset in assets:
        issues = ", ".join(asset["issues"]) if asset["issues"] else "-"
        lines.append(f"| {asset['asset']} | {asset['score']}/100 | {issues} |")
    lines.append("")
    return "\n".join(lines)


def write_report(scores: list[AssetScore], output_dir: str | Path) -> dict[str, Path]:
    """Write ``scorecard.json`` and ``scorecard.md`` to ``output_dir``."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = build_report(scores)

    json_path = out / "scorecard.json"
    md_path = out / "scorecard.md"
    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(render_markdown(report))
    return {"json": json_path, "markdown": md_path}
