# Task contract: SOURCE-OPENELECTIONS-HISTORICAL-001

- Accountable role: `source_provenance`
- Owner: `/root`
- Status: `complete`
- Objective: Acquire and register the verified OpenElections general-election precinct files that fill fourteen Southern state-cycle gaps from 2000 through 2016.
- Non-goals: No parsing, canonical warehouse writes, model changes, or replacement of official sources.
- Upstream snapshot: Pinned OpenElections repository commits audited 2026-08-22.
- Read scope: Local OpenElections repositories for tree inspection; `data/processed/source_audits/southern_sos_precinct_inventory.csv`.
- Write scope: `scripts/acquire_openelections_historical_gaps.py`; `scripts/tests/test_openelections_historical_acquisition.py`; `data/raw/openelections_historical_gaps/`; `data/processed/source_audits/openelections_historical_gap_manifest.csv`; `project_docs/sources/OPENELECTIONS_HISTORICAL_GAPS.md`; `project_docs/coordination/SOURCE-OPENELECTIONS-HISTORICAL-001.md`
- Warehouse mode: `read-only`
- Inputs: Pinned OpenElections AR, GA, MO, and SC repository commits and verified general-election members.
- Outputs: Immutable source files and a hash/provenance manifest for AR 2008, GA 2012/2014/2016, MO 2000–2016 even cycles, and SC 2006.
- Acceptance checks: Downloads use commit-pinned raw URLs; existing unequal raw files are never overwritten; every manifest hash and byte count matches disk; only general-election files are admitted; expected fourteen state-cycle combinations are present; focused tests pass.
- Handoff recipient: `elections_geography`
- Known risks: Georgia 2014 is labeled unofficial by OpenElections; OpenElections is secondary and never outranks official returns.
