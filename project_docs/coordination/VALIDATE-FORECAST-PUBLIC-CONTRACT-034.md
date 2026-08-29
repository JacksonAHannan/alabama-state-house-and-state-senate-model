# Task contract: VALIDATE-FORECAST-PUBLIC-CONTRACT-034 forecast publication contract refresh

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Replace obsolete hard-coded 7.08 headline-MAE assertions with a manifest-driven public consistency contract for the independently approved direct fundraising model.
- Non-goals: Modify model code/outputs, dashboard code, published HTML/data, or unrelated test expectations.
- Upstream snapshot: Approved forecast build `8cad753f1720c2a1b107` and current published `docs/` outputs from `WEB-FORECAST-FINANCE-PUBLISH-033`.
- Read scope: Forecast manifest/metrics, `docs/index.html`, `docs/methodology.html`, existing forecast and published-site tests.
- Write scope: `scripts/tests/test_forecast_dashboard.py`; `scripts/tests/test_published_site_consistency.py`; `project_docs/audits/FORECAST_PUBLIC_CONTRACT_VALIDATION.md`; `project_docs/coordination/VALIDATE-FORECAST-PUBLIC-CONTRACT-034.md`.
- Warehouse mode: `read-only`
- Inputs: Approved manifest-selected specification and generated public methodology.
- Outputs: Tests that verify the published MAE and labels against the selected manifest specification rather than a stale literal from the previous model.
- Acceptance checks: The two previously failing tests pass; full focused forecast/public suite passes; tests still fail if published methodology disagrees with the manifest-selected metric; no unrelated assertions are weakened.
- Handoff recipient: `orchestrator`
- Known risks: Avoid replacing a precise current-run assertion with a vague string-presence check.

## Validation handoff

- Verdict: **APPROVE**
- Completed: 2026-08-28
- Report: `project_docs/audits/FORECAST_PUBLIC_CONTRACT_VALIDATION.md`
- Result: Both stale assertions now derive the unique manifest-selected metric, reconcile it to the manifest MAE, and require the exact public sentence plus direct-relative-fundraising label. An in-memory stale-`7.08` mutation fails the new checks. Workflow validation and the 34-test focused forecast/public suite pass.
