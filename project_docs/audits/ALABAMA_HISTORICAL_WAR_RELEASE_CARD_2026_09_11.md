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
| Historical Alabama WAR | `data/processed/war/alabama_historical_war_v1/manifest.json` (`historical_war_run_id`) | 510 races, 1,020 candidate orientations (2002 House 27 added 2026-09-11) |

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

510 contested D-versus-R general-election races, 1994–2022 (54/18, 57/28,
52/23, 40/22, 42/21, 40/16, 49/15, 25/8 by cycle house/senate); 546 races
excluded as unopposed (266 D, 280 R); 0 races excluded for missing context.
2002 Marshall County adjudications (`RUN-DFB1D093D7594AB68A264292050E924D`,
`audits/SOURCE_COLLISION_ADJUDICATION_PACKET_2026_09_11.md`): House 26 now
carries the DeKalb + Marshall district total (D 7,069 / R 4,459), House 27 was
added (D 7,724 / R 4,789; Klarner-corroborated), and Senate 9 gained its
Marshall segment (D 24,603 / R 16,995; the recorded winner was inverted before).
Madison County's Senate 9 precinct cells sum 160 / 247 votes above the sheet's
printed totals; the precinct-cell sum is retained and the discrepancy recorded.

## Backcast policy

413 races (1994–2014) are backcasts: the modern fitted relationship applied to
historical ticket, incumbency, chamber and prior-presidential context
(`scoring_scope = post2016_southern_model_backcast`, `backcast_extrapolation_years`
per row). They are not same-cycle fits and carry no cross-fitted validation.
Era sensitivity (`audits/ALABAMA_BACKCAST_SENSITIVITY_2026_09_11.md`, parity
passed on this run): the backcast preserves rank order against a descriptive
same-era fit on 1994–2014 Alabama (Pearson 0.91–0.96 per cycle) but not level:
same-era residuals are lower by a mean of 20.5 points (5th–95th percentile
−31 to −7), sign agreement 0.66, and the incumbency coefficient halves between
the modern fit (6.2) and 1994–2006 (13.6). Read backcast WAR as a within-cycle
ranking and a modern-relationship extrapolation, not as a level comparable to
2018/2022. Within-cycle bootstrap SE of the expected gap: median 4.7 (1994),
4.9 (1998), 2.4 (2002), 2.3 (2006), 1.5 (2010), 1.7 (2014). 19 races lack lag
context and are scored with the explicit missing-context encoding (`alabama-08`);
a no-lag specification moves them by +2.0 to +5.9 points with one sign change
(2002 House 63).

## Baseline-sensitive districts

Districts whose WAR moved by more than 10 points between the 2026-09-02 export
and this release because their ticket baseline changed, not their legislative
result:

| Race | Baseline before → after | Cause |
|---|---|---|
| 2014 House 52 | 55.6 → 88.3 | federal contested coverage ≈ 0.55 in 2014; allocation re-keyed |
| 2014 House 56 | 39.8 → 74.0 | same |
| 2002 House 26 | −17.7 → −39.6 | Marshall segment missing from the legislative total (now adjudicated; legislative margin 29.6 → 22.6) |

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
