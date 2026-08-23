# Task contract: WEB-HEADER-ATLAS-CLEANUP-001 — masthead alignment and stale atlas removal

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Align the forecast brand lockup with the compact portrait/name treatment used elsewhere and remove the stale Candidate Atlas links from the Ideology & Caucuses page.
- Acceptance checks: Forecast portrait, name, and subtitle form one compact lockup at desktop and mobile widths; no duplicate portrait pseudo-element; Ideology & Caucuses contains no Candidate Atlas header or footer link; site navigation and interactive page content still work; focused tests and independent browser validation pass.
- Read scope: `dashboard/blue_oxblood_theme.css`; `scripts/build_democratic_transition_page.py`; current generated public pages and web tests.
- Write scope: `dashboard/blue_oxblood_theme.css`; `scripts/build_democratic_transition_page.py`; `docs/`; `project_docs/coordination/WEB-HEADER-ATLAS-CLEANUP-001.md`.
- Upstream inputs: Public site at commit `d78db10`.
- Expected outputs: Rebuilt public pages with a corrected forecast identity lockup and no stale atlas link on the merged ideology page.
- Warehouse access: read-only.
- Handoff recipient: `validation_release`.

## Handoff

- The forecast now renders a single portrait in the same compact identity lockup used by the CMO and ideology pages.
- Candidate Atlas links were removed from the Ideology & Caucuses header and footer.
- Focused tests passed 38/38; `VALIDATE-HEADER-ATLAS-CLEANUP-001` independently returned PASS at desktop and mobile widths.
