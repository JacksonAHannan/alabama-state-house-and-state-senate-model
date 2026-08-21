# Task contract: VALIDATE-CMO-V3-SITE-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`

## Handoff

- Outcome: `PASS`
- Passing gates: all 1,018 ideology analysis scores reconcile by stable ID;
  all 1,018 CMO dashboard scores reconcile by unique race/party; all 4,697
  ideology public observations reconcile by ID; Morrow is +0.510313 source and
  +0.51 public; all five v3 downloads are byte-identical; rendered methodology
  is v3-consistent; focused/site tests pass 34/34.
- Final blocker checks: ideology measure prose/formula define the direct ticket
  subtraction; the candidate-CMO selector reads `Direct ticket CMO`; the CMO
  explorer says `direct-CMO percentiles`; wiki-box labels say ticket baseline.
- Changed implementation/public/model files: none.
- Report: `project_docs/audits/CMO_V3_SITE_VALIDATION.md`.
- Downstream invalidation: none.
- Next action: web owner may publish the approved v3 CMO and ideology pages.
- Objective: Independently validate CMO v3 propagation through ideology analysis, CMO dashboard, methodology, and downloads.
- Acceptance checks: Candidate-ID reconciliation passes in analysis and public payloads; Morrow 1998 HD-18 is +0.51; no obsolete context CMO is presented as headline; focused and site tests pass; report is written.
- Read scope: CMO v3 outputs, rebuilt research outputs, site builders, `docs/`, and tests.
- Write scope: `project_docs/audits/CMO_V3_SITE_VALIDATION.md`; this contract; its ledger row.
- Upstream inputs: `IDEO-CMO-V3-001` and `WEB-CMO-V3-001` review candidates.
- Expected outputs: Independent PASS/FAIL publication gate.
- Warehouse mode: read-only.
