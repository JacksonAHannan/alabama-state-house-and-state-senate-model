# Southern WAR preparation without finance: validation

## Validated run

- Build run: `RUN-9070853C1F2146768D326B69A8C6395C`
- Code version recorded by run: `569b019fecb7786a1c824fcc81490202e39cc4bc`
- Warehouse schema: 15
- Finance included: no
- Foreign-key violations: 0

## Result

The run materialized 4,583 model-valid D-v-R outcomes from 2016 through 2024.
Of these, 2,329 pass the strict no-finance training gates and another 738 pass
the research gates. The unresolved set is 1,390 rows without a baseline and
126 rows without any matching context. No row reached a missing-incumbency gate
after the earlier gates were applied.

| State | Outcomes | Strict | Research | Missing baseline | Missing context |
|---|---:|---:|---:|---:|---:|
| AL | 97 | 97 | 0 | 0 | 0 |
| AR | 223 | 93 | 102 | 28 | 0 |
| FL | 489 | 203 | 0 | 285 | 1 |
| GA | 474 | 248 | 225 | 1 | 0 |
| KY | 344 | 168 | 0 | 176 | 0 |
| LA | 41 | 0 | 41 | 0 | 0 |
| MO | 502 | 295 | 124 | 83 | 0 |
| MS | 65 | 39 | 0 | 1 | 25 |
| NC | 663 | 323 | 132 | 208 | 0 |
| OK | 296 | 139 | 0 | 157 | 0 |
| SC | 285 | 125 | 0 | 159 | 1 |
| TN | 302 | 132 | 114 | 56 | 0 |
| TX | 467 | 467 | 0 | 0 | 0 |
| VA | 335 | 0 | 0 | 236 | 99 |

Louisiana contributes 41 correctly staged contests: districts resolved in
October use the first round, and only districts reaching November use the
runoff. These remain research-grade because their current incumbency evidence
is classified as experimental. The 126 missing-context outcomes comprise
Mississippi 2023 (25), Virginia 2023 (99), Florida 2020 Senate (1), and South
Carolina 2018 Senate (1).

## Source-selection checks

- 4,539 outcomes use the canonical model-eligible observation.
- 43 use a lower-authority, model-eligible complete observation.
- 1 uses the explicitly validated Texas official companion-panel fallback
  (2024 House District 56), which is absent from the central regular-stage key.
- Virginia 2019 Senate District 33 is excluded because it contains two
  Republican candidates and therefore fails the exact-one-D/R contract.
- Candidate rows from different providers are never added together.

## Alabama 2026 incumbency review

The workbook supplies 140 populated Alabama 2026 seats: 105 House and 35
Senate. It reports 122 incumbents running and 18 open seats. There is one
disagreement with the earlier forecast roster: Senate District 9. The workbook
and certified candidate roster support incumbent Republican Wes Kitchens as
running, while the older roster marks the seat open. The normalized roster
records this as `workbook_supported_correction` with `review_status=proposed`;
human approval remains required.

The workbook does not contain populated 2016-2024 or other-state incumbent
records. Rows in `Election_Cycles`, `Sources`, and `Extraction_Log` are source
maps or pending-work notes and were not promoted to evidence.

## Automated checks

The focused preparation, history, and WAR-panel test set passed 14 tests. The
full repository suite completed with 580 passed and 1 failed. The sole failure
is the pre-existing assertion in
`scripts/tests/test_canonical_historical_finance.py`: the fixture expects 352
canonical-finance-complete races while the current unrelated finance build
produces 353. No preparation, Southern history, or WAR-panel test failed.
