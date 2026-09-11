# Arkansas 1994-1998 precinct staging

## Sources and scope

This experimental staging normalizes the official Arkansas Secretary of State
general-election workbooks already registered under
`data/raw/southern_sos_elections/AR/`. It reads the 1994 and 1996 XLS files and
the single XLS member of the original 1998 ZIP without modifying or extracting
the raw sources.

The output retains candidate-level precinct observations for state House,
state Senate, president, U.S. Senate, governor, and U.S. House. Workbook grand
total and summary sheets, totals columns, and non-candidate report blocks are
excluded. Exact repeated report rows are retained once and their source
multiplicity is exposed.

## Legislative release gate

Parsed Democratic and Republican district totals are compared with the
independent Klarner candidate-result archive. Klarner remains the candidate and
outcome authority; SOS precinct returns are potential allocation evidence.
A district is experimentally eligible only when both sources are present and
the combined absolute major-party vote discrepancy is either zero or no more
than the larger of ten votes and one percent of Klarner major-party votes.
Material mismatches and one-source-only rows remain in the reconciliation audit
but are not eligible.

## Outputs

- `arkansas_pre2000_precinct_observations.csv`
- `arkansas_pre2000_district_candidates.csv`
- `arkansas_pre2000_coverage.csv`
- `arkansas_pre2000_legislative_reconciliation.csv`
- `arkansas_pre2000_manifest.json`

These are staging outputs, not canonical warehouse tables or production model
inputs. Admission to the combined Southern panel requires independent review of
parsing, coverage, context allocation, and reconciliation gates.
