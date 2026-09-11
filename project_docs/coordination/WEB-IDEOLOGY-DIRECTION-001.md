# Task contract: WEB-IDEOLOGY-DIRECTION-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Remove the apparent directional contradiction between the within-election bloc comparison and CQI-by-era graphic by making the sign, color, and estimand interpretation explicit and internally consistent.
- Non-goals: Re-estimate CQI, change cluster membership, change Shor–McCarty regressions, publish `docs/`, or alter model data.
- Upstream snapshot: Current validated CQI v5, Democratic clustering output, and absolute-ideology era estimates.
- Read scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; current ideology research and CMO outputs.
- Write scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `project_docs/audits/IDEOLOGY_DIRECTION_REPAIR.md`; `project_docs/coordination/WEB-IDEOLOGY-DIRECTION-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Within-cycle-and-chamber traditionalist-minus-progressive contrasts and Democratic CQI/absolute-conservatism estimates by era.
- Outputs: Directionally explicit chart labels and color scales, an explanatory bridge between the two estimands, focused tests, and a local page artifact.
- Acceptance checks: Positive within-election values are labeled as a traditionalist advantage; the positive side uses the traditionalist oxblood color and the negative side uses progressive blue; era coefficients are labeled as CQI per standard deviation more conservative; current estimates remain unchanged; focused tests pass.
- Handoff recipient: `validation_release`
- Known risks: Bloc membership and continuous Shor–McCarty ideology are related but nonidentical estimands and have different coverage; the page must not imply they are interchangeable or causal.
