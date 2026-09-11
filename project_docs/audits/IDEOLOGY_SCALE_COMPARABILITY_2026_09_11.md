# Ideology scale comparability (checklist `ideology-08`)

- Task: `IDEOLOGY-SCALE-COMPARABILITY-20260911` (role `legislative_ideology`)
- Date: 2026-09-11 (evidence gathered 2026-09-11 21:53Z)
- Upstream snapshot: HEAD `d93dd8c6`; `AL-HIST-WAR-V1-44F191EB8D939EF062CC`;
  v3 `WAR-POST2016-V3-530FBD4238CC483E557C`
- Checklist text (`ideology-08`): "Explain incompatible ideology scales —
  Document absolute Shor–McCarty anchoring versus chamber/biennium behavioral
  scales, orientation and comparison limits. Do not plot unlike scales as if
  interchangeable."
- Write scope (registered in `coordination/active_tasks.csv`):
  this file + `.json`, `scripts/build_democratic_transition_page_v2.py`,
  `scripts/tests/test_ideology_performance_page.py`,
  `artifacts/site/ideology-performance.html`.
- Not written: `docs/`, the warehouse, published exports, the checklist,
  `active_tasks.csv`, `CANONICAL_PIPELINES.md`.

## Outcome

The public ideology page (`ideology-performance.html`) does **not** place two
unlike scales on one axis, does **not** mix orientations, and does **not** label a
within-sample z as absolute. The one displayed z (`absolute_conservatism_z`) was
verified to be standardized against the **full national** Shor–McCarty
distribution, so the page's "nationally comparable" wording is accurate.

The only defect found was a **disclosure gap**, not a data or chart defect: the
page carried no explicit statement of what each displayed measure is anchored to
or which comparisons are invalid. A copy-only `Scale comparability` method block
was added to the page builder and the artifact was re-rendered. No payload,
clustering, score, or WAR value was changed.

## Checks and commands

```powershell
# measure inventory / orientation / anchoring
.venv/Scripts/python.exe -c "import pandas as pd; ..."   # see Counts below
# page payload and chart inventory (parsed from the built artifact)
.venv/Scripts/python.exe -c "import json; from pathlib import Path; ..."
# render
.venv/Scripts/python.exe scripts/build_democratic_transition_page.py
#   -> Wrote ...\artifacts\site\ideology-performance.html
# focused tests
.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_ideology_performance_page.py -q
#   -> 12 passed in 7.17s
```

Grep over the built page: `behavioral_ideology` 0, `chamber_percentile` 0,
`legislator_pre_election` 0, `candidate_ideology_full` 0, `votesmart` 0,
`candidate_issue_valence` 0, `absolute_conservatism_z` 3,
`primitive_conservative_` 6222. No `.csv`/`.json`/`.tsv`/`.zip` `href` exists in
the page, and `docs/data/` contains no ideology export, so the page has **no
download channel** through which another scale could reach the public.

## Counts used below

- Raw Shor–McCarty: `data/raw/ideology/shor_mccarty_individual_legislators_1993_2018.tsv`,
  24,716 rows / 24,716 non-null `np_score`, 50 states, DOIs `10.7910/DVN/GZJOT3`,
  CC0 1.0, retrieved 2026-08-15, sha256 `62e96b1d…923ff351`. `np_score` mean
  0.019054, sd (ddof=0) 0.898526, min −3.739, max 4.704; party means D −0.7725,
  R +0.7587, X −0.1198.
- `research/cmo_ideology/absolute_rebuild_panel.csv`: 1,018 rows; 407 with
  `absolute_conservatism_z` (209 D, 198 R); D range [−1.500, +0.619],
  R range [+0.155, +1.805].
- Page payload: 311 member rows (both parties), 131 Democratic candidate-cycles,
  127 people; 3 clusters over 18 issue features, silhouette 0.2352, bootstrap
  adjusted Rand index 0.8375; 20 selectable issues, 31 `issueMeta` axes,
  32 `primitive_conservative_*` columns in the panel.
- `legislator_pre_election_window_scores.csv`: 1,101 rows, cycles
  1998–2022, house+senate, D 535 / R 563 / I 3; `behavioral_ideology` range
  [−2.396, +2.397], overall mean 0.000 and sd 1.000, and sd exactly 1.000 within
  **every** one of the 13 chamber-cycle groups; `chamber_percentile` ∈ [0.48, 100].
