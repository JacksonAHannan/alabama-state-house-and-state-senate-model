# Post-2016 Southern residual WAR field contract

## Grain and identity

`race_war.csv` contains exactly one row per strict post-2016 Southern D-versus-R final contest, keyed by `war_outcome_id` and uniquely by `state_code`, `cycle`, `chamber`, and `district`.

`candidate_cycle_war.csv` contains exactly two party-oriented observations per race, keyed by `war_outcome_id` and `canonical_party`. Candidate identity fields describe the candidate in that race and do not pool the score across elections.

## Headline calculation

All margins and WAR values use Democratic two-party margin points:

`raw_gap = legislative_dem_margin - baseline_dem_margin`

`war = raw_gap - fitted_structural_expected_gap`

A positive race WAR is Democratic overperformance; a negative race WAR is Republican overperformance. `war_party` is `D`, `R`, or `EVEN`, and `war_magnitude = abs(war)`.

Candidate-cycle orientation is mechanical: the Democratic candidate receives `candidate_cycle_war = war`; the Republican candidate receives `candidate_cycle_war = -war`. These are two views of one race differential, not separately identified individual effects.

## Structural baseline and validation

The headline structural baseline is fitted separately on the full eligible sample within each post-2016 election cycle, consistent with the implemented descriptive residual methodology. Specification and regularization are selected using earlier-cycle forward validation. Cross-fitted predictions and errors remain separate validation diagnostics and are never labeled WAR.

Finance remains outside the headline baseline unless it passes its prespecified nested forward gate and has a compatible source contract. Missing lag or finance context remains explicit and is never converted into observed zero.

No second-stage candidate-effect regression, candidate pooling penalty, or unexplained-residual allocation may modify headline WAR.

## Reference and explicit adaptation

Split Ticket describes WAR as the residual from a congressional-minus-
presidential margin-gap regression. Its 2024 explanation identifies incumbency,
prior presidential margins/swings, spending and district demographics as
structural inputs. This project adopts the residual framing, not an identical
federal model or its fitted coefficients. Reference checked September 7, 2026:
[Split Ticket, Deconstructing WAR](https://split-ticket.org/2025/08/15/deconstructing-war/).

The repository-specific contract follows
[`design_matrices`](../../scripts/retrain_post2016_southern_war_v2.py) and
[`fitted_cycle_predictions`](../../scripts/retrain_post2016_southern_war_v3.py):

- The universe is strict-ready, final-stage Southern state-legislative D/R
  contests after 2016, not federal House/Senate contests. Exact source stage,
  plan, geography and exclusion eligibility come from the shared warehouse.
- The comparator is each row's declared `baseline_dem_margin` with its
  `baseline_source`, `baseline_office` and quality/coverage. It is not uniformly
  an observed same-cycle presidential result. Never relabel a non-presidential
  comparator or reconstructed district allocation as one.
- The base design includes `incumbency_balance`, ticket margin and its squared
  term, years since 2016, odd-year and presidential-cycle indicators, plus
  state, chamber and baseline-office-family indicators. The selected
  `decaying_lag` adds prior presidential margin, current-ticket-minus-prior-
  presidential change, and that change interacted with years since 2016.
- This selected design has no demographic columns. It does not reproduce the
  reference's demographic or spending controls. Finance is excluded under the
  existing gate; fundraising receipts are not spending. No acquisition or
  predictor expansion is implied by documenting those deviations.
- Lag inputs retain explicit availability/source fields. Zero-filled design
  entries are compatibility encodings, not observed zero values; review their
  sensitivity before release. Ridge regularization and the forward selection
  procedure are project choices, not claimed reference implementation details.
- Southern 2016 and pre-2016 Alabama extensions follow their separate backcast
  contracts, not same-cycle fit claims. The prospective forecast is a separate
  estimand and requires its own temporal/calibration checks. Neither a residual
  nor its association with ideology isolates a causal individual effect.

This documentation reconciliation does not rerun or recertify existing models.
Previously hashed manifests retain their historical contract hash until a
separately validated run records the revised document.
