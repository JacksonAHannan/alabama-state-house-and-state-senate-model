# Task contract: WAREHOUSE-CATALOG-CLEANUP-001

- Accountable role: `warehouse_integrator`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the obsolete preliminary-CMO publication entry in the canonical data catalog with the current v4 candidate export.
- Acceptance checks: Catalog generator and generated catalog agree; the active publication asset points to `docs/data/cmo_v4_candidates.csv` and its current builder; no deleted preliminary publication path remains active.
- Read scope: Current data catalog, catalog builder, and v4 publication outputs.
- Write scope: `scripts/build_data_catalog.py`; `project_docs/data_catalog.csv`; this contract and ledger row.
- Upstream inputs: Approved CMO v4 publication and REPO-CLEANUP-001 review candidate.
- Expected outputs: Updated canonical catalog entry and reproducible catalog build.
- Warehouse mode: warehouse writer for catalog metadata only; no database schema or table changes.
