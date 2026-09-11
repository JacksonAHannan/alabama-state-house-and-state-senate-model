# HEDA historical precinct staging validation

**Task:** `VALIDATE-HEDA-HISTORICAL-001`  
**Date:** 2026-08-22  
**Verdict:** **FAIL — staging is suitable for continued reconciliation, but Florida 2010 is not fit for direct canonical promotion.**

## Scope and method

I independently read the contracted pipeline, tests, source note, two source
archives, and current staging outputs. I rebuilt the pipeline into a new
directory under `%TEMP%`; no production output or warehouse table was written.

Principal commands:

```powershell
python scripts/build_heda_historical_precinct_staging.py --output <temporary-directory>
python -m pytest scripts/tests/test_heda_historical_precinct_staging.py -q
Get-FileHash "data/raw/historical_statewide_elections/dataverse_files (4).zip" -Algorithm SHA256
Get-FileHash "data/raw/historical_statewide_elections/dataverse_files.zip" -Algorithm SHA256
```

I also independently loaded every release and temporary CSV with pandas,
compared frames, recomputed district aggregates from precinct fragments,
audited compound keys and missingness, and inspected the underlying Florida
2010 Klarner rows before the reconciliation filter.

## Reproducibility

- The rebuilt data content exactly equals all seven staged release tables.
- Five uncompressed CSVs are byte-identical to the release.
- The two gzip files have different file hashes between builds, although their
  decompressed SHA-256 hashes are identical:
  - legislative fragments: `f42babfcd38c68fed450bbde6e11c1b1a832fc71df3c48e2c11e797da358d6ee`
  - context: `db1b8146f3f0db36fd6422d730869a32395d91b1ca8fd1dd1109d4f9c93b2f35`
- The gzip-byte difference is consistent with nondeterministic gzip metadata.
  It does not change records, but it prevents fully byte-deterministic builds.
- The focused suite passed: **4 passed**.

Rebuilt counts:

| Output | Rows |
|---|---:|
| state-year coverage | 85 |
| legislative precinct fragments | 240,160 |
| precinct context | 1,777,718 |
| legislative district totals | 4,867 |
| Klarner reconciliation | 4,867 |
| Florida 2010 precinct fragments | 13,640 |
| Florida 2010 district totals | 160 |

## Provenance and keys

- The HEDA archive SHA-256 is
  `49fbe39c7e2d3a2ba07cdd42d2092a297a9f8892a95f6f5fb45748b6e4079bdc`.
  Every legislative and context row carries that exact hash, ZIP member, and
  one-based source row.
- The Klarner archive SHA-256 is
  `b4c0913fa7bfb0aff4da2dbf67a22da696e9f07b45615f30e78127edd794a3e1`.
- Legislative keys `(source_member, source_row, chamber, district_slot)` have
  zero duplicates. Context keys `(source_member, source_row, office,
  contest_slot)` also have zero duplicates. District keys `(state, year,
  chamber, district)` have zero duplicates.
- All legislative rows identify their original district and D/R/total source
  fields. Context district-source fields are appropriately absent for
  statewide offices.
- The contracted artifacts do **not** include a complete source manifest with
  source URL, retrieval timestamp, license/terms, geographic vintage, code
  version, configuration, or build/run identifier. The row-level archive hash
  is useful but does not satisfy the repository's complete provenance contract
  for canonical promotion.

## Missingness and split slots

The normalizer does not fill missing party observations with zero. Across the
legislative table, 31,861 Democratic observations and 26,369 Republican
observations are missing while explicit source zeroes remain explicit zeroes.
All but 119 total-vote observations are present. County, precinct name, and
precinct code are source-dependent and missing in 14,598, 108,705, and 196,275
rows respectively; these limitations must survive promotion as unknowns.

Numbered district slots are preserved: 12,498 legislative fragment rows use a
slot above one, representing 7,644 distinct source rows, with slots extending
through 16. No fragment-key duplication was found. Every recomputed district
D/R/total sum equals the published aggregate (zero mismatches).

## Florida 2010

The file contains every nominal district identifier:

- House: 120 distinct districts, exactly 1 through 120.
- Senate: 40 distinct districts, exactly 1 through 40.
- Florida fragment keys are unique; county, precinct, and vote fields have no
  missing values.

That nominal coverage is not equivalent to 160 complete election contests:

- 24 House districts and 16 Senate districts aggregate to zero two-party votes.
- Klarner has a finite comparison for only 84 House and 16 Senate districts.
  This is partly expected because its Florida records contain `NaN` party
  totals for districts without a reported contest, including staggered Senate
  seats and apparently uncontested/unreported House seats.
- More seriously, 12 House and 8 Senate districts without a finite Klarner
  contest still contain positive, generally small HEDA fragment totals. This
  pattern is consistent with precinct/district allocation leakage or source
  reporting conventions and cannot be interpreted as a complete district race
  without further evidence.
- Among the 100 finite Klarner comparisons, only 43 match both party totals
  exactly (37/84 House and 6/16 Senate).
- For comparable House races the aggregate absolute discrepancy is 1.18% of
  Klarner two-party votes. The largest party discrepancy is 3,272 votes; House
  17 differs by +905 Democratic and -2,824 Republican votes.
- For comparable Senate races the aggregate absolute discrepancy is 0.30%; the
  largest party discrepancy is 1,345 votes.
- Florida exposes only slot 1 (`ld`/`sd`) in this extraction, despite the
  suspicious positive fragments in districts lacking a Klarner contest.
  Therefore the general split-slot support demonstrated elsewhere does not by
  itself resolve Florida's allocation ambiguity.
- `total_votes` exceeds D+R in 3,762 of 13,640 Florida fragments and never falls
  below it, totaling 343,391 additional votes. This is plausible third-party or
  other-candidate activity, not an arithmetic failure, but candidate-level or
  office-specific verification is required before using total vote as a
  two-party denominator.

## Promotion decision

The extractor and staging tables pass their mechanical checks and are useful
secondary evidence. **Florida 2010 should not be promoted as a definitive
canonical precinct legislative result in its current form.** Promotion should
require:

1. a reviewed district-status field distinguishing held election, uncontested
   or unreported race, staggered/no-election seat, and unresolved fragment;
2. reconciliation of all 57 nonexact finite comparisons and the 20 positive
   HEDA districts with no finite Klarner result against Florida's official
   contest totals or another authoritative source;
3. review of precincts that may span legislative districts, especially where
   HEDA provides only `ld`/`sd` slot 1;
4. a complete source/build manifest and deterministic gzip serialization; and
5. an explicit warehouse authority rule retaining HEDA and Klarner as
   conflicting secondary observations rather than silently selecting either.

Until then, Florida 2010 may be staged with an unresolved/review status and may
support targeted geography work, but it should not train or validate a model as
if all 120 House and 40 Senate totals were certified complete contests.
