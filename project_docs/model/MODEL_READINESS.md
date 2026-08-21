# Alabama legislative Candidate Margin Overperformance: readiness status

> **August 2026 model change:** The public product is now Candidate Margin
> Overperformance (CMO), not Wins Above Replacement. CMO is a retrospective,
> zero-sum margin residual for contested D/R races; it does not estimate wins,
> a replacement nominee, or independent effects for both candidates. See
> `project_docs/model/CMO_MODEL_CARD.md`. References to WAR below describe legacy filenames retained
> for pipeline compatibility.

This repository now produces a reproducible preliminary WAR database for the
2010, 2014, 2018, and 2022 Alabama House and Senate elections. The 2010
extension is experimental because 2008 precinct-level presidential results are
unavailable and its presidential-trend field is deliberately null.

## Current result

- 420 district-cycle feature rows: 105 House and 35 Senate districts in each cycle.
- 154 contested Democratic-versus-Republican races receive WAR scores: 57 in
  2014, 64 in 2018, and 33 in 2022.
- Uncontested and non-D/R races remain in the source tables but are not scored.
- Candidate scores are zero-sum within a race: the Republican score is the
  sign-reversed Democratic residual.
- The former bootstrap confidence intervals have been retired. Public outputs
  instead show a cross-cycle stability band, explicitly not a confidence or
  predictive interval.
- All 204 modeled 2018 legislative candidate totals exactly match the official
  Alabama county workbooks, with no unmatched candidates or vote differences.

The headline **Total CMO** specification is a ridge regression of legislative
margin minus a same-cycle statewide ballot index on prior presidential margin
and trend, demographics, cycle, and chamber. It deliberately excludes
incumbency and prior candidate performance. Strong candidates often acquire
incumbency by overperforming enough to win; rerunning, surviving, and deterring
challengers further select the incumbent pool. Conditioning the headline score
on incumbency would therefore remove part of the candidate-strength phenomenon
being measured.

The separate **Predictive Total** specification retains party-specific
`dem_incumbent` and `rep_incumbent` indicators because they can improve outcome
prediction without being interpreted causally. Earlier diagnostics found that
the two incumbent associations were not mirror images: Democratic incumbency
was associated with roughly +14 points of raw overperformance, while Republican
incumbency was associated with about -3 points and was not statistically
significant. Those figures describe a selected cross-section, not the causal
effect of taking office. The candidate-history sensitivity further decomposes
the process into strictly lagged prior CMO, prior winner and contest status,
first-term versus established incumbency, cycle gap, and prior incumbent
appearances. See `CMO_HYPOTHESIS_REGISTRY.md` for the complete framework.

`white_college_share` is now pulled directly from ACS table C15002H (White
alone, not Hispanic or Latino, by sex by educational attainment) instead of
being approximated as `white_share x overall_college_share`. The old
multiplicative proxy was mechanically correlated with `nonwhite_share` by
construction (since `white_share = 1 - nonwhite_share`), which was inflating
the apparent collinearity between the two demographic terms beyond their real
overlap; the correlation between `nonwhite_share` and `white_college_share`
dropped from -0.44 to +0.06 after switching to the direct ACS measure. A
smaller, real (non-mechanical) collinearity remains between `nonwhite_share`
and `prior_pres_dem_margin` -- both track the same underlying racial and
partisan geography of Alabama -- and both features still carry
counterintuitive negative ridge coefficients in the pooled fit. That is a
genuine multicollinearity limitation of the current specification, not a
data-construction bug, and is a candidate for future work (e.g., dropping one
of the two correlated terms or combining them into a single index).

## Validation status

The August 2026 CMO validation suite makes out-of-fold Total CMO the headline
historical score and adds district-grouped and forward-cycle tests:

| Specification | Random MAE / R² | District-grouped MAE / R² | Leave-cycle-out MAE / R² |
| --- | --- | --- | --- |
| Total CMO | 12.51 / 0.419 | 12.69 / 0.395 | 17.94 / -0.130 |
| Resource-adjusted CMO | 12.51 / 0.405 | 12.91 / 0.379 | 16.56 / 0.060 |