- `candidate_ideology_full_universe.csv`: 1,564 candidate rows, 1994–2022, 550
  scored (`scored_pre_election_legislative_behavior`).
- `candidate_issue_valence_v3.csv`: 18,958 candidate-cycle-axis rows, 1,124
  candidate-cycles, 79 axes, 1994–2022, values in [−1, +1];
  `candidate_family_valence_v3_all_sources.csv` 4,538 rows; model features 658
  candidate rows over 7 family columns.
- Page era regressions (`absoluteEra`): pre-2008 n=56 coefficient +10.20,
  2008–2014 n=17 coefficient +39.55, post-2016 n=5 coefficient +20.35, all
  "estimated"; each row prints its own n.

## Measure inventory

"Reaches page" means the measure is rendered in
`artifacts/site/ideology-performance.html`; the page has no downloads.

| # | Measure | Definition | Orientation (positive sign) | Range / units | Anchoring | Coverage | Producer | Reaches page | Comparable across chambers / years / people |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `shor_np_score` | Shor–McCarty individual-legislator common-space ideal point | higher = more conservative | [−3.739, +4.704], unitless source score | **absolute / national**: source normalizes across all states and both chambers, 1993–2018 | 24,716 legislator rows, 50 states | `download_shor_mccarty_ideology.py` (acquisition + manifest) | indirect (ancestor of #2) | Yes across chambers and states; a person carries one career score, so not a per-cycle measure |
| 2 | `absolute_conservatism_z` | `(np_score − 0.019054) / 0.898526`, i.e. z against the **full national** `np_score` distribution | higher = more conservative | national z units | **national** (24,716-row national mean and sd), explicitly not the analysis-sample sd | 407 candidate-cycles (209 D, 198 R) in the analysis panel | `analyze_symmetric_incumbency_ideology.py` (`symmetric_incumbency_panel.csv`) → `analyze_absolute_ideology_rebuild.py` | **yes** — `#continuous` era chart | Yes for score construction; the fitted sample is Alabama-only, officeholder-selected, and Democrats occupy only ~2.1 SD of the national range |
| 3 | `behavioral_ideology` | First principal component of binary HB/SB roll calls inside one chamber, one pre-election window, sign-flipped so Republicans score higher, divided by that window's sd | higher = more Republican/conservative | sd = 1 within each chamber-cycle; overall [−2.396, +2.397] | **within chamber-biennium** (each of 13 chamber-cycle groups standardized to sd 1) | 1,101 chamber-cycle member rows, cycles 1998–2022 | `build_full_candidate_legislative_ideology.py` | **no** (see out-of-scope finding O1) | **No** — a score of 1.0 means "one window sd", not a fixed ideology difference; ranks are comparable only inside the same chamber and window |
| 4 | `chamber_percentile` | Within-chamber-cycle percentile of #3 | higher = more conservative relative to peers | 0.48–100 | within chamber-cycle | same 1,101 rows | `build_full_candidate_legislative_ideology.py` | no | **No** across chambers or windows |
| 5 | `caucus_median`, `distance_from_caucus_median` | Party median of #3 and signed distance from it, inside a chamber-cycle | higher = more conservative than own caucus median | #3 score units | within chamber-cycle × party | same 1,101 rows | `build_full_candidate_legislative_ideology.py` | no | **No** |
| 6 | career `behavioral_ideology` | #3 recomputed over the archived 1998–2026 career window per chamber | higher = more conservative relative to chamber | sd = 1 within chamber | within-chamber career standardization | `candidate_career_ideology_through_2026.csv` | `build_full_candidate_legislative_ideology.py` | no | **No** across chambers; consumed by the 2026 forecast feature build, not by the ideology page |
| 7 | `issue_valence`, `model_issue_valence` | Evidence-weight mean of `position_value × primitive_axis_direction(axis, pole)` per candidate-cycle-axis | positive = the **first declared pole of that ontology axis**, which is not universally conservative | [−1, +1] per axis | **within-axis**; no national bridge and no bridge to Shor–McCarty | 18,958 rows, 1,124 candidate-cycles, 79 axes | `build_candidate_issue_valence_v3.py` (uses `ideology_ontology_v3.primitive_axis_direction`) | no (composite #11 is) | Within axis and within candidate set only |
| 8 | family `family_valence`, `model_family_valence`; `ideology_v3_<family>` | Evidence-weight mean of primitives loaded onto one of 8 ontology families via `ideology_ontology_v3.LOADINGS` | positive = first pole of the family | [−1, +1] | within-family | 4,538 rows; 658 candidate rows over 7 model features | `build_candidate_issue_valence_v3.py` (`aggregate_families`) | no | Within family only |
| 9 | `absolute_evidence_weight`, `evidence_records`, `conflict_ratio`, `position_status` | Evidence metadata (weight sum, row count, opposing-weight ratio, disposition) | n/a | weight / count / [0,1] | n/a | 18,958 rows | `build_candidate_issue_valence_v3.py` | no | n/a (not a position) |
| 10 | Vote Smart PCT dimensions | Candidate-supplied questionnaire dimension scores, shown as −1 progressive to +1 conservative | higher = conservative as displayed | [−1, +1] | candidate questionnaire (self-reported) | `votesmart_pct_candidate_cycle_features.csv` | `build_legislator_ideology_page.py` (dead output) | no | Not comparable between candidates with and without a questionnaire; different instrument from every roll-call score |
| 11 | `primitive_conservative_<axis>` | `model_issue_valence × PRIMITIVE_DIRECTIONS[axis]` (32 axes) | higher = **more conservative Alabama position for that axis only** | [−1, +1] per axis | within-axis; no national anchor | panel columns 32; Democratic per-axis coverage 2 (`due_process`) to 202 (`gun_access`) | `analyze_absolute_ideology_rebuild.py` | **yes** — group profiles, issue scatter, cluster features | Within axis only, subject to axis coverage; **not** across axes and **not** Shor–McCarty units |
| 12 | `issue_conservative_<family>` | 7 family composites from `ISSUE_DIRECTIONS` | higher = more conservative | [−1, +1] | within-family | 7 columns | `analyze_absolute_ideology_rebuild.py` | no | Within family only |
| 13 | `candidate_cycle_war` | Race residual: legislative-minus-ticket gap minus fitted structural expected gap | higher = candidate outran expectation (candidate-directional, **not** left/right) | two-party margin points | **two vintages**: post-2016 Southern model backcast (1998–2014) and published same-cycle residual (2018, 2022) | 311 page rows; 509 contested races 1994–2022 in the export | `build_alabama_historical_war_v1.py` | **yes** — headline, distribution, trend, cases, table | Within one vintage; backcast and same-cycle rows are different constructions and the page discloses this |
| 14 | `candidate_federal_overperformance`, `candidate_presidential_overperformance` | `party_direction × (legislative margin − baseline margin)` | higher = outran that specific baseline | two-party margin points | federal index baseline / previous presidential result | page member rows | election marts + `analyze_absolute_ideology_rebuild.py` | **yes** — overview, distribution, trend, cases, table | Same units as each other but **different baselines**; neither is a substitute for WAR or for ideology |
| 15 | cluster label, `cluster_id`, `constellation_x/y` | K-means label and 2-D MDS projection of per-party standardized primitive axes | n/a (descriptive) | unitless projection coordinates | within-sample | 131 Democratic candidate-cycles; 18 features | `analyze_democratic_ideological_clusters.py`; `build_caucus_analysis_page.py` | **yes** — composition, similarity map | Descriptive within this sample only; not a scale, not formal caucus membership |
| 16 | `sourceCoverage` counts | Rows / candidate-cycles / axes per evidence category | n/a | counts | full research file, both parties | 5 categories | `build_democratic_transition_page_v2.py` | **yes** — methods | Counts, not a scale |

**Measure count: 16** inventoried. Of these, **6 reach the page**: #2, #11, #13,
#14, #15, #16 (plus the per-row WAR scope label, which is a provenance tag, not a
measure). The remaining 10 are internal or, for the chamber/biennium behavioral
scale, currently unpublished (O1).

