# Alabama historical WAR — release card and limitations (2026-09-11)

Checklist item `alabama-11`. This card accompanies the historical Alabama WAR
release built on the retrained Southern residual source. It is copied into the
public downloads by the story-page builder so the run identifiers and
limitations travel with the data. It does not itself approve publication.

## Run identifiers

| Layer | Run | Notes |
|---|---|---|
| Warehouse (analytical target) | `RUN-504CE4C4DF904D88A5A40D268F3FCEAB` | `southern_war_preparation_no_finance`; 4,582 outcomes, 4,280 strict |
| Southern residual source | see `data/processed/war/post2016_southern_war_v3/manifest.json` (`model_run_id`) and `project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` | approved for descriptive historical use; supersedes `WAR-POST2016-V3-4AF79A70EAA8F39EBD49` and, before it, `8BB52074…` |
| Modern Alabama WAR | `data/processed/war/alabama_war_v1/manifest.json` (`alabama_war_run_id`) | exact Alabama rows of the source run, 97 races |
| Historical Alabama WAR | `data/processed/war/alabama_historical_war_v1/manifest.json` (`historical_war_run_id`) | 509 races, 1,018 candidate orientations |

Exact identifiers and hashes are read from those manifests at publication time;
the published `docs/data/*_manifest.json` copies are the authoritative record for
the page. Reproducible commands (in order): `scripts/build_canonical_geographic_weights.py`,
`scripts/build_1994_cmo_baseline.py`, `scripts/build_historical_federal_baselines.py`,
`scripts/build_canonical_cmo_features.py`, `scripts/rebuild_cmo_candidate_quality_v5.py`,
`scripts/build_southern_war_panel_v1.py`, `scripts/load_southern_war_preparation_warehouse.py`,
`scripts/retrain_post2016_southern_war_v3.py`, `scripts/build_alabama_war_v1.py`,
`scripts/build_alabama_historical_war_v1.py`, `scripts/build_war_story_page.py`.

## Repaired-input status

- Certified canvass totals (2018, 2022) are the legislative totals: 21 canonical
  corrections, 12 inside the 97 modern races
  (`audits/ALABAMA_CERTIFIED_CANONICAL_REPAIR_2026_09_08.md`).
- 2022 incumbency corrected on 17 in-universe races
  (`audits/ALABAMA_HISTORICAL_RACE_UNIVERSE_2026_09_10.md`).
- Precinct identity re-keyed under the September repairs; 1994 precincts are
  provider-code keyed (7,384 weight rows vs 6,441 name-keyed before).
- Morgan 1994 Attorney General precinct 26001 adjudicated to the provider's
  reported total 144 (`ADJ-1994-MORGAN-26001-AG2-K48`); the raw workbook cell
  (144.4) and before-image are retained.
- The same-cycle federal ticket baseline was rebuilt from the repaired warehouse
  (`RUN-70A750C82BEC43D686E5F4B1FE13461C`). The prior published scores used the
  2026-08-21 baseline; see `audits/ALABAMA_TICKET_BASELINE_STALENESS_2026_09_11.json`.

## Coverage and exclusions

509 contested D-versus-R general-election races, 1994–2022 (54/18, 57/28,
51/23, 40/22, 42/21, 40/16, 49/15, 25/8 by cycle house/senate); 546 races
excluded as unopposed (266 D, 280 R); 0 races excluded for missing context.
Recorded open question: 2002 House 27 appears as a contested race in the SOS
source but has no canonical candidate row (not adjudicated; `warehouse-05`).

## Backcast policy

412 races (1994–2014) are backcasts: the modern fitted relationship applied to
historical ticket, incumbency, chamber and prior-presidential context
(`scoring_scope = post2016_southern_model_backcast`, `backcast_extrapolation_years`
per row). They are not same-cycle fits and carry no cross-fitted validation.
Era sensitivity is not yet assessed (`alabama-07`). 18 races lack lag context
and are scored with the explicit missing-context encoding (`alabama-08`).

## Baseline-sensitive districts

Districts whose WAR moved by more than 10 points between the 2026-09-02 export
and this release because their ticket baseline changed, not their legislative
result:

| Race | Baseline before → after | Cause |
|---|---|---|
| 2014 House 52 | 55.6 → 88.3 | federal contested coverage ≈ 0.55 in 2014; allocation re-keyed |
| 2014 House 56 | 39.8 → 74.0 | same |
| 2002 House 26 | −17.7 → −39.6 | Marshall County conflicting `vote_observations` sets (unadjudicated) |

Median absolute WAR change across all 509 races: 0.42 points. Full deltas:
`artifacts/war/alabama_dependency_rebuild_20260910/` and
`audits/ALABAMA_WAR_DEPENDENCY_REBUILD_2026_09_10.md`.

## Geography uncertainty

Display outlines are the registered plan geometries; they do not certify a vote
allocation. 1994–2006 allocations use legislative-activity splits with county
fallback (`build_canonical_cmo_features.py`), 2010–2022 use the canonical
precinct-to-district weights. The 2008 precinct-name allocation review
(`alabama-06`) remains open.

## Not established

Era sensitivity of the backcast; the 2002 House 26/27 source adjudications;
independent browser review of the published page (performed at publication);
any predictive claim.