Forward R² is negative for both available tests: training on 2014 and testing
2018, and training on 2014+2018 and testing 2022. The automated readiness gate
therefore fails cross-era generalization. This does not prevent retrospective
descriptive use, but it prohibits describing CMO as validated for an unseen
cycle or as a 2026 forecast. Detailed outputs are `cmo_diagnostics.csv`,
`cmo_forward_validation.csv`, and `cmo_benchmark_diagnostics.csv`.

The legacy diagnostics below document earlier specifications and data-rebuild
history; they are retained for provenance rather than as the current release
metrics.

Random-fold out-of-sample performance is R-squared 0.172 with MAE 7.71;
leave-one-cycle-out performance is R-squared 0.033 with MAE 9.19. Both moved
twice during the precinct-data rebuild, and both moves are disclosed rather
than tuned away:

| Metric | Pre-rebuild | After rebuild | After data-correctness fixes |
| --- | --- | --- | --- |
| Random-fold R-squared | 0.219 | 0.1995 | 0.172 |
| Random-fold MAE | 7.40 | 7.51 | 7.71 |
| Leave-one-cycle-out R-squared | 0.143 | 0.043 | 0.033 |
| Leave-one-cycle-out MAE | 8.18 | 9.04 | 9.19 |

Three corrections account for the last column, and every one of them replaces a
wrong number with a right one:

1. **Absentee and provisional ballots are counted again.** The rebuilt
   presidential extractor was discarding every precinct row named `ABSENTEE`,
   `PROVISIONAL`, `FAILSAFE`, `OVERSEAS` or `UOCAVA` along with the genuinely
   duplicated `TOTAL` summary rows. Those are not duplicates; they are real
   ballots reported at county level instead of at a named polling place. For
   2020 alone that dropped 311,836 two-party votes (202,917 Democratic and
   108,919 Republican) -- 13.6% of the electorate and 65.1% Democratic -- which
   moved the statewide two-party margin 8.8 points and reversed the sign of the
   2016-to-2020 presidential swing feature.
   The three presidential source years now reconcile to their certified
   statewide totals exactly where the source file is complete (2020:
   849,624 Democratic and 1,441,170 Republican).
2. **2014 legislative totals are no longer double-counted.** `TOTAL`,
   `CALCULATED TOTALS` and `REPORTED TOTALS` precinct rows restate a county's
   own precinct sums, and the 2014 aggregation had been adding them on top of
   the components. Statewide 2014 two-party legislative votes fall from
   2,364,018 to 2,105,004; 47 of 420 district-cycles change, 18 of them by
   enough to move the district's legislative margin. 2018 and 2022 are
   bit-for-bit unchanged, and the 2018 official-workbook comparison still
   matches all 204 candidate totals exactly.
3. **Districts with incomplete presidential source coverage are flagged, not
   silently dropped.** See "Presidential source coverage" below.

The earlier rebuild-driven move (middle column) traces to the 2018 cycle's
`pres_swing_2012_2016` presidential-trend feature, which is
now built by the single OpenElections-based
`build_presidential_district_features.py` matching pipeline (see "Rebuild and
validate" below) instead of the old ad hoc 2012 crosswalk. The old value was
already self-flagged unreliable for every 2018 row
(`pres_2012_source_complete=False` universally) and contained at least one
outright degenerate value (a near-zero-vote denominator), so the new value is
more honest. However, Jefferson County's 2012 precinct names diverge from the
2018 target precinct set enough that zero of Jefferson's 2012 precincts match
directly, so all 15 of Jefferson's districts (12 House + 3 Senate) fall back
to a single county-wide average trend value instead of a district-specific
one -- a real, disclosed methodological limitation, not a data-quality
regression. The 2014 cycle remains much noisier than the later cycles.
Outputs retain the `preliminary_` prefix.

The same limitation dominates the 2016-to-2020 swing feature: the districts
with the most extreme values are all Jefferson County districts, where zero of
2016's precincts match the 2022 precinct names (`pres_2016_fallback_share` of
1.0) while 2020's match normally, so a single county-wide 2016 margin is
differenced against district-specific 2020 margins. Restricting to districts
whose fallback share is below 0.2 on both source years leaves a swing range of
-0.4 to +5.1 points around a mean of +2.6, against a true statewide swing of
+3.0. `pres_{year}_fallback_share` is the column to filter on before treating a
district's presidential trend as precinct-derived.