## Chart-by-measure table (`ideology-performance.html`)

16 rendered chart/table units in 11 sections, produced by 13 named JS renderers.

| # | Section | Unit | Measures plotted | Axis handling | Like-scale verdict |
|---|---|---|---|---|---|
| 1 | `#performance` | `warHeadline` (2 cards) | #13 WAR contrast | text values only | one scale |
| 2 | `#performance` | `contrastList` (2 rows) | #13 WAR contrast | one shared margin-point extent | one scale |
| 3 | `#overview` | `groupGrid` (3 cards) | #13/#14 group means | three separately labeled metric cells, no shared axis | same units, distinct labeled baselines |
| 4 | `#overview` | `ticketContrastList` (4 rows) | #14 federal + presidential contrasts | shared margin-point extent; each row labeled with its baseline | same units, distinct labeled baselines |
| 5 | `#transition` | `transitionChart` | cluster shares | stacked share bars | not a scale |
| 6 | `#positions` | `profileChart` (15 rows × 3 dots) | #11 primitive conservative score | one issue axis per row | per-axis; cross-axis ordering is descriptive only (F3) |
| 7 | `#distribution` | `performanceDistribution` | one selected #13/#14 outcome | one measure per render, axis re-limit | one scale |
| 8 | `#time` | `trendChart` | one selected #13/#14 outcome | one measure per render | one scale |
| 9 | `#issues` | `issuePlot` | #11 (x) vs one #13/#14 outcome (y) | two labeled axes | bivariate by design, not one axis |
| 10 | `#issues` | `issueCoverage` | axis coverage count | count bar | not a scale |
| 11 | `#cases` | `caseStudies` (6 cards) | #13/#14 + dimension count | labeled cells | one scale per cell |
| 12 | `#candidate-explorer` | `constellation` (MDS) | #11 standardized axes → 2-D | projection, explicitly "not individual ideological axes" | projection, not a scale |
| 13 | `#candidate-explorer` | `candidateDetail` | WAR + top `primitive_conservative_*` | labeled list | mixed but separately labeled values |
| 14 | `#candidate-explorer` | `candidateRows` (table) | #13/#14 | one labeled column per measure | one scale per column |
| 15 | `#continuous` | `eraEvidence` (3 rows) | #2 slope per era, with n and 95% interval | one scale, one axis | one scale |
| 16 | `#methods` | `sourceGrid` (5 cards) | #16 counts | counts | not a scale |

