# Official Southern election warehouse pipeline

## Purpose

`scripts/load_southern_election_warehouse.py` stages and loads official state
election returns acquired under `data/raw/southern_sos_elections/`. The central
interface is one candidate-party-contest result at the provider's reported
contest geography. Precinct and county components are summed only within the
same election, stage, office, district, candidate, and normalized party family.

```powershell
python scripts/load_southern_election_warehouse.py
python -m pytest scripts/tests/test_southern_election_warehouse.py -q
```

## State adapters

| State | Accepted official format | Current treatment |
|---|---|---|
| AR | Tally JSON; validated 1994-1998 workbook staging | parsed |
| FL | county text files inside statewide ZIPs | parsed |
| KY | official statewide-by-office fixed-width summaries | parsed where available |
| LA | per-contest wide `ByPrecinct` CSVs | parsed; first round and runoff remain separate |
| NC | legacy and modern delimited precinct ZIPs | parsed |
| OK | precinct-result CSV ZIPs | parsed where valid |
| SC | county fixed-width detail ZIPs | county totals composed; absent party labels remain unknown |
| TN | precinct workbooks | parsed where machine-readable |
| VA | statewide precinct CSVs | parsed |
| MS | county PDF recaps | review queue; no unvalidated PDF extraction |
| GA, MO | no acquired official return files | explicit acquisition gap |
| AL | existing canonical warehouse tables | not duplicated |
| TX | companion Texas repository | external, not copied |

## Validation and joins

- Source manifest to local file is `1:1`; a duplicate path is represented once
  and changed bytes retain acquisition evidence.
- A result-to-source join is `m:m` through
  `bridge_southern_candidate_result_source`; this is required for county
  components and is never implemented as an implicit many-to-many join.
- Candidate-result uniqueness is enforced on the stable
  `candidate_election_id`; display variants such as `03` and `3` collapse while
  all originals and source links are retained.
- Every parsed file reconciles the votes accepted by its adapter to the votes
  emitted by that adapter with zero tolerance.
- Vote shares are derived only within the observed candidate set. They do not
  assert complete contest coverage.
- District plan vintage and contest status remain explicitly unknown until an
  authoritative plan or contest-status source is joined and reviewed.

## Outputs

- SQLite: `source_southern_election_file`,
  `source_southern_candidate_election`,
  `bridge_southern_candidate_result_source`,
  `fact_southern_candidate_election`, and two QA tables.
- Compatibility export:
  `data/processed/elections/southern_state_candidate_results.csv.gz`.
- Audits and run manifest under `data/processed/source_audits/`.

This schema-version-10 interface intentionally remains the official-only
compatibility view. Consumers needing all states and years should query
`fact_southern_legislative_candidate_election`, built by
`scripts/load_southern_legislative_history_warehouse.py`.
