# Task contract: WEB-IDEOLOGY-CMO-V2-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild the ideology page from the corrected CMO v2 context-outcome panel and remove stale preliminary-CMO values from every public visualization.
- Acceptance checks: The published payload uses `candidate_context_cmo`; Barbara Boyd's 2022 HD-32 CMO is approximately -4.37; no legacy CMO field is present in the rebuilt panel; focused page tests pass.
- Read scope: `research/cmo_ideology/absolute_rebuild_*`; `scripts/build_ideology_thesis_page.py`; current site templates.
- Write scope: `docs/ideology-performance.html`; `artifacts/site/ideology-performance.html`; this contract; its active-task ledger row.
- Upstream inputs: `IDEO-ABS-REBUILD-001` corrected analysis outputs.
- Expected outputs: Rebuilt public ideology page and release candidate.
- Warehouse mode: read-only.
- Handoff recipient: `validation_release`.

## Handoff

- Rebuilt the ideology page after replacing the superseded preliminary candidate CMO with CMO v2 context scores.
- Focused analysis and page tests pass.
- Independent validation is required before release.
