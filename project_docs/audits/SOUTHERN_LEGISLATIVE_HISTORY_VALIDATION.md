# Southern legislative history warehouse validation

## Validated run

- Build run: `RUN-F8FBA87A48244C2B83960ACE5EAFFBBD`
- Code commit recorded by the run: `569b019fecb7786a1c824fcc81490202e39cc4bc`
- Contract version: 2
- Warehouse schema version: 13
- Provider-specific contest observation sets: 52,231
- Provider-specific candidate results: 82,361
- Authority-selected candidate results: 79,812
- Final-stage regular-cycle candidate results: 75,059
- States: 14
- Canonical year extent: 1968-2024
- Scheduled 2018-2024 state-cycle-chambers represented: 95 of 95

The 95-row schedule begins in 2018. The older 96-row post-2016 WAR audit also
included Virginia's 2017 House election, so the two denominators intentionally
differ by one.

## Integrity and reconciliation

- SQLite integrity check: `ok`
- Foreign-key violations: 0
- Provider candidate-key duplicates: 0
- Canonical candidate-key duplicates: 0
- Final contest-key duplicates: 0
- Louisiana runoffs without an observed first round, 1995-2024: 0
- Vote reconciliation review/failures: 0
- Exact source/member reconciliations: 46
- Source/member combinations with no legislative rows: 4
- Focused acquisition, official/comprehensive warehouse, and WAR-stage tests: 28 passed

The repository-wide suite completed with 571 passes and one unrelated finance
failure. `test_canonical_historical_finance.py` still expects 352 complete
races while the current finance inputs produce 353. This pipeline neither
reads nor writes those finance inputs or implementations.

The schema-version-10 official compatibility view remains unchanged at 15,834
candidate results. The comprehensive view selects a whole source observation
set per contest; it never adds votes from overlapping providers.

## Canonical state extents

| State | First | Last | Distinct years | Candidate results |
|---|---:|---:|---:|---:|
| AL | 1970 | 2022 | 15 | 2,917 |
| AR | 1968 | 2024 | 29 | 4,093 |
| FL | 1968 | 2024 | 29 | 6,596 |
| GA | 1968 | 2024 | 29 | 8,081 |
| KY | 1969 | 2024 | 29 | 5,048 |
| LA | 1968 | 2023 | 16 | 4,480 |
| MO | 1968 | 2024 | 29 | 8,581 |
| MS | 1971 | 2023 | 16 | 3,432 |
| NC | 1970 | 2024 | 28 | 6,393 |
| OK | 1968 | 2024 | 29 | 5,334 |
| SC | 1968 | 2024 | 28 | 6,633 |
| TN | 1968 | 2024 | 29 | 5,588 |
| TX | 1968 | 2024 | 29 | 7,181 |
| VA | 1969 | 2023 | 30 | 5,455 |

Distinct years include observed special elections when they appear outside a
state's regular schedule.

## Limitations

- MEDSL 2024 files are uneven and often contested-only. All scheduled
  state/chamber combinations are represented, but observed district counts are
  not asserted to be complete seat universes.
- Louisiana seat-roster counts are not the outcome-completeness gate. Its
  official files retain both regular stages; the final-stage interface uses the
  runoff only where present and otherwise uses the first round. For 2019 and
  2023 this yields 168 observed final contests, including 41 exactly-one-D/R
  contests eligible for the current WAR outcome rule. Unreported uncontested
  seats are not converted to missing competitions or zero-vote opponents.
- Klarner null vote fields, frequently associated with unopposed candidates,
  remain unknown. The `dontuse` model-quality flag is preserved in source JSON
  and does not erase a structurally valid election observation.
- Historical district plan vintages have not been adjudicated. Records use a
  state/cycle/chamber `reported-unknown-vintage` identifier and must not be
  joined to modern district geometry without an explicit crosswalk.
- National MEDSL archive retrieval times are recorded as filesystem-mtime
  proxies because the original download manifests were not retained. The
  manifest labels this limitation and records immutable local hashes.

## Reproduction

```powershell
python scripts/load_southern_election_warehouse.py
python scripts/load_southern_legislative_history_warehouse.py
python -m pytest scripts/tests/test_southern_legislative_history_warehouse.py scripts/tests/test_southern_election_warehouse.py -q
```
