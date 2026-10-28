# Fresh pipeline validation

Status: COMPLETE. Executed the new end-to-end command on 28 October 2026.

Command: `.venv/bin/python scripts/run_pipeline.py --run-dir data/pipeline_runs/first_fresh_demo`

Snapshot: `720049bec6e4a2eb65bed159a1f6fec6a91aeaea69243013368e44600d672d46`.
Receipt cutoff: `2026-10-28T16:11:05.671443+00:00`.
Completed: `2026-10-28T16:13:44.483942+00:00`.

| Endpoint | Records in new cumulative snapshot / RAW load |
| --- | ---: |
| Drives | 227,924 |
| Warnings | 320,811 |
| Users | 3,095 |

The first run used the approved immutable baseline as its parent. It fetched
7,162 drive reports and 9,915 warning reports with a 24-hour receipt overlap;
the current users endpoint returned 3,095 records. Entire response pages and
checkpoints were preserved. Snapshot assembly retained receipt content and maximum
observed multiplicity for identical overlap payloads; no canonical-session
business deduplication happened in RAW loading.

Immutable file/envelope checks passed. RAW loading reconciled all payloads,
ordinals, hashes, receipts, and file lineage before commit. dbt built all five
models with the new snapshot and cutoff explicitly passed as vars. Its structural,
quality, and internal metric tests succeeded with zero errors; the three historical
notebook-reference tests were inapplicable to this changed snapshot/cutoff and
returned no failures by design. This is not a claim that fresh data reproduces old
exact notebook counts.

Fresh data quality warnings:
- `warning_clock_anomalies`: 155 records.
- `warning_orphans`: 133 records.

The drive-level model contains 223,519 canonical sessions for the new cutoff.
Expected warning-level exceptions do not fail the build. The successful local
checkpoint advances only after all blocking checks pass. The approved baseline
source files, warehouse rows, and checked-in dbt defaults remain preserved.

Eight offline invariant tests passed, including overlap multiplicity, immutable
source checks, pagination scope/repeated-cursor guards, and refusing failed/older
checkpoint advancement. Local live-run evidence is under
`data/pipeline_runs/first_fresh_demo/`.

No Steep work or Git push was performed. See [pipeline run guide](../docs/pipeline_run_guide.md)
for normal runs, resumption, full extraction, baseline replay, and source limitations.
