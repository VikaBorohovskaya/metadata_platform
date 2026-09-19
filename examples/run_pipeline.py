"""End-to-end example: seed, harvest, score, report, and gate against Databricks.

Run against a live SQL warehouse:

    METADATA_WAREHOUSE_ID=<id> uv run python examples/run_pipeline.py

Requires a configured Databricks profile (the Databricks SDK picks it up from
the environment). Writes scorecards to ``out/`` and prints the gate result.
"""

from __future__ import annotations

from pathlib import Path

from metadata_platform.config import Policy
from metadata_platform.gate import evaluate_gate
from metadata_platform.harvester import DatabricksSqlExecutor, harvest
from metadata_platform.report import write_report
from metadata_platform.scorer import score_assets
from metadata_platform.seed import seed

POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "metadata_policy.yml"


def main() -> None:
    policy = Policy.load(POLICY_PATH)
    executor = DatabricksSqlExecutor(warehouse_id=policy.require_warehouse())

    print(f"Seeding demo tables in {policy.catalog}.{policy.schema} ...")
    seed(executor, policy)

    print("Harvesting metadata ...")
    assets = harvest(executor, policy)

    scores = score_assets(assets, policy)
    paths = write_report(scores, "out")
    print(f"Scorecards written to {paths['json']} and {paths['markdown']}")

    result = evaluate_gate(scores, policy.min_score)
    print(result.format_report())


if __name__ == "__main__":
    main()
