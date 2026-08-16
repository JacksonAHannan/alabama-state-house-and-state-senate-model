# Precinct data rebuild: OpenElections as the canonical vote source

## Problem

The WAR model's precinct-level vote data is currently assembled from a
different pipeline per election cycle:

- **2014 legislative + statewide baseline**: `openelections-data-al`'s
  normalized precinct CSV, manually copied into
  `data/raw/openelections/20141104__al__general__precinct.csv`, plus a
  hand-written repair (`load_jefferson_2014_legislative` in
  `scripts/build_war_database.py`) because OE's 2014 file omits Jefferson
  County's state legislative contests.
- **2018 legislative + statewide baseline**: same pattern, OE CSV manually
  copied to `data/raw/openelections/20181106__al__general__precinct.csv`, no
  known gaps.
- **2012 presidential** (feeds the 2014 trend feature): a raw Alabama
  Secretary of State zip (`data/raw/alabama_elections_and_geography/2012General-PrecinctLevel.zip`),
  a bespoke normalizer (`scripts/normalize_2012_president.py`), and a
  purpose-built VTD crosswalk (`scripts/build_2012_president_vtd_crosswalk.py`,
  `scripts/build_2012_president_on_2018_map.py`).
- **2016 and 2020 presidential** (feed the 2018 and 2022 trend features): VEST
  shapefiles (`data/raw/alabama_elections_and_geography/al_vest_16`, `al_vest_20`) matched to
  legislative-district allocation weights via inline `rapidfuzz` fuzzy string
  matching in `scripts/build_vest_presidential_districts.py`.
- **2022 legislative + statewide baseline + presidential trend source**: RDH
  precinct/district-split shapefiles (`data/raw/alabama_elections_and_geography/al_gen_22_prec`).

This patchwork is the source of the inconsistency the rebuild is meant to
fix: four different vote-count sources, normalization logic duplicated and
subtly diverging across scripts, a silent manual copy step for the two
cycles that already use OE, and an inline fuzzy-matcher (no accept/review
split, no persisted crosswalk) for two of the five non-2022 cycles.

`openelections-data-al` (sibling repo at
`C:\Users\User\Documents\GitHub\openelections-data-al`) now has
precinct-level general-election results for 2012, 2014, 2016, 2018, and 2020,
verified byte-identical to this repo's current 2014/2018 copies. It does not
yet have 2022.

## Goals

1. OpenElections precinct CSVs become the single vote-count source for every
   cycle OE covers: 2012, 2014, 2016, 2018, 2020.
2. One shared normalization module (party mapping, pseudo-candidate
   filtering, office filtering) replaces the logic currently duplicated
   across `build_war_database.py`, `normalize_2012_president.py`, and
   `build_vest_presidential_districts.py`.
3. Precinct-to-legislative-district geometry crosswalks are reused across
   cycles that share a map vintage, instead of being rebuilt per cycle with
   different methodologies.
4. Every OE-sourced cycle gets an automated total-checksum validation step
   (component rows sum to reported `Total` rows) as part of the pipeline,
   not a one-off manual check.
5. Outputs are diffed against the current committed WAR feature table and
   precinct totals before any old script is deleted, so regressions are
   visible before cutover.

## Non-goals

- 2022 is out of scope. The RDH shapefile pipeline
  (`rdh_2022_cycle` in `build_war_database.py`) is untouched — OE has no 2022
  precinct data yet.
- No change to the WAR model specification, feature set, or fitting scripts
  beyond what's needed to consume the rebuilt precinct data with the same
  schema as today.
- No attempt to backfill 2008 presidential precinct data (already documented
  in `project_docs/model/MODEL_READINESS.md` as unavailable; unaffected by this rebuild).

## Design

### Precinct-to-district allocation: one matching technique, not per-cycle geometry

Closer reading of the actual (as opposed to nominally documented) current
pipeline found that the live, consumed method for 2012->2014 is not the VTD
crosswalk at all: `build_2012_presidential_districts.py` matches 2012
precinct names directly (county-scoped exact/fuzzy `rapidfuzz` match,
accept threshold score>=92/margin>=4) against 2014's own
`precinct_district_allocation_weights.csv`, with within-county fallback
distribution for unmatched votes. The VTD-crosswalk scripts
(`build_2012_president_vtd_crosswalk.py`, `build_2012_president_on_2018_map.py`,
and the underlying `build_2014_precinct_crosswalk.py` VTD-matching apparatus)
are redundant with this — not the live path. Likewise, for 2016/2020 the
live method in `build_vest_presidential_districts.py` is polygon-area
overlay of VEST shapefiles against district shapefiles (`build_spatial`);
that file's `rapidfuzz`-based `build()` function is dead code.