## Presidential source coverage

## Census-block geographic allocation

Same-cycle statewide and presidential votes are now allocated independently of
legislative contest turnout. `build_geographic_crosswalks.py` joins official
Census block population to block assignments for VTD, House, and Senate:

- 2014: 2010 Census Block Assignment Files and 2010 PL 94-171 population.
- 2018: 2020 block/VTD assignments and the Census-tabulated 2018-session SLDs.
- 2022: 2020 block/VTD assignments joined to the Census 2022 SLD block
  equivalency files.

Election precinct labels are matched to VEST VTD labels within county. Direct
matches use population-weighted VTD district shares. Unmatched labels and
county-wide absentee/provisional batches use county population district shares,
not legislative activity. Direct name-match coverage is 1,639 of 2,309 target
precinct labels in 2014, 1,679 of 2,240 in 2018, and 1,470 of 1,939 in 2022;
the remainder are explicitly marked `county_population_fallback`. All precinct
weights sum to one and statewide baseline allocations reconcile to source votes.

This correction is substantively large. Relative to the retired
legislative-activity allocation, the mean absolute district-baseline change is
21.5 House / 19.2 Senate points in 2014, 7.2 / 5.4 in 2018, and 8.4 / 6.3 in
2022. Maximum changes range from 28 to 73 points. These differences confirm the
old weights were not a defensible neutral baseline, but they also mean the new
county-population fallbacks are now the largest unresolved measurement risk.
Candidate rankings should remain preliminary until high-impact unmatched
precinct labels are reviewed or connected to election-specific geometry.

Raw Census sources, URLs, sizes, and SHA-256 hashes are recorded in
`data/raw/census/source_manifest.csv`. Run
`download_census_crosswalk_sources.py` before `build_geographic_crosswalks.py`.

The 2012 OpenElections file covers 62 of Alabama's 67 counties; Bullock,
Butler, Hale, Montgomery and Wilcox have no rows at all. This is an upstream
gap, not a processing loss, and it has two distinct effects that the numbers
alone cannot distinguish:

- Five districts lie entirely inside Montgomery County (House 74, 76, 77, 78
  and Senate 26) and therefore have no 2012 presidential margin at all.
- Ten more 2014-cycle districts (nine in the 2018 cycle) span a missing county
  plus a covered one, so they receive a margin computed from only part of their
  electorate.

`build_presidential_district_features.py` now emits a
`pres_{year}_source_complete` flag for every district and every source year, so
both cases are visible downstream instead of being indistinguishable from a
well-covered district. It also writes a full 140-row output per cycle -- the
five uncovered districts appear with null margins rather than vanishing -- and
`check_output_completeness()` fails the build on any missing row, or on any null
margin that is *not* attributable to a source year with a known county gap.
2016, 2018 and 2020 are complete for all 67 counties.

One smaller source residual is known and unresolved: the 2016 file totals
727,869 Democratic and 1,317,127 Republican presidential votes against certified
statewide figures of 729,547 and 1,318,255, a shortfall of roughly 0.2% that is
internally consistent within the file (all its own total checksums reconcile)
and therefore appears to originate upstream.

The automated QA file is `data/processed/war/model_readiness_qa.csv`. The
largest residuals and their principal input fields are in
`data/processed/war/extreme_war_validation.csv`.

The cycle-shift audit shows that the instability is substantive and not just a
row-coverage artifact. Among contested races, mean raw Democratic
overperformance is +7.81 points in 2014, -0.62 in 2018, and +3.67 in 2022.
The 2014 standard deviation is also 19.69 points, versus 6.61 and 5.26 in the
later cycles. In addition, presidential trend is unavailable for every 2014
race because precinct-level 2008 presidential returns have not been located.
The cycle fixed effect makes retrospective pooled scores usable, but an unseen
cycle cannot inherit that fitted intercept.

For that reason, use the pooled output for historical WAR comparisons and the
2018–2022 contemporary specification only as a sensitivity analysis for future
work. Neither specification should yet be presented as a calibrated 2026
forecast.

