# Task contract: WEB-CMO-V2-001 publish revised CMO methodology

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Migrate the public CMO dashboard and methodology page to the independently approved v2 outputs while preserving maps, chamber/cycle controls, race wiki-boxes, baseline context, branding, and all unrelated forecast behavior.
- Non-goals: Do not refit models, mutate warehouse tables, change forecast probabilities, or alter raw evidence.
- Upstream snapshot: Independently approved `CMO-METHODOLOGY-V2-001` outputs and model card.
- Read scope: `data/processed/war/cmo_v2_*`; CMO model card/report/validation; existing CMO builder, tests, public pages, and shared theme.
- Write scope: `scripts/build_war_story_page.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `scripts/tests/test_site_brand.py`; `docs/cmo.html`; `docs/cmo-methodology.html`; `docs/data/cmo_v2_`; `artifacts/site/alabama-legislative-cmo.html`; `artifacts/blue_oxblood_site/`; this contract and its active-task row.
- Warehouse mode: read-only.
- Inputs: Approved v2 races/candidates/diagnostics, current historical race results, and current map payloads.
- Outputs: Public CMO dashboard with context/raw/within-cycle/partial-pooled views; revised methodology; versioned download exports; rebuilt branded pages.
- Acceptance checks: Headline values equal approved context CMO; cross-era view uses within-cycle CMO; predictive residual is visibly separate; nominal/1994/identity/uncertainty flags render; no old Fundamentals+ headline claims remain; maps and all 16 cycle/chamber controls work; wiki-box and baseline toggles work; deterministic build; JS compiles; responsive/contrast checks; focused and full tests; independent release approval.
- Handoff recipient: `validation_release`.
- Known risks: Compatibility aliases, large embedded map payload, stale historical labels, and confusing raw/context/personal-effect terminology.
