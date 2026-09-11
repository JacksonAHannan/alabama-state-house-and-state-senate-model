# Site release — 2026-09-11

Owner authorization (2026-09-11): publish the four pages and commit the
accepted work. Executed under `coordination/CHECKLIST-EXECUTION-20260910.md`
after the structural fix to the v3 manifest contract. Publication commit `f407b9d0` pushed to `origin/master` (GitHub Pages serves
`docs/`); the prior published state is commit `720c350`, the rollback reference.
Not committed: SQLite warehouse and backups (ignored), two >100 MB replay
proposals under `artifacts/warehouse/legacy_source_lineage_20260908/`, the three
`precinct_identity_stage_*` copies, `data/processed/precinct_history/*.gpkg`,
scratch directories; all remain on disk with hashes recorded in their audits.

## Lineage published

| Product | Run / build | Source |
|---|---|---|
| Southern residual source | `WAR-POST2016-V3-530FBD4238CC483E557C` | warehouse `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`; decision `SOUTHERN_V3_RELEASE_DECISION.json`; reviews `SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_11.md` (scientific) and `…_CONTRACT.md` (manifest contract) |
| Southern historical WAR (`docs/southern-war.html`) | `WAR-SOUTH-HIST-V1-6D84680E7B757B057AF1` | 116 slices, 4,280 strict races, 8,560 orientations, 620 labeled 2016 backcasts, 302 reason-coded exclusions; map payload SHA-256 `c9535d00bce8316dc0ea8d37ddc26b4690b0101a436a7c9d308172add9c327ab` |
| Modern Alabama WAR | `AL-WAR-V1-C00FF05BC2BE58E16087` | exact Alabama rows of the source run (97) |
| Historical Alabama WAR (`docs/cmo.html`) | `AL-HIST-WAR-V1-76814789B2F7641E4255` | 509 races / 1,018 orientations; release card published as `docs/data/alabama_historical_war_release_card.md` |
| 2026 forecast (`docs/index.html`) | build `368bb272a990ff436e56` | `war_training_warehouse_run_id RUN-504CE4C4…`; owner-selected structural spec; 48 modeled seats × 3 scenarios |
| Ideology and caucuses (`docs/ideology-performance.html`, `caucuses.html`, `legislators.html`) | local candidates copied by the site publisher | joined to `AL-HIST-WAR-V1-76814789…`; Luna full-corpus adjudication and sponsorship channel (2026-09-08) now public |

## What changed for readers

- Alabama 2018/2022 residuals and every Alabama-derived product now use the
  same-cycle ticket baseline rebuilt from the repaired warehouse; the previous
  publication used the 2026-08-21 baseline (`ALABAMA_TICKET_BASELINE_STALENESS_2026_09_11.json`).
  Six Southern `war_party` labels changed (AL 2018 HD47 is the only material one).
- Certified 2018/2022 canvass totals and corrected 2022 incumbency flow through.
- Forecast page: the "adjustment remains zero" contradiction is gone; the MAE
  note names the 2,039-race post-2016 training set; the uniform national-to-Alabama
  transfer is labeled an owner-selected assumption; 24 legacy forecast downloads
  removed from `docs/data/` (list in `FORECAST_PUBLIC_CONTRACT_RECONCILIATION_2026_09_10.md`
  handoff); scenarios CSV dropped legacy columns and carries
  `status=uniform_generic_ballot_environment_selected`.
- Alabama methodology gained explicit limitations for provisional pre-2010
  allocation geometry and the baseline-sensitive districts 2014 HD52/HD56 and
  2002 HD26.

## Verification

- Publisher: `python scripts/project.py build site --publish` (six builders,
  theme applied to ten pages).
- Browser (headless Chromium, served over HTTP, 1258×900 and 390×844, all ten
  pages): 0 console errors, 0 page errors, 0 failed requests; forecast and Alabama
  maps render (105 / 189 district paths), Southern map renders; no legacy claim
  strings; run identifiers on the Southern methodology page equal the manifests.
  Known pre-existing issue, identical in the prior published HEAD: horizontal
  overflow at 390 px on the three methodology shells (shared header nav /
  mobile TOC; `table.limitations` on the Southern methodology). Logged for
  `release-05`.
- `scripts/run_southern_war_browser_checks.mjs`: all 116 slices, keyboard focus
  after empty slice, no overflow, no console/page/request errors; `failures: []`.
- Download parity: every `docs/data` copy of the Alabama historical/modern WAR,
  Southern historical manifest, forecast bundle and release card is byte-identical
  to its upstream; `docs/index.html` payload version equals the published forecast
  manifest build id.
- Tests after publication: 68 passed (story page, forecast dashboard, published
  site consistency, site brand, Southern map, ideology and caucus pages, data
  catalog); earlier in the cycle 57 gate/v3/stale-input tests and 50 Southern
  data tests passed. No full repository suite was run for this release.

## Limitations carried into the release

Backcast era sensitivity (`alabama-07`), 2002 HD26/HD27 source adjudications
(`warehouse-05`), polling snapshot refresh policy (`forecast-04`), and the
ideology evidence-layer acceptance items (`ideology-04..11`) remain open and are
stated on the respective pages or cards. Publication does not close them.

