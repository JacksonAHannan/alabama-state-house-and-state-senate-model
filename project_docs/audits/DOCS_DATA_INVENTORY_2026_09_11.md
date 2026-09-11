# docs/data inventory — linked pages, producers, upstream parity and orphan disposition

Audit for checklist item `release-01` ("Remove proven-unused code and duplicate
outputs"), evidence slice `RELEASE-01-DOCS-DATA-ORPHANS-20260911`. Umbrella:
`coordination/CHECKLIST-EXECUTION-20260911.md` (checkpoint 2). Authority: owner
"Proceed" on the listed open follow-ups; this task inventories and proposes, it
does **not** delete, move, publish or rebuild anything.

- Audit timestamp: `2026-09-11T17:05:00Z`
- Repository HEAD inspected: `aa690465` (`git rev-parse --short HEAD`)
- Published lineage: `AL-HIST-WAR-V1-44F191EB8D939EF062CC` on v3
  `WAR-POST2016-V3-530FBD4238CC483E557C`; warehouse
  `RUN-DFB1D093D7594AB68A264292050E924D`; Southern historical
  `WAR-SOUTH-HIST-V1-6D84680E7B757B057AF1`; modern Alabama
  `AL-WAR-V1-C00FF05BC2BE58E16087`; forecast build `368bb272a990ff436e56`
- Companion data: `DOCS_DATA_INVENTORY_2026_09_11.csv` (61 rows, one per file;
  MD5 `e48cb91280035b756296384d57338ae3`; all `mtime` values are UTC)

## 1. Scope and method

Every file under `docs/data/` (61 regular files, no subdirectories) was
inventoried for: linking page(s), producing/copying script, upstream artifact
and byte parity, mtime, embedded run/build id, and a disposition proposal.

Checks run (read-only; no builder, warehouse, or publication write; no LLM/API
call):

| Check | Command / query | Result |
|---|---|---|
| File universe | directory listing of `docs/data/` | 61 files |
| Bytes / mtime | SHA-256 + `stat` per file, in-process (`hashlib`) | recorded per row |
| Page links | regex `(?<![\w/])data/([A-Za-z0-9_.\-]+)` over all 10 `docs/*.html` (covers `href=`, `fetch()`, embedded JSON payload `"download"` fields) | 24 files referenced (exactly the `active` set); 37 not referenced |
| Producers | every `scripts/**/*.py` scanned for each basename and for `docs/data` / `DOCS_DATA` / `site_data` | 3 live writers found |
| Upstream parity | SHA-256 of the declared or same-named upstream under `data/` / `project_docs/` | 44 match, 15 differ, 2 generated in place |
| Git state | `git ls-files docs/data` \| `wc -l`; `git status --porcelain docs/data`; `git check-ignore -v docs/data/cmo_v4_candidates.csv` | 61 tracked, 0 untracked/dirty, not ignored |
| Legacy age | `git log -1 --format='%h %ad %s' --date=short -- docs/data/<file>` | last touched 2026-08-21/22/26 (see §5) |
| Catalog | `grep -n 'docs/' project_docs/data_catalog.csv` | 3 rows (see §7) |

## 2. Result — counts per class

| Class | Count | Share |
|---|---|---|
| `active` (linked by a live page **and** produced by a live publisher) | 24 | 39.3 % |
| `unlinked_current` (produced by a live publisher this release, no page link) | 8 | 13.1 % |
| `superseded` (no live page, no live publisher; legacy leftovers) | 29 | 47.5 % |
| `unknown` (no producer found) | 0 | 0 % |
| **Total** | **61** | |

Byte parity: 44 exact matches, 15 mismatches (all `superseded` stale snapshots),
2 generated in place (`southern_war_map_payload.json`,
`southern_war_map_join_audit.csv` — no upstream by design).

## 3. The three live writers of `docs/data/`

Only three scripts write or copy into `docs/data/`; everything else there is a
leftover. This is the load-bearing finding for `release-01`.

1. **`scripts/build_southern_war_map.py`** — direct writes (`DOCS_DATA.mkdir`
   L575; payload L576; join audit L577-580) and `shutil.copy2` of five Southern
   historical files (L581-588) plus the geography source manifest (L587):
   `southern_historical_war_v1_{race_war,candidate_cycle_war,coverage,manifest}`,
   `southern_historical_war_v1_state_release_coverage`,
   `southern_legislative_geography_manifest`.
2. **`scripts/build_war_story_page.py`**, live `__main__` block at L954-1004 —
   copies the Alabama historical export (5 files), the modern Alabama export
   (4 files), `alabama_war_forecast_v1_forward_metrics.csv`, and
   `project_docs/audits/ALABAMA_HISTORICAL_WAR_RELEASE_CARD_2026_09_11.md`
   (as `alabama_historical_war_release_card.md`).
3. **`scripts/build_2026_forecast_dashboard.py`**, publish block L459-483 —
   copies 17 files from `data/processed/forecast_calibration/`,
   `data/processed/polling/`, `data/raw/polling/silver_recent/`,
   `data/processed/demographics/`, `data/processed/war/`, and
   `data/processed/elections/`; then unlinks 24 named stale files (L485-517).

`scripts/build_blue_oxblood_site.py` (the `project.py build site --publish`
publisher) touches only the ten `docs/*.html` pages and `docs/data/` not at all.

### Dead code named by the task

`scripts/build_war_story_page.py` line 865:

```python
if False and __name__ == "__main__":  # superseded by the residual-WAR publisher below
```

Inside that dead block (L865-913) the loop at L909-911 still copies every
`data/processed/war/cmo_v6_southern_*` into `docs/data/`, and L912 still copies
`project_docs/model/CMO_METHODOLOGY_V6_SOUTHERN_PRIOR.md` to
`docs/data/cmo_methodology_v6.md`. Because the guard is `if False`, this block
never executes: **no live builder copies any `cmo_v4_*`, `cmo_v5_*`, `cmo_v6_*`
or `cmo_methodology_v*.md` file into `docs/data/` today.** The six
`cmo_v6_southern_*` files and `cmo_methodology_v6.md` present there are the
frozen output of that retired publisher (last committed 2026-08-22/26).

## 4. `active` — 24 files (keep as-is)

| Group | Files | Linked by |
|---|---|---|
| Southern map | `southern_war_map_payload.json` (fetched), `southern_war_map_join_audit.csv`, `southern_historical_war_v1_{race_war,candidate_cycle_war,coverage,manifest}`, `southern_historical_war_v1_state_release_coverage.csv`, `southern_legislative_geography_manifest.csv` | `southern-war.html`, `southern-war-methodology.html` |
| Historical Alabama | `alabama_historical_war_v1_{candidate_cycle_war,race_war,coverage,structural_coefficients,manifest}`, `alabama_historical_war_release_card.md` | `cmo.html`, `cmo-methodology.html` |
| Modern Alabama | `alabama_war_v1_candidate_cycle_war.csv` | `index.html` embedded source ledger, `methodology.html` |
| Forecast and shared inputs | `alabama_war_forecast_v1_{2026_scenarios,forward_metrics,forward_predictions,manifest}`, `robust_forecast_v1_error_components.csv`, `2026_sld_demographics.csv`, `polling_environment.csv`, `next_forecast_tournament_region_features.csv`, `canonical_cmo_candidates.csv` | `index.html` / `methodology.html` (some links are emitted at runtime from the embedded ledger JSON) |

Every `active` file is byte-identical to its upstream or generated in place.
Proposal: **keep, no change.**

Two task-hinted names are **not** superseded and must not be removed on that
basis: `canonical_cmo_candidates.csv` and `2026_sld_demographics.csv` are copied
by the live forecast publisher (`build_2026_forecast_dashboard.py` L479/L476) and
linked from the `index.html` embedded source ledger. `southern_legislative_geography_manifest.csv`
is likewise live-copied and linked.

## 5. `unlinked_current` — 8 files (live, unlinked)

| File | Producer | Proposal |
|---|---|---|
| `alabama_war_v1_race_war.csv` | `build_war_story_page.py`, `build_2026_forecast_dashboard.py` | keep; optionally link from the Alabama downloads block. **Byte-parity pinned** by `test_published_site_consistency.py::test_publication_exports_match_current_model_outputs` and read by `test_public_cmo_and_forecast_row_counts` + `test_grimsley_public_war_is_corrected_race_residual`; removal needs those tests changed |
| `alabama_war_v1_coverage.csv` | same | keep; optionally link. Pinned by the byte-parity test |
| `alabama_war_v1_manifest.json` | same | keep; optionally link. Pinned by the byte-parity test |
| `alabama_war_forecast_v1_2026_full_uncertainty.csv` | `build_2026_forecast_dashboard.py` (upstream `run_alabama_war_generic_forecast.py`) | keep; optionally link from `methodology.html`. Pinned by the byte-parity test |
| `alabama_war_forecast_v1_2026_modeled_seats.csv` | same | keep; optionally link (seat accounting). Pinned by the byte-parity test |
| `alabama_war_forecast_v1_probability_families.csv` | same | keep; optionally link (probability-family comparison). Pinned by the byte-parity test |
| `poll_source_manifest.csv` | `build_2026_forecast_dashboard.py` L475, from immutable `data/raw/polling/silver_recent/manifest.csv` | **link** from `methodology.html` as polling provenance (preferred); or remove by deleting the copy line. Not pinned |
| `rdh_2024_sld_cvap.csv` | `build_2026_forecast_dashboard.py` L477, from `data/processed/demographics/` | **remove** from `docs/data/` — it is a model input, not a published product; delete the copy line. Not pinned. Alternative: link as a demographics source |

## 6. `superseded` — 29 files, exact removal list proposal

All 29 have no page link and no live publisher. The docs copies are either
byte-identical duplicates of an upstream that is retained, or stale snapshots
that now disagree with the rebuilt upstream.

| Files (29) | Producer of the upstream | Parity | Note |
|---|---|---|---|
| `cmo_v4_races.csv`, `cmo_v4_candidates.csv`, `cmo_v4_components.csv`, `cmo_v4_coefficients.csv`, `cmo_v4_model_tournament.csv`, `cmo_v4_construct_validity.csv`, `cmo_v4_cycle_diagnostics.csv`, `cmo_v4_provenance.csv` (8) | `scripts/rebuild_cmo_war_analogue.py` | byte-identical to `data/processed/war/` | last committed 2026-08-21; **catalog-coupled** (see §7) |
| `cmo_v5_races.csv`, `cmo_v5_candidates.csv`, `cmo_v5_candidate_effects.csv`, `cmo_v5_model_tournament.csv`, `cmo_v5_case_studies.csv`, `cmo_v5_incumbency_transitions.csv`, `cmo_v5_party_symmetry.csv`, `cmo_v5_provenance.csv` (8) | `scripts/rebuild_cmo_candidate_quality_v5.py` | **differ** | docs snapshot 2026-08-22; upstream rebuilt 2026-09-11. Upstream `cmo_v5_races/candidates.csv` remain required compatibility inputs for the live Alabama historical builder — only the docs copies are proposed for removal |
| `cmo_v6_southern_races.csv`, `cmo_v6_southern_candidates.csv`, `cmo_v6_southern_quality.csv`, `cmo_v6_southern_validation.csv`, `cmo_v6_southern_case_studies.csv`, `cmo_v6_southern_manifest.json` (6) | `scripts/rebuild_cmo_southern_prior_v6.py` | **differ** | docs snapshot 2026-08-26; upstream rebuilt 2026-09-11; upstream retained as the legacy compatibility bundle |
| `cmo_diagnostics.csv`, `cmo_forward_validation.csv`, `cmo_benchmark_diagnostics.csv` (3) | `scripts/fit_preliminary_war_model.py` | byte-identical to `data/processed/war/` | last committed 2026-08-21 |
| `cmo_forward_interval_calibration.csv` (1) | `scripts/calibrate_forward_cmo_uncertainty.py` | byte-identical | last committed 2026-08-21 |
| `cmo_methodology_v5.md` (1) | source `project_docs/model/CMO_METHODOLOGY_V5.md` (retained) | **differs** (2,216 B vs 2,366 B) | stale prose snapshot |
| `cmo_methodology_v6.md` (1) | source `project_docs/model/CMO_METHODOLOGY_V6_SOUTHERN_PRIOR.md` (retained) | byte-identical | copied only by the dead `if False` block |
| `cmo_model_card.md` (1) | source `project_docs/model/CMO_MODEL_CARD.md` (retained) | byte-identical | copied only by the dead `if False` block |

### Proposed removal set (30 files)

Primary (this audit's recommendation, subject to owner authorization):

```
docs/data/cmo_v4_candidates.csv          docs/data/cmo_v5_candidates.csv
docs/data/cmo_v4_coefficients.csv        docs/data/cmo_v5_candidate_effects.csv
docs/data/cmo_v4_components.csv          docs/data/cmo_v5_case_studies.csv
docs/data/cmo_v4_construct_validity.csv  docs/data/cmo_v5_incumbency_transitions.csv
docs/data/cmo_v4_cycle_diagnostics.csv   docs/data/cmo_v5_model_tournament.csv
docs/data/cmo_v4_model_tournament.csv    docs/data/cmo_v5_party_symmetry.csv
docs/data/cmo_v4_provenance.csv          docs/data/cmo_v5_provenance.csv
docs/data/cmo_v4_races.csv               docs/data/cmo_v5_races.csv
docs/data/cmo_v6_southern_candidates.csv docs/data/cmo_diagnostics.csv
docs/data/cmo_v6_southern_case_studies.csv docs/data/cmo_forward_interval_calibration.csv
docs/data/cmo_v6_southern_manifest.json  docs/data/cmo_forward_validation.csv
docs/data/cmo_v6_southern_quality.csv    docs/data/cmo_benchmark_diagnostics.csv
docs/data/cmo_v6_southern_races.csv      docs/data/cmo_methodology_v5.md
docs/data/cmo_v6_southern_validation.csv docs/data/cmo_methodology_v6.md
docs/data/rdh_2024_sld_cvap.csv          docs/data/cmo_model_card.md
```

= 29 `superseded` + `rdh_2024_sld_cvap.csv` (unlinked model input).

Conditional / not recommended for removal without further edits:

- `poll_source_manifest.csv` — prefer linking as polling provenance.
- `alabama_war_v1_{race_war,coverage}.csv`, `alabama_war_v1_manifest.json`,
  `alabama_war_forecast_v1_2026_{full_uncertainty,modeled_seats}.csv`,
  `alabama_war_forecast_v1_probability_families.csv` — keep (or link): 6 of them
  are byte-parity pinned by `test_published_site_consistency.py`; removing them
  requires updating that test (and, for `race_war`, two row-count tests).

Alternative to removal for the 29 `superseded` files: move them under an
explicitly labelled `docs/data/superseded/` path if the owner wants the old
public URLs to keep resolving. The repository's only existing superseded-path
precedent is `data/processed/war/post2016_southern_war_v3_archive/`; there is no
`docs/` precedent today.

## 7. Catalog cross-check

`project_docs/data_catalog.csv` references `docs/data/` in exactly 3 of its rows:

| asset_id | locator | declared owner | status | Finding |
|---|---|---|---|---|
| `published_cmo_v4_data` | `docs/data/cmo_v4_candidates.csv` | `scripts/build_war_story_page.py` | `active` | **incorrect if the removal proceeds** — the file is unlinked and its only copier is the dead `if False` block; "Current publication-only CMO export" is also contradicted by `CANONICAL_PIPELINES.md` ("CMO v4/v5 … are not current public defaults") |
| `southern_war_map_payload` | `docs/data/southern_war_map_payload.json` | `scripts/build_southern_war_map.py` | `active` | correct, no change |
| `southern_war_map_join_audit` | `docs/data/southern_war_map_join_audit.csv` | `scripts/build_southern_war_map.py` | `active` | correct, no change |

Catalog entries that would need updating if a file were removed:

- `published_cmo_v4_data` (data_catalog.csv row 39; declared in
  `scripts/build_data_catalog.py` `ASSETS`, L47). If `cmo_v4_candidates.csv` is
  removed, this asset must be re-pointed or dropped. Because
  `scripts/tests/test_data_catalog.py::test_catalog_export_and_sync_are_idempotent`
  asserts `data_catalog.csv` equals `build_data_catalog.ASSETS` exactly (and the
  synced `warehouse_asset`/`warehouse_asset_lineage` rows), the CSV and the
  `ASSETS` list must change together.
- Regenerating the catalog with `python scripts/build_data_catalog.py` writes
  both `project_docs/data_catalog.csv` **and** the warehouse (`warehouse_asset`,
  `warehouse_asset_lineage`), so a catalog refresh is a warehouse write and
  needs the same authorization as any warehouse change.
- No catalog row exists for the current Alabama historical, modern Alabama or
  forecast publication files (only the Southern payload/join audit are
  catalogued as publications). This is a catalog gap independent of removal.
- `scripts/audit_repository_hygiene.py` (`audit` target) flags only
  `cmo_v2_*`, `cmo_v3_*`, `preliminary_cmo_*` under `docs/data/` (regex
  `LEGACY_PUBLIC`, L11). It does not flag `cmo_v4_*`, `cmo_v5_*`, `cmo_v6_*` or
  the duplicated methodology/model-card prose, which is why these leftovers
  survived the hygiene check. Extending that regex is an optional follow-up if
  the removal policy is adopted.

## 8. Repository rules and authorization boundary

- `AGENTS.md` and `CANONICAL_PIPELINES.md`: `docs/` and `docs/data/` are
  publication outputs, never upstream inputs; publication is a separate,
  explicitly authorized action with a recorded rollback path.
- Consequence: deleting any file under `docs/data/` changes the public site
  (GitHub Pages serves `docs/`) and is a **publication action**, not a code
  cleanup. This audit only proposes; the removal requires the owner's explicit
  authorization and a commit, with the published-state rollback reference for
  the current release (`f407b9d0`).
- Deleting the 29 superseded files from `docs/data/` does **not** delete any
  upstream artifact: the `data/processed/war/cmo_v4_*`, `cmo_v5_*`,
  `cmo_v6_southern_*` and `cmo_diagnostics`-family files stay in place, and the
  prose sources stay under `project_docs/model/`. This preserves the required
  replay/compatibility artifacts and the `cmo_v5_*` compatibility inputs used by
  the live Alabama historical builder.
- The dead `if False` publisher block (L865-913) is code the cutover already
  obsoletes; removing it is a separate, in-scope cleanup candidate but is not
  done by this task (write scope is this audit's two files).

## 9. What is NOT established / limitations

- No builder was executed. Producer attribution is static source reading;
  a producer that writes a differently-named file, or a manual/out-of-band
  commit, would not be caught. The `unknown` count of 0 is therefore
  "no producer found in `scripts/`", not proof that none exists elsewhere.
- No HTTP check against the live GitHub Pages deployment was performed, and no
  external inbound links (search engines, third-party sites) were enumerated.
  Removing files could break external deep links; that risk is unmeasured here.
- No analytics or access logs were consulted, so actual download demand for any
  file (active or superseded) is unknown.
- The warehouse was not opened at all; no database reads or writes were made.
- Only `test_published_site_consistency.py`, `test_southern_war_map.py`,
  `test_forecast_dashboard.py`, `test_data_catalog.py` and
  `test_absolute_ideology_rebuild.py` were read to establish pinning; the full
  suite was not run (per task instructions), so an additional consumer test
  outside those files cannot be fully excluded.
- `bytes_match` compares the docs copy against the single declared or same-named
  upstream; for the two in-place generated files it is reported `n/a`.

## 10. Out-of-scope findings (recorded, not acted on)

- `scripts/build_war_story_page.py` retains large legacy template dead code
  (`modernize_v6_copy`, `build_methodology` variants, the `if False` block at
  L865-913) whose rendered strings name superseded products; no live page emits
  them.
- `scripts/build_2026_forecast_dashboard.py` already unlinks 24 stale forecast
  downloads at publish time (L485-517), but the equivalent cleanup for the
  CMO-era and `rdh_2024_sld_cvap.csv`/`poll_source_manifest.csv` leftovers does
  not exist — this is the recurrence path that produced the current 29
  superseded files.
- The earlier removal of the 24 legacy forecast downloads is recorded by
  `FORECAST_PUBLIC_CONTRACT_RECONCILIATION_2026_09_10.md` and
  `audits/SITE_RELEASE_2026_09_11.md`; the current inventory confirms none of
  them remain.
