# Raw data

Raw source material is stored here. Some provenance-critical sources are
tracked, while very large, reproducible, licensed, or local-only downloads may
remain untracked. Do not add or remove tracking for an entire source tree
without checking its license, size, and existing Git history.

Current top-level categories include:

- `alabama_elections_and_geography/` — SOS returns, precinct files, validation pages, and map files
- `finance/alabama/` — Alabama campaign-finance and FollowTheMoney downloads
- `candidates/` — source candidate rosters
- `polling/` — polling, crosstab, and pollster-quality source files
- `ideology/` — Shor–McCarty and related ideology sources
- `legiscan/` and `alabama_legislature/` — legislative data and bill text
- `reference_pages/` — downloaded third-party pages retained for design or methodology reference

Processed, normalized, or modeled outputs belong in `data/processed/`, not here.
Scripts should refer to these paths through `ROOT / "data" / "raw" / ...` and
must not rely on a source directory at the repository root.