The 2014 incumbency follow-up audit corrected one false annotation: Michael J.
Gladden was the HD 29 challenger, while Becky Nordgren was the incumbent. It
also preserves Dickie Drake and Jack Williams as independently verified
incumbents and verifies the five Democratic-to-Republican incumbent party
switches (Mike Millican, Steve Hurst, Alan Harper, Lesley Vance, and Alan C.
Boothe). Candidate-level evidence is recorded in
`data/processed/war/2014_incumbency_candidate_audit.csv`.

## Remaining work before a final release

1. Compare 2022 legislative candidate totals with a separate certified Alabama
   canvass, and obtain a certified comparison for 2014 if a machine-readable
   district canvass becomes available. The 2018 comparison is complete: all 204
   candidate totals exactly match the official county workbooks. The 2014
   results now come from the OpenElections normalization of the official county
   workbooks, with Jefferson County replaced directly from its official file;
   the erroneous Wikipedia outcome override has been removed.
   The archived 2022 Wikipedia pages provide only a partial diagnostic: 142
   candidate totals match exactly, but the pages mix primary and general tables
   and their later House district structure does not parse reliably. These
   results are therefore not used as a readiness pass/fail test.
2. Resolve finance identities for the remaining contested races. Both major
   candidates are matched in 125 of 154 races (81.2%). Missing ratios are
   imputed by the model and accompanied by a finance-completeness indicator.
3. Manually review the ten races with absolute out-of-fold WAR of at least 25,
   especially races with incomplete core baselines or substantial presidential
   county fallback. `build_war_review_queue.py` now applies the fallback-share
   flag in every cycle, against whichever presidential source years feed that
   cycle, rather than only to 2014 against 2012; that widens the flagged set
   from 4 races to 31 (5 in 2014, 19 in 2018, 7 in 2022).
4. Decide how the production model should handle the 2014 structural break.
   Reasonable release options are a pooled historical model with an explicit
   warning, an era-aware/hierarchical model, or a separate contemporary model
   for 2018 onward. The smaller contemporary sample performs much better in
   absolute error but remains too limited for strong cross-cycle claims.
5. Refit after 2026 results become available. A fourth cycle is the most useful
   addition for measuring generalization, particularly because the 2026 Senate
   geography uses the remedial plan.

## Rebuild and validate

Run the scripts in dependency order after changing source data. Precinct-level
vote data for 2012, 2014, 2016, 2018, and 2020 now comes from a single source
(`openelections-data-al`, synced explicitly rather than copied by hand), with
2022 unchanged on the RDH pipeline.

```powershell
python scripts\sync_openelections_data.py
python scripts\download_census_crosswalk_sources.py
python scripts\validate_oe_precinct_totals.py (Get-ChildItem data\raw\openelections\*.csv)
```

**The validation step is expected to exit 1.** It reports 19 checksum
mismatches, all in the 2014 file: 4 in DeKalb County, 14 in Escambia County and
1 in Lamar County. In each, the county's own reported `Total` row disagrees with
the sum of the precinct rows it claims to summarize -- a quality problem in the
source workbook, confirmed by hand against the raw CSV. It does not affect the
model, because the pipeline drops every reported-total row (`SUMMARY_ROW_RE` in
`oe_normalize.load_oe`) and always sums the components instead. The other four
files reconcile cleanly. Treat a *changed* mismatch count, not a nonzero one, as
the signal worth investigating.

```powershell
python scripts\build_war_database.py
python scripts\build_geographic_crosswalks.py
python scripts\build_war_database.py  # rebuild baselines using geographic weights
python scripts\build_oe_president_precinct.py --year 2012
python scripts\build_oe_president_precinct.py --year 2016
python scripts\build_oe_president_precinct.py --year 2020
python scripts\build_presidential_district_features.py
python scripts\build_incumbency_features.py
python scripts\build_candidate_finance_features.py
python scripts\assemble_war_features.py
python scripts\fit_preliminary_war_model.py
python scripts\compare_war_specifications.py
python scripts\audit_allocation_sensitivity.py
python scripts\build_war_review_queue.py
python scripts\build_war_story_page.py
python scripts\validate_2018_official_legislative_totals.py
python scripts\validate_2022_wikipedia_legislative_totals.py
python scripts\audit_cycle_shift.py
python scripts\validate_war_outputs.py
```

Presidential and ACS preparation scripts are separate upstream steps and only
need to be rerun when their raw inputs or map allocations change.
