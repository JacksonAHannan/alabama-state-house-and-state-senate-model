# Catalist-calibrated ecological inference

## Completed foundation

The national calibration table is normalized from Catalist's current public
2024 workbook. Its 2008 and 2010 gaps are backfilled from the historical table
published with Catalist's revised 2018 analysis. Newer workbook values take
precedence in every overlapping year.

The race-first Alabama prototype spatially assigns every populated 2020 Census
block to the VEST 2018 and 2020 precinct polygons. It uses voting-age counts
from PL 94-171 P3/P4 and complete geocoded statewide Governor/President votes.

## Current diagnostic

A simple aggregate binomial mixture reaches boundary solutions for Black and
other voters. Numerical convergence is not substantive identification. These
estimates are marked `failed_boundary_diagnostic` and are prohibited from use
in the forecast.

The subsequent race x education model successfully allocates all 3,925 ACS
block groups into the complete VEST 2018/2020 precinct universes and jointly
models turnout and preference. Strong turnout pooling removes the near-zero
turnout pathology. Near-boundary Black support is not treated as an automatic
failure: precincts estimated at least 95% Black cast 95.7% Democratic votes in
2018 and 97.2% in 2020, making very high latent Black support substantively
plausible. Homogeneous-precinct returns are the primary polarization anchor.

CES subgroup estimates are retained as a sensitivity comparison, not a release
veto, because effective Alabama samples range from roughly 4 to 127. Remaining
concerns are concentrated in the prior-sensitive `other` cells, the inability
to validate education splits directly from homogeneous precincts, and using a
2022 ACS vintage as a proxy for the 2018/2020 electorate.

## Selected core specification

The selected model estimates four substantive support cells: white noncollege,
white college, Black noncollege, and Black college. The heterogeneous residual-
race category is collapsed across education and its preference is fixed to the
Alabama-shifted Catalist calibration; its turnout remains estimated. This
prevents a weakly identified nuisance category from absorbing arbitrary turnout
and preference while preserving its contribution to precinct totals.

At prior strength 400, all five cells pass the sensitivity gate in both cycles.
The four estimated cells move by only 0.3-2.4 points across the tested prior
strengths. Black estimates pass homogeneous-precinct polarization anchors. The
five-cell model's weighted precinct MAE is 6.86 points in 2018 and 6.60 in 2020,
only 0.04 and 0.12 points worse than the more flexible six-cell model. Both
cycle-level model gates pass. The historical ACS-vintage limitation remains and
must be propagated as model uncertainty in prospective use.

The failure demonstrates that precinct vote totals plus marginal racial voting-
age composition do not identify subgroup support without turnout information,
joint demographics, and partial-pooling priors. This is the ecological-fallacy
problem the proposed method was intended to address.

## Required production model

1. Construct mutually exclusive race x education x age/sex cells from ACS
   block-group tables, allocated into precinct polygons with Census blocks.
2. Estimate group turnout separately from vote preference. CVAP or VAP is a
   population denominator, not an electorate composition estimate.
3. Fit a hierarchical ecological model with county/urbanity variation and
   Catalist national targets as uncertain calibration priors.
4. Validate by recovering held-out precinct totals, statewide totals, CES
   Alabama estimates, and stable subgroup trajectories.
5. Only then estimate partially pooled Alabama response coefficients and apply
   the YouGov 2026 demographic polling environment.

## Outputs

- `data/processed/polling/catalist_national_demographic_master.csv`
- `data/processed/polling/alabama_vtd_race_ei_inputs.csv`
- `data/processed/polling/alabama_race_vote_ei_estimates.csv`
- `data/processed/polling/vest_precinct_joint_race_education.csv`
- `data/processed/polling/alabama_joint_race_education_ei_sensitivity.csv`
- `data/processed/polling/alabama_joint_ei_ces_comparison.csv`
- `data/processed/polling/ei_homogeneous_precinct_validation.csv`
- `data/processed/polling/ei_black_polarization_validation.csv`
- `data/processed/polling/alabama_core_race_education_ei_estimates.csv`
- `data/processed/polling/alabama_core_race_education_ei_sensitivity.csv`
- `data/processed/polling/alabama_core_ei_model_gate.csv`
