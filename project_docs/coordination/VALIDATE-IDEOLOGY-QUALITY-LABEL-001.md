# Task contract: VALIDATE-IDEOLOGY-QUALITY-LABEL-001 — independent ideology outcome validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify that the combined ideology/caucus page uses the current v6 candidate-quality residual everywhere it previously mislabeled a structural residual as CMO.
- Non-goals: Change model outputs, cluster assignments, page design, source code, or publication files.
- Upstream snapshot: `WEB-IDEOLOGY-QUALITY-LABEL-001` release candidate built from commit `c1f9fe4` and current uncommitted page repair.
- Read scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `data/processed/war/cmo_v6_southern_candidates.csv`; `research/cmo_ideology/democratic_clusters/`; `artifacts/site/ideology-performance.html`; `docs/ideology-performance.html`.
- Write scope: `project_docs/audits/IDEOLOGY_QUALITY_LABEL_VALIDATION.md`; `project_docs/coordination/VALIDATE-IDEOLOGY-QUALITY-LABEL-001.md`
- Warehouse mode: `read-only`
- Inputs: Current release candidate, v6 candidate rows, cluster membership, and published page.
- Outputs: Independent pass/fail report with field-level reconciliation, label audit, interaction checks, and caveats.
- Acceptance checks: Recompute the two Democratic bloc means and their difference from v6; confirm 274/274 exact candidate joins; run the focused tests; inspect the rendered page at desktop and narrow viewport; verify no chart, card, tooltip, or table presents the candidate-quality residual as CMO; confirm valid CMO navigation/method references remain.
- Handoff recipient: `orchestrator`
- Known risks: Direct CMO, raw candidate-quality residual, partial-pooled candidate quality, and total electoral value are distinct measures with similar units.

## Validation handoff

- Verdict: `PASS`
- Completed: 2026-08-23
- Report: `project_docs/audits/IDEOLOGY_QUALITY_LABEL_VALIDATION.md`
- Summary: All 274 public candidate values reconcile one-to-one to the current v6
  `candidate_quality_residual`; Democratic bloc means and their 12.393743-point
  difference independently reproduce; stale CMO labels/fields are absent while
  legitimate CMO navigation and methodological distinctions remain; focused
  tests, interactions, console, and desktop/497/390 responsive checks pass.
