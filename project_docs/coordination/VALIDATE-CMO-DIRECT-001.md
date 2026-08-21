# Task contract: VALIDATE-CMO-DIRECT-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`

## Handoff

- Outcome: `PASS`
- Evidence: 509/509 race arithmetic identities; 413 state-only and 96 verified
  70/30 selected baselines; exact alternative-ticket null patterns; all 509 D/R
  headline pairs and every available alternative are zero-sum; all uncertainty
  terms and oriented endpoints reconstruct; Morrow is +0.510313; 37 regression
  context pathologies remain audit-only; focused tests pass 5/5.
- Changed implementation/model/output files: none.
- Report: `project_docs/audits/CMO_DIRECT_ESTIMAND_VALIDATION.md`.
- Downstream invalidation: none.
- Non-blocking follow-up: enrich the v3 provenance manifest with code,
  configuration, run, and output hashes.
- Next action: accountable owner may proceed with v3 publication integration.
- Objective: Independently validate the CMO v3 direct ticket-overperformance estimand and its arithmetic, source policy, candidate orientation, uncertainty, and Morrow reconciliation.
- Acceptance checks: All race scores reconcile exactly to legislative minus selected ticket margin; candidate D/R scores are zero-sum; Morrow 1998 HD-18 is approximately +0.51; no regression context residual enters a public score; focused tests pass; a PASS/FAIL report is written.
- Read scope: `scripts/rebuild_cmo_direct_estimand.py`; `data/processed/war/cmo_v3_*`; canonical upstream inputs; v2 diagnostics for comparison.
- Write scope: `project_docs/audits/CMO_DIRECT_ESTIMAND_VALIDATION.md`; this contract; its active-task ledger row.
- Upstream inputs: `CMO-DIRECT-ESTIMAND-001` review candidate.
- Expected outputs: Independent validation report and release recommendation.
- Warehouse mode: read-only.
