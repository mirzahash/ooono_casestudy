# Fresh laptop: API → Snowflake → dbt

Commands use macOS/Linux shell paths and run from the repository root. Git,
Python 3.14 (ingestion) and Python 3.12 (dbt) are the previously tested versions.
No copied local baseline, snapshot, or checkpoint is needed.

## 1. Clone and install

```sh
git clone https://github.com/mirzahash/ooono_casestudy.git
cd ooono_casestudy
git switch feature/simplify-batch-ingestion
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3.12 -m venv .venv-dbt
.venv-dbt/bin/python -m pip install -r requirements-dbt.txt
cp -n .env.example .env
```

The branch must be pushed before it can be checked out on another laptop.

## 2. Configure authentication

Populate local .env with API credentials and your Snowflake account/login,
warehouse OOONO_WH, database OOONO_CASE, schema RAW, and:

```dotenv
SNOWFLAKE_ROLE=OOONO_INGESTOR
SNOWFLAKE_AUTHENTICATOR=SNOWFLAKE_JWT
SNOWFLAKE_PRIVATE_KEY_FILE=/absolute/path/to/encrypted_key.p8
SNOWFLAKE_PRIVATE_KEY_PASSWORD=<key passphrase>
DBT_SNOWFLAKE_ROLE=OOONO_DBT
```

Provision an encrypted PKCS8 key locally and register its public key on the
Snowflake user, or transfer an existing key securely. Google browser login does
not establish this connector authentication. Use the actual LOGIN_NAME, which
may differ from CURRENT_USER(). Keys and credentials are not included in Git.

## 3. One-time Snowflake setup

If using a new account, an authorized administrator first creates:

```sql
CREATE WAREHOUSE IF NOT EXISTS OOONO_WH
    WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE;
CREATE DATABASE IF NOT EXISTS OOONO_CASE;
CREATE SCHEMA IF NOT EXISTS OOONO_CASE.RAW;
```

Then an administrator-capable login can run:

```sh
.venv/bin/python scripts/setup_dbt.py
```

This additive helper selects ACCOUNTADMIN only for setup. It creates the new RAW
objects, grants ingestion/dbt permissions and prepares STEEP_READONLY usage.
It does not grant the reader role to a Steep user automatically. Existing legacy
snapshot tables and model ownership are not replaced. Skip setup when already
provisioned for your runtime user; ask your administrator if you lack authority.

## 4. Verify and run

```sh
.venv/bin/python scripts/check_snowflake.py --check-config
.venv/bin/python scripts/check_snowflake.py
.venv-dbt/bin/python scripts/run_dbt.py debug
.venv/bin/python scripts/run_pipeline.py
```

With no COMPLETE warehouse run, extraction automatically starts from full history.
It inserts reports once, builds/tests dbt, then saves the successful warehouse
cutoff. Subsequent runs fetch updates, not all history. The full users list is
replaced each time. No notebook is required.

Fresh live data need not match the historical interview counts. The default dbt
build uses the last successful warehouse run; it does not select an old frozen
snapshot. The five model names and final mart schema are unchanged for Steep.

See the [run guide](pipeline_run_guide.md) for recovery, explicit full reconciliation,
limitations and local audit files. Running in a shared account rebuilds shared
STAGING/ANALYTICS models, so coordinate with other users first.
