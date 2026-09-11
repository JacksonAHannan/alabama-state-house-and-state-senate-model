# Ideology coverage rerun validation

**Final verdict: PASS.**

The rebuilt ontology-v3 evidence, absolute ideology analysis, and caucus clustering are fresh and consistent with the corrected identity layer.

## Results

- Focused validation passes: 49 tests.
- Legislative evidence contains 12,192 rows; the combined evidence ledger contains 24,273 rows.
- Both ledgers have globally unique `evidence_id` values and unique `(canonical_candidate_id, evidence_id)` keys.
- No legislative evidence row with a parseable evidence year is later than its election cycle.
- Available pre-election scores have no duplicate `(year, chamber, member_source_id)` assignment and no future-window leakage.
- The canonical ideology candidate table contains 1,564 unique candidates; the absolute-analysis panel contains 1,018 unique candidates.
- The cluster membership output contains 274 unique candidate-cycles: 115 Democrats and 159 Republicans. The selected deterministic solutions are two Democratic and three Republican clusters.
- Analysis and cluster outputs postdate the rebuilt ideology mart.

## Identity propagation

The corrected Jack Williams resolution propagates downstream: 2014 HD-47 is linked to `LEGISCAN-3418` and contributes 44 legislative evidence rows, while 2014 HD-102 remains ambiguous, unlinked, and without legislative evidence.

No stale identity, duplicate evidence, or temporal eligibility blocker remains.

