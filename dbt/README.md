# dbt project

Run from the repository root:

```sh
.venv-dbt/bin/python scripts/run_dbt.py debug
.venv-dbt/bin/python scripts/run_dbt.py build
```

Build uses the latest successful warehouse ingestion cutoff. The full pipeline
supplies candidate run_id/receipt_cutoff variables before marking it successful.

Sources are append-only RAW.DRIVE_REPORTS and WARNING_REPORTS, plus replace-current
USER_PROFILES. No snapshot selection is needed. Staging types reports and collapses
agreeing business payloads; intermediate aggregates warnings before joining drives;
the weekly mart exposes complete-week metrics. Model grains/definitions are in YAML.

The 23-column mart schema is retained for Steep. SNAPSHOT_ID now labels the
analytical run. STEEP_READONLY grants are reapplied by dbt. See
[design](../docs/dbt_design.md), [setup](../docs/fresh_laptop_setup.md), and
[validation](../reports/simplification_validation.md).
