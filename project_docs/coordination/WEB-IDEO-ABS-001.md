# Task contract: WEB-IDEO-ABS-001 absolute ideology page rebuild

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the legacy relative-ideology thesis page with a clean release candidate built exclusively from the reviewed absolute-ideology rebuild outputs, using a restrained editorial template derived from the existing CMO methodology design rather than generic dashboard motifs.
- Acceptance checks: No legacy relative-score, cluster, matched-pair, or old headline-estimate dependency remains; all visual payloads derive from `absolute_rebuild_*`; absolute Shor, party asymmetry, mediator decomposition, primitive issues, era/selection limitations, and candidate evidence are displayed; missing/underpowered values render safely; no `undefined`, mojibake, stale disclaimer, or legacy thesis artifact appears; the visual system uses a compact masthead, article hierarchy, serif explanatory typography, thin rules, figure-like graphics, and a persistent contents rail while suppressing gradients, floating cards, decorative pills, and oversized dashboard callouts; focused UI tests and workflow validation pass.
- Read scope: `research/cmo_ideology/absolute_rebuild_*`; `project_docs/model/ABSOLUTE_IDEOLOGY_REBUILD.md`; existing site navigation and CMO design language; current ideology page only as a migration reference.
- Write scope: `scripts/build_ideology_thesis_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; this contract and its active-task row.
- Upstream inputs: `IDEO-ABS-REBUILD-001` review candidate and current shared navigation conventions.
- Expected outputs: Self-contained ideology page release candidate, embedded absolute-analysis payload, rebuilt interactive visuals, and UI/data contract tests.
- Warehouse mode: read-only.
- Non-goals: No `docs/` publication, warehouse mutation, forecast change, or re-estimation of ideology findings.
- Handoff recipient: `validation_release`.
- Known risks: Shor selection, sparse post-2016 Democratic coverage, limited cross-party overlap, and uneven primitive-axis evidence must remain visually prominent.

## Handoff

- Replaced `scripts/build_ideology_thesis_page.py`; the builder now reads only `absolute_rebuild_*` inputs and writes the release candidate to `artifacts/site/ideology-performance.html`.
- Replaced `scripts/tests/test_ideology_performance_page.py` with absolute-data, taxonomy, missing-state, self-containment, stale-artifact, and publication-boundary checks.
- Rebuilt visuals: absolute Shor scatter with candidate hover, party slope summaries, selection/common-support cards, total-versus-mediator decomposition, primitive issue forest, candidate issue explorer, district-congruence forest, and era/underpowered display.
- Removed legacy dependencies and presentation: conservative-fit index, exploratory caucus clusters, old headline-family estimates, matched-pair claims, relative caucus ranks, stale explanatory disclaimers, and old issue explorer payloads.
- Recast the visual system as an editorial research article: compact masthead, restrained headline/dek, ruled finding statement and metric ledger, sticky contents rail, serif analytical copy, unfilled figure treatments, and plain methodological notes. Existing gradients, floating card treatments, decorative badges, and oversized callouts are suppressed by the template.
- Checks: 16 combined page and absolute-analysis tests passed; JavaScript syntax check passed; the desktop headless-Chrome render was visually inspected; workflow validation passed; artifact scan found no legacy identifiers, `undefined`, or mojibake.
- Publication status: `docs/ideology-performance.html` was intentionally not modified. Independent `validation_release` review is required before copying the candidate to `docs/`.
- Caveats presented on-page: Shor winner selection, 37-observation common support, five post-2016 Democratic Shor observations, uneven primitive coverage, multiple testing, mediator interpretation, and lack of prospective challenger coverage.
