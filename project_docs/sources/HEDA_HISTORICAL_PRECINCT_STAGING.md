# Historical Election Data Archive precinct staging

The staging pipeline reads the downloaded HEDA Stata archive at
`data/raw/historical_statewide_elections/dataverse_files (4).zip` without
modifying it. HEDA is treated as a secondary normalized source: official state
returns remain authoritative where they overlap.

Run:

```powershell
python scripts/build_heda_historical_precinct_staging.py
```

Outputs under `data/processed/precinct_history/heda/` include a state-year
coverage inventory, gzip-compressed precinct-fragment legislative observations,
nonlegislative context observations, and legislative district aggregates. Florida 2010 is
also exported separately because the archive supplies precinct returns and
explicit state House and Senate district fields for that previously missing
comparison cycle.

HEDA represents precincts split among districts with numbered vote and
district slots (`dv2` with `ld2`, for example). The pipeline preserves each
slot as a separate precinct fragment. It does not assign an entire precinct to
the first district, and it does not convert absent party observations to zero.
Every observation retains the archive SHA-256, ZIP member, source row, and
original vote/district field names.

`build_manifest.json` records source hashes, locally available retrieval
metadata, embedded-documentation provenance, code commit, build ID, authority
and missingness policies, row counts, and output hashes. Unknown license and
exact retrieval metadata remain explicitly unknown. Gzip outputs use a fixed
timestamp for reproducible serialization.

`heda_klarner_district_reconciliation.csv` compares the precinct-fragment sums
with the independent Klarner district contest archive. Differences are retained
as diagnostics rather than resolved by silently preferring either secondary
source.

The outputs are canonical-ready staging data, not canonical warehouse tables.
Before promotion, overlapping cycles should be reconciled against official
returns, identity keys should be integrated by the warehouse writer, and
context-only precinct returns should receive reviewed geographic assignments.
