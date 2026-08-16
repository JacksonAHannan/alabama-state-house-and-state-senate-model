# Historical CMO extension validation: 1998, 2002, and 2006

## Status

All three cycles remain **experimental**. Election returns, district plans,
decennial demographics, incumbency evidence, and finance coverage are now
warehoused. Validation does not yet support promoting the cycles into the
published fitted CMO.

## Passed checks

- Legislative-activity allocation weights sum to one within every represented
  precinct/chamber.
- The official 1996, 2000, and 2004 presidential files produce usable district
  context for most eligible races.
- Candidate identifiers are unique and observed finance totals are nonnegative.
- Governor-only and attorney-general-only rankings remain strongly correlated
  with the equal-weight core baseline (all chamber-cycle Spearman correlations
  exceed 0.94).
- Census allocations cover 99.997% of 1990 population and 99.988% of 2000
  population.

## Failed or cautionary checks

### Baseline source-vote coverage

The production historical baseline currently performs an inner join between
statewide precinct returns and legislative activity. Counties or precincts
without a contested race in a chamber have no activity weight and are dropped.
Minimum party/office coverage is approximately 98.3% in 1998, 95.2% in 2002,
and 92.7% in 2006. This fails the 99% gate.

The omissions are structural rather than arithmetic. Examples include Blount
County Senate votes in 1998, Calhoun County Senate votes in 2002, and several
Black Belt or northeastern counties in 2006. See
`historical_baseline_unmatched_county_detail.csv`.

A validation-only county-population fallback restores these votes. Rankings
are highly stable overall, but several seats move materially: 2002 SD-12 moves
12.4 baseline points and 2006 SD-8 moves 21.4 points. These races require
manual source review before the fallback becomes canonical.

### County-fallback review resolution (superseded after source repair)

The initial review identified six material movements. A subsequent source audit
found that their legislative votes were present but excluded by legacy office
labels or missing district metadata. The normalizer now recognizes labels such
as `Senator, Dist 9`, `STATE HOUSE 64`, and `State House, District 33`, and
fills uniquely recoverable Senate districts from adjudicated candidate links.

The original validation-only movements were:

| Cycle | District | Baseline change | Principal restored county | Resolution |
|---|---:|---:|---|---|
| 2006 | SD-8 | +21.38 | Jackson | Accept fallback |
| 2002 | SD-12 | +12.41 | Calhoun | Accept fallback |
| 2006 | SD-23 | -7.80 | Monroe | Accept fallback |
| 1998 | SD-9 | -5.63 | Blount | Accept fallback |
| 2006 | HD-64 | +5.45 | Monroe | Accept fallback |
| 2006 | HD-33 | +2.80 | Coosa | Accept fallback |

After rebuilding from source, none of these movements remains above the
two-point materiality threshold. The former acceptance decisions are therefore
superseded: these counties now use their recovered precinct legislative votes,
not county-population fallback.

The review decisions and vote-level supporting evidence are retained in
`historical_county_population_fallback_manual_review.csv` and
`historical_county_population_fallback_evidence.csv`.

### Presidential allocation

The initial 2002 build appeared to fail the median-fallback-below-50% gate.
Source review found duplicate countywide rows named `CALCULATED` and `REPORTED`
that had been parsed as precincts, adding approximately 1.27 million duplicate
two-party votes. These rows are now excluded. The corrected median fallback is
37.7% for House districts and 33.1% for Senate districts, so the cycle passes
the gate. The archive covers 63 counties; incomplete-source districts remain
explicitly flagged.

The 1998 median fallback share is approximately 48%. The 2006 median is much
better (9% House and 12% Senate), though statewide allocated totals still omit
counties lacking target legislative activity.

### Incumbency and finance

Incumbency is positive-evidence based. Unknown does not mean non-incumbent.
Supported incumbents among eligible races total 71 in 1998, 60 in 2002, and 55
in 2006. Candidate-level unknown counts remain 99, 88, and 67 respectively.

DIME supplies complete two-candidate finance observations for 64 of 85 eligible
1998 races, 43 of 74 in 2002, and 51 of 61 in 2006. Missing finance remains
unknown and is never converted to zero.

## Required next actions

1. Promote the reviewed hybrid allocation:
   direct precinct/activity allocation where available, independent
   county-population allocation where legislative activity is absent.
2. Do not require presidential context for rows whose source coverage remains
   incomplete.
3. Fit an experimental historical model with missingness indicators and nested
   leave-one-cycle-out validation. Compare 1998-2006 inclusion against the
   existing 2010-2022 specification before publication.

## Generated audit files

All machine-readable outputs live in `data/processed/elections/validation/`.
The authoritative gate table is `historical_cmo_readiness_gates.csv`.
## Canonical fallback promotion

The canonical historical baseline now allocates unmatched statewide-result
precincts with independently constructed Census tract population shares by
county and district. Direct precinct legislative-activity weights remain the
first choice. The allocation method is retained on every district baseline as
`county_population_fallback` whenever any fallback observation contributes.
`baseline_fallback_share` separately records the largest fallback vote share
across the component statewide offices, avoiding the implication that a flagged
district is primarily fallback-derived.
This promotion follows the sensitivity audit: no reviewed movement reached two
percentage points and rank correlations rounded to 0.9999 or better.
