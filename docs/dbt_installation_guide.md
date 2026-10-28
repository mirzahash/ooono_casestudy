# dbt Core installation and setup guide

This guide covers the existing OOONO case-study project on macOS/Linux. Run every
command from the repository root, which contains `requirements-dbt.txt` and
`scripts/`. The dbt project itself lives in `dbt/`.

The project is already installed and validated on this laptop. To use that
installation, go directly to step 5. Do not recreate environments or keys merely
to run the existing project.

## 1. Prerequisites

- Python 3.12 and Git installed.
- Access to the Snowflake account and `OOONO_WH` warehouse.
- Existing `OOONO_CASE.RAW` source tables and the approved completed snapshot.
- A registered Snowflake public key and its matching encrypted PKCS8 private key
  stored locally. Keys and credentials are not supplied in this repository.

Check Python:

```sh
python3.12 --version
```

This project's tested combination is Python 3.12.11, dbt Core 1.12.6, and
`dbt-snowflake` 1.12.4. Pinning is recorded in `requirements-dbt.txt`.

## 2. Install into an isolated environment

On a new machine, create the dbt environment separately from ingestion:

```sh
python3.12 -m venv .venv-dbt
.venv-dbt/bin/python -m pip install -r requirements-dbt.txt
.venv-dbt/bin/python -m pip check
.venv-dbt/bin/dbt --version
```

Expected versions: Core **1.12.6** and Snowflake adapter **1.12.4**.

Activation is optional because these commands use explicit executable paths.
Installing the adapter also installs its compatible Snowflake connector. The
validated dbt environment uses connector 4.8.1; the existing ingestion `.venv`
continues using connector 5.1.0. Do not install the dbt requirements into `.venv`.

## 3. Configure local authentication

If `.env` already exists, edit it and preserve its existing API/ingestion settings.
Only on a new checkout without `.env`, copy the template:

```sh
cp -n .env.example .env
```

Set the following locally; these are examples/placeholders, not credentials:

```dotenv
SNOWFLAKE_ACCOUNT=<organization-account>
SNOWFLAKE_USER=<actual_LOGIN_NAME>
SNOWFLAKE_WAREHOUSE=OOONO_WH
SNOWFLAKE_DATABASE=OOONO_CASE
SNOWFLAKE_SCHEMA=RAW
SNOWFLAKE_ROLE=OOONO_INGESTOR
SNOWFLAKE_AUTHENTICATOR=SNOWFLAKE_JWT
SNOWFLAKE_PRIVATE_KEY_FILE=/absolute/path/to/encrypted_key.p8
SNOWFLAKE_PRIVATE_KEY_PASSWORD=<local_key_passphrase>
DBT_SNOWFLAKE_ROLE=OOONO_DBT
```

Use the actual Snowflake `LOGIN_NAME`, which can differ from the user object name
returned by `CURRENT_USER()`. Register the matching public key on that user before
connecting. Google sign-in to Snowsight does not itself configure connector SAML SSO.

The current dbt profile uses encrypted key-pair authentication. The wrapper reads
the passphrase from local `.env` and passes it through
`DBT_ENV_SECRET_KEY_PASSPHRASE`, which dbt treats as secret. Unlike the ingestion
connection helper, this wrapper does not prompt for a missing key passphrase.
Keep `.env` and the private key outside version control.

The wrapper creates ignored `dbt/profiles.yml` from
`dbt/profiles.yml.example` if absent. The YAML contains `env_var` references, not
embedded credential values. You do not need to run `dbt init`: the project is
already initialized in `dbt/dbt_project.yml`.

## 4. One-time Snowflake role setup

**Already complete for the current account.** Skip this for normal builds.

For a new account, an authorized setup administrator must first provide the
warehouse, database, validated RAW sources, and registered key. Review
`sql/dbt_setup.sql`. It creates/reuses STAGING and ANALYTICS, creates OOONO_DBT,
and grants source read/model creation permissions.

The existing setup helper runs from the ingestion environment and uses ACCOUNTADMIN
only for administration:

```sh
.venv/bin/python scripts/setup_dbt.py
```

