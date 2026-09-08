# Combined Southern historical panel validation

**Task:** `VALIDATE-SOUTHERN-COMBINED-PANEL-001`  
**Date:** 2026-08-22  
**Verdict:** **PASS for experimental analytical use.**

## Independent rebuild and tests

I rebuilt the combined panel into a separate absolute workspace path and
repeated the build at the same path.

```powershell
python scripts/build_combined_historical_southern_panel.py --output <absolute-temp>
python -m pytest scripts/tests/test_combined_historical_southern_panel.py -q
```

All three CSV outputs are byte-identical to the release candidate. The manifest
is byte-identical on a repeated same-path build. Focused tests: **2 passed**.

## Allocation and coverage

I independently reconstructed the normalized precinct keys, legislative
turnout mapping, context-party aggregation, split weights, allocated votes,
district baselines, office priority, and both coverage measures.

- 67,250 precinct/chamber mapping groups were formed.
- Every mapping group with positive legislative turnout has weights summing to
  one; negative weights: 0.
- Across 247,128 allocatable precinct/chamber/office/party groups, allocated
  votes reproduce source context votes to floating-point precision (maximum
  difference `1.82e-12`).
- 3,604 groups have no positive legislative-turnout proxy. Their 443,580
  context votes remain unallocated rather than receiving manufactured weights.
  The difference remains visible through allocated-versus-source votes and
  `minimum_party_vote_coverage`.
- All 2,178 selected district baselines independently reproduce their office,
  D/R votes, margin, context-footprint coverage, and turnout-join coverage.
  One selected baseline has no corresponding Klarner outcome, leaving 2,177
  OpenElections candidate rows as expected.
- Presidential, then U.S. Senate, then governor priority has zero mismatches.
- All 48 state/year/chamber/office coverage rows independently reproduce the
  published coverage output.
- Turnout-join coverage is bounded from 0.8745 to 1.0 across all coverage rows.
  Every strict OpenElections row passes the 0.95 gate; the strict minimum is
  0.97524.

The statewide context footprint is diagnostic rather than a gate, consistent
with the documented staggered-Senate rationale. Among strict rows its minimum
is 0.4569 (Missouri staggered Senate footprints), while its median is 0.9985.
This field must remain available for sensitivity analysis.

## Cycle and district gates

Recomputing `strict_cycle_gate` produces zero row mismatches. The exclusions
are enforced as follows:

- Georgia 2014: all 236 candidate rows fail the cycle gate; strict rows: 0.
- Arkansas 2008: all 29 candidate rows fail the cycle gate; strict rows: 0.
- South Carolina 2006 and Missouri 2014 create no candidate baseline/outcome
  rows under the configured office set; strict rows: 0.
- Missouri 2012 HD150, Georgia 2012 SD30, and Georgia 2016 SD13 each explicitly
  fail the cycle gate; strict rows: 0 for each key.

Of 981 permissive two-party rows with a baseline, 908 are strict. Seventy-three
fail a cycle restriction. Twenty-two Arkansas House rows also fail turnout-join
coverage, so no otherwise allowed cycle is removed solely by that coverage
gate in this release.

The 908 strict OpenElections rows occur only in the approved Georgia 2012/2016
and Missouri 2000–2012/2016 cycle-chamber sets after the specified district
exclusions.

## HEDA precedence and exact composition

- Strict HEDA rows: **1,805**.
- Strict OpenElections rows before overlap: **908**.
- HEDA/OpenElections key overlaps: **440**.
- Additive OpenElections rows after HEDA precedence: **468**.
- Combined rows: **2,273 = 1,805 + 468**.

All 1,805 HEDA keys are present once. Their D/R outcomes, legislative margin,
baseline margin, raw overperformance, and incumbency balance are unchanged.
No added OpenElections key overlaps HEDA. Combined
`(state, year, chamber, district)` keys have zero duplicates, every row is
strictly model eligible, and no row is `partial_unresolved`.

## Manifest

The expected build ID independently recomputed from the current HEDA-panel
manifest, OpenElections-staging manifest, and current combined-panel script is
`1a95ee5fe000f0534d79`, exactly matching the release manifest. Both recorded
input hashes reconcile. All three output sizes and SHA-256 hashes reconcile,
and manifest counts equal the independently observed 1,805, 908, 468, and
2,273 rows.

The default production dependency chain also transitively pins the Klarner
archive used for outcomes. A nonblocking CLI provenance limitation remains:
custom `--heda`, `--oe-dir`, or `--klarner` arguments are not substituted into
the manifest dependency paths/build ID. Before this builder is used with
nondefault inputs, manifest construction should hash and record the resolved
arguments directly, including Klarner.

## Disposition

The 2,273-row combined panel is approved for the documented experimental
Southern CMO tournament. It is not canonical election data and does not replace
the production Alabama forecast. Secondary-source authority, the absence of
1994–1998 coverage, staggered-Senate footprint sensitivity, and all explicit
cycle/district quarantines must remain visible in downstream model reporting.
