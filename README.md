# OOONO release-health exploration

Work in progress for an Analytics Engineer interview case. The notebooks inspect
the Events API and profile release-related activity. No confirmed drive-failure
metric, dbt models, ingestion pipeline, or dashboard has been built yet.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your own API credentials to `.env`. Open the notebooks from the project root
in VS Code with Jupyter support and select `.venv/bin/python` as the kernel.
Run cells from top to bottom.

| Notebook | Purpose |
| --- | --- |
| `01_api_exploration.ipynb` | Fetch five sample records from drives, warnings, and users; inspect columns. |
| `02_data_profiling.ipynb` | Fetch and cache all historical drives and warnings; inspect identity, nulls, distributions, timestamps, and joins. |
| `03_event_counts.ipynb` | Independently count all API rows and distinct IDs without retaining full payloads. |
| `04_weekly_connection_behavior.ipynb` | Use cached records offline to validate canonical IDs, examine timestamps, and compare provisional weekly connection behavior. |

Profiling and counting cache their progress under `data/`. Completed reruns use
saved data without API calls; interrupted downloads resume. A new cache requires
fresh API pagination. The counting notebook performs its own scan, so it is not
needed to run profiling. The API is live and can change during pagination.
The fourth notebook exports aggregate results to `reports/weekly_findings.md`;
its proposed metric is documented in `reports/metric_definitions.md`. It uses
device wall-calendar week labels provisionally; source timezone semantics and
connection-counter meaning remain unconfirmed.
The profiling notebook's latest local cache was refreshed on 27 October 2026
using a 24-hour overlap on receipt time; that one-off refresh is not an automated
notebook feature. Backdated receipts outside the overlap may be missed.

## Assumptions and limitations

- Receipt timestamps are UTC; device timestamps without offsets need semantic
  validation before weekly reporting.
- Multiple recorded connections are descriptive behavior, not confirmed failures.
- Repeated drive reports need a business-identity policy; profiling currently
  excludes repeated IDs conservatively from joins.
- Missing warning actions do not establish ignored warnings or product failure.
- The primary weekly metrics and release comparisons remain proposals.
- Streaming, financial attribution, production orchestration, and cloud deployment
  are deliberately outside the current exploration.

The intended production mapping is Python ingestion on AWS, raw data in Snowflake,
dbt transformations, and reporting in Steep. See `PROJECT_CONTEXT.md` for project
context and planned work; planned cloud setup is not implemented in this repo.

## Repository hygiene

Credentials, raw data, local environments, the supplied interview PDF, and local
dbt profiles are excluded. Notebook outputs are cleared before committing to avoid
publishing sample records. Do not commit outputs after running the notebooks.
