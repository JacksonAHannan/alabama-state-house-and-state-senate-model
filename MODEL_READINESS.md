# Alabama legislative WAR model: readiness status

This repository now produces a reproducible preliminary WAR database for the
2014, 2018, and 2022 Alabama House and Senate elections.

## Current result

- 420 district-cycle feature rows: 105 House and 35 Senate districts in each cycle.
- 154 contested Democratic-versus-Republican races receive WAR scores: 57 in
  2014, 64 in 2018, and 33 in 2022.
- Uncontested and non-D/R races remain in the source tables but are not scored.
- Candidate scores are zero-sum within a race: the Republican score is the
  sign-reversed Democratic residual.
- Model uncertainty is estimated with 300 bootstrap fits.
- All 204 modeled 2018 legislative candidate totals exactly match the official
  Alabama county workbooks, with no unmatched candidates or vote differences.

The current specification is a ridge regression of legislative margin minus a
same-cycle statewide ballot index on incumbency, prior presidential margin and
trend, demographics, spending, finance completeness, cycle, and chamber.
Incumbency enters as two separate indicators, `dem_incumbent` and
`rep_incumbent`, rather than a single signed `dem_incumbent - rep_incumbent`
term. An unconstrained OLS check found the two effects are not mirror images:
Democratic incumbency is associated with roughly +14 points of
overperformance (highly significant), while Republican incumbency is
associated with about -3 points and is not statistically significant. Forcing
a single symmetric coefficient understated the Democratic incumbency effect
and overstated the Republican one; splitting the term removed most of the
leftover incumbency-correlated bias in the WAR residuals (group-mean bias
dropped from -2.15/+0.32/+3.95 points across Republican-incumbent/open/
Democratic-incumbent races to -0.50/-0.26/+1.41).

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

Random-fold out-of-sample performance is useful (R-squared 0.219; MAE 7.40
margin points), and leave-one-cycle-out performance is R-squared 0.143 (MAE
8.18) after the incumbency-term and white-college-share fixes above. The 2014
cycle remains much noisier than the later cycles. Outputs retain the
`preliminary_` prefix.

The automated QA file is `data/processed/war/model_readiness_qa.csv`. The
largest residuals and their principal input fields are in
`data/processed/war/extreme_war_validation.csv`.

The cycle-shift audit shows that the instability is substantive and not just a
row-coverage artifact. Among contested races, mean raw Democratic
overperformance is +8.01 points in 2014, -0.62 in 2018, and +3.67 in 2022.
The 2014 standard deviation is also 18.79 points, versus 6.61 and 5.26 in the
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
3. Manually review the nine races with absolute out-of-fold WAR of at least 25,
   especially 2014 races with incomplete core baselines or substantial 2012
   presidential county fallback.
4. Decide how the production model should handle the 2014 structural break.
   Reasonable release options are a pooled historical model with an explicit
   warning, an era-aware/hierarchical model, or a separate contemporary model
   for 2018 onward. The smaller contemporary sample performs much better in
   absolute error but remains too limited for strong cross-cycle claims.
5. Refit after 2026 results become available. A fourth cycle is the most useful
   addition for measuring generalization, particularly because the 2026 Senate
   geography uses the remedial plan.

## Rebuild and validate

Run the scripts in dependency order after changing source data:

```powershell
python scripts\build_war_database.py
python scripts\build_incumbency_features.py
python scripts\build_candidate_finance_features.py
python scripts\assemble_war_features.py
python scripts\fit_preliminary_war_model.py
python scripts\compare_war_specifications.py
python scripts\build_war_review_queue.py
python scripts\validate_2018_official_legislative_totals.py
python scripts\validate_2022_wikipedia_legislative_totals.py
python scripts\audit_cycle_shift.py
python scripts\validate_war_outputs.py
```

Presidential and ACS preparation scripts are separate upstream steps and only
need to be rerun when their raw inputs or map allocations change.
