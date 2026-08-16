# VoteHub-linked demographic crosstab pipeline

VoteHub is the poll catalog and provenance key. Its public API provides
toplines but not demographic tables, so source documents remain authoritative
for every extracted cell.

## Run order

```powershell
python scripts/build_votehub_crosstab_source_inventory.py --from-date 2026-01-01 --download
python scripts/build_votehub_demographic_polling.py
```

The inventory writes a complete manifest, a status summary, and a prioritized
document-review queue under `data/processed/polling/`. Archived source files are
content-hashed under `data/raw/polling/votehub_crosstabs/`.

Enter verified cells in
`data/raw/polling/votehub_crosstabs_reviewed.csv`. `dimension` must be one of
`overall`, `race`, `education`, `race_education`, `age`, or `gender`; `group`
contains the normalized category. Percentages remain on the poll's published
denominator, and `cell_base` should be populated whenever reported. Record the
page/table and extraction method and set `reviewed=true` only after comparing
the entry with the archived source.

The pooling stage rejects unknown VoteHub IDs, invalid percentages, duplicate
cells, unsupported dimensions, and unreviewed rows. It excludes partisan and
internal polls; keeps the latest observation from each pollster for each cell
in a 42-day window; and weights by recency, sample population, and the square
root of a reported cell base. Outputs include both the normalized long data and
a cell-by-cell coverage report. A pooled cell should not replace the consistent
YouGov tracker unless its pollster count and category definitions are adequate.

## Current inventory

The expanded VoteHub-era crawl archived 339 poll documents. Pollster-specific
adapters currently recover 114 cells from 19 YouGov polls and 10 cells from one
Focaldata poll. The current pooled overall, White, Black, and Hispanic cells
therefore include two pollsters. Education definitions remain source-specific
and are not pooled across incompatible degree bins. Some pollster sites block
automated requests; these remain explicit `source_request_error` rows.

The release environment applies the supplied Nate Silver ratings independently
of that broad research pool. Normalized exact-name matches and one explicit
Marist College/University alias identify B+ or better sources; combined firms do
not inherit a constituent firm's grade. Supported adapters recover 41 cells
from TIPP, PPP, and three Marist releases. The current quality-gated topline
uses eight eligible pollsters in a 60-day window. Race shapes pool the latest
TIPP, PPP, and Marist cells relative to each poll's own topline; education uses
Marist's compatible college/noncollege split. YouGov and Focaldata remain in
the research archive but are excluded from the selected current environment.
