# Task contract: VALIDATE-IDEOLOGY-CASE-SELECTION-001 — independent representative-case validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify that the representative case for each Democratic bloc is selected on current v6 candidate-quality-residual proximity rather than federal overperformance.
- Non-goals: Change the selection code, page output, cluster membership, or model data.
- Upstream snapshot: `WEB-IDEOLOGY-CASE-SELECTION-001` release candidate based on commit `41ef2ea`.
- Read scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `data/processed/war/cmo_v6_southern_candidates.csv`; cluster membership; rebuilt ideology page.
- Write scope: `project_docs/audits/IDEOLOGY_CASE_SELECTION_VALIDATION.md`; `project_docs/coordination/VALIDATE-IDEOLOGY-CASE-SELECTION-001.md`
- Warehouse mode: `read-only`
- Inputs: Current v6 residuals, current cluster assignments, and public case cards.
- Outputs: Independent pass/fail report covering case identities, median distances, labels, and page interaction.
- Acceptance checks: Recompute full-bloc medians; verify each representative is the eligible minimum-distance observation; confirm Galliher replaces White; run focused tests; inspect cards at desktop and narrow viewport.
- Handoff recipient: `orchestrator`
- Known risks: Card eligibility requires a federal comparison while the target median uses the complete quality-scored bloc.

## Validation handoff

- Verdict: `PASS`
- Completed: 2026-08-23
- Report: `project_docs/audits/IDEOLOGY_CASE_SELECTION_VALIDATION.md`
- Summary: Independent reconstruction from cluster membership and current v6
  residuals selects Galliher and McClammy as the unique eligible observations
  nearest their full-bloc medians. Labels disclose the criterion and federal
  eligibility requirement; four-card desktop/mobile rendering, console,
  focused tests, and workflow validation pass.