No unit plots two unlike scales on one axis, and no unit mixes orientation.

## Findings

- **F1 — `absolute_conservatism_z` is nationally anchored, not a within-sample z.**
  `analyze_symmetric_incumbency_ideology.py` builds it as
  `(panel.shor_np_score − national.mean()) / national.std(ddof=0)` where
  `national` is every `np_score` in the raw 1993–2018 file (24,716 rows, mean
  0.019054, sd 0.898526). The page's wording "nationally comparable Shor–McCarty
  scale" and "one-standard-deviation move" are therefore accurate, and the name
  `absolute_conservatism_z` is not a within-sample mislabel. No fix required.
- **F2 — Orientation is consistent across the page.** Shor (`np_score`, the z),
  the conservative-oriented primitive composites, and the WAR/ticket
  candidate-directional measures each carry their documented sign, and chart
  labels/legends state the orientation. No chart mixes a "positive = liberal"
  scale with a "positive = conservative" scale.
- **F3 — Cross-axis magnitude ordering is the only soft comparability
  assumption.** `profileChart` orders rows by the range of three group means, and
  `primitive_conservative_*` axes are only comparable within an axis (same
  construction, different candidate coverage). The page never claims cross-axis
  comparability, but it also did not state the limit; the new block now does.
- **F4 — The chamber/biennium behavioral scale reaches no public page.**
  `build_legislator_ideology_page.py` writes `docs/legislators.html`, but
  `build_blue_oxblood_site.py` immediately overwrites that file with a redirect
  stub to `ideology-performance.html#issues` (verified: the published file's
  title is "Candidate evidence · Jackson Hannan" and it contains no
  `legislativeIdeology`/`Pre-election score` content). The page copy now states
  that the chamber-relative roll-call score is not displayed. No page fix beyond
  that statement is in scope.
- **F5 — Disclosure gap (fixed).** The page carried no cross-scale statement.
  Added `Scale comparability` to the methods, naming each measure's anchoring
  (national absolute Shor–McCarty z; per-issue coordinates; chamber-relative
  roll-call scale absent; WAR/ticket margin points against different baselines;
  descriptive cluster/similarity/count summaries) and the invalid comparisons
  (one SD is national, issue magnitudes are not cross-issue comparable, no
  measure substitutes for another).
