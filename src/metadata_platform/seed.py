"""Seed three demo tables with deliberately mixed metadata quality.

The tables are created only in the policy's target schema and are safe to run
repeatedly (``CREATE TABLE IF NOT EXISTS`` plus idempotent tag assignment):

    * ``demo_orders_complete``  - complete metadata (the good example).
    * ``demo_customers_partial`` - missing owner and one column description.
    * ``demo_payments_sparse``  - missing table description and classification.

``last_altered`` is maintained automatically by Unity Catalog, so the sixth
field is populated for every seeded table without extra work.
"""

from __future__ import annotations

from .config import Policy
from .harvester import SqlExecutor


def _statements(catalog: str, schema: str) -> list[tuple[str, str]]:
    """Build the ordered (label, SQL) pairs that seed the demo tables."""
    prefix = f"{catalog}.{schema}"
    return [
        ("create schema", f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}"),
        # 1. Fully complete table.
        (
            "create demo_orders_complete",
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}.demo_orders_complete (
                order_id BIGINT COMMENT 'Unique identifier for the order; use to join order-level records.',
                customer_id BIGINT COMMENT 'Unique identifier for the customer who placed the order; use for customer-level analysis.',
                total DECIMAL(12, 2) COMMENT 'Total amount recorded for the order; use to calculate order value and sales metrics.'
            )
            COMMENT 'Completed customer orders, with one row per order. Use for order volume, sales, and customer purchase analysis.'
            """,
        ),
        (
            "tag demo_orders_complete",
            f"ALTER TABLE {prefix}.demo_orders_complete "
            "SET TAGS ('owner' = 'data-commerce', 'lifecycle' = 'latest', 'classification' = 'internal')",
        ),
        # 2. Missing owner tag; some columns lack descriptions.
        (
            "create demo_customers_partial",
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}.demo_customers_partial (
                customer_id BIGINT COMMENT 'Unique identifier of the customer',
                email STRING,
                segment STRING
            )
            COMMENT 'Customer records.'
            """,
        ),
        (
            "tag demo_customers_partial",
            f"ALTER TABLE {prefix}.demo_customers_partial "
            "SET TAGS ('lifecycle' = 'latest', 'classification' = 'confidential')",
        ),
        (
            "classify demo_customers_partial.email as PII",
            f"ALTER TABLE {prefix}.demo_customers_partial ALTER COLUMN email "
            "SET TAGS ('classification' = 'pii')",
        ),
        # 3. Missing table description and classification; cryptic columns.
        (
            "create demo_payments_sparse",
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}.demo_payments_sparse (
                pmt_id BIGINT,
                customer_id BIGINT,
                amount DECIMAL(12, 2)
            )
            """,
        ),
        (
            "tag demo_payments_sparse",
            f"ALTER TABLE {prefix}.demo_payments_sparse "
            "SET TAGS ('owner' = 'data-finance', 'lifecycle' = 'prerelease')",
        ),
    ]


def seed(executor: SqlExecutor, policy: Policy) -> list[str]:
    """Create the demo tables and return the labels of executed statements."""
    executed: list[str] = []
    for label, sql in _statements(policy.catalog, policy.schema):
        executor.execute(sql)
        executed.append(label)
    return executed
