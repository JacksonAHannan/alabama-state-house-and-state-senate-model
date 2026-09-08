# Southern historical panel Tennessee extension validation

**Verdict: PASS for experimental panel use, with upstream Tennessee coverage caveats.**

The review candidate preserves the validated 2,383-row Southern panel exactly and appends 19 strictly gated Tennessee 1998 contests. Allocation, admission, provenance, and determinism checks pass.

## Independent commands

```powershell
python scripts/build_tennessee_extended_historical_southern_panel.py --output "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\southern_extended_tn"
python -m pytest scripts/tests/test_tennessee_extended_historical_southern_panel.py -q
```

The focused suite passes 4/4. Two complete builds in the same absolute temporary directory produce identical outputs and manifest SHA-256 `9ae95c5b72b71eb32a5f6e0482f465a5b5026f173c7f9a8e2d9efb4ee3bf5785`. The build ID is `fe47269907ad7c4e0b60`.

## Panel preservation and keys

- Input panel: 2,383 rows.
- Tennessee strict additions: 19 rows—15 House and 4 Senate, all from 1998.
- Extended panel: 2,402 rows.
- The extended panel and Tennessee candidate table have zero duplicate `state, year, chamber, district` keys.
- A one-to-one merge recovers all 2,383 prior rows. Every one of the 54 shared non-key columns is value-identical, including null placement; no prior observation is overwritten.
- Temporary CSV outputs byte-match the release candidate. The temporary manifest differs from the production manifest only in its recorded output paths.

## Independently recomputed admission gates

The Tennessee candidate table contains 116 Klarner outcome rows. Recomputed gate counts are:

| Gate | Passing rows |
|---|---:|
| Staging reconciliation | 79 |
| Contested two-party outcome | 43 |
| Finite governor baseline | 116 |
| At least 95% legislative-turnout join coverage | 69 |
| All four gates | 19 |

The independently recomputed conjunction matches `model_eligible` on every row. The 19 admissions are HD-10, 22, 24, 29, 36, 45, 47, 48, 49, 63, 67, 85, 86, 89, and 99, plus SD-7, 9, 25, and 27.

The integration therefore does not admit uncontested outcomes, missing baselines, staging failures, or districts below the declared 95% context-join threshold.

## Allocation and coverage

- The legislative source contains 123 grouped district/precinct mappings with zero turnout. After independently reconstructing the join, none appears in the allocation rows and every retained allocation weight is finite and positive.
- Twenty-five precinct/chamber cells split across multiple districts. For their 50 party audit rows, allocation weights sum to exactly 1.0 and the maximum absolute vote-conservation difference is `9.09e-13` votes.
- Across all 7,138 allocation-audit rows, weights sum to 1.0 and allocated Democratic and Republican votes reproduce observed governor votes within floating-point tolerance.
- Coverage is bounded from `0.1988873435` to `1.0`; no matched legislative turnout exceeds its source turnout.
- Missing or unmatched context is not converted to zero. Rows below the coverage threshold remain `partial_unresolved` and ineligible.

## Provenance and hashes

All seven manifest input hashes independently match the current files:

- validated 2,383-row panel and its manifest;
- Tennessee legislative precinct turnout;
- Tennessee governor precinct context;
- Tennessee reconciliation and staging manifest;
- immutable Klarner archive.

All four recorded output hashes and row counts reproduce. The manifest records the 95% threshold, governor baseline office, prior-panel precedence, and the county-plus-alphanumeric-precinct join definition.

## Caveats

- Approval applies only to the 19 appended strict rows and experimental model work. It does not promote the Tennessee OCR staging or governor context to a canonical warehouse source.
- The upstream Tennessee governor extraction remains incomplete, and many otherwise plausible contests fail staging, contest, or coverage gates. This is expected conservative exclusion, not evidence of complete statewide coverage.
- OCR-normalized precinct labels are used only within the documented county and chamber allocation context; they are not stable cross-cycle precinct identities.

Within those limits, the Tennessee extension is fit for the next experimental Southern model tournament.
