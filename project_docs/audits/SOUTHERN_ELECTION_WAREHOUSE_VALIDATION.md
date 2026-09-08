# Official Southern election warehouse validation

## Validated run

- Build run: `RUN-35590D9B96854406956CCF248F60CB6A`
- Code commit recorded by the run: `569b019fecb7786a1c824fcc81490202e39cc4bc`
- Contract version: 1
- Warehouse schema version: 10
- Candidate-party-contest rows: 15,834
- Registered acquired artifacts: 4,013
- Parsed and reconciled source files: 1,196
- Rejected parsed files: 0
- Parsed vote reconciliation failures: 0
- States with newly normalized official results: 9

The SQLite integrity check returned `ok`, `PRAGMA foreign_key_check` returned
zero rows, all 15,834 candidate-election identifiers were unique, all vote
values were nonnegative and observed, all vote shares were within `[0, 1]`,
and every candidate result had at least one source-file bridge.
All validated legislative rows also had a numeric district within the state's
chamber-specific range; zero rows remained in the district review gate.

`scripts/validate_agent_workflow.py` passed. The focused acquisition, staging,
and warehouse suite passed 28 tests, and the dedicated new adapter suite passed
9 tests. The repository-wide suite completed with 558 passes and one unrelated,
repeatable historical-finance fixture failure: the current checked-in finance
inputs produce 353 complete races while
`test_canonical_historical_finance.py` still expects 352. Neither the failing
test nor its finance inputs are read or written by this pipeline.

## Loaded coverage

| State | Cycles | Candidate results | Status |
|---|---:|---:|---|
| AR | 1994-2000, 2010-2016 | 942 | parsed official workbooks, ZIP, and Tally JSON |
| FL | 2012-2016 | 1,637 | parsed official precinct ZIPs |
| KY | 2000-2008 | 945 | parsed official statewide-by-office summaries |
| LA | 1995-2023 | 2,458 | parsed official first-round and runoff contest CSVs |
| NC | 2000-2016 | 4,308 | parsed nine legacy/modern precinct-layout cycles |
| OK | 2012-2016 | 416 | parsed official precinct CSV ZIPs |
| SC | 2008-2016 | 1,961 | composed official county totals |
| TN | 2008-2016 | 1,627 | parsed official precinct workbooks |
| VA | 2005-2015 | 1,540 | parsed official statewide precinct CSVs |

Alabama remains in `fact_candidate_election`; it was not duplicated. Texas
remains in its companion repository. Georgia and Missouri remain acquisition
gaps. Mississippi's downloaded county recaps remain a PDF extraction review
queue. Other registered-but-unparsed cycles remain visible in
`qa_southern_election_coverage` and are not described as complete.

## Known limitations

- The source acquisition manifests do not establish enacted district-plan
  vintages. Legislative rows therefore use a state/cycle/chamber
  `reported-unknown-vintage` identifier and must not be joined as if the plan
  were adjudicated.
- South Carolina's fixed-width detail exports do not include party labels;
  those party families remain `unknown`.
- Observed candidate counts and vote shares describe the available provider
  rows. A single candidate does not become an `uncontested` classification.
- Louisiana regular runoffs use canonical stage `other` with the provider's
  original `runoff` label preserved because the shared enum has no regular
  general-runoff value. First-round and runoff votes are never added.
- Licensing/reuse terms were absent from the acquisition manifest. Each source
  is registered as an official public record with terms review required.

## Reproduction

```powershell
python scripts/load_southern_election_warehouse.py
python scripts/build_data_catalog.py
python -m pytest scripts/tests/test_southern_election_warehouse.py -q
```
