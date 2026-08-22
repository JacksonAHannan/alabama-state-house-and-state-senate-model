# Task contract: CMO-WAR-ANALOGUE-001

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Build a state-legislative analogue of Split Ticket WAR: model the legislative-minus-same-cycle-federal gap using incumbency and lagged partisanship as primary structural factors, tightly constrained demographics and campaign effort as minor factors, and define candidate CMO as the party-oriented residual.
- Acceptance checks: Raw ticket gap, predicted structural gap, component contributions, and residual reconcile exactly; incumbency and lagged-partisanship controls dominate minor adjustments; demographic and campaign contributions obey declared caps; cycle/era validation is published; candidate values are zero-sum; focused tests pass.
- Read scope: Canonical election, federal baseline, demographic, incumbency, and finance inputs; CMO v2/v3 diagnostics; Split Ticket methodology article.
- Write scope: `scripts/rebuild_cmo_war_analogue.py`; `scripts/tests/test_cmo_war_analogue.py`; `data/processed/war/cmo_v4_*`; `project_docs/model/CMO_METHODOLOGY_V4.md`; this contract; its ledger row.
- Upstream inputs: Corrected canonical district election results, historical federal district baselines, prior presidential context, demographics, incumbency, and campaign-finance coverage.
- Expected outputs: Race and candidate WAR-style scores, component decomposition, model tournament, cycle validation, provenance, and methodology report.
- Warehouse mode: read-only.
- Non-goals: No ideology in the CMO model; no public publication or forecast refit in this task.
- Handoff recipient: `validation_release` and downstream ideology/web tasks.
