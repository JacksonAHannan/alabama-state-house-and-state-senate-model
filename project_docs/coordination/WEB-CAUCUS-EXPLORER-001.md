# Task contract: WEB-CAUCUS-EXPLORER-001 Interactive caucus analysis

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Publish an interactive, accessible caucus explorer using the independently validated party-specific clustering outputs.
- Non-goals: Refit clusters, change issue adjudications, alter CMO, or present Republican clusters as stable formal caucuses.
- Upstream snapshot: Validated `IDEO-CAUCUS-RECLUSTER-001` outputs at commit `31469fc`.
- Read scope: `research/cmo_ideology/democratic_clusters/`; existing site builders, theme, and ideology-page design.
- Write scope: `scripts/build_caucus_analysis_page.py`; `scripts/build_blue_oxblood_site.py`; `scripts/build_ideology_thesis_page.py`; `scripts/tests/test_caucus_analysis_page.py`; `artifacts/site/caucuses.html`; `artifacts/site/ideology-performance.html`; `docs/caucuses.html`; `docs/ideology-performance.html`; `project_docs/coordination/WEB-CAUCUS-EXPLORER-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Validated assignments, profiles, diagnostics, sensitivity, era composition, and CMO v4 checks.
- Outputs: Self-contained interactive HTML release candidate and public page.
- Acceptance checks: Party/caucus/issue/era/outcome controls work; profiles and performance use current files; member hover/detail works; Republican instability warning is prominent; narrow and desktop layouts have no critical overflow; tests pass; independent validation approves publication.
- Handoff recipient: `validation_release`
- Known risks: Dense issue labels, sparse candidate evidence, large embedded payload, and misleading discrete interpretation of weak Republican clusters.
