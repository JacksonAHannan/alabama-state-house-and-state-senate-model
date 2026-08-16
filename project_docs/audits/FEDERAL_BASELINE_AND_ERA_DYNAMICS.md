# Federal baseline and era-dynamics research

## Question

Does same-cycle federal voting better represent the partisan environment for
Alabama legislative elections, particularly after the nationalizing breaks
associated with 2008 and 2016?

This is a retrospective research analysis. It does not change the published
CMO definition or leaderboard.

## Construction

Official Alabama SOS U.S. House and U.S. Senate precinct returns are allocated
to state House and Senate districts. Only contests containing both Democratic
and Republican votes contribute to the federal margin. Votes from uncontested
federal contests remain in `federal_contested_coverage`, preventing a one-party
ballot from being interpreted as a 100-point partisan preference.

The federal index is the equal-component mean of the available U.S. House and
U.S. Senate margins. House and Senate margins, vote totals, component counts,
coverage, and allocation methods remain separately auditable.

The eras are defined before looking at results:

- Pre-2008: 1994, 1998, 2002, and 2006.
- Obama era: 2010 and 2014.
- Trump-era nationalization: 2018 and 2022.

## Baseline findings

The state-office baseline has the lowest MAE before 2008 and in 2010-2014. A
single federal weight selected from all prior cycles therefore remains zero.
This rules out replacing the historical baseline with one universally heavy
federal weight.

The pattern changes in 2018-2022. On those 96 races, the state baseline has
9.75-point MAE, the federal baseline has 9.34-point MAE, and a 60% federal blend
has 8.62-point MAE. This is consistent with increased nationalization after
2016.

The honest era-adaptive test is less favorable. A 60% weight selected on 2018
and applied to 2022 produces 9.29-point MAE, compared with 8.99 for the state
baseline. The post-2016 finding is therefore useful evidence of a structural
change, but it does not yet pass the predictive promotion gate.

## Non-regression findings

Two tree ensembles, held out by future election cycle, were compared with the
unadjusted federal baseline. They substantially improve 2010 and 2014, fail in
2018, and are mixed in 2022. Training only on 2018 for the 2022 test also fails
to improve convincingly. This instability is itself evidence that the mapping
from local attributes to overperformance changes by era.

Across mutual information, held-out permutation importance, binned profiles,
and within-era/chamber nearest-neighbor contrasts, the strongest recurring
signals are:

- The federal-state partisan gap.
- White-college composition.
- Democratic incumbency.
- Candidate resource advantage, where observed.
- Nonwhite composition.

Matched comparisons estimate higher federal-relative Democratic performance in
high-nonwhite districts, with Democratic incumbents, and with a Democratic
resource advantage. High-white-college districts show lower Democratic
federal-relative performance in this historical Alabama sample. These are
descriptive contrasts, not causal effects.

## Interpretation and limitation

The federal-state gap is a measure of electoral nationalization, not a direct
measure of cultural conservatism. It also contains federal candidate quality,
incumbency, uncontested-race selection, and measurement error. Because it shares
components with the overperformance outcomes, its unusually high importance
must not be presented as independent causal proof.

Testing the cultural-conservatism mechanism requires linking the candidate
issue matrix, sponsorship and roll-call evidence, and Shor-McCarty scores to
these race-cycle records. The relevant tests are whether culturally conservative
Democrats outperform otherwise similar Democrats specifically where federal
Republican voting exceeds state Republican voting, and whether that relationship
strengthens after 2008 or 2016.

## Outputs

- `historical_federal_district_baselines.csv`
- `historical_federal_contest_components.csv`
- `federal_baseline_specification_comparison.csv`
- `federal_baseline_forward_validation.csv`
- `federal_baseline_era_adaptive_validation.csv`
- `cmo_nonparametric_forward_validation.csv`
- `cmo_permutation_importance.csv`
- `cmo_matched_ingredient_contrasts.csv`
- `cmo_ingredient_binned_profiles.csv`
- `cmo_era_break_diagnostics.csv`
- `cmo_mutual_information.csv`
