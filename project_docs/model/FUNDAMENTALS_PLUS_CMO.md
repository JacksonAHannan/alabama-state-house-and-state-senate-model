# Fundamentals+ historical CMO

The headline historical CMO is recalculated for every contested Democratic–Republican race from 1994 through 2022 using the Fundamentals+ expectation.

Each cycle is scored by a model trained on every other cycle. The expected legislative margin begins with the prior presidential district margin and the historically supported national-environment transfer, then adds 20% of a ridge adjustment capped at four points. The adjustment contains demographic composition, regional context when available, finance, incumbency and open-seat status, chamber, and available candidate-history indicators.

This is retrospective leave-one-cycle-out estimation. In particular, the 1994 score uses later cycles for training and must not be described as a forecast that could have been issued in 1994. Races without prior-presidential district geography use the same-cycle statewide index as an explicitly labeled fallback. Numerical prior-CMO features are unavailable in the current historical training panel and therefore contribute no fitted variation; prior-appearance and prior-winner indicators remain available.

The public `candidate_cmo_total_oof` field now points to the cycle-held-out Fundamentals+ result. Earlier headline values are preserved on race rows under `legacy_*` columns. Resource-adjusted and fundraising-adjusted sensitivity fields remain separate and are not relabeled as Fundamentals+.
