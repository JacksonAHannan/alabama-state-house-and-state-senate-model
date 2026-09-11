# 2026 candidate-finance zero audit

## Result

The prior FCPA live-summary build classified 36 candidates as
`committee_found_no_cycle_activity` and omitted another six D/R roster
candidates.  Reconciliation against the official Alabama state House and
Senate committee-summary exports downloaded on August 14, 2026 found that the
live-summary zeros were overwhelmingly false.

| Prior condition | Candidates | Resolution |
|---|---:|---|
| Live-summary zero | 36 | 33 recovered with positive fundraising; 3 remain absent from the state export |
| No candidate-cycle row | 6 | 5 recovered with positive fundraising; 1 (Bruce Sparkman) has an observed record with noncash activity only |
| **Total audited** | **42** | **39 matched to official state records** |

The roster-complete result now has:

- 188 D/R candidates;
- 185 candidates matched to the official August 14 state summary;
- 184 candidates with positive cash contributions or other receipts;
- one candidate with an observed record and noncash activity only; and
- three candidates whose PCC exists but whose cycle totals remain unverified
  because they are absent from the downloaded summary and the live endpoint
  returned no annual payload.

The three unresolved candidates are Kinsley Hammons (HD-82), Charlie Watts
(HD-99), and Thayer Bear Havard Spencer (SD-23).  They are retained as
`unverified_live_summary_zero`; their absence is not promoted to an observed
zero.

## Cause

Two independent problems created the false-zero classifications:

1. The live committee financial-summary endpoint returned empty annual
   payloads for candidates whose official downloaded state summary contained
   substantial 2026 activity.
2. The existing state-summary matcher did not normalize `LAST, FIRST MIDDLE`
   order or middle-name/initial variants.  It therefore missed straightforward
   identities such as Allison T Montgomery / Allison Taylor Montgomery and
   Scott Ortis / Scott Anthony Ortis.

The replacement reconciliation uses the state export as the cutoff-specific
authority, reorders comma-formatted legal names, treats compatible middle
initials as identity evidence, bridges through the already matched FCPA legal
name, and preserves one explicit reviewed alias for Will Barfoot / Charles
Williamson Barfoot.

## Important recovered records

- Allison T Montgomery: $6,257.20 fundraising and $3,969.71 expenditures.
- Scott Ortis: $846,800.00 fundraising and $738,171.46 expenditures.
- Will Barfoot: $604,323.71 fundraising and $455,617.00 expenditures.
- Phadra Carson Foster: $18,000.00 fundraising and $16,418.13 expenditures.
- Billy Beasley: $111,850.00 fundraising and $10,709.50 expenditures.

`fundraising_total` remains cash contributions plus other receipts.  Beginning
cash, in-kind contributions, expenditures, and ending cash remain separate.

## Outputs and checks

- `data/processed/finance/2026_candidate_finance_reconciled.csv`
- `data/processed/finance/2026_candidate_finance_match_audit.csv`
- `data/manual/finance/2026_candidate_finance_aliases.csv`

Reproduce and test with:

```powershell
python scripts/reconcile_2026_candidate_finance.py
python -m pytest scripts/tests/test_2026_candidate_finance_reconciliation.py -q
```

The forecast should consume the reconciled table rather than treating an empty
live-summary response as an observed zero.
