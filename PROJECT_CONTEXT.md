# OOONO — Release Health Analytics Engineering Case | Project Context

_Last updated: 28 October 2026_

## 1. Assignment and objective

Build a first working version of a **weekly release-health view** for the Head of Product using the CO-DRIVER Events API. The central question is: **Did drivers have a worse experience last week than the week before, and why?**

The solution must be demonstrable during the interview. Choose an appropriate architecture, data model, metrics, and refresh cadence; prioritize a small reliable solution over technical complexity. Explain how it would operate at OOONO, which uses **AWS, Snowflake, dbt, and Steep**.

The Head of Engineering wants faster detection, the CFO wants proportionate cost and an understanding of affected drivers, and the two-person data team needs something maintainable. Avoid equating technical crash-free rate with a good driver experience.

**Delivery requirements:** Code in a public repository or ZIP (exclude virtual environments, data dumps, credentials); README describing execution, assumptions, exclusions, and production deployment; a dashboard or concise findings about the last complete week and recent releases (no slides); live pipeline demo and walkthrough at the 60-minute interview. Submit by 20:00 the day before the interview. API access ends **13 November 2026**. Time budget: approximately **3–4 hours** for the first working slice.

## 2. Current progress — confirmed

- API exploration and full-history profiling are complete. Four notebooks cover exploration, profiling, event counts, and weekly behavior.
- Frozen baseline `e943b3aefc3411575c251ada7404c7013b54bf9510e8d37e9e69bd2f80bf863a` is loaded into Snowflake RAW: 224,200 drives, 315,614 warnings, 3,085 current-state users. A separate SMALL_TEST snapshot remains in RAW; always select the intended snapshot.
- The notebook UTC receipt cutoff is `2026-10-27T15:21:56.773109+00:00`. It selects 224,194 drive reports and 315,601 warnings; six drive and 13 warning receipts after cutoff remain in RAW.
- Canonicalization collapses 4,346 receipt-only repeats to 219,848 sessions, with no business-field conflicts in the baseline. Source records are not deduplicated during ingestion.
- `OOONO_CASE.RAW`, `STAGING`, `ANALYTICS`, and `OOONO_WH` are verified. Ingestion uses OOONO_INGESTOR; transformations use dedicated OOONO_DBT, with SELECT-only RAW access. Encrypted key-pair authentication works. The actual LOGIN_NAME differs from the user object name; use local configuration, not assumptions.
- dbt Core 1.12.6 / dbt-snowflake 1.12.4 run in isolated Python 3.12 `.venv-dbt`. The original Python 3.14 ingestion environment and connector 5.1.0 are unchanged.
- Implemented `stg_drives`, `stg_warnings`, `stg_users` as STAGING views; `int_drive_connection_behavior` as a STAGING table; `mart_weekly_release_health` as an ANALYTICS table. dbt debug and the complete build passed; known orphan/clock warnings remain visible.
- Metric contract and three Product findings are in `reports/metric_definitions.md` and `reports/weekly_findings.md`. Connection behavior is descriptive, not a confirmed failed-drive rate. iOS 6.3.0 counter comparability remains unconfirmed.
- Steep was explored previously but has not been implemented. Do not start it without the user's next instruction.
- Local private files and an unrelated untracked document must not be included in project commits. See Git status before staging.

## 3. Selected architecture

```text
CO-DRIVER Events API
       |
       v
Python extraction (OAuth, cursor pagination, retries)
       |
       v
Snowflake: OOONO_CASE.RAW (drives, warnings, users)
       |
       v
dbt Core + dbt-snowflake (developed in VS Code)
       |
       +--> OOONO_CASE.STAGING (clean, typed source models)
       |
       v
Snowflake: OOONO_CASE.ANALYTICS (drive-level and weekly metrics)
       |
       v
Steep (weekly release-health dashboard)
```

**Responsibilities:** Python ingests; Snowflake stores raw and modelled data; dbt compiles, runs, documents, and tests transformations **inside Snowflake** (dbt does not host tables); Steep queries Snowflake through a supported connector and appropriate permissions. Git/VS Code are used for development and version control.

**Trade-off:** This stack aligns directly with OOONO's tools but adds cloud connectivity and credentials to a laptop demo. Keep an exported local summary or findings document as a demo fallback. Avoid adding AWS deployment, streaming, Terraform, CI/CD, or an elaborate dashboard to the MVP.

**Production mapping:** Schedule Python extraction with an existing AWS service (e.g., Lambda/ECS + scheduler), load Snowflake raw tables, run dbt on Snowflake, and serve Steep. Discuss incremental loads, late-arriving events, observability, security, permissions, and cost without implementing a full production platform.

