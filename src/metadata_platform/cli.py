"""Command-line interface: seed / harvest / report / check.

Commands:
    seed     Create the demo tables in the target schema.
    harvest  Print harvested assets as JSON (debugging).
    report   Harvest, score, and write scorecards to an output directory.
    check    Harvest, score, and fail (exit 1) when required metadata is missing.

All commands read the policy file and resolve the target scope and warehouse
from config plus environment variables.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from .config import Policy
from .gate import evaluate_gate
from .harvester import DatabricksSqlExecutor, SqlExecutor, harvest
from .report import build_report, write_report
from .scorer import score_assets
from .seed import seed

_DEFAULT_POLICY = Path(__file__).resolve().parents[2] / "config" / "metadata_policy.yml"


def _build_executor(policy: Policy) -> SqlExecutor:
    """Construct the live Databricks executor for the configured warehouse."""
    return DatabricksSqlExecutor(
        warehouse_id=policy.require_warehouse(), host=policy.host
    )


def _load_policy(path: str) -> Policy:
    return Policy.load(path)


def _cmd_seed(args: argparse.Namespace) -> int:
    policy = _load_policy(args.policy)
    executed = seed(_build_executor(policy), policy)
    print(f"Seeded {policy.catalog}.{policy.schema}: {', '.join(executed)}")
    return 0


def _cmd_harvest(args: argparse.Namespace) -> int:
    policy = _load_policy(args.policy)
    assets = harvest(_build_executor(policy), policy)
    print(json.dumps([dataclasses.asdict(asset) for asset in assets], indent=2, default=str))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    policy = _load_policy(args.policy)
    assets = harvest(_build_executor(policy), policy)
    scores = score_assets(assets, policy)
    paths = write_report(scores, args.output)
    summary = build_report(scores)["summary"]
    print(f"Wrote {paths['json']} and {paths['markdown']}")
    print(f"Overall average score: {summary['overall_average_score']}/100")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    policy = _load_policy(args.policy)
    assets = harvest(_build_executor(policy), policy)
    scores = score_assets(assets, policy)
    result = evaluate_gate(scores, policy.min_score)
    print(result.format_report())
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="metadata-platform", description=__doc__)
    parser.add_argument(
        "--policy",
        default=str(_DEFAULT_POLICY),
        help="Path to the metadata policy YAML file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Create demo tables in the target schema.").set_defaults(func=_cmd_seed)
    sub.add_parser("harvest", help="Print harvested assets as JSON.").set_defaults(func=_cmd_harvest)

    report_parser = sub.add_parser("report", help="Write scorecards to an output directory.")
    report_parser.add_argument("--output", default="out", help="Output directory (default: out).")
    report_parser.set_defaults(func=_cmd_report)

    sub.add_parser("check", help="Fail when required metadata is missing.").set_defaults(func=_cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point used by the ``metadata-platform`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
