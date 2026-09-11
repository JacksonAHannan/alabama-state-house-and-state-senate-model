# Tennessee 1998 precinct OCR staging validation — V6

**Verdict: PASS for conservative experimental staging, with explicit coverage caveats.**

V6 resolves the final state-inheritance defect without manufacturing precinct observations. Senate District 33 now retains its readable Shelby County precinct rows, while its unresolved OCR shortfall remains visible and keeps the district out of the eligible panel.

## Independent rebuild and tests

Using the frozen OCR cache, I independently rebuilt twice to an absolute temporary path:

```powershell
python scripts/build_tennessee_1998_precinct_staging.py --output "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\tennessee_1998_v6" --workers 3 --zoom 2.0
python -m pytest scripts/tests/test_tennessee_1998_precinct_staging.py -q
```

Both runs reproduce build ID `b94bf629de0d40f3157c` and the following counts:

- 47,212 frozen OCR tokens
- 4,008 legislative precinct observations
- 2,518 governor precinct observations
- 50 governor-review rows
- 117 district reconciliation rows
- 88 governor county totals
- 117 district-header audit rows
- 79 eligible districts: 68 House and 11 Senate

The focused suite passes 9/9. The temporary manifest is deterministic across consecutive rebuilds (SHA-256 `36f6b51db9420cd14318110dbf0a269e669a04585f1d9e25bcbb5c7760c86453`). All non-manifest temporary outputs byte-match the release candidate; the manifest differs only because it records the output path.

## Source and parser checks

- The header inventory contains all 99 unique House districts and 18 unique Senate districts: SD-8 plus every odd district from SD-1 through SD-33.
- The ten House and two Senate documented header overrides agree with source-page inspection. Previously misread punctuation and split digits no longer cause district state bleed.
- Senate page 6 is correctly SD-8, page 7 is SD-9, and both contests are retained separately. SD-8 is explicitly secondary-source-missing and ineligible; SD-9 reconciles within 1% and is eligible.
- Senate pages 28–29 visibly contain the SD-33 header, Shelby precinct block, and printed district total. V6 carries the source-established Shelby county state into that district rather than dropping the block.
- `COUNTY TOTAL`, OCR variants `COUNTY TOTAD` and `COUNTY ZOTAL`, subtotals, candidate headers, report labels, and write-in headings do not appear as precinct records.
- Source-verified county aliases remain correct: `HLINS -> SMITH`, `LIHM -> WHITE`, and `NOSNHOF -> JOHNSON`. No staged county is unresolved.
- Legislative keys are unique, required keys are populated, and vote counts are nonnegative.
- Raw PDF, Klarner, OCR-cache, and output hashes agree with the manifest.
- Independent aggregation reproduces the released reconciliation statuses and eligibility decisions. Eligible rows have finite source totals and satisfy the declared tolerance.

## Conservative SD-33 treatment

V6 stages 60 readable SD-33 precinct rows totaling 22,460 votes. The separately preserved printed district-total audit records 23,653, exactly matching Klarner's 23,653. The 1,193-vote gap is therefore an identified precinct-OCR completeness problem, not evidence that the aggregate should be distributed or inserted as a fabricated precinct.

The released reconciliation correctly records:

```text
legislative_turnout       22,460
Klarner total             23,653
vote_delta                -1,193
reconciliation_status     material_mismatch
model_eligible            false
```

This treatment satisfies the repository's missing-data and provenance rules: available precinct observations are retained, the authoritative aggregate is preserved for audit, and the unresolved difference prevents model eligibility.

## Integration caveats

- Approval applies only to the 79 explicitly eligible district rows. SD-8, SD-33, and every other missing/materially mismatched district must remain excluded unless separately remediated and revalidated.
- The governor context remains incomplete: 50 lines are routed to review, only 88 finite county totals are available, and five county coverage ratios exceed one. Missing values are not zero-filled. Any downstream use must retain the published coverage/review gates.
- OCR precinct spellings are source-derived identifiers, not proof of stable cross-cycle precinct identity.
- The frozen token cache is deterministic and source-hashed; reproducing OCR itself remains comparatively expensive and may vary with OCR software versions.

Subject to those constraints, V6 is fit for experimental historical-panel staging.
