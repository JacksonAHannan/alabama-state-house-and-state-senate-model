# Southern finance warehouse

## Scope

`scripts/load_southern_finance_warehouse.py` loads the canonical 2016-2024
Southern candidate-cycle finance panel into the central SQLite warehouse. The
load depends on the final-stage Southern legislative candidate history and
does not change finance amounts or convert missing observations to zero.

## Layers and join contract

- `source_southern_finance_file` registers the acquisition manifests, the
  canonical input, the incumbency workbook, the reviewed finance-identity
  adjudication file, and supplemental upstreams.
- `source_southern_candidate_cycle_finance` preserves every candidate-cycle
  input row and source observation status.
- `source_southern_incumbency_evidence` preserves populated workbook rows,
  provider-reported flags, source-backed web roster observations, prior-winner
  continuity, and approved adjudications. Absence is never negative evidence.
- `bridge_southern_finance_candidate_identity` requires exact state, cycle,
  chamber, district, and party scope, followed by an exact or conservative
  fuzzy name match. Its expected cardinality is `1:0..1`; duplicates fail.
- `mart_southern_candidate_cycle_finance` includes accepted identity links,
  including accepted candidates whose finance amount remains unknown.
- `mart_southern_race_finance` publishes the smoothed D/R log fundraising
  ratio only when both identities and finance observations are complete.

## Current validated load

Build `RUN-2805DFEADF4E46C9AE1902ADCA9271D2` loaded 12,559 source candidate
rows, accepted 12,527 identity links, and linked 9,791 usable finance totals.
The race mart contains 7,976 district-cycle rows and 3,436 finance-complete D/R
races. All 18,179 manifest artifacts and two supplemental upstreams have
resolved lineage. Scope, observed-value, complete-race, and foreign-key checks
reported zero violations.

The incumbency workbook contributes 140 Alabama 2026 records. The generated
2016-2024 roster contributes 4,271 additional evidence rows, alongside 5,356
positive provider-reported flags. Its README and
extraction log mark historical 2016-2025 population as pending, so blank tabs
are not used as evidence. Instead, 5,356 positive provider-reported incumbent
flags already preserved in the election warehouse support scoped identity
matching. Absence of such a flag is never treated as non-incumbency.

Georgia transaction exports now supply 1,385 usable candidate-cycle totals.
The required 2015 window is present, and 2024 uses the versioned refreshed
Record Search collection while retaining the defective first response set as
raw evidence. Legacy candidate and official committee-name aliases are grouped
by stable filer ID before reciprocal cycle-scoped identity resolution. This
completes 360 of Georgia's 474 modeled D/R races. North Carolina exact official committee
queries and complete annual exports supply 1,472 usable totals, including
explicit zeros only after an
accepted committee query over the complete window returns no monetary receipt
records. The adapter searches both chamber exports because the portal can
classify historical transactions under a committee's current office. Its v3
refresh uses final election-warehouse names, excludes explicit nonlegislative
committees, and permits surname-only identity only for a unique cycle surname
whose committee name reduces exactly to that surname. Reviewed legal-name and
nickname decisions are restricted to exact election scope and retain their
source evidence. This leaves only three candidate-source unknowns and completes
661 of 663 D/R races.

Florida supplies 1,158 usable candidate-cycle totals. Its adapter reads
only non-truncated leaves of the official partitioned detail export, separates
cash/check/money-order/refund/interest from carryover, in-kind, and loans, and
promotes a value only when all-candidacy detail reconciles to the official
candidate summary within two cents. Net-negative receipt windows and malformed
provider codes remain review states. Current-normalizer name signatures replace
serialized historical audit keys without changing accepted source evidence.
This closes 449 of Florida's 489 modeled
D/R races.

Kentucky supplies 820 usable candidate-election totals and completes 303 of
344 modeled D/R races after scoped official legal-name/nickname adjudications.
Louisiana supplies 95 of 100 candidate totals and completes 38 of 41 modeled
D/R races; the Lawrence "Larry" Frieman bridge is tied to official Ethics filer
4430. Oklahoma's exhaustive Guardian extracts supply 811 of 830 candidate
totals and complete 278 of 296 modeled D/R races after unique reciprocal aliases
are aggregated by provider transaction ID. South Carolina supplies 865 of 941
candidate totals and completes 222 of 284 modeled D/R races; strictly contained
interim report periods are excluded while partial overlaps remain review items.

Tennessee supplies 831 usable candidate-cycle totals from official
candidate-report summaries; the server-batched statewide transaction export is
retained only as reconciliation evidence. Texas supplies 1,228 totals after
applying TEC's documented blank-when-zero numeric contract and exact-scope
reviewed filer identities. Alabama supplies 374 of 377 candidate totals after
retaining immutable FCPA search and calendar-year summary evidence for duplicate
historical committee records.

Virginia's candidate-search and committee-report collections were refreshed as
new immutable versions after the 2023 election rows entered the candidate
universe. Conservative surname, given-name, and exact first/last discovery
accepts 706 of 775 modeled candidates and selects 9,311 report XML files. The canonical panel
contains 657 usable candidate totals and the WAR universe has 237
finance-complete D/R outcomes across 2017-2023. Multiple committees,
substantive report overlaps, and unsafe identities remain explicit review or
unknown states.

## Reproduction

```powershell
python scripts/acquire_southern_candidate_finance_summaries.py --states AL TN --completion-only
python scripts/build_southern_candidate_cycle_finance.py
python scripts/load_southern_legislative_history_warehouse.py
python scripts/load_southern_finance_warehouse.py
python scripts/validate_southern_finance_release.py
python scripts/export_southern_finance_model_features.py
python scripts/load_southern_war_preparation_warehouse.py
python scripts/audit_southern_war_2016_2024.py
python -m pytest scripts/tests/test_southern_finance_warehouse.py -q
```

Generated compatibility and audit outputs are:

- `data/processed/finance/southern_warehouse_candidate_finance.csv`
- `data/processed/finance/southern_warehouse_race_finance.csv`
- `data/processed/source_audits/southern_finance_warehouse_coverage.csv`
- `data/processed/source_audits/southern_finance_warehouse_identity_review.csv`
- `data/processed/source_audits/southern_finance_warehouse_manifest.json`
- `data/processed/source_audits/southern_finance_release_validation.json`
- `data/processed/finance/southern_race_finance_model_features.csv`
- `data/processed/finance/southern_race_finance_model_features_manifest.json`

The model-facing export preserves all race keys and carries a missingness flag,
but fundraising amounts and the D/R log ratio remain null unless both candidate
totals are observed and both identities are accepted. It does not alter the
outcome-only WAR definition.