## Second release, 2026-09-11 (post-crash continuation)

Owner authorization: publish once after the 2002 Marshall rebuild. Published:

- Historical Alabama WAR `AL-HIST-WAR-V1-44F191EB8D939EF062CC` (510 races /
  1,020 orientations; 413 backcast; 19 missing-lag) after the owner-adjudicated
  2002 Marshall canonical repair `RUN-DFB1D093D7594AB68A264292050E924D`
  (House 26 A1, House 27 B1, Senate 9 same defect; independent pre-application
  review `ALABAMA_2002_MARSHALL_CANONICAL_REVIEW_2026_09_11.md` PASS). Versus the
  first release exactly two WAR values changed (2002 Senate 9 +21.1, 2002 House 26
  −7.0) and House 27 was added; the other 507 races are unchanged. The Southern
  v3 run, its training-frame digest, the forecast and the Southern historical run
  are unaffected (2002 is outside the modern training frame).
- Alabama methodology and release card: era-level non-transportability of the
  backcast disclosed (`ALABAMA_BACKCAST_SENSITIVITY_2026_09_11.md`), the 2002
  adjudications and the Madison sheet discrepancy recorded.
- Mobile shells: `blue_oxblood_theme.css` narrow-viewport containment; all ten
  pages render without horizontal overflow at 390 px.
- 2014 House 31/66, Senate 30 party labels: owner option C1 — preserved as source
  fact with a consumer warning in the adjudication packet; canonical totals were
  already correct and the contests are unopposed/excluded.

Verification: 20 page renders (ten pages × 1258/390 px) over HTTP; 0 overflow, 0
legacy claim strings, era disclosure present, maps render (105/189/130 district
paths). One transient request failure on the first desktop load of `index.html`
did not reproduce. Download parity byte-identical for the Alabama historical
manifest/export, release card and the legacy `cmo_v6` downloads. Tests: 71
affected tests pass (historical WAR, Alabama v1, cmo v5/v6, canonical finance,
panel, ideology/caucus pages, repair fixtures, backcast sensitivity).

## Third release, 2026-09-11 (forecast probability scale; docs/data cleanup)

Owner decisions: select the Student-t(5) scale from holdout margin residuals
(option 1 of `FORECAST_SELECTION_AND_CALIBRATION_INDEPENDENCE_2026_09_11.md`);
remove the 30 superseded `docs/data` downloads; leave git history as is.

- Forecast build `b76d607f2d81e54697a3`: scale 8.00 by maximum likelihood on the 33
  holdout residuals (was 2.00 at the Brier grid boundary); nominal 80% interval
  now covers 85% of holdout residuals (was 18%); holdout Brier 0.0176 (was
  0.0051). Point margins and chamber seat distributions are identical to the
  previous build; nine district probabilities move by more than 0.05 (max 0.27)
  and four races now sit in the 0.10–0.90 band; expected Democratic seats 12.05
  → 12.31. The manifest records `probability.selection_rule`,
  `holdout_coverage_80` and `holdout_brier`; the field contract forbids
  binary-Brier scale selection; page and methodology state the rule and coverage.
- `docs/data`: 30 superseded files removed at publish (cmo_v4/v5/v6 families,
  legacy diagnostics and model cards, `rdh_2024_sld_cvap.csv`); 31
  files remain, all produced by the three live publishers. Catalog: the public
  export node now points at the historical WAR download; `published_cmo_v4_data`
  is `retired`; `alabama_historical_war_release` added.

Verification: 20 renders (ten pages × two viewports) with no overflow, no page
or console errors except the browser's automatic `favicon.ico` request (no
favicon is published; pre-existing), no legacy claim strings; methodology
carries the scale rule. 33 forecast/dashboard/catalog/story-page tests pass.

## Fourth release (2026-09-11, after commit `a26f9013`)

Owner decisions: repair the 2014 state-ticket baseline source substitution
(`alabama-04`); accept the source-terms inventory as documented without
further sourcing work (`release-08`).

- `build_canonical_cmo_features.py` applies the legacy spatial override only to
  2018/2022; 2014 keeps the SOS-canonical allocation (exact conservation).
  Rebuilt: canonical features -> cmo_v5 -> cmo_v6 prior -> Southern panel ->
  `alabama_war_v1` (`AL-WAR-V1-68CE14574E53AD91E73F`, values identical to the
  published export; re-hashes the amended forecast field contract) -> forecast
  build `db49297557ebfc98fb33` (scenarios byte-identical) -> historical
  `AL-HIST-WAR-V1-0E018273EBEDEEEFAD75` (26 of 510 races moved, |ΔWAR| ≤ 2.2 pp).
  v3 `WAR-POST2016-V3-530FBD4238CC483E557C` and its training-frame digest unchanged.
- Ideology page: source attribution (LegiScan CC BY 4.0, Vote Smart,
  Shor–McCarty CC0, SOS) and scale-comparability block published.
- Forecast field contract: seat-treatment section published via methodology rebuild.
- Verification: 10 pages × 2 viewports served over HTTP, 0 console errors,
  0 failed requests, 0 horizontal overflow; six `docs/data` downloads hash-equal
  to their upstream artifacts; 53 chain tests + 65 page/site tests pass.
