# OOONO release-health dbt project

This directory is the dbt project root. Repository-level Python ingestion,
environments, and reports remain outside it.

```text
dbt/
├── dbt_project.yml
├── profiles.yml.example
├── models/
│   ├── staging/ooono/       # source definitions, typed/canonical source views
│   ├── intermediate/        # drive-level warning aggregation and eligibility
│   └── marts/               # weekly release-health table
├── macros/
└── tests/                   # singular dbt data tests
```

From the repository root:

```sh
.venv-dbt/bin/python scripts/run_dbt.py debug
.venv-dbt/bin/python scripts/run_dbt.py build
```

The runner supplies this project directory, loads the repository's ignored `.env`,
and uses the dedicated OOONO_DBT role. The generated local `profiles.yml`, `target/`,
and `logs/` are ignored. Requirements remain in repository-level
`requirements-dbt.txt` so the isolated environment can be reproduced.

The staging → intermediate → marts layers follow dbt's project-structure guidance.
Source folders group staging models and their YAML definitions. Staging uses views;
the drive intermediate and mart use tables for straightforward inspection and reuse.
Canonical replay collapse remains in staging as an explicit case-study convention
from the approved metric contract. dbt's general guidance avoids grain-changing
aggregation in staging; here the source already describes drive-session reports,
and agreeing replays are collapsed to that documented canonical grain. No metric
or model-grain changes are part of this layout refactor.

The custom schema macro intentionally targets the existing STAGING/ANALYTICS
schemas in this single-user case. A team deployment should add isolated development
schemas. Snapshot/cutoff defaults are explicit vars, never latest-snapshot lookups.

References:

- [Project structure](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)
- [Staging conventions](https://docs.getdbt.com/best-practices/how-we-structure/2-staging)
- [Project root and --project-dir](https://docs.getdbt.com/reference/dbt_project.yml)
