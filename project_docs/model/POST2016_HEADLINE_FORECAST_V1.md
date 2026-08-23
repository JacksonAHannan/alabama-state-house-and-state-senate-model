# Post-2016 headline forecast

## District estimate

The forecast treats the current national generic-ballot movement from 2024 as the federal result that would otherwise anchor down-ballot performance. Each district begins with its 2024 presidential margin and receives the same national polling swing.

The model then estimates the usual legislative difference from that federal baseline using Alabama elections after 2016. The candidate adjustment includes generic down-ballot lag, incumbency, and fundraising strength relative to what would normally be expected from district partisanship, competitiveness, chamber, and incumbency.

The fundraising normalization uses the current cycle's fundraising and district covariates but no election result. Missing campaign-finance observations remain missing and receive no fundraising adjustment. Current finance coverage is 43 of 48 contested Democratic-versus-Republican races.

## Historical test

The model trains on 59 contested races in 2018 and predicts 30 contested races in 2022. Its 2022 mean absolute margin error is 7.08 points, compared with 10.00 for the polling-federal baseline and 9.54 for polling plus incumbency.

The paired bootstrap improvement over the polling-federal baseline is +2.91 points, with a 95% interval from +0.83 to +5.00.

## Polling-error scenarios

The Democratic-favorable and Republican-favorable scenarios move every district by one historical national polling-error standard deviation (2.20 margin points) in the corresponding direction. These are shared national shifts, not independent district adjustments.

## Probabilities and chamber totals

Expected margins are converted to conditional win probabilities with a Student-t curve with five degrees of freedom and a 5.75-point scale. Chamber summaries use 50,000 simulations with shared national, statewide, and chamber errors plus district-specific error.

## Limitations

Only one Alabama forward cycle directly tests the full candidate adjustment. Historical fundraising is measured over the full election cycle, while the current 2026 figures are a partial-cycle snapshot. Fundraising can reflect donor expectations and campaign strength as well as resources available to the candidate, so its coefficient should not be interpreted causally.

Build: `e178fb3f50c98c9c312b`.
