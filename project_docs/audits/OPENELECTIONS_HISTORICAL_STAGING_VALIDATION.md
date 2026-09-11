# OpenElections historical staging validation

**Task:** `VALIDATE-OPENELECTIONS-STAGING-001`  
**Date:** 2026-08-22  
**Verdict:** **FAIL pending Georgia 2016 presidential-office parsing fix.**

The included observations, aggregation, reconciliation, party safeguards, and
provenance all pass. A complete general-election context staging does not pass
because 8,079 Georgia presidential observations are omitted.

## Independent rebuild and tests

I rebuilt the staging into a new absolute temporary directory and repeated the
build at the same path.

```powershell
python scripts/build_openelections_historical_staging.py --output <absolute-temp>
python -m pytest scripts/tests/test_openelections_historical_staging.py -q
```

The seven data outputs are byte-identical to the release candidate. The
manifest is byte-identical on a repeated same-path build. Focused tests:
**4 passed**.

Rebuilt counts match the manifest: 720,261 relevant observations, 126,683
legislative rows, 446,513 context rows, 2,353 district aggregates, and fourteen
state-cycle combinations.

## Provenance, keys, and manifest

- Observation and legislative keys `(source_file, source_row)` have zero
  duplicates.
- District and reconciliation keys `(state, year, chamber, district)` have
  zero duplicates.
- Legislative source file, SHA-256, and source row are complete on every row.
- The Georgia 2014 source's 27,694 included observations retain
  `unofficial_label`; all other 692,567 included observations retain
  `repository_normalized`.
- The expected build ID recomputed from the acquisition-manifest, Klarner, and
  current staging-script hashes is `cc9baccb8e87ffcc8120`, exactly matching the
  manifest.
- Both input hashes, all seven output hashes and byte sizes, and every manifest
  row count reconcile.

## Georgia vote modes

I independently reopened all 161 Georgia source files and recalculated vote
values by source row.

- Georgia 2012 and 2014 use exactly one sum of election-day, advanced,
  absentee-by-mail, and provisional modes.
- All 159 Georgia 2016 county files use their provided total `votes` field;
  none has a row where that total is missing while component modes are present.
- All 67,959 **included** Georgia normalized observations match the independent
  source-row calculation; mismatches: 0.

The mode-sum logic therefore passes for rows that reach normalization.

## Party resolution and known-label preservation

I independently normalized every `party_raw` value.

- 354,093 included rows have a known source D/R label.
- Known labels overwritten: **0**.
- Known labels assigned a resolution other than `source`: **0**.
- Among raw-unknown rows, 12,411 resolve from the same candidate elsewhere in
  the same state-cycle-office and 90 resolve from Klarner; 353,667 remain
  unknown.
- The party-resolution audit sums exactly to all 720,261 observations.

Georgia 2016 legitimately relies heavily on cross-file candidate resolution:
3,150 legislative rows (2,886,088 votes). Exact candidate matching preserves
the raw label and resolution method. Its remaining unknown legislative votes
are 25,577, or 0.37% of included legislative votes.

## Missouri 2000 embedded districts

Missouri 2000 has no populated raw district column on its 12,811 legislative
rows. All 12,811 office labels yield an embedded district; every normalized
district equals that embedded value. The output contains House districts
1–163 and the 17 Senate districts appearing in that election (numbered within
1–33). No district is missing.

## District aggregation and Klarner reconciliation

Reaggregating normalized D/R observations reproduces all 2,353 district-party
rows with zero vote mismatches. Reconciliation deltas and exact-total flags
also recompute correctly.

The reconciliation identifies source-specific fitness limitations:

- Arkansas 2008 is materially incomplete: House absolute discrepancy is about
  35.1% of Klarner party votes and its single Senate district differs by 20.6%.
- Georgia 2012 House party totals match Klarner exactly wherever both are
  observed. Senate district 30 is anomalous: OpenElections reports 56,995
  Republican votes versus Klarner's 6,463, a 50,532-vote difference.
- Georgia 2014 is explicitly unofficial and differs by about 2.9% overall in
  both chambers, with several large district discrepancies.
- Georgia 2016 House party totals match wherever observed. Senate results are
  close overall, but Democratic district 13 differs by 1,586 votes.
- Missouri is generally extremely close to Klarner. The main exception is
  2012 House district 150, where D and R totals are lower by 3,977 and 3,956
  votes. Other Missouri cycle/chamber weighted discrepancies are at or below
  roughly 0.026%, usually much less.
- Missouri 2016 includes Senate district 18 without a Klarner comparison; it
  must remain a separately reviewed contest rather than be discarded.

`exact_party_totals` is deliberately strict and is false when one source has a
missing party observation, so raw exact-row rates understate agreement in
uncontested districts. The party-by-party comparisons above condition on both
sources having a value.

## Blocking office-classification defect

The Georgia 2016 files contain **8,079** rows labeled `President of the United
States`. They are absent from staging. The classifier currently requires a
presidential label not to contain the substring `state`; that substring occurs
inside `United States`, so a valid U.S. presidential office is rejected.

This is not an upstream-coverage absence. It is a deterministic normalization
error. It causes Georgia 2016 to show no `USP` context and reduces the claimed
relevant/context counts. Add a fixture for `President of the United States`,
correct the classification rule, rebuild, and revalidate Georgia mode sums,
counts, output hashes, and manifest.

The only other suspicious unclassified labels found were lieutenant-governor
contests, which are intentionally outside the configured office set.

## Experimental cycle-use assessment

No output should enter a canonical warehouse as authoritative election fact.
For an experimental panel after the parsing fix:

| State-cycle | Assessment |
|---|---|
| MO 2000, 2002, 2004, 2006, 2008, 2010, 2016 | usable with secondary-source flags and strict Klarner outcome gate |
| MO 2012 | usable only after quarantining/reconciling House 150 or using an independent outcome and completeness check |
| MO 2014 | legislative validation only under the current baseline definition; no USP/USS/GOV context is present |
| GA 2012 | House usable; Senate requires district-30 review or exclusion |
| GA 2014 | unofficial sensitivity view only, not a default training cycle |
| GA 2016 | potentially usable after restoring presidential context; retain Senate-13 and party-resolution diagnostics |
| AR 2008 | context-only; legislative results are too incomplete for an outcome or turnout-allocation source |
| SC 2006 | context-only; no legislative contest observations are present |

Using Klarner as the district outcome prevents stray OpenElections observations
from manufacturing races, but it does not by itself cure incomplete precinct
coverage used to construct or allocate a baseline. Any panel builder must carry
allocation completeness and explicit district quarantine fields.

## Required remediation

1. Recognize `President of the United States` as `USP` without weakening the
   state-office guard.
2. Add a regression test for that exact label.
3. Rebuild staging and update the manifest/counts.
4. Preserve the cycle/district restrictions above in the downstream review or
   eligibility contract.

After the Georgia parsing fix, the staging can be approved as secondary
normalized evidence with the documented cycle-specific restrictions.
