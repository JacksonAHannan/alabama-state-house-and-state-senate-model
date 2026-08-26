# Task contract: WEB-IDEOLOGY-WAR-HEADLINE-011

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Make the candidate-quality result the ideology page's headline measure and present it publicly as WAR, with explicit attribution to Split Ticket's naming and methodology.
- Non-goals: Do not rename the internal `candidate_quality_index` field, refit the quality model, alter cluster assignments, change canonical data, or publish `docs/`.
- Read scope: Current three-group ideology release candidate; CQI/WAR v5 candidate output; Split Ticket methodology attribution supplied by the user.
- Write scope: `scripts/build_democratic_transition_page_v2.py`; `scripts/build_war_story_page.py`; `scripts/site_brand.py`; `scripts/tests/test_ideology_performance_page.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `scripts/tests/test_site_brand.py`; `artifacts/site/ideology-performance.html`; `project_docs/coordination/WEB-IDEOLOGY-WAR-HEADLINE-011.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Completed `WEB-IDEOLOGY-THREE-BLOC-REBUILD-010` release candidate and `data/processed/war/cmo_v5_candidates.csv`.
- Outputs: A local ideology page led by adjusted WAR comparisons, with raw federal and presidential overperformance clearly secondary; consistent WAR terminology in the CMO and site-method builders; and explicit Split Ticket credit.
- Acceptance checks: No public-facing CQI label remains; WAR is defined once and used consistently; adjusted WAR is the first quantitative result; Split Ticket attribution and link are present; internal field name remains stable; focused tests and browser checks pass.
- Handoff recipient: `validation_release` if publication is requested.

## Handoff

- Changed files: `scripts/build_democratic_transition_page_v2.py`, `scripts/site_brand.py`, `scripts/tests/test_ideology_performance_page.py`, `scripts/tests/test_site_brand.py`, this contract, and `project_docs/coordination/active_tasks.csv`.
- Generated output: `artifacts/site/ideology-performance.html` (local release candidate only).
- Result: Adjusted WAR is the first quantitative section and receives two dedicated headline cards. Group means and raw federal/presidential comparisons follow as supporting measures. All public CQI labels were replaced with WAR while `candidate_quality_index` remains the stable internal field.
- Attribution: The methods section defines Wins Above Replacement, credits and links Split Ticket, and explains that this implementation is measured in margin points rather than literal seats or wins.
- Validation: 23 focused ideology, caucus, CMO-story compatibility, and brand tests passed; inline JavaScript passed `node --check`; desktop and mobile headless-Chrome renders produced zero console errors; no public `CQI` or `Candidate Quality Index` label remains in the local page.
- Downstream action: Independent `validation_release` review is required before updating `docs/`.
