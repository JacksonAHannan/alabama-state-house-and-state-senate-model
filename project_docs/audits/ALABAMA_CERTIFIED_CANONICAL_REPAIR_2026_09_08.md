# Alabama certified-canvass authority: warehouse integration (2026-09-08)

Status: three guarded warehouse writes committed and verified; no model, public
artifact or checklist status is certified by this record. Task record:
`../coordination/SOUTHERN-WAR-COMPLETION-20260908.md`.

## Authority decision

The certified State Canvassing Board canvass is the authoritative source for
Alabama 2018 and 2022 general-election legislative contest totals. The Alabama
canonical candidate route remains the Southern outcome source family; each
canonical candidate is bridged to exactly one certified cell with explicit name
evidence, disagreeing canonical totals are corrected to the certified value with
before-images, and the Southern preparation producer derives the scalar source
file and third-party total from the bridged certified set. Contract text:
`../DATA_CONTRACTS.md`, "Alabama certified canvass authority and canonical bridge".

## Step 1: 2018 certified cohort registered and appended

- Run `RUN-DD7FF8C9ACBE4EAAA026AD1046693CA9` (`alabama_2018_certified_source_append`),
  expected prior run `RUN-3723F54646824B1682D8543BE39C7EC5`; backup
  `data/processed/elections/backups/pre-al2018-source-load-2026-09-08.sqlite`
  (5,786,759,168 bytes, quick_check ok, latest run in backup = prior run).
- Registered `SRC-A3632F0E8738FDFB544D` (canvass SHA-256
  `a83be9be26ac195989bf94ad5097e4269f516674f645373526a9d6621f310044`); appended 140
  observation sets, 352 certified candidate/write-in rows and one reconciliation QA
  row; source family `alabama_sos_certified_canvass`, validation `review`; 30
  precinct-subtotal review rows retained with row-level `review` status. Row-level
  evidence pin `ALABAMA_2018_CERTIFIED_SOURCE_ROWS.json` (SHA-256
  `14f62727cbe9658c42c6c6bd223c15e507a9d5cf9c6046e506b67bd53ab74664`).
- Replay without `--apply` reports `unchanged`. Repair QA row
  `AL18LOAD-FBC560B5DC5167599755A352` (`source_loaded_pending_adoption`).

## Step 2: canonical/certified bridge and total corrections

- Run `RUN-4C2EF8D12CC442D99A516E0D393DE157` (`alabama_certified_canonical_total_repair`),
  expected prior run `RUN-DD7FF8C9ACBE4EAAA026AD1046693CA9`; backup
  `pre-alabama-certified-totals-2026-09-08.sqlite` (5,798,825,984 bytes, quick_check
  ok). Application report copied to `ALABAMA_CERTIFIED_CANONICAL_REPAIR_2026_09_08.json`.
- Schema version 27; `bridge_alabama_canonical_candidate_certified_result` holds 377
  approved rows: 203 `surname_unique_race_party` (2018 canvass surnames), 173
  `decoded_ballot_code_exact_normalized_name` (2022 README decoder), and 1
  `precinct_workbook_exact_name_alignment_canvass_label_disagrees` (2018 HD83, where
  the canvass prints "Gray II" for the Republican and the same provider's precinct
  workbook names Michael J Holden II at exact contest/party grain).
- 21 canonical totals corrected to certified (11 in 2018, 10 in 2022; all canonical
  values equalled incomplete precinct subtotals); 23 materialized rows in
  `canonical_southern_legislative_candidate_election` updated (votes and shares) in
  16 contests; no winner flag changed; materialized rows equal the live view;
  readiness states unchanged; foreign keys clean. QA row
  `WQA-ALCERT-RUN-4C2EF8D12CC442D99A516E0D393DE157` carries the before-images.
- Replay without `--apply` reports `unchanged` with 0 pending corrections.

## Step 3: outcome-mart rebuild

- Backup `pre-southern-outcome-rebuild-2026-09-08.sqlite` (5,799,325,696 bytes,
  quick_check ok; `.backup.json` records counts 4,582 / 8,085 / 140). Run
  `RUN-92AB8DE353AC47D6AECE3D7767C29FCD` (`southern_war_preparation_no_finance`)
  validated with 4,582 outcomes, 4,280 strict, 302 research-only, 116 slices, 0
  missing context/baseline/incumbency, 140 roster rows.
- Parity audit (`scripts/audit_southern_outcome_rebuild_parity.py`): context and
  roster identical apart from the run ID; 97 outcome rows changed, all Alabama;
  changed fields `source_file_id` (97, now `SRC-A3632F0E8738FDFB544D` for 2018 and
  `SRC-DD940F20743C33261CC2` for 2022), `third_party_votes` (97, certified non-major
  named and write-in totals, 9,861 votes in total) and
  `source_quality_flags_json` (97, bridge provenance); `dem_votes`/`rep_votes`/
  `two_party_votes`/`legislative_dem_margin` changed only for the seven corrected
  strict races: 2018 HD81, HD83, SD14, SD27 and 2022 HD32, HD68, HD92.
- Readiness inventory `SOUTHERN_RELEASE_READINESS_2026_09_08.json`: 4,582 = 4,280
  strict + 302 excluded, 0 missing scalar source-file IDs, one outcome and context
  run.

## Downstream state

- Stale, recorded, not rebuilt here: `data/processed/war/race_candidate_results.csv`
  and its producer `build_war_database.py` (pre-certified 2018/2022 totals;
  `build_candidate_identity.py` would regenerate canonical candidates from them, so
  the Southern producer now fails on disagreement); identity alias evidence tables
  copying `canonical_votes`; CMO compatibility exports; Alabama WAR, historical WAR
  and forecast bundles consuming canonical 2018/2022 totals.
- Rebuilt after this record: Southern WAR v3 (`WAR-POST2016-V3-4AF79A70EAA8F39EBD49`)
  and its dependants; see the completion task record for the sequence.
