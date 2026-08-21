# Fundamentals+ historical CMO

The headline historical CMO is recalculated for every contested Democratic–Republican race from 1994 through 2022 using the Fundamentals+ expectation.

Each cycle is scored by a model trained on every other cycle. The expected legislative margin begins with the same-cycle statewide ticket margin measured inside the legislative district, then adds 20% of a ridge adjustment capped at four points. The adjustment contains demographic composition, regional context when available, finance, incumbency and open-seat status, chamber, presidential context, and available candidate-history indicators. Starting from the same-cycle ticket prevents presidential partisanship from being counted twice in a retrospective measure whose target is performance relative to that ticket.

This is retrospective leave-one-cycle-out estimation. In particular, the 1994 score uses later cycles for training and must not be described as a forecast that could have been issued in 1994. It is distinct from the prospective forecast baseline, which begins with presidential partisanship and a projected national environment. Numerical prior-CMO features are unavailable in the current historical training panel and therefore contribute no fitted variation; prior-appearance and prior-winner indicators remain available.

The public `candidate_cmo_total_oof` field now points to the cycle-held-out Fundamentals+ result. Earlier headline values are preserved on race rows under `legacy_*` columns. Resource-adjusted and fundraising-adjusted sensitivity fields remain separate and are not relabeled as Fundamentals+.
