# OpenElections historical staging validation, v2

**Task:** `VALIDATE-OPENELECTIONS-STAGING-002`  
**Date:** 2026-08-22  
**Verdict:** **PASS for experimental staging with the v1 cycle restrictions.**

## Parser confirmation

The revised classifier recognizes `President of the United States` as `USP`,
and the focused test contains that exact regression fixture.

I independently scanned every raw source office label containing `president`.
The bundle contains 138,480 such rows across Arkansas 2008, Georgia 2012 and
2016, and Missouri presidential cycles. Every distinct presidential label is a
genuine U.S. presidential office and every one classifies as `USP`; the broader
predicate introduces no false positive within this bundle.

Georgia 2016 specifically now has:

- 8,079 raw rows labeled `President of the United States`;
- 8,079 relevant normalized rows;
- 8,079 rows with normalized office `USP`;
- 8,079 context rows;
- zero duplicate `(source_file, source_row)` keys;
- zero missing vote values; and
- zero vote mismatches against the original county-file `votes` fields.

The prior release had omitted exactly those 8,079 rows. The rebuilt totals
therefore change exactly as expected:

| Measure | Before | Current | Change |
|---|---:|---:|---:|
| relevant observations | 720,261 | 728,340 | +8,079 |
| context observations | 446,513 | 454,592 | +8,079 |
| legislative observations | 126,683 | 126,683 | 0 |
| district aggregates | 2,353 | 2,353 | 0 |
| state-cycle combinations | 14 | 14 | 0 |

## Independent rebuild and determinism

```powershell
python scripts/build_openelections_historical_staging.py --output <absolute-temp>
python -m pytest scripts/tests/test_openelections_historical_staging.py -q
```

All seven temporary data outputs are byte-identical to the release candidate.
The manifest is byte-identical on a repeated build at the same absolute path.
Focused tests: **4 passed**.

## Provenance and prior safeguards

- The recomputed current build ID is `db15d56eecac21da4f05`, exactly matching
  the release manifest.
- Both manifest input hashes and all seven output hashes and sizes reconcile.
- Actual row counts equal every manifest count.
- Observation, legislative, district, and reconciliation keys have zero
  duplicates.
- All 2,353 district D/R aggregates independently reproduce the legislative
  candidate observations.
- All reconciliation deltas independently reproduce the staged and Klarner
  totals.
- 354,121 rows now have a recognizable raw D/R label; known labels overwritten:
  0, and known labels assigned a non-source resolution: 0.
- Legislative, district, and reconciliation output bytes remain unchanged from
  v1, so the previously validated Georgia mode sums, Missouri 2000 embedded
  districts, and district-level caveats are unaffected.
- Georgia 2014 retains `unofficial_label`.

## Experimental-use disposition

The staging is approved as normalized **secondary evidence**, not canonical
election fact. The cycle restrictions from v1 remain:

- broadly usable with strict outcome and completeness gates: Missouri 2000,
  2002, 2004, 2006, 2008, 2010, and 2016;
- district review required: Missouri 2012 House 150, Georgia 2012 Senate 30,
  and Georgia 2016 Senate 13;
- no configured top-ticket context: Missouri 2014;
- unofficial sensitivity only: Georgia 2014;
- context-only because legislative returns are incomplete or absent: Arkansas
  2008 and South Carolina 2006.

Georgia 2016 now contains its presidential context and is eligible for
experimental panel construction subject to the existing Senate-13,
party-resolution, allocation-completeness, and Klarner-outcome safeguards.
