# Task contract: WEB-CONTRAST-001 Blue/Oxblood contrast correction

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace low-contrast white-on-light-blue interface surfaces with oxblood-backed treatments and verify readable text across every public page.
- Acceptance checks: Shared theme passes automated color-contrast checks; all six pages rebuild deterministically; desktop and 497 px mobile screenshots show no unreadable text or horizontal overflow; maps, selectors, and semantic party colors remain intact; independent `validation_release` approval precedes publication.
- Read scope: `dashboard/blue_oxblood_theme.css`; public builders; `docs/`; `artifacts/blue_oxblood_site/`.
- Write scope: `dashboard/blue_oxblood_theme.css`; `scripts/tests/test_site_brand.py`; `artifacts/blue_oxblood_site/`; `docs/`; this contract and its active-task row.
- Warehouse mode: read-only.
- Upstream inputs: Commit `a94d9da`, current six-page Blue/Oxblood release, and its validation report.
- Expected outputs: Corrected shared theme, rebuilt public pages, contrast regression tests, and visual audit evidence.
- Handoff recipient: `validation_release`.
