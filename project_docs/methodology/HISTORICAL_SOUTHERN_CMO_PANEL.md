# Historical Southern HEDA comparison panel

This experimental panel extends cross-state legislative comparisons backward
using the HEDA precinct staging and Klarner candidate metadata. It is not the
production 2026 probability calibrator.

For each state-year-chamber-district, the panel records Democratic and
Republican legislative votes from the Klarner contest archive, candidate names and incumbency when available,
and a same-cycle baseline selected in this order: presidential, U.S. Senate,
then governor. The hierarchy keeps a federal baseline whenever the archive
contains one.

When one reported precinct belongs to multiple legislative districts, HEDA
provides separate legislative vote slots but only one statewide result. The
pipeline allocates statewide votes among those fragments in proportion to
their legislative turnout. Whole-precinct assignments are marked
`whole_precincts`; affected district baselines are marked
`includes_turnout_share_allocation`. Missing or unallocatable context remains
missing. Each selected baseline also carries expected, allocated, and
incomplete context-group counts. Any district containing an unallocatable
group is marked `partial_unresolved`.

The output is suitable for exploratory downballot-lag and candidate-quality
tests. Promotion into a model requires validation of HEDA staging, robustness
checks excluding allocated splits, and supplementation with official and
OpenElections cycles absent from HEDA.

HEDA legislative district sums are retained only as reconciliation evidence.
They are not treated as proof that a contest occurred: the `model_eligible`
flag requires finite, positive Democratic and Republican Klarner contest totals
and a complete available HEDA baseline. A separate
`model_eligible_permissive` field exposes rows with partial baselines only for
explicit sensitivity work. This prevents small stray precinct fragments in
uncontested or staggered districts from becoming synthetic elections.

`historical_southern_heda_manifest.json` records input and output hashes, code
identity, configuration, build ID, and strict/permissive row counts.
