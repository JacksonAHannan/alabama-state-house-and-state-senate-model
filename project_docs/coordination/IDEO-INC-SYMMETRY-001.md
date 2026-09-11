# Task contract: IDEO-INC-SYMMETRY-001 symmetric incumbency and absolute ideology

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `review`
- Objective: Use matched Democratic and Republican candidates to test whether a common incumbency effect plus absolute Shor–McCarty ideology—and specifically Democratic movement rightward and Republican movement leftward—explains overperformance.
- Non-goals: No causal incumbency claim, warehouse mutation, forecast refit, or website publication.
- Upstream snapshot: Corrected historical CMO commit `58871e2`; current federal baselines; immutable Shor–McCarty individual file; reviewed matching logic from `IDEO-SHOR-HIST-001`.
- Read scope: `data/raw/ideology/`, `data/processed/war/`, `data/processed/elections/historical_federal_district_baselines.csv`, `scripts/analyze_historical_shor_mccarty_cmo.py`.
- Write scope: `scripts/analyze_symmetric_incumbency_ideology.py`; `research/cmo_ideology/symmetric_incumbency_*`; `project_docs/model/SYMMETRIC_INCUMBENCY_IDEOLOGY.md`; `tests/test_symmetric_incumbency_ideology.py`; this contract and its active-task row.
- Warehouse mode: `read-only`
- Inputs: Corrected candidate/race CMO, federal baselines, Shor–McCarty national individual ideal points.
- Outputs: Two-party match panel, model estimates, absolute-score and center-proximity summaries, common-incumbency and Republican-calibrated decompositions, report.
- Acceptance checks: Both parties have analysis-ready matches; candidate-directional outcomes are correctly sign-reversed; party-specific and constrained incumbency specifications are reported; tests and workflow validation pass.
- Handoff recipient: `validation_release`
- Known risks: Shor coverage selects legislators and disproportionately incumbents; career scores can contain later votes; ideological scales may be imperfectly comparable across eras; party switching and sparse post-2016 Democratic overlap.

## Handoff

- Changed code: `scripts/analyze_symmetric_incumbency_ideology.py`; `tests/test_symmetric_incumbency_ideology.py`.
- Generated outputs: two-party matches, review queue, panel, model summaries and terms, ideology/incumbency contrasts, Republican calibration, and absolute Democratic terciles under `research/cmo_ideology/symmetric_incumbency_*`; report at `project_docs/model/SYMMETRIC_INCUMBENCY_IDEOLOGY.md`.
- Checks run: analysis regenerated successfully; ten combined focused tests passed; workflow validation passed before final review transition.
- Caveats: the matched panel conditions on legislative service; Republican and Democratic Shor distributions have limited overlap; federal geography before 2010 is provisional; equal incumbency is an imposed sensitivity assumption.
- Downstream action: independent `validation_release` review before publication or use as a causal estimate.
