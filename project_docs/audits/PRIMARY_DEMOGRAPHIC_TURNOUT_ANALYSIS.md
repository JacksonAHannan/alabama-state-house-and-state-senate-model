# Alabama primary turnout as a demographic turnout signal

## Result

First-round primary turnout has real out-of-cycle predictive value for the
geographic distribution of general-election turnout. It should enter the 2026
forecast as a constrained turnout-composition signal, not as a statewide vote
swing or a direct causal effect.

### Direct racial-turnout revision

The SOS also publishes direct county ballots cast by voter-file race for the
2018, 2020, and 2024 general elections. Matching these numerators to the SOS
annual registration workbooks gives direct Black and White turnout rates and is
more probative than inferring racial turnout from county composition.

On this outcome, the primary signal is much weaker. A registration-composition
model has 0.0879 forward MAE for relative Black turnout. Total primary turnout
reduces it to 0.0853 and party-specific primary features reduce it to 0.0845.
The party-primary improvement is 0.0036 in a county-clustered bootstrap, with a
95% interval of -0.0009 to 0.0081 and 94.2% probability of improvement. Primary
features slightly worsen White-turnout MAE, from 0.0550 to 0.0589; that result
is also uncertain.

The much larger gain found for total county turnout therefore mostly captures
geographic election intensity and electorate size. It is not evidence of a
large, reliably measured racial-turnout effect. The direct racial result should
govern forecast use.

Direct statewide turnout among registered voters was 47.9% Black versus 51.3%
White in 2018, 57.1% versus 65.6% in 2020, and 50.3% versus 62.9% in 2024. These
are voter-file racial classifications and should not be conflated with Census
race categories.

Across leave-one-cycle-out tests for 2018, 2022, and 2024, a demographics-only
county model has 0.124 mean absolute error when predicting county turnout
relative to the statewide rate. Adding first-round primary turnout reduces MAE
to 0.0876. Adding Democratic primary share and Black-share interactions reduces
MAE to 0.0850. The full improvement over demographics alone is 0.0390 (clustered
county bootstrap 95% interval 0.0250 to 0.0547; probability of improvement
1.000). The demographic interaction's incremental improvement over primary
level alone is much smaller, 0.00265 (clustered 95% interval 0.00081 to 0.00523).

| Held-out cycle | Demographics only | Primary level | Primary + demographic interactions |
|---:|---:|---:|---:|
| 2018 | 0.1354 | 0.0901 | 0.0858 |
| 2022 | 0.1334 | 0.0870 | 0.0853 |
| 2024 | 0.1035 | 0.0859 | 0.0838 |

## The 2026 signal

The official first-round ballots equal 22.50% of 2020 Census VAP statewide.
County Black VAP share correlates 0.60 with county turnout relative to the
statewide primary rate. Counties in the top Black-VAP-share quartile average
1.47 times the statewide primary rate, versus 1.03 among other counties.

That pattern is elevated but not unprecedented. The same high-Black-share
counties averaged 1.70 times statewide turnout in the 2018 primary, 1.50 in
2022, and 1.38 in the 2024 presidential primary. Their unweighted absolute 2026
primary turnout rate is 33.1%, compared with 32.6% in 2022 and 38.7% in 2018.
The broad evidence therefore does **not** support treating 2026 as a uniform,
historically exceptional Black-turnout surge. It does support localized uplift:
Greene and Perry are the clearest high-side primary-turnout anomalies, followed
by Wilcox and Lowndes.

After accounting for demographics, the full primary model raises predicted
relative general turnout by 1.2% in high-Black-share counties and lowers it by
2.8% in other counties, on average. These are relative turnout multipliers, not
percentage-point changes in Democratic vote margin.

## Forecast use

1. Preserve the national environment and demographic preference model as the
   vote-choice channel.
2. Add the primary model only to the turnout-composition channel.
3. Center county multipliers so they cannot manufacture a statewide turnout
   level; allocate the SOS primary signal to legislative districts by county
   overlap.
4. Because direct racial forward validation is inconclusive, do not add a
   statewide racial-turnout adjustment to the public forecast. Retain 0%, 25%,
   and 50% weights only as experimental sensitivity variants. If used, 25%
   applies to the small learned multiplier—not to an assumed turnout surge.
5. Do not encode the Voting Rights Act controversy as a standalone numerical
   feature. The observed primary anomaly is the measurable evidence channel.
6. Keep Greene and Perry influence bounded so two counties cannot determine the
   statewide racial-turnout coefficient.

## Data and limitations

- Primary and general ballots come from official Alabama Secretary of State
  county precinct workbooks archived with checksums in
  `data/raw/alabama_elections_and_geography/historical_primaries/source_manifest.csv`.
- SOS precinct registration fields are generally zero. The analysis therefore
  aggregates ballot counts to counties and divides by 2020 Census VAP.
- The preferred racial validation instead uses SOS direct participation by race
  and SOS active-plus-inactive registration denominators for 2018, 2020, and
  2024. No equivalent 2022 racial participation report is listed on the SOS
  election-data page.
- Outcomes are normalized within cycle. This tests where turnout is elevated,
  not the unknowable 2026 statewide general-election turnout level.
- There are only three completed validation cycles, including one presidential
  primary. County-clustered uncertainty protects against treating repeated
  county observations as independent but cannot create additional election
  environments.
- Primary contest intensity differs across parties, counties, and years. The
  signal is predictive, not necessarily causal.

Reproduce with `python scripts/analyze_primary_demographic_turnout.py` and
`python scripts/analyze_direct_racial_turnout.py`.
