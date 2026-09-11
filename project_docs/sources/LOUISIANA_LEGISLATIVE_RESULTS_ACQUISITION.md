# Louisiana legislative results acquisition

## Source and scope

The Louisiana Secretary of State graphical-results application exposes a
structured race index and a precinct CSV for each listed contest. The
acquisition covers both stages of every regular state legislative cycle from
1995 through 2023:

- first round: October election;
- runoff: November election for contests not decided in the first round.

The source endpoint pattern is:

```text
https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob={YYYYMMDD}/ElectionRaces.htm
https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob={YYYYMMDD}/csv/ByPrecinct_{race_id}.csv
```

## Preserved evidence

Raw evidence remains under `data/raw/southern_sos_elections/LA/{year}/`.
Each election-date race index is named `ElectionRaces_{YYYYMMDD}.htm`; each
contest is retained as `ByPrecinct_{race_id}.csv`. Existing raw files were
validated byte-for-byte rather than overwritten.

The 2026-08-30 acquisition produced:

- 16 race indexes;
- 913 legislative contest files;
- 929 distinct SHA-256 hashes;
- 5,549,776 downloaded bytes;
- zero unresolved or failed downloads.

The files contain office/district, parish, ward, precinct, candidate, party,
and vote-count information. Source dates and stages are registered in
`data/processed/source_audits/louisiana_legislative_results_manifest.csv`.

## Interpretation rule

Louisiana uses an open-primary system. A final district result must therefore
use the runoff when the district appears in November and otherwise use the
first-round result. The two stages must never be added together. First-round
candidate observations remain available for research even when a runoff is
the final result.

## Reproduction and validation

```powershell
python scripts/acquire_southern_sos_precinct_results.py --louisiana-legislative-only
python -m pytest scripts/tests/test_southern_sos_acquisition.py -q
```

The downloader is immutable: an existing path with different bytes raises an
error rather than replacing the original source.
