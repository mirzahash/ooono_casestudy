# OOONO — Release Health Analytics Engineering Case | Project Context

_Last updated: 25 October 2026_

## 1. Assignment and objective

Build a first working version of a **weekly release-health view** for the Head of Product using the CO-DRIVER Events API. The central question is: **Did drivers have a worse experience last week than the week before, and why?**

The solution must be demonstrable during the interview. Choose an appropriate architecture, data model, metrics, and refresh cadence; prioritize a small reliable solution over technical complexity. Explain how it would operate at OOONO, which uses **AWS, Snowflake, dbt, and Steep**.

The Head of Engineering wants faster detection, the CFO wants proportionate cost and an understanding of affected drivers, and the two-person data team needs something maintainable. Avoid equating technical crash-free rate with a good driver experience.

**Delivery requirements:** Code in a public repository or ZIP (exclude virtual environments, data dumps, credentials); README describing execution, assumptions, exclusions, and production deployment; a dashboard or concise findings about the last complete week and recent releases (no slides); live pipeline demo and walkthrough at the 60-minute interview. Submit by 20:00 the day before the interview. API access ends **13 November 2026**. Time budget: approximately **3–4 hours** for the first working slice.

## 2. Current progress — confirmed

- Reviewed the case assignment and API documentation.
- Identified three API resources: **drives**, **warnings**, **users**.
- Confirmed OAuth authentication with approximately one-hour access tokens and cursor-based pagination. The first request after inactivity may be slow.
- Created a local Python environment (`.venv`, `requirements.txt`, `.env`, `.env.example`, `.gitignore`) with secrets excluded from Git.
- Created **two notebooks**: **Data Exploration** and **Data Profiling**. Data Exploration has been used to request and inspect small samples (five records per endpoint). Data Profiling has been created; its specific checks, outputs, and findings should be read from the notebook before claiming they are complete or validated.
- Observed drives fields including session/user identifiers, platform, app version, device, country, start/end times, duration, connection count, and received time. Observed warnings fields include warning/session/user identifiers, warning type, device time, user action, and received time. Verify exact column names in the notebooks; do not infer undocumented fields.
- Created a **Snowflake account** and selected Snowflake as the project warehouse rather than the originally proposed DuckDB approach.
- Opened Snowflake **Projects → Workspaces → Add new → SQL file** and prepared setup SQL for database `OOONO_CASE`, schemas `RAW`, `STAGING`, `ANALYTICS`, and warehouse `OOONO_WH` (XSMALL, 60-second auto-suspend). **Verify these objects actually exist before treating setup as complete.**
- Created a **Steep account** and explored its data-source connection interface. The intended reporting integration is **Steep → Snowflake analytics models**; connection and dashboard are not yet confirmed complete.
- **No dbt models or Snowflake ingestion pipeline have been confirmed as built.**

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

## 6. Intended project structure

Adapt filenames to the two notebooks that already exist; do not rename or overwrite them blindly.

```text
ooono-release-health/
├── PROJECT_CONTEXT.md
├── README.md
├── .env                       # local only; excluded from Git
├── .env.example               # variable names/placeholders only
├── .gitignore
├── requirements.txt
├── notebooks/
│   ├── <existing Data Exploration notebook>.ipynb
│   └── <existing Data Profiling notebook>.ipynb
├── scripts/
│   └── ingest.py
├── dbt_project.yml             # if dbt project lives at repository root
├── models/
│   ├── staging/
│   │   ├── stg_drives.sql
│   │   ├── stg_warnings.sql
│   │   └── stg_users.sql
│   └── marts/
│       ├── fct_drive_experience.sql       # only if justified
│       └── fct_weekly_release_health.sql
└── reports/
    └── findings.md
```

The above is a **target layout**, not a claim that all files exist. Keep raw extracts and credentials out of the submitted repository.

## 7. Next implementation steps

1. **Verify Snowflake setup**: Confirm `OOONO_CASE`, `RAW`, `STAGING`, `ANALYTICS`, and `OOONO_WH` exist and the active role has permissions. If absent, create them in a SQL file in Snowflake Workspaces.
2. **Review Data Profiling results**: Inspect completeness, duplicates, session integrity, timestamp consistency, available failure signals, and app-version coverage. Record findings and unresolved questions before fixing metrics.
3. **Build repeatable ingestion**: Convert exploratory API calls into a small Python ingestion script with OAuth renewal, cursor pagination, retries, a bounded time window, and safe reruns. Load `RAW` tables in Snowflake; retain source timestamps and ingestion timestamp.
4. **Configure local dbt Core**: Install `dbt-snowflake`, configure a secure Snowflake profile, and run `dbt debug`. Create `sources.yml` for raw tables.
5. **Create models and tests**: Build three staging models; then the minimum drive-level model needed to support the selected KPI and one weekly mart. Test uniqueness/not-null where justified, accepted values, timestamp sanity, and reconciliation to raw source counts.
6. **Connect Steep**: Connect Steep to Snowflake with read access to the analytics schema; use the final mart for the weekly release-health view. Keep visuals compact and readable.
7. **Validate findings and demo**: Check the last complete week versus previous week, version/platform differences, data freshness, and 2–3 evidence-based takeaways. Document known limitations and rehearse a short live run. Prepare a local fallback in case cloud connectivity fails.

## 8. Important engineering decisions

- **Deduplication:** Confirm stable IDs and source uniqueness; avoid inventing composite keys without evidence.
- **Late arrivals:** Separate occurrence time from API received/ingested time. Consider a lookback window and idempotent merges; explain limitations for older backfills.
- **Session outcomes:** Do not call missing end timestamps failures until checking ongoing drives and ingestion lag.
- **Version comparisons:** Avoid comparing unlike populations or small samples without caveats.
- **Refresh frequency:** A daily ingestion and Monday weekly summary is a reasonable *proposal*, not yet a committed design. Explain why real-time monitoring is outside MVP scope.
- **Cost:** XSMALL warehouse, auto-suspend, small bounded extracts, and compact marts; do not assume trial credits are unlimited.
- **Privacy:** Do not publish raw user-level data, access tokens, Snowflake secrets, or full API extracts.

## 9. How Codex should collaborate

Act as a pragmatic senior Analytics Engineer pairing with a candidate. Read this file and the **actual two notebooks** before changing code. Work in small, reviewable steps, state expected effort and trade-offs, distinguish observed facts from hypotheses, and avoid creating unnecessary infrastructure. Prioritize a trustworthy Head-of-Product weekly answer. Ask before choosing a business definition unsupported by data. Check `.gitignore` and credential handling before commits. End with a concise README, two or three defensible findings, and a 5–10 minute demo narrative.

**Immediate next action:** Verify Snowflake database/schema/warehouse setup and inspect the Data Profiling notebook's actual findings. Then decide the first reliable drive-experience KPI and implement a minimal raw ingestion path into Snowflake.
