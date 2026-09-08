# Southern historical WAR v1

Run: `WAR-SOUTH-HIST-V1-45EC0B380AAEA007C2DF`

> **Release status:** this builder ran only after the exact upstream v3 release gate passed. The manifest records that decision as an input.

The release scores 4,280 strict D-versus-R regular legislative races in the 14-state Southern scope from 2016 through 2024. Post-2016 races preserve the published Southern WAR v3 same-cycle structural residual. The 2016 races are scored by applying the selected post-2016 `decaying_lag` ridge model (alpha 100) backward, without using any 2016 outcome to fit the model.

`WAR = legislative-minus-ticket gap - fitted structural expected gap`.

Fundraising is displayed only where both major-party observations and identities are complete. It does not enter headline WAR because the prespecified nested time-forward finance test failed. Missouri and Mississippi are the principal finance gaps in this warehouse run; missing finance is unknown, never zero. Research-only context, uncontested races, and non-D/R races remain unscored.

## Explicit empty schedule slices

Virginia's 2017 and 2021 lower-chamber slices remain present in the schedule with zero scored contests because their same-year governor returns use 2019-plan cross-election precinct membership and locality fallback. Recovery requires registered election and contemporaneous-plan sources, reviewed allocations, retained fallback/unknown rows, and district/state reconciliation. Missing WAR is not zero.

## Exclusions, source lineage and plan provenance

The warehouse holds 4,582 model-valid D-versus-R outcomes for the schedule; 302 remain research-only and unscored: 151 because their recorded ticket baseline is not strictly eligible (the two Virginia lower-chamber slices above) and 151 because incumbency rests on experimental prior-winner continuity without roster evidence. Reason-coded counts per state are in `state_release_coverage.csv`; a documented exclusion is not a zero score.

4,280 of 4,280 strict races carry a registered scalar source file; 0 do not. Alabama 2018 and 2022 contests take the certified State Canvassing Board canvass as their registered source through the reviewed canonical/certified bridge, which also supplies their third-party vote totals. Every scored race retains the provider-reported district plan label; display geometry does not certify an allocation.
