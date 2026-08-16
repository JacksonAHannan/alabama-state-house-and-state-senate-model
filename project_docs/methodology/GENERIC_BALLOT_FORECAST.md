# Generic-ballot environment adjustment

The headline prospective baseline remains each district's projected 2024 presidential two-party margin. The selected national-environment adjustment now uses Catalist's national demographic history, VoteHub-linked polls graded B+ or better in the supplied Nate Silver ratings, Alabama ecological-inference offsets, and 2024 ACS district composition. The current topline pools eight eligible pollsters; White, Black, and Hispanic relative shapes pool Marist, PPP, and TIPP; and the compatible education split comes from A- rated Marist. YouGov's historical tracker remains the 2024 comparison because the public VoteHub era begins after that election.

`download_votehub_generic_ballot.py` preserves the raw API response, normalizes Democratic and Republican responses to a two-party margin, excludes internal and partisan polls, keeps the latest release per pollster/sponsor within each window, and combines 7-, 14-, and 21-day averages with 30/50/20 weights. Likely-voter polls receive weight 1, registered-voter polls 0.75, and adult samples 0.5. VoteHub is attributed under CC BY 4.0.

VoteHub's public API does not expose demographic crosstabs. The separate
`build_votehub_crosstab_source_inventory.py` pipeline uses VoteHub as a poll
catalog, discovers and optionally archives pollster-published tabulation files,
and writes a source manifest. Reviewed cells are entered in the generated
`data/raw/polling/votehub_crosstabs_reviewed.csv` template. Then
`build_votehub_demographic_polling.py` enforces poll-ID provenance, valid shares,
explicit human review, and unique cells before producing long-form and pooled
demographic estimates. The pool excludes partisan/internal polls, retains only
the latest pollster observation per cell, and applies recency, population, and
reported-cell-base weights. The selected release output applies the independent
Silver B+ quality gate and canonical pollster names before pooling.

The original comparison layer remains deliberately transparent:

`district 2026 margin = district 2024 presidential margin + (2026 generic ballot margin - 2024 national presidential margin)`

The demographic layer uses white noncollege, white college, Black noncollege,
Black college, and a Catalist-calibrated residual category. The 2024-to-2026
national joint-cell change combines pooled VoteHub-linked race movements and
YouGov education movements on the logit scale and subtracts the overall
movement once to avoid double counting.
Alabama offsets are pooled from 2018 and 2020. Carrying the 2018 offsets forward
predicts the four independently estimated 2020 white/Black cells with 2.66-point
mean absolute error and 4.13-point maximum error, passing the declared 5/10 gate.

Poststratification over 2024 ACS cells produces district Democratic swings of
1.4 to 7.6 points, averaging roughly 3.4 points. These replace the uniform swing
in `poll_adjusted_dem_margin`; the uniform VoteHub result is retained in
`uniform_poll_adjusted_dem_margin`. The prospective race model remains labeled
experimental because full historical forecast errors and intervals are large.

Important limitations:

- VoteHub's beta API currently begins in December 2024, so it cannot supply historical polling backtests for 2010–2022.
- The polling snapshot records its latest poll date and staleness. A stale feed must not be presented as a current average.
- Generic ballot and presidential vote are not identical electorates or offices. The adjustment is an environment signal, not a literal forecast of the Alabama legislative vote.
- The joint polling movement is reconstructed from marginal race and education crosstabs; YouGov does not publish the exact joint cells used here.
- Only one forward Alabama offset transition (2018 to 2020) is currently available.
- Historical ecological estimates use 2022 ACS small-area cells as a proxy and carry corresponding vintage uncertainty.
- Candidate margin overperformance and fundraising/incumbency adjustments remain separate downstream layers.
