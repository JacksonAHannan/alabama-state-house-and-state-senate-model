# Post-2016 Southern WAR v2: explicit lag and finance sensitivity

## Headline structural model

The selected specification is `decaying_lag` with ridge alpha 100. It predicts the observed legislative-minus-ticket margin gap from incumbency, ticket partisanship, era, state, chamber, and ticket-office context. Validated prior-presidential margin and ticket change enter only where an exact race-key context exists; missing lag context stays labeled. The lag specification is selected in expanding-window tests, while the historical structural expectation used for WAR is cross-fitted within cycle so each race is excluded from its own prediction.

Lag context is available for 1,284 of 3,660 races. On forward lag-complete rows, selected-model MAE is 4.805 points. Mean absolute modeled lag is 3.910 points in 2018 and 1.875 in 2022; these are model contributions, not raw group means.

## Fundraising sensitivity

Split Ticket's 2024 federal model treats spending mainly as a campaign-viability indicator: when both parties are above or both below $1.5 million, its spending feature is zero; otherwise it uses the spending ratio. Their published discussion says the median WAR adjustment is below 0.25 margin points and explicitly notes that finance could reasonably be excluded. See https://split-ticket.org/2025/08/15/deconstructing-war/.

This repository has candidate fundraising, not comparable candidate-plus-outside spending, so the federal dollar threshold is not ported. We test a diagnostic grid at every $10k from $10k through $100k, plus $250k as an upper sensitivity, on the same finance-complete forward rows. The $10k lower bound is a stress-test gate, not a substantive claim that $10k makes a campaign viable. The retrospective grid minimum is `viability_gated_10k` with MAE 5.976; it is not promoted. Nested forward selection chooses `viability_gated_250k` for the latest-cycle sensitivity: fixed-threshold MAE 6.042 versus 6.019 without finance; latest-cycle MAE 5.186 versus 5.125. Nested threshold selection yields MAE 5.645 versus 5.625, with predictive status `fails_nested_forward_gate`. Promotion status is `rejected_not_comparable_total_spending_and_endogenous`. Finance remains outside headline WAR because receipts are endogenous to candidate strength and source coverage is incomplete.

## Interpretation

WAR remains a partial-pooled candidate effect in two-party margin points after the selected cross-fitted structural expectation. Candidate-pair-only effects remain uncertain. The v1 model is preserved; v2 does not overwrite it. Dexter Grimsley comparison: v1 5.600; v2 2.882.

Model run: `WAR-POST2016-V2-710F713D8C6FBCDB4D4C`.
