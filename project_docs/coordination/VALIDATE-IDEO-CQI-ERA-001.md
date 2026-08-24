# Task contract: VALIDATE-IDEO-CQI-ERA-001 independent CQI-era validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the CQI-by-era regression rows and confirm the screenshot-identified chart now displays those rows rather than raw federal overperformance.
- Non-goals: Do not edit analysis code, model outputs, builders, tests, public pages, the warehouse, or active task records.
- Upstream snapshot: `IDEO-CQI-ERA-001` and `WEB-IDEO-CQI-ERA-001` completed candidates.
- Read scope: Current git diff; `scripts/analyze_absolute_ideology_rebuild.py`; `data/processed/war/cmo_v5_candidates.csv`; absolute-ideology inputs and outputs; merged page builder, tests, staged page, and docs page.
- Write scope: `project_docs/audits/IDEOLOGY_CQI_ERA_VALIDATION.md`; `project_docs/coordination/VALIDATE-IDEO-CQI-ERA-001.md`.
- Warehouse mode: `read-only`
- Inputs: Current CQI source, absolute Shor–McCarty panel inputs, generated era estimates, and public page candidate.
- Outputs: PASS/FAIL report independently reconstructing coefficients, intervals, sample sizes, source identity, displayed labels, and runtime behavior.
- Acceptance checks: Independently reproduce Democratic slopes and cluster-robust intervals; verify +9.0 before 2008, +7.8 in 2008–2014, underpowered n=5 after 2016; verify the public chart uses CQI and contains no -2.5 raw-federal card; run the 36-test suite and browser checks at desktop/mobile widths.
- Handoff recipient: `orchestrator`

## Validation handoff

- Verdict: `PASS`
- Completed: 2026-08-24
- Report: `project_docs/audits/IDEOLOGY_CQI_ERA_VALIDATION.md`
- Summary: Independent OLS and person-clustered sandwich reconstruction exactly
  reproduces +9.035738 (n=143), +7.800752 (n=61), and the underpowered modern
  n=5 result. The staged and published chart uses CQI, contains no prior -2.5
  raw-federal card, and passes the contracted 36 tests plus desktop/mobile
  browser checks.
- Known risks: Retrospective CQI, officeholder-selected Shor coverage, small modern sample, and 2008–2014 interval crossing zero.
