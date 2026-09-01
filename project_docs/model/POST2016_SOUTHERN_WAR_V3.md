# Post-2016 Southern WAR v3: race-level structural residual

## Definition

Headline WAR is the observed Democratic legislative-minus-ticket margin gap minus the gap predicted by the fitted structural regression. This implements Split Ticket's published definition of WAR as the regression residual. The score belongs to the race differential: candidate-cycle rows merely reverse its sign for the Republican perspective. No second-stage candidate pooling or ridge penalty modifies WAR.

The `decaying_lag` specification with alpha 100 was selected by earlier-cycle forward validation, then fitted separately within each cycle for descriptive post-election scoring. Cross-fitted predictions remain validation fields and are not WAR.

All 3,658 strict races after 2016 were scored. Dexter Grimsley: raw gap D+18.590, fitted structural gap D+5.295, WAR D+13.295.

## Lag and finance

On lag-context races, mean absolute fitted lag is 4.125 points in 2018 and 2.011 in 2022. Missing lag context remains explicit.

Candidate fundraising remains outside headline WAR. The diagnostic threshold grid runs every $10,000 through $100,000 plus $250,000, and its nested forward status is `fails_nested_forward_gate`. State fundraising is not treated as comparable to Split Ticket's candidate-plus-outside federal spending measure.

Split Ticket methodology: https://split-ticket.org/2025/08/15/deconstructing-war/

Model run: `WAR-POST2016-V3-D9C7EE17BD14B8C7D23A`.