## 4. API access and security

- Base URL: `https://qw7ytrkpd3swtndax6c4a73oua0mcrky.lambda-url.eu-west-1.on.aws`
- Documentation: `https://qw7ytrkpd3swtndax6c4a73oua0mcrky.lambda-url.eu-west-1.on.aws/docs`
- OAuth credentials originate in the assignment PDF. Keep them only in `.env` or a secure local credential store; never commit, print, or place them in notebooks or documentation.
- Store Snowflake credentials securely in environment variables or local dbt `profiles.yml` excluded from the repository. Use least-privilege roles for ingestion, dbt, and Steep where practical.
- API is live; records may arrive late or be revised. Respect pagination, timeouts, retries, and sensible rate limits.

## 5. Product metric strategy — validate against profiling

**Primary outcome:** A defensible drive-experience metric for the last **complete Monday–Sunday week**, compared with the preceding complete week. Do **not** label drives as 'bad' until a valid failure/interruption signal is established from the API and Data Profiling notebook.

Candidate supporting metrics, only if fields and semantics permit:

- Eligible drives and distinct drivers, week over week.
- Bad/interrupted drive rate and affected driver count, if a valid definition can be established.
- Warning or interaction behaviour as context, not automatically a proxy for product failure.
- Differences by app version/release, platform, device, and country; show denominators and avoid attributing correlation to a release without evidence.
- Data freshness, late-arrival volume, missingness, and other quality signals where relevant.

Document for each KPI: business meaning, numerator, denominator, exclusions, event-time column, timezone, week boundary, treatment of incomplete sessions, and limitations. Use event time for reporting and received/ingestion time for ingestion watermarks when supported. Avoid interpreting a low warning count as proof of a healthier app.

## 6. Current project structure

```text
OOONO-CaseStudy/
├── dbt/                        # dbt project root
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── models/
│   │   ├── staging/ooono/
│   │   ├── intermediate/
│   │   └── marts/
│   ├── macros/
│   └── tests/
├── scripts/                    # ingestion, connection, dbt runner
├── sql/                        # one-time role/RAW setup
├── tests/test_ingestion.py     # Python invariants
├── reports/
├── docs/
├── 01_api_exploration.ipynb
├── 02_data_profiling.ipynb
├── 03_event_counts.ipynb
├── 04_weekly_connection_behavior.ipynb
├── requirements.txt
├── requirements-dbt.txt
└── .env.example
```

Ignored local inputs include `.env`, environments, keys/data snapshots, and dbt
profile/output/log files. `scripts/run_dbt.py` selects `dbt/` explicitly.

## 7. Next steps after validated dbt

1. Review `reports/dbt_validation.md` and the five implemented models with the candidate.
2. Keep the default snapshot/cutoff pinned; change them only with explicit dbt vars. Never automatically choose the latest snapshot.
3. When the user authorizes reporting, connect Steep with read-only access to ANALYTICS and expose the weekly mart with honest connection-behavior labels.
4. Prepare the short live demo and local aggregate fallback; explain iOS instrumentation and timestamp limitations.
5. Commit/push only relevant reviewed files, excluding credentials, data dumps, notebook outputs, unrelated files, dbt logs, and targets.

## 8. Important engineering decisions

- **Deduplication:** Confirm stable IDs and source uniqueness; avoid inventing composite keys without evidence.
- **Late arrivals:** Separate occurrence time from API received/ingested time. Consider a lookback window and idempotent merges; explain limitations for older backfills.
- **Session outcomes:** Do not call missing end timestamps failures until checking ongoing drives and ingestion lag.
- **Version comparisons:** Avoid comparing unlike populations or small samples without caveats.
- **Refresh frequency:** A daily ingestion and Monday weekly summary is a reasonable *proposal*, not yet a committed design. Explain why real-time monitoring is outside MVP scope.
- **Cost:** XSMALL warehouse, auto-suspend, small bounded extracts, and compact marts; do not assume trial credits are unlimited.
- **Privacy:** Do not publish raw user-level data, access tokens, Snowflake secrets, or full API extracts.

## 9. How Codex should collaborate

Act as a pragmatic senior Analytics Engineer pairing with a candidate. Read this file, the relevant notebooks, and the validation documents before changing code. Work in small, reviewable steps, state expected effort and trade-offs, distinguish observed facts from hypotheses, and avoid creating unnecessary infrastructure. Prioritize a trustworthy Head-of-Product weekly answer. Ask before choosing a business definition unsupported by data. Check `.gitignore` and credential handling before commits. End with a concise README, two or three defensible findings, and a 5–10 minute demo narrative.

**Immediate next action:** Review the completed dbt validation with the user. Do not start Steep yet.
