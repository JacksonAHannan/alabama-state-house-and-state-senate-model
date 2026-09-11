# Task contract: PEOPLE-SOUTHERN-INCUMBENCY-2024-001

- Accountable role: `people_finance`
- Owner: `/root`
- Status: `complete`
- Objective: Recover 2024 incumbency labels for the recent Southern calibration panel from candidate names and complete 2022 winner observations already present locally.
- Non-goals: No canonical identity decision, warehouse write, forecast fit, probability model, website, or publication change.
- Upstream inputs: MEDSL 2024 precinct general returns and Klarner 2022 candidate-contest file, including uncontested winners.
- Read scope: Referenced raw ZIP members; current Southern probability panel and source coverage.
- Write scope: `scripts/build_southern_2024_incumbency.py`; `scripts/tests/test_southern_2024_incumbency.py`; `data/processed/forecast_calibration/southern_2024_incumbency_*`; `project_docs/sources/SOUTHERN_2024_INCUMBENCY.md`; `project_docs/coordination/PEOPLE-SOUTHERN-INCUMBENCY-2024-001.md`.
- Warehouse mode: `read-only`
- Outputs: Candidate-level match evidence, race-level incumbency balance/status, ambiguous-review queue, coverage audit, and deterministic manifest.
- Acceptance checks: Preserve all 335 eligible 2024 races; use all 2022 winners rather than contested-only rows; exact normalized matches are unique within state/chamber; fuzzy matches require a unique high-confidence margin and remain distinguishable; unresolved cases remain missing; both-party conflicts are rejected; evidence and hashes are retained; focused tests pass.
- Handoff recipient: `forecast_model`, then `validation_release` before use.
- Known risks: Candidate suffix/name changes, chamber switches, post-2022 special elections, and Georgia plan changes can make prior-winner matching incomplete; nonmatch alone is not evidence of an open seat.