- **F6 — No downloads.** The page has zero data-file links and `docs/data/`
  holds no ideology export, so no scale can reach readers through a download that
  the audit has not inventoried.

## Fix made (copy/label only)

File: `scripts/build_democratic_transition_page_v2.py` — one added
`<div class="method"><h3>Scale comparability</h3><p>…</p></div>` block in the
existing methods grid. No Python logic, payload field, clustering input, WAR
value, or chart geometry changed (artifact grew 594,827 → 596,038 bytes; section
count unchanged at 11). Test file gained four assertions pinning the new copy in
the existing `test_page_language_and_measurements_are_explicit`.

The page's one-paragraph comparability statement now reads:

> These measures are not interchangeable, and no chart mixes measurement
> families on one axis. The Shor–McCarty section uses the source's absolute
> scale, whose scores place legislators from different states and chambers on one
> common continuum; the displayed z-score is distance from the mean of the full
> national 1993–2018 legislator distribution in that scale's own standard
> deviation, so one standard deviation is a national scale unit, not an Alabama
> party, chamber, or election-cycle unit, and the Democratic candidates shown
> occupy only part of that national range. Issue coordinates are separate
> per-issue scales between the poles of that issue, oriented so positive is the
> more conservative Alabama position for that issue only; their magnitudes are
> not comparable across issues and are not Shor–McCarty units. The
> chamber-relative roll-call score used in the research layer is not displayed on
> this page. Residual WAR and the raw federal and presidential comparisons are
> two-party margin points against different baselines, not ideology units. Group
> labels, similarity-map coordinates, and evidence counts are descriptive
> within-sample summaries, not scales, and the grouping was formed before any
> performance or absolute-ideology measure was attached.

Verification: `.venv/Scripts/python.exe scripts/build_democratic_transition_page.py`
rendered the artifact; `.venv/Scripts/python.exe -m pytest --testmon
--testmon-noselect -p no:cacheprovider scripts/tests/test_ideology_performance_page.py -q`
→ **12 passed**. Copy-only nature was confirmed by the artifact size delta and an
unchanged section count; no payload field changed because no Python executed by
`payload()` was edited.

## What remains not comparable (and how the page says so)

- Shor–McCarty absolute z vs the issue coordinates: different anchoring and
  units; the methods block states the z is national and the issue coordinates are
  per-issue, and the `#continuous` section states it "is not a cluster
  comparison".
- Issue coordinate across issues: magnitudes are not comparable; the methods
  block states this. Rows are still ordered by within-axis range (F3), which is a
  presentation convenience, not a commensurability claim.
- Chamber/biennium behavioral score vs everything else: not published and now
  explicitly named as absent.
- WAR backcast vs same-cycle WAR: disclosed in the WAR-definition block; the two
  are not unified into a single certified measure.
- Federal vs presidential raw comparisons: same units, different baselines;
  labeled per row.
- Post-2016 era slope rests on n=5 and each row prints its own n and interval;
  the small n is displayed but no power adjustment is applied.

## Not established

- No independent re-estimation of the era slopes, clustering, or WAR was
  performed; this audit reads published artifacts and source code only.
- The Shor–McCarty source's own national normalization procedure was taken from
  the dataset and its observed party means (D −0.7725, R +0.7587 over 50 states);
  the vendor's calibration document was not consulted.
- Whether an Alabama-only officeholder sample is an adequate basis for the
  national-z slope is a coverage question owned by `ideology-09` (cluster/
  threshold sensitivity) and the evidence-layer validation, not settled here.
- The published `docs/ideology-performance.html` does not yet carry the new
  block; publication is a separate authorized action.

## Out-of-scope findings

- **O1** `scripts/build_legislator_ideology_page.py` is in the site publisher's
  `BUILDERS` list and writes `docs/legislators.html`, which the publisher then
  overwrites with a redirect stub. Its payload (including a `shor` object never
  consumed by `dashboard/legislator_ideology.js`) is discarded, and the
  chamber/biennium behavioral score has no public surface. Fixing or removing it
  touches `docs/` and is outside this task's write scope.
- **O2** `PROJECT_COMPLETION_CHECKLIST.html` still marks `ideology-08` `done:false`
  with empty evidence; per instructions the checklist was not edited.
