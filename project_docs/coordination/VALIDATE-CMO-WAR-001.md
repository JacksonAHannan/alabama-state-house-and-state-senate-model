# Task contract: VALIDATE-CMO-WAR-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the Alabama Split Ticket-style WAR analogue, including source selection, structural feature definitions, decomposition arithmetic, caps, zero-sum orientation, validation design, and methodological fidelity.
- Acceptance checks: All 509 race and 1,018 candidate rows reconcile; federal-primary and fallback policies are exact; component arithmetic and caps pass; ideology is absent; no cycle fixed effect or asymmetric party-incumbency coefficient absorbs candidate performance; focused tests pass; limitations are reported.
- Read scope: `scripts/rebuild_cmo_war_analogue.py`; `data/processed/war/cmo_v4_*`; canonical upstream inputs; Split Ticket article and v3 comparison outputs.
- Write scope: `project_docs/audits/CMO_WAR_ANALOGUE_VALIDATION.md`; this contract; its ledger row.
- Upstream inputs: `CMO-WAR-ANALOGUE-001` review candidate.
- Expected outputs: Independent PASS/FAIL report with any blocking methodological discrepancies.
- Warehouse mode: read-only.
