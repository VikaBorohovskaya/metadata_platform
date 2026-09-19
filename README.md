# Metadata Platform POC

A proof of concept used for improving metadata quality and coverage across the platform by measuring how complete the required metadata is for a
set of Unity Catalog assets, surfacing the gaps as scorecards, and enforcing a minimum bar in CI.

## Required metadata fields

The PoC scores six fields per asset:

1. **Table description** — table-level comment.
2. **Column descriptions** — comment on every column.
3. **Owner** — governed `owner` tag (falls back to the table owner).
4. **Lifecycle** — governed `lifecycle` tag (`latest` / `prerelease` / `decommissioned`).
5. **Last successful update** — `last_altered` from table metadata.
6. **Data classification** — one of `public`, `internal`, `confidential`, `strictly_confidential`.

## Flow

```
seed -> harvest -> score -> report -> gate
```

- **seed** — create three demo tables with mixed metadata.
- **harvest** — read real metadata from `system.information_schema`.
- **score** — transparent rules-based completeness score (0–100) + issues.
- **report** — per-asset and aggregate scorecards (JSON + Markdown).
- **gate** — CI check that fails when required metadata is missing.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and a configured Databricks profile
(the Databricks SDK reads it from the environment). Configure the target scope
and warehouse in [config/metadata_policy.yml](config/metadata_policy.yml) or via
environment variables:

| Variable | Purpose |
| --- | --- |
| `METADATA_WAREHOUSE_ID` | SQL Warehouse used to run statements (required for live commands). |
| `METADATA_HOST` | Databricks workspace URL.
| `METADATA_CATALOG` | Override the target catalog. |
| `METADATA_SCHEMA` | Override the target schema. |

```bash
make install
```

## Usage

```bash
# 1. Create the demo tables (writes only to the target schema)
METADATA_WAREHOUSE_ID=<id> make seed

# 2. Score and write scorecards to ./out
METADATA_WAREHOUSE_ID=<id> make report

# 3. Run the CI gate (exits non-zero on missing metadata)
METADATA_WAREHOUSE_ID=<id> make check
```
## Provenance & idempotency

Every scored field in `scorecard.json` carries a provenance stamp
(`source`, `status`, `generated_at`, `confidence`, `approved_by`). Because the
PoC only reads existing catalog metadata, values are stamped
`source="observed"`; the `confidence`/`status`/`approved_by` slots are where an
AI suggestion (`source="ai_suggestion"`, `status="pending_review"`) would attach
through the disabled extension.

The flow is safe to re-run:

- **Seed** uses `CREATE TABLE IF NOT EXISTS` and idempotent `SET TAGS`, so
  running it twice makes no additional changes.
- **Harvest → score → report** are read-only and deterministic; re-running
  overwrites the scorecard with the same result for unchanged metadata.

## Tests

Tests run fully offline — the harvest layer is mocked, so no warehouse is
required.

```bash
make test
```

## Optional extension 1: AI suggestions (disabled)

`src/metadata_platform/suggester.py` defines a `MetadataSuggester` interface and
a **disabled** `LLMSuggester` stub behind the `ENABLE_AI_SUGGESTIONS` flag. It is
not wired into the flow and performs no write-back; it only marks where
AI-assisted description/classification suggestions would plug in.

## Optional extension 2: AI validation (disabled)

`src/metadata_platform/validator.py`  defines a `validate_description_with_llm` to assess metadata descriptions against supplied evidence.

## Project layout

```
metadata-platform/
├── config/metadata_policy.yml     # scope, allowlists, weights, gate threshold
├── src/metadata_platform/
│   ├── models.py                  # Asset / Column / score models
│   ├── config.py                  # policy loading + validation
│   ├── seed.py                    # create demo tables
│   ├── harvester.py               # read metadata from information_schema
│   ├── validator.py               # allowlist validation
│   ├── scorer.py                  # rules-based completeness score
│   ├── gate.py                    # CI pass/fail decision
│   ├── report.py                  # scorecards (JSON + Markdown)
│   ├── suggester.py               # disabled AI extension point
│   └── cli.py                     # seed / harvest / report / check
├── tests/                         # offline unit tests
└── examples/run_pipeline.py       # end-to-end live example
```
