# Task contract: IDEO-SHOR-HIST-001 historical Shor–McCarty extension

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `review`
- Objective: Match all eligible 1994–2018 Democratic CMO candidate-cycles to Alabama Shor–McCarty records where defensible, and test ideology against corrected CMO, prior-presidential overperformance, and same-cycle federal overperformance.
- Non-goals: No raw-source mutation, warehouse schema change, forecast refit, or website publication.
- Upstream snapshot: Corrected historical CMO commit `58871e2`; current historical federal district baselines; immutable Shor–McCarty individual file.
- Read scope: `data/raw/ideology/`, `data/processed/war/`, `data/processed/elections/historical_federal_district_baselines.csv`.
- Write scope: `scripts/analyze_historical_shor_mccarty_cmo.py`; `research/cmo_ideology/historical_shor_mccarty_*`; `project_docs/model/HISTORICAL_SHOR_MCCARTY_CMO.md`; `tests/test_historical_shor_mccarty_cmo.py`; this contract and its active-task row.
- Warehouse mode: `read-only`
- Inputs: Shor–McCarty individual legislator TSV, corrected candidate/race CMO exports, federal district baseline export.
- Outputs: Candidate crosswalk, review queue, model estimates, grouped summaries, source-quality and era sensitivities, methodology report.
- Acceptance checks: The analysis command and focused tests pass; every accepted match records method and temporal status; 1994 is excluded from headline inference and retained only as later-observed sensitivity; outcome joins are one-to-one.
- Handoff recipient: `validation_release`
- Known risks: Career ideal points may use post-election votes; Alabama is absent before 1996; historical federal geography relies on provisional fallbacks; candidate name collisions and party switching require conservative matching.

## Handoff

- Changed code: `scripts/analyze_historical_shor_mccarty_cmo.py`; `tests/test_historical_shor_mccarty_cmo.py`.
- Generated outputs: historical crosswalk, review queue, analytical panel, estimates, and tercile summary under `research/cmo_ideology/`; methodology report at `project_docs/model/HISTORICAL_SHOR_MCCARTY_CMO.md`.
- Checks run: analysis regenerated successfully; 3 focused tests passed; 7 combined Shor/CMO ideology tests passed; workflow validation passed.
- Caveats: 1994 is sensitivity-only; 32 headline matches have only later-observed service; pre-2010 federal geography is provisional; the 2018 Shor overlap is underpowered.
- Downstream action: independent `validation_release` review before any website publication or promotion to a headline causal claim.
