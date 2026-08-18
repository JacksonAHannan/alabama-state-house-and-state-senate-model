# Cross-state implementation roadmap

## Phase 0 — scaffold

- common repository topology and agent instructions
- state identity configuration
- architecture, data-contract, and adapter documentation

## Phase 1 — authoritative election backbone

- official candidate and district results
- election, contest, candidate, party, and incumbency identities
- district-plan registry and geography validation
- completeness and vote-total reconciliation

## Phase 2 — comparable context

- federal/statewide baseline elections
- Census/ACS district demographics by correct vintage
- campaign-finance coverage and missingness policy
- political-environment features with explicit as-of dates

## Phase 3 — legislative evidence

- legislators, bills, sponsorships, roll calls, and member votes
- candidate-to-legislator identity crosswalks
- ideology and issue-position models with review queues

## Phase 4 — modeling

- common baseline specifications
- state-specific deviations documented as configuration
- time-forward validation, calibration, ablation, and sensitivity analysis
- versioned House and Senate simulations

## Phase 5 — publication and federation

- model cards and audit summaries
- accessible state dashboards
- contract-versioned cross-state exports
- portfolio-level comparison without erasing state-specific uncertainty

