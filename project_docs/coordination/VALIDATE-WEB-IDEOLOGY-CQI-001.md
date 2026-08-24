# Task contract: VALIDATE-WEB-IDEOLOGY-CQI-001 independent CQI-page validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify that the merged ideology/caucus page uses validated CQI rather than the failed modern Southern-prior residual and remains publication-safe.
- Non-goals: Do not modify model outputs, clusters, public pages, builders, or the warehouse.
- Upstream snapshot: `WEB-IDEOLOGY-CQI-CORRECTION-001` review candidate.
- Read scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `data/processed/war/cmo_v5_candidates.csv`; `data/processed/war/cmo_v6_southern_candidates.csv`; `docs/ideology-performance.html`; `docs/index.html`; current git diff.
- Write scope: `project_docs/audits/IDEOLOGY_CQI_CORRECTION_VALIDATION.md`; `project_docs/coordination/VALIDATE-WEB-IDEOLOGY-CQI-001.md`.
- Warehouse mode: `read-only`
- Inputs: Current review candidate and the independently validated v5/v6 CMO outputs.
- Outputs: PASS/FAIL validation report covering metric identity, modern-era signs, labels, stale-field absence, runtime safety, and focused tests.
- Acceptance checks: Independently reconstruct post-2016 Democratic bloc CQI means; confirm traditionalist mean is positive and progressive mean is near zero; confirm the Shor modern regression remains not estimated; run `python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q`; confirm no public ideology-page field labels the Southern residual as CQI.
- Handoff recipient: `orchestrator`
- Known risks: Small post-2016 traditionalist sample, retrospective CQI, and generated single-line HTML can obscure stale payload fields.

## Validation handoff

- Verdict: `PASS`
- Completed: 2026-08-24
- Report: `project_docs/audits/IDEOLOGY_CQI_CORRECTION_VALIDATION.md`
- Summary: All 274 public values reconcile one-to-one to v5 CQI and all differ
  from the v6 Southern residual. Post-2016 Democratic means independently
  reproduce at +5.317851 (traditionalist, n=4) and -0.169340 (progressive,
  n=20). The five-observation Shor modern regression remains underpowered and
  visibly not estimated. Labels, runtime, responsive checks, focused tests, and
  workflow validation pass.
