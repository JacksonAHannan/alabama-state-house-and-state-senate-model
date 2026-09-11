# 2026 finance and incumbency repair

## Outcome

The 2026 finance input now represents non-overlapping 2025 and 2026 cycle
components, and the incumbency input now resolves 2022 winners to candidate
names before matching them to the certified 2026 roster.

## Defects repaired

- The prior finance reconciliation replaced 2025 committee totals with the
  August 14, 2026 state export. The corrected total is the sum of 2025 FCPA
  activity and 2026 state-reported activity.
- The prior incumbency builder compared current candidate names with encoded
  canonical result labels. It recognized only nine Senate incumbents and
  incorrectly treated Sam Givhan as a nonincumbent in SD-7.
- The FCPA committee inventory did not include every 2026 nominee. The rebuild
  uses the final 2026 roster, robust name scoring, reviewed aliases, and active
  principal campaign committees.

## Key validation cases

| Candidate | Corrected finance | Corrected incumbency |
|---|---:|---|
| Sam Givhan, SD-7 R | $370,509.84 | Incumbent |
| Jared Sluss, SD-7 D | $19,146.16 | Nonincumbent |
| Pam Howard, HD-40 D | $5,483.71 | Nonincumbent |
| Will Barfoot, SD-25 R | $757,875.50 | Incumbent |
| Billy Beasley, SD-28 D | $226,600.00 | Incumbent |

The rebuilt roster contains 188 finance rows. Three candidates remain without
an observed usable total: Kinsley Hammons, Charlie Watts, and Thayer Bear
Havard Spencer. Those records remain missing and are not converted to zero.

The incumbency output contains 91 House incumbents and 30 Senate incumbents.
No race contains more than one incumbent.

## Commands and checks

```powershell
python scripts/build_fcpa_candidate_committee_finance.py
python scripts/reconcile_2026_candidate_finance.py
python scripts/build_2026_incumbency.py
python -m pytest scripts/tests/test_2026_candidate_finance_reconciliation.py scripts/tests/test_2026_incumbency.py -q
```

Result: `7 passed`.

## Handoff

- Outcome: `accepted candidate`
- Upstream snapshot used: Official 2025 FCPA committee summaries, official
  August 14, 2026 state summary, certified 2026 roster, canonical 2022 winners,
  and reviewed candidate identity crosswalk.
- Changed source files: `scripts/build_fcpa_candidate_committee_finance.py`,
  `scripts/reconcile_2026_candidate_finance.py`,
  `scripts/build_2026_incumbency.py`, and their focused tests.
- Generated outputs: `data/processed/war/fcpa_candidate_committee_*`,
  `data/processed/war/fcpa_candidate_cycle_finance.csv`,
  `data/processed/finance/2026_candidate_finance_*`, and
  `data/processed/war/2026_*incumbency*.csv`.
- Manual decisions: Existing reviewed aliases and incumbency overrides were
  retained; no raw source evidence was changed.
- Assumptions and limitations: The 2025 FCPA snapshot and 2026 state export are
  treated as disjoint annual components. The three unresolved candidates remain
  explicitly missing.
- Warehouse changes requested: None; these are model staging inputs.
- Downstream invalidation: The post-2016 polling-CMO forecast and promoted 2026
  headline artifacts must be rebuilt.
- Reviewer: Focused automated checks passed; public release still requires an
  independent validation task.
- Next action: Rebuild and validate the 2026 forecast from these corrected
  inputs.
