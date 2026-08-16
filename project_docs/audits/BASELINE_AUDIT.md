# District baseline audit

The canonical candidate-margin-overperformance baseline is the equal-weight mean of the Democratic two-party margins for Governor and Attorney General. Only offices contested by both major parties are included. Alabama SOS precinct returns are authoritative; OpenElections is retained as a reconciliation source.

## Completed audits

1. **Source reconciliation.** `baseline_source_reconciliation.csv` compares SOS and OpenElections by county, office, party, and cycle. `baseline_statewide_source_reconciliation.csv` provides the corresponding statewide comparison. A separate certified-canvass comparison remains explicitly marked pending rather than treating a precinct sum as the canvass.
2. **Geography conflicts.** VTD identifiers are normalized before evidence is compared. Eleven genuine competing-VTD links remain in `precinct_geography_conflict_impact.csv`, ranked by core-office vote volume. Apparent formatting differences such as `123` versus `000123` are no longer conflicts.
3. **Baseline uncertainty.** `canonical_baseline_uncertainty.csv` gives the
   minimum, maximum, mean, standard deviation, and range across the exact
   production weights plus strict-consensus, county-fallback, direct-evidence,
   and source-transfer scenarios. An earlier version omitted the production
   regime and materially understated uncertainty. The spread is confined to
   2014: mean 3.21 points, median 1.38, and maximum 26.83. All other cycles have
   effectively zero scenario spread under the current evidence. House District
   53, the Anthony Daniels case, has a 9.27-point range (`-13.65` to `-4.38`).
4. **Alternative definitions.** `canonical_district_baseline_definitions.csv` contains Governor-only, Attorney-General-only, core equal-weighted, core turnout-weighted, expanded-office equal-weighted, expanded-office turnout-weighted, and latent-office-factor baselines. `baseline_definition_diagnostics.csv` compares each with the core equal-weighted reference.

Across strict-consensus scenarios, core turnout weighting changes the reference by 0.29 points on average. The expanded and latent definitions differ by roughly 1.25–1.64 points on average; single-office definitions differ by roughly 2.63 points. These are sensitivity specifications, not replacements for the frozen core definition.

## Rebuild

Run `python scripts/analyze_canonical_baselines.py` after rebuilding the
elections database, canonical geography evidence, **and production canonical
weights**. The audit intentionally excludes uncontested statewide offices,
which otherwise appear as artificial plus or minus 100-point baselines.

## Remaining release gate

Obtain or parse certified statewide canvass totals and reconcile them against the official SOS precinct sums. Until then, the relevant output field remains `separate_canvass_comparison_pending`.
