# Task contract: WEB-CAUCUS-3D-001 Three-dimensional caucus view

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Add an accessible, rotatable 3D candidate view using the three issue axes that most separate the selected party's empirical clusters.
- Non-goals: Refit clusters, claim causal issue effects, or imply that candidates missing any selected axis occupy the center.
- Upstream snapshot: Validated interactive caucus explorer at commit `dfd29cf`.
- Read scope: validated cluster profiles and assignments; current caucus page builder and tests.
- Write scope: `scripts/build_caucus_analysis_page.py`; `scripts/tests/test_caucus_analysis_page.py`; `artifacts/site/caucuses.html`; `docs/caucuses.html`; `project_docs/coordination/WEB-CAUCUS-3D-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Absolute candidate issue positions and validated cluster profile means.
- Outputs: Rotatable SVG projection, dynamic party-specific axes, point hover/click detail, legend, coverage note, and reset control.
- Acceptance checks: Axes equal the three largest between-cluster profile ranges for each party; only candidates observed on all three axes are plotted; drag rotation and reset work; point selection opens existing detail; desktop and 497px layouts do not overflow; focused tests and independent browser validation pass.
- Handoff recipient: `validation_release`
- Known risks: Perspective can obscure points; three-axis complete-case coverage is selective; Republican cluster instability must remain visible.
