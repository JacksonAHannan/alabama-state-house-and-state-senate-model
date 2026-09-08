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

The headline structural baseline is fitted on the full eligible post-2016 sample, consistent with Split Ticket's descriptive residual methodology. Specification and regularization are selected using earlier-cycle forward validation. Cross-fitted predictions and errors remain separate validation diagnostics and are never labeled WAR.

Finance remains outside the headline baseline unless it passes its prespecified nested forward gate and has a compatible source contract. Missing lag or finance context remains explicit and is never converted into observed zero.

No second-stage candidate-effect regression, candidate pooling penalty, or unexplained-residual allocation may modify headline WAR.