On a new checkout, that command requires the ingestion `.venv` and dependencies
from `requirements.txt`; it is not a prerequisite for a user whose role is already
provisioned. The helper targets this case's `OOONO_CASE` / `OOONO_WH` names.

Routine dbt commands use **OOONO_DBT**, never ACCOUNTADMIN. The role has SELECT
on the four RAW tables, usage on warehouse/database/schemas, and CREATE TABLE /
CREATE VIEW on STAGING and ANALYTICS. Ingestion keeps OOONO_INGESTOR independently.

## 5. Verify connectivity

```sh
.venv-dbt/bin/python scripts/run_dbt.py debug
```

Expected output includes:

```text
role: OOONO_DBT
Connection test: OK connection ok
All checks passed!
```

The wrapper loads repository `.env`, supplies `dbt/` as project/profile directory,
and uses the isolated dbt executable. Prefer it over calling bare `dbt` because
bare dbt does not automatically load `.env`.

## 6. Build and test

```sh
.venv-dbt/bin/python scripts/run_dbt.py build
```

The five models are:

| Model | Location in Snowflake |
| --- | --- |
| stg_drives | OOONO_CASE.STAGING |
| stg_warnings | OOONO_CASE.STAGING |
| stg_users | OOONO_CASE.STAGING |
| int_drive_connection_behavior | OOONO_CASE.STAGING |
| mart_weekly_release_health | OOONO_CASE.ANALYTICS |

For the default baseline, the validated result is **5 models, 26 passing data
tests, 2 expected warning tests, and 0 errors**. dbt's summary counts models too:
`PASS=31 WARN=2 ERROR=0 SKIP=0`. The warnings expose 150 anomalous warning clocks
and 152 orphan warnings. They are retained rather than silently deleted.

Full builds replace dbt-owned derived models. RAW data is read-only and unchanged.
See [dbt validation](../reports/dbt_validation.md) for exact reconciled counts.

## 7. Understand the analytical baseline

`dbt/dbt_project.yml` defaults to the approved full snapshot and UTC receipt cutoff:

- Snapshot: `e943b3aefc3411575c251ada7404c7013b54bf9510e8d37e9e69bd2f80bf863a`.
- Cutoff: `2026-10-27T15:21:56.773109+00:00`.

The project does not automatically select a newer snapshot or call the API.
To intentionally use another completed full baseline:

```sh
.venv-dbt/bin/python scripts/run_dbt.py build --vars '{"snapshot_id":"<64_character_snapshot_id>","receipt_cutoff":"<ISO_8601_UTC_timestamp>"}'
```

Replace both placeholders with real values. Generic tests still run, but exact
notebook-reference tests apply only to the original default ID/cutoff. A new
baseline needs its own reference reconciliation.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `dbt: command not found` | Use `.venv-dbt/bin/dbt` or the wrapper, not a global installation. |
| Missing environment variable | Populate local `.env` and run through the wrapper. |
| `JWT_TOKEN_INVALID_USER_IN_ISSUER` | Confirm the actual LOGIN_NAME, not just the user object name. |
| Invalid key/passphrase | Check the encrypted PKCS8 file path, local passphrase, and registered public-key fingerprint. |
| Permission/schema errors | Confirm OOONO_DBT assignment and the grants in `sql/dbt_setup.sql`. |
| Missing/not-complete snapshot | Load the approved frozen snapshot first; do not switch automatically to another one. |
| Unexpected reference-count failure | Stop and inspect snapshot, cutoff, and source data; do not change definitions to force a pass. |

Ignored local artifacts are `.venv-dbt/`, `dbt/profiles.yml`, `dbt/target/`,
`dbt/logs/`, and `dbt/dbt_packages/`. Do not commit them or private keys.

## References

- [dbt Python compatibility](https://docs.getdbt.com/faqs/Core/install-python-compatibility)
- [Snowflake adapter setup](https://docs.getdbt.com/docs/local/connect-data-platform/snowflake-setup?version=1.12)
- [Connection profiles](https://docs.getdbt.com/docs/core/connect-data-platform/connection-profiles)
- [This project's layout](../dbt/README.md)
