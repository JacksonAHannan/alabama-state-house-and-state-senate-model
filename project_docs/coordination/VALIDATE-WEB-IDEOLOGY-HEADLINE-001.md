# Task contract: VALIDATE-WEB-IDEOLOGY-HEADLINE-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify that the corrected ideology headline compares Democratic blocs within election context and renders accurately without regressing the page.
- Non-goals: No implementation edits, model changes, warehouse writes, cluster reassignment, or publication.
- Upstream snapshot: `WEB-IDEOLOGY-HEADLINE-CONTEXT-001` review candidate based on commit `081ef85`.
- Read scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `research/cmo_ideology/democratic_clusters/`; `data/processed/war/cmo_v5_candidates.csv`; `artifacts/site/ideology-performance.html`; `docs/ideology-performance.html`; `project_docs/coordination/WEB-IDEOLOGY-HEADLINE-CONTEXT-001.md`.
- Write scope: `project_docs/audits/WEB_IDEOLOGY_HEADLINE_CONTEXT_VALIDATION.md`; `project_docs/coordination/VALIDATE-WEB-IDEOLOGY-HEADLINE-001.md`.
- Warehouse mode: `read-only`
- Inputs: Corrected within-context payload, current source rows, generated page, and focused regression tests.
- Outputs: Independent pass/fail report covering arithmetic, support restriction, labels, responsive rendering, accessibility, and release recommendation.
- Acceptance checks: independently recompute all three contrasts; confirm only cycle/chamber cells with both blocs identify estimates; verify old pooled means are absent; run focused tests; inspect the block at desktop and 390px with no clipping or console errors.
- Handoff recipient: `/root`
- Known risks: A visually correct chart could still use pooled-era arithmetic or misstate uncertainty; validation must check source values independently rather than trusting the embedded payload.

## Validation handoff

- Verdict: **PASS**
- Completed: 2026-08-24
- Report: `project_docs/audits/WEB_IDEOLOGY_HEADLINE_CONTEXT_VALIDATION.md`
- Independent reconstruction matched all three published contrasts and person-clustered intervals to floating-point precision.
- Exact 1440px and 390px browser checks passed with no overflow, clipping, unnamed visible control, or substantive console error.
- Focused tests: 13 passed; workflow validation passed.
