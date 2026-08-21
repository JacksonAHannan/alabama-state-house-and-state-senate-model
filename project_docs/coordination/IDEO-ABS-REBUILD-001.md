# Task contract: IDEO-ABS-REBUILD-001 absolute ideology rebuild

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild the historical ideology/overperformance analysis around ideology-blind outcomes, absolute ideological position, party-directed convergence, symmetric incumbency sensitivity, mediator decompositions, durable federal baselines, and issue-by-district congruence, using approved CMO v2 context scores rather than the superseded preliminary CMO outcome.
- Acceptance checks: Both parties are represented; CMO outcomes are not conditioned on ideology; total-effect and mediator-controlled specifications are separately labeled; absolute Shor and issue-level estimates include party, era, and district-context heterogeneity; coverage and overlap diagnostics are published; focused tests and workflow validation pass.
- Read scope: `data/processed/elections/`; `data/processed/war/`; `data/processed/ideology/`; `data/raw/ideology/`; `research/cmo_ideology/`; existing analysis scripts and model documentation.
- Write scope: `scripts/analyze_absolute_ideology_rebuild.py`; `tests/test_absolute_ideology_rebuild.py`; `research/cmo_ideology/absolute_rebuild_*`; `project_docs/model/ABSOLUTE_IDEOLOGY_REBUILD.md`; this contract; its active-task ledger row; the ideology section of `project_docs/model/CMO_HYPOTHESIS_REGISTRY.md`.
- Upstream inputs: Corrected ideology-blind historical CMO candidates; federal and presidential district baselines; immutable Shor–McCarty scores; ideology-v3 candidate evidence; incumbency, finance, and district demographics.
- Expected outputs: Frozen analysis panel, coverage/overlap audit, absolute-ideology estimates, convergence estimates, incumbency and mediator decomposition, issue-position and congruence estimates, era/durability diagnostics, and synthesis report.
- Warehouse mode: read-only.
- Non-goals: No canonical warehouse mutation, production forecast refit, website publication, causal claim, or backward imputation of later issue evidence.
- Handoff recipient: `validation_release`.
- Known risks: Shor scores select officeholders and can contain post-election votes; issue coverage is sparse and nonrandom; finance and incumbency are mediators as well as predictors; 1994 has limited Shor coverage; district-fit tests are exploratory.

## Handoff

- Changed code: `scripts/analyze_absolute_ideology_rebuild.py`; `tests/test_absolute_ideology_rebuild.py`.
- Generated outputs: `research/cmo_ideology/absolute_rebuild_panel.csv`, absolute estimates, primitive/family issue estimates, coverage, overlap, selection, and durability audits under the same prefix; synthesis at `project_docs/model/ABSOLUTE_IDEOLOGY_REBUILD.md`.
- Documentation: updated the ideology section of `project_docs/model/CMO_HYPOTHESIS_REGISTRY.md` with absolute-scale, mediator, and selection findings.
- Checks: pipeline regenerated; 18 focused ideology tests passed; agent-workflow validation passed.
- Caveats: Shor coverage strongly selects winners and officeholders; only 37 candidate-cycles occupy cross-party common support; only five Democratic post-2016 Shor observations are available; primitive issue coverage is uneven and observational; issue interactions remain exploratory after multiplicity adjustment.
- Downstream action: independent `validation_release` review before website publication, forecast inclusion, or causal language.
