# Southern SOS precinct-result acquisition

## Scope

This pipeline inventories and downloads official historical election-result
files needed for the 1994–2016 Southern legislative candidate-quality panel.
Alabama and Texas are not reacquired: Alabama is already canonical in this
project, and the relevant Texas files are held in the companion Texas project.

```powershell
python scripts/acquire_southern_sos_precinct_results.py
```

Use `--audit` to inventory links without downloading result files.

## Evidence policy

- Raw responses are immutable. Changed responses receive a hash-suffixed name.
- The manifest records official URL, retrieval time, media type, size, SHA-256,
  and byte-identical duplicates.
- Precinct status requires explicit source labeling or validated precinct
  columns/content. County, district, report-only, registration, and unknown
  files remain separately classified.
- Missing official data are never converted to zero or silently replaced by a
  lower-granularity source.
- `docs/` is publication output and is never an acquisition input.

## Provider-specific recovery

| State | Result |
|---|---|
| Arkansas | Precinct files recovered for 1994, 1996, 1998, 2000, 2010, 2012, 2014, and 2016. The 1994 workbook contains a county-sheet precinct matrix; the latter three use the public full-data JSON behind the current SOS Tally application. Official reports or files of uncertain granularity are retained for 2002, 2004, and 2006. |
| Florida | Official precinct ZIPs downloaded for 2012, 2014, and 2016. The current collection begins in 2012. |
| Georgia | Exact official 2012–2016 precinct/summary ZIP URLs were identified, but Cloudflare rejects automated retrieval. They are listed for browser download. |
| Kentucky | County precinct recaps were recovered for 2002–2016. Older precinct-named files were verified as registration statistics, not vote returns. |
| Louisiana | Per-race SOS `ByPrecinct` CSVs were recovered for every contested state House and Senate race in 1995, 1999, 2003, 2007, 2011, and 2015. The Legislature's official SOS-derived 2000–2011 combined archive is also preserved. |
| Mississippi | All 82 county precinct-recap PDFs were recovered for 2003, 2007, 2011, and 2015. No equivalent public 1995 or 1999 collection was exposed. |
| Missouri | The SOS states that precinct-level general-election files from 1996 onward are available for purchase; they are not public downloads. |
| North Carolina | Official precinct ZIPs were downloaded for 2000–2016. The current bulk collection does not expose 1994–1998. |
| Oklahoma | Official precinct extracts were recovered for 2010–2016. Earlier official publications are linked, but no machine-readable precinct export was exposed. |
| South Carolina | County precinct detail exports were recovered for 2008–2016 from the official election-night archive. Earlier official election reports were preserved, but the retired precinct-return system is not present in the current historical database. |
| Tennessee | Official general-election precinct files were recovered for 1998–2016. No 1994 or 1996 general precinct download was exposed. |
| Virginia | Official bulk precinct CSVs were recovered for 2005–2015. The historical database has 1995–2003 contest CSVs, but inspection shows locality rather than precinct detail. |

## Outputs

- `data/raw/southern_sos_elections/<STATE>/`: immutable official snapshots and downloads.
- `data/processed/source_audits/southern_sos_download_manifest.csv`: provenance and hashes.
- `data/processed/source_audits/southern_sos_precinct_inventory.csv`: cycle-level coverage.
- `data/processed/source_audits/southern_sos_unresolved_links.csv`: failed or ambiguous requests.
- `data/processed/source_audits/southern_sos_manual_access.csv`: exact browser, purchase, archive, and records-request routes for remaining gaps.

## Handoff

The acquisition outputs remain immutable source evidence. The downstream
`scripts/load_southern_election_warehouse.py` pipeline now normalizes the
validated machine-readable formats, aggregates them to candidate-contest
grain, reconciles every parsed file, and loads the central SQLite warehouse.
PDF-only and unavailable formats remain explicit review/gap rows rather than
being treated as completed data.