Since `precinct_district_allocation_weights.csv` already exists for every
target cycle (2014, 2018, and 2022, the last via the untouched RDH path),
the direct-name-match-against-target-weights technique already proven for
2012->2014 generalizes cleanly to all four source/target pairs — 2012->2014,
2016->2018, 2016->2022, 2020->2022 — as one function, with no shapefiles, no
VTD crosswalk, and no map-vintage bookkeeping required. This is a bigger
simplification than originally scoped: it retires the VTD-crosswalk
apparatus entirely (its only consumers were the presidential-trend scripts
being replaced), not just the 2012 and 2016 pieces.

2020->2022 remains the one case with real residual uncertainty: 2020's
election used the 2017-remedial map, but its votes are matched against
2022's RDH precinct names (2021-enacted map), so precinct consolidation
across that redistricting can lower the match rate versus the other three
pairs. The technique surfaces this directly through its per-row
`match_method` and per-district `fallback_share` outputs rather than hiding
it in geometry, so it stays flagged as lower-confidence and reviewed on its
own rather than assumed equivalent to the other three pairs.

### Pipeline stages

1. **Sync**: an explicit script copies the relevant OE CSVs
   (`2012/20121106__al__general__precinct.csv`,
   `2014/20141104__al__general__precinct.csv`,
   `2016/20161108__al__general__precinct.csv`,
   `2018/20181106__al__general__precinct.csv`,
   `2020/20201103__al__general__precinct.csv`) from the sibling
   `openelections-data-al` repo into `data/raw/openelections/`, replacing the
   current silent manual copy. Running it is a visible, logged step, not a
   one-time hand copy.
2. **Normalize**: one shared module applies party mapping, pseudo-candidate
   filtering (`Write-ins`, `Over Votes`, `Under Votes`, `Total`,
   `Registered Voters`), and office filtering, used by every OE-sourced
   cycle. The Jefferson County 2014 repair stays (it's a documented gap in
   OE's own 2014 file, not something this rebuild changes), but moves into
   this shared module's cycle-specific hook rather than living inline in
   `build_war_database.py`.
3. **Allocate to legislative districts**: one generalized function matches
   source-year precinct names against the target cycle's own
   `precinct_district_allocation_weights.csv` (county-scoped exact/fuzzy
   match, within-county fallback for unmatched votes) — the technique
   already proven for 2012->2014, applied uniformly to 2012->2014,
   2016->2018, 2016->2022, and 2020->2022.
4. **Validate**: an automated checksum step (component rows sum to reported
   `Total` rows per precinct/candidate, following OE's own
   `src/total_checksum.py` logic) runs for every OE-sourced cycle's output.
5. **Assemble**: `build_war_database.py` and `assemble_war_features.py`
   consume the rebuilt precinct/crosswalk outputs in place of the retired
   scripts' outputs, with the 2022 RDH path unchanged.

### Retired

- `scripts/normalize_2012_president.py`
- `scripts/build_2012_president_vtd_crosswalk.py`
- `scripts/build_2012_president_on_2018_map.py`
- `scripts/build_2012_presidential_districts.py` (generalized into the new
  unified allocation script rather than left standalone)
- `scripts/build_vest_presidential_districts.py`
- `scripts/build_2014_precinct_crosswalk.py`,
  `scripts/build_2014_multisource_crosswalk.py`,
  `scripts/validate_2014_precinct_crosswalk.py` (the VTD-crosswalk apparatus
  — its only consumers were the presidential-trend scripts above)
- `data/manual/2014_precinct_geometry_overrides.csv` and the derived
  `data/derived/crosswalks/` VTD/geometry crosswalk files
- The silent manual copy of OE CSVs into `data/raw/openelections/`

### Kept unchanged

- `rdh_2022_cycle` and all 2022 RDH shapefile handling in
  `build_war_database.py`.
- The overall WAR feature schema, model fitting, and validation scripts
  downstream of precinct assembly.

## Rollout

Build the new pipeline alongside the old one. Diff its outputs — the WAR
feature table and precinct-level vote totals — against the currently
committed results. Only after the diff is reviewed and reconciled does
cutover happen: old scripts deleted, `project_docs/model/MODEL_READINESS.md` updated to
describe the new single-source pipeline.

## Open risks

- The 2020→2022 cross-vintage allocation carries irreducible geometric
  uncertainty; this rebuild changes its vote source and matching
  methodology but does not eliminate that uncertainty.
- Extending the 2014 crosswalk methodology to 2012 and 2016 assumes those
  cycles' precinct naming is similar enough to reuse the same token-
  normalization rules; some counties may need review-queue entries the same
  way 2014 did.
