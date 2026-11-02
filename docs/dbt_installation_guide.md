# dbt installation and operation

See [fresh-laptop setup](fresh_laptop_setup.md) for API credentials, encrypted
key-pair authentication and one-time Snowflake provisioning.

## Install separately from ingestion

```sh
python3.12 -m venv .venv-dbt
.venv-dbt/bin/python -m pip install -r requirements-dbt.txt
.venv-dbt/bin/python -m pip check
.venv-dbt/bin/dbt --version
```

The validated pins are dbt Core 1.12.6 and dbt-snowflake 1.12.4. Separation preserves
the existing Python 3.14 ingestion environment and connector dependencies.

## Connect, build and test

```sh
.venv-dbt/bin/python scripts/run_dbt.py debug
.venv-dbt/bin/python scripts/run_dbt.py build
```

The wrapper loads local .env, requires OOONO_DBT, supplies the encrypted-key
passphrase through dbt's secret environment variable, and creates an ignored
profiles.yml from placeholders if absent. No secrets are interpolated into YAML.

For standalone build/run/test, it reads the last COMPLETE entry in
RAW.INGESTION_RUNS and passes run_id/receipt_cutoff. Run ingestion first if that
table has no success. The pipeline passes its candidate values explicitly so it
can validate before advancing the successful cutoff. No hardcoded baseline.

Staging models are STAGING views; the intermediate is a STAGING table and the
weekly mart is an ANALYTICS table. RAW is read-only to dbt. The mart grants SELECT
to STEEP_READONLY after rebuilding, preserving reporting access.

Known warning anomalies/orphans are warning-level tests. Conflicts and metric
inconsistencies remain blocking. Complete dbt publication is not atomic; partial
model replacements can remain on failure. Review results before reporting.

`validate_baseline=true` enables fixed historical reference assertions only during
controlled baseline validation. It is not appropriate for arbitrary current data.
Logs: dbt/logs/dbt.log; default artifacts: dbt/target. Pipeline invocations keep
isolated run_results.json under their local run folder's dbt_target directory.
