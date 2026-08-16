# Plausible ideology relationships: first test battery

These are exploratory associations, not causal estimates. The Shor--McCarty score is a career-level ideal point and can incorporate post-election votes.

## Headline OOF CMO results

| Test | N | Estimate | Cluster-bootstrap range | Read |
|---|---:|---:|---:|---|
| overall conservatism | 52 | +1.02 | [-3.20, +5.68] | direction fits, highly uncertain |
| conservative candidate x republican district | 52 | +1.91 | [-3.56, +5.73] | direction fits, highly uncertain |
| conservatism x incumbency | 52 | -3.32 | [-14.56, +9.14] | does not fit hypothesized direction |
| caucus extremity | 52 | +1.71 | [-2.30, +5.38] | does not fit hypothesized direction |
| conservatism in majority white districts | 14 | +13.03 | [+4.46, +52.57] | direction fits; range excludes zero |
| conservatism in majority nonwhite districts | 10 | -6.64 | [-26.37, +47.80] | direction fits, highly uncertain |

## Interpretation rules

- Estimates are CMO points associated with a one-standard-deviation change in the named focal term, conditional on cycle, chamber, and incumbency.
- The candidate-district-fit model also includes candidate ideology and district Republican lean as main effects.
- Candidate-clustered bootstrap ranges describe resampling sensitivity; they are not calibrated causal confidence intervals.
- Race-composition splits have only the subset with available district demographics and should be treated as a power audit.
- Issue-specific cultural and economic results remain descriptive because the pre-election coded samples are tiny.

## Files

- `research\cmo_ideology\plausible_ideology_relationship_tests.csv`
- `research\cmo_ideology\pre_election_issue_relationship_tests.csv`
