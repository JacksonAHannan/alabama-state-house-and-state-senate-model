# Task contract: WEB-IDEOLOGY-MEASURE-LABELS-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Explicitly distinguish issue-cluster contrasts from continuous Shor–McCarty ideology slopes everywhere they appear together on the ideology page.
- Non-goals: Re-estimate CQI, alter cluster membership, change Shor–McCarty scores, publish `docs/`, or modify model data.
- Upstream snapshot: Completed `WEB-IDEOLOGY-DIRECTION-001` local artifact and current validated ideology outputs.
- Read scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; current cluster and Shor–McCarty analysis outputs.
- Write scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `project_docs/audits/IDEOLOGY_MEASUREMENT_LABELS.md`; `project_docs/coordination/WEB-IDEOLOGY-MEASURE-LABELS-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Binary issue-record cluster assignments, within-election CQI contrasts, continuous absolute Shor–McCarty scores, and era-specific CQI slopes.
- Outputs: Explicit measurement labels, units, conversion explanation, focused tests, and rebuilt local page artifact.
- Acceptance checks: Every joint presentation names the issue-cluster contrast and Shor–McCarty slope separately; +4.5 is labeled CQI points between clusters; +9.0/+7.8 are labeled CQI points per one Shor–McCarty SD; the observed 0.424/0.522 SD cluster separation and implied 3.83/4.08 CQI gaps are disclosed; estimates remain unchanged; focused tests pass.
- Handoff recipient: `validation_release`
- Known risks: The cluster-to-Shor conversion is descriptive because coverage differs and post-2016 Shor support is insufficient.
