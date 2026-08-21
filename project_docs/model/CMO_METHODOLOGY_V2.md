# CMO methodology v2

This build replaces the single ambiguous headline with four explicitly different quantities. It is a versioned staging release and does not overwrite the prior public fields until independent validation and web migration are complete.

## Four estimands

1. **Raw ticket overperformance:** legislative Democratic margin minus the source-aware same-cycle ticket baseline.
2. **Context CMO:** the cycle-held-out residual after adjusting only for non-candidate electoral context.
3. **Within-cycle CMO:** context CMO centered on the chamber-cycle median for comparisons across eras.
4. **Predictive residual:** error from a separately labeled expected-performance model that may use incumbency, finance, and strictly lagged candidate history.

## Invariants

- Headline context CMO excludes incumbency, finance, candidate history, and ideology.
- Predictive expected performance is separately labeled and may use candidate-derived information.
- The source-aware baseline vote-weights Governor and Attorney General and adds a prespecified 30% federal component from 2018 when federal coverage is usable.
- Races below 5% losing-party vote share are nominal contests and do not train the expectation model.
- Cycle-held-out margin ridge, Huber, and logit-share specifications are retained for uncertainty.
- Nested-forward selection uses only cycles earlier than the test cycle.
- Candidate/opponent effects use a crossed ridge model and are explicitly partial-pooled.

## Implementation of the ten priorities

1. The model card and implementation now use one candidate-variable-free headline definition.
2. Absolute and chamber-cycle-centered CMO are both retained.
3. Predictive expected performance is a different output rather than a replacement definition of CMO.
4. Governor and Attorney General are aggregated by actual two-party votes; usable post-2016 federal context receives a prespecified 30% weight; previous presidential margin is the fallback.
5. Nominal contests are scored but excluded from fitting.
6. Ridge-in-margin-space, robust Huber, and bounded logit-share expectations are compared.
7. Every expectation is cycle-held-out, and a nested-forward selector chooses specifications using earlier cycles only.
8. Headline features are available conceptually in every era; recent-only region fields are excluded rather than zero-filled into the headline.
9. Candidate and opponent attribution uses stable person identities in a crossed, partial-pooled model.
10. Repeat-candidate, next-win bivariate, same-seat successor, and incumbent-departure successor diagnostics test construct validity.

Eligible races: 509.

| tier | races |
| --- | --- |
| meaningful | 508 |
| nominal | 1 |

## Predictive diagnostics

| specification | cycle_balanced_mae | latest_cycle_mae |
| --- | --- | --- |
| baseline_ensemble_margin | 16.035555049272 | 5.2499453540391166 |
| expected_margin_context | 14.713978839482605 | 9.38149445501142 |
| expected_margin_context_huber | 14.570557555516757 | 8.707607061636393 |
| expected_margin_context_logit | 14.331359489205305 | 8.2587030533103 |
| expected_margin_nested_forward | 15.316112671266223 | 8.2587030533103 |
| expected_margin_predictive | 12.677490627239713 | 6.733457245921704 |

## Construct validity

| design | outcome | n | pearson | pearson_p | spearman | spearman_p |
| --- | --- | --- | --- | --- | --- | --- |
| repeat_candidate_next_cycle | candidate_context_cmo | 77 | 0.3740598378116868 | 0.0008045787016842899 | 0.30842841369157153 | 0.006351601729705802 |
| repeat_candidate_next_cycle | candidate_within_cycle_cmo | 77 | 0.4096613570799774 | 0.00021582156668625938 | 0.368683947631316 | 0.0009691946724463059 |
| repeat_candidate_next_cycle | candidate_raw_ticket_overperformance | 77 | 0.49250271932707074 | 5.370227439868017e-06 | 0.5047058204952941 | 2.861080507215524e-06 |
| prior_cmo_next_win_bivariate_association | winner_i | 77 | -0.12545825545725872 | 0.27695397009271705 | -0.16041350824425746 | 0.16342554571449228 |
| different_candidate_same_seat_party | candidate_context_cmo | 173 | 0.513192955031007 | 5.220833290834933e-13 | 0.4887313367109966 | 8.98199273035369e-12 |
| incumbent_departure_successor | candidate_context_cmo | 16 | -0.22144345781958022 | 0.4098093361597379 | -0.21176470588235297 | 0.431083247239221 |

Repeat-candidate persistence is positive but modest, while same-seat persistence for different candidates is stronger. Context CMO must therefore remain a candidate-side electoral residual, not a fully identified personal effect. The partial-pooled effect is the more conservative candidate-level attribution.

## Race-specific uncertainty

The specification/data-quality radius has a 10th percentile of 4.03 points, median of 11.99, and 90th percentile of 18.85. It combines disagreement among the baseline-only, ridge, Huber, and logit expectations with geographic-fallback and nominal-contest penalties. It does not add predictive residual error around a residual by definition.

## Release rules

- Public candidate tables should default to context CMO and offer raw, within-cycle, and partial-pooled views.
- Cross-era rankings should use within-cycle CMO, not uncentered context CMO alone.
- Forecasts should consume expected performance, never historical CMO labels as if they were probabilities.
- Nominal contests and 1994 sensitivity rows require visible flags.
- Candidate partial-pooled effects require appearance counts and attribution reliability.

## Limitations

The ensemble's post-2016 federal weight is prespecified from prior source-frozen analysis rather than identified anew here. Same-cycle ticket results make every CMO retrospective. Partial pooling cannot fully separate candidates who appear only once. Full-name identity linkage is conservative and splits names that collide within a cycle; surname-only rows are race-specific and excluded from longitudinal linkage until manually resolved. The method may still miss a person whose recorded full name changes. The uncertainty interval is a specification-and-data-quality band, not a causal confidence interval. The 1994 tier retains weaker geography and presidential inputs. Successor persistence shows that unmeasured local context remains. The bivariate prior-CMO/next-win association is not a multivariable predictive test and does not validate CMO as a future-win score.