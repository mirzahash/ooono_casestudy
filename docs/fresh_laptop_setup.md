# Fresh-laptop setup: API → Snowflake → dbt

For macOS/Linux, run commands from the repository root. No notebooks or previous
local data snapshots are needed for the first full extraction. You need valid API
credentials, Snowflake access, Git, Python 3.12, and Python 3.14. The original
ingestion environment was validated on Python 3.14; dbt was validated on 3.12.
This guide documents the setup path; it has not been tested on a second laptop.

## 1. Clone and install

```sh
git clone https://github.com/mirzahash/ooono_casestudy.git
cd ooono_casestudy
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3.12 -m venv .venv-dbt
.venv-dbt/bin/python -m pip install -r requirements-dbt.txt
.venv/bin/python -m pip check
.venv-dbt/bin/python -m pip check
cp -n .env.example .env
```

Repository access is required if it is private. The two environments isolate the
ingestion and dbt dependency sets. No global dbt installation is necessary.

## 2. Configure authentication locally

Edit `.env` with your own values:

```dotenv
OOONO_CLIENT_ID=<API client ID>
OOONO_CLIENT_SECRET=<API client secret>
SNOWFLAKE_ACCOUNT=<organization-account>
SNOWFLAKE_USER=<actual Snowflake LOGIN_NAME>
SNOWFLAKE_ROLE=OOONO_INGESTOR
SNOWFLAKE_WAREHOUSE=OOONO_WH
SNOWFLAKE_DATABASE=OOONO_CASE
SNOWFLAKE_SCHEMA=RAW
SNOWFLAKE_AUTHENTICATOR=SNOWFLAKE_JWT
SNOWFLAKE_PRIVATE_KEY_FILE=/absolute/path/to/encrypted_key.p8
SNOWFLAKE_PRIVATE_KEY_PASSWORD=<key passphrase>
DBT_SNOWFLAKE_ROLE=OOONO_DBT
```

Provide an encrypted PKCS8 RSA private key locally and have a Snowflake
administrator register its matching public key on your user. An existing key may
be transferred securely, or a new pair provisioned; do not overwrite a registered
key without coordinating existing access. Neither keys nor credentials are included
in the repository. Google browser login alone does not configure this key-pair
connection. Use the actual LOGIN_NAME, which can differ from the user object name.

Keep `.env` and private keys out of Git. The wrapper supplies the passphrase to dbt
and creates ignored `dbt/profiles.yml` from the environment-variable template.
See [dbt installation guide](dbt_installation_guide.md#3-configure-local-authentication).

## 3. Provision Snowflake once, if necessary

**Existing configured account:** skip creation/setup if the warehouse, schemas,
tables, and both role assignments already exist for your user. A new laptop alone
does not require recreating them.

**New account:** an authorized administrator can run this in Snowsight. The setup
helpers use these case-study names; they are not arbitrary deployment parameters.

```sql
USE ROLE ACCOUNTADMIN;
CREATE WAREHOUSE IF NOT EXISTS OOONO_WH
    WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;
CREATE DATABASE IF NOT EXISTS OOONO_CASE;
CREATE SCHEMA IF NOT EXISTS OOONO_CASE.RAW;
```

After key registration, run the one-time helpers with an authorized administrator
login configured locally. These create RAW objects and grant the routine roles:

```sh
SNOWFLAKE_ROLE=ACCOUNTADMIN .venv/bin/python scripts/ingest.py setup
.venv/bin/python scripts/setup_dbt.py
```

The second helper selects ACCOUNTADMIN internally for setup. If you do not have
administrator access, have your administrator review `sql/raw_setup.sql`,
`sql/dbt_setup.sql`, and the grants in `scripts/snowflake_io.py`, and provision the
objects and roles for your runtime user. Routine runs use OOONO_INGESTOR and
OOONO_DBT, not ACCOUNTADMIN. Do not place administrator settings in routine jobs.

## 4. Check both connections

```sh
.venv/bin/python scripts/check_snowflake.py --check-config
.venv/bin/python scripts/check_snowflake.py
.venv-dbt/bin/python scripts/run_dbt.py debug
```

Resolve authentication or permission errors before extracting. `debug` checks
connectivity; it does not create analytical models or require a loaded snapshot.

## 5. Run the first end-to-end extraction

```sh
.venv/bin/python scripts/run_pipeline.py --full --run-dir data/pipeline_runs/first_full
```

This fetches all pages of drives, warnings, and users, saves a verified immutable
snapshot, loads Snowflake RAW, and builds/tests all five dbt models. It passes the
new snapshot ID and cutoff explicitly to dbt, without altering project defaults.
It does not need the original laptop's frozen baseline or checkpoint.

A successful run ends with status COMPLETE and records its snapshot/cutoff in
`data/pipeline_state.json`. Review the printed test results and the run artifacts
under `data/pipeline_runs/first_full/`. Known warning-level anomalies remain
visible; unexpected blocking test failures must be investigated.

To resume this same extraction after interruption, repeat the exact command above.
Do not reuse that directory for a genuinely new extraction.

## 6. Run subsequent updates

```sh
.venv/bin/python scripts/run_pipeline.py
```

Normal updates use the last successful local snapshot, a 24-hour receipt overlap
for drives/warnings, and a full users capture. dbt rebuilds its derived tables.
See the [pipeline run guide](pipeline_run_guide.md) for limitations and recovery.

Fresh API data will not necessarily reproduce historical interview counts. Exact
frozen-baseline checks require that original snapshot in Snowflake. Running dbt
`build` without vars selects the checked-in original baseline, not your new one;
on a new account without it, that build will fail the snapshot check. Use the
pipeline command above for updates, or deliberately supply the snapshot/cutoff
from your successful run when invoking dbt separately.

No Steep dashboard or AWS deployment is created by these commands. Building in an
existing account replaces the shared STAGING/ANALYTICS models, so coordinate with
other users of those tables before running.
