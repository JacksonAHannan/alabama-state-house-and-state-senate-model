# Task contract: REPO-CLEANUP-001

- Accountable role: `orchestrator`
- Owner: `/root`
- Status: `complete`
- Objective: Reduce accidental use of obsolete pipelines and publication artifacts by defining canonical entry points, removing legacy public exports, adding hygiene validation, and documenting retained historical products without modifying raw evidence or active research outputs.
- Acceptance checks: The canonical pipeline registry identifies exactly one current CMO and site build; `docs/data/` contains no legacy CMO v2/v3/preliminary exports; upstream code does not read `docs/`; the site rebuild remains reproducible; focused and full tests pass; all removed files remain recoverable from Git history or retained processed outputs.
- Read scope: Repository code, documentation, generated-output inventories, Git status, and reference graph. `data/raw/` is read-only.
- Write scope: `.gitignore`; `README.md`; `project_docs/REPOSITORY_LAYOUT.md`; `project_docs/CANONICAL_PIPELINES.md`; `project_docs/legacy_asset_registry.csv`; `scripts/project.py`; `scripts/audit_repository_hygiene.py`; `scripts/build_war_story_page.py`; `scripts/tests/test_repository_hygiene.py`; obsolete tracked `docs/data/cmo_v2_*`, `docs/data/cmo_v3_*`, and `docs/data/preliminary_cmo_*` publication copies; this contract and ledger row.
- Upstream inputs: Current CMO v4 release, current forecast/site builders, existing repository layout and data catalog.
- Expected outputs: Canonical command surface, machine-readable legacy registry, hygiene audit, cleaned publication directory, updated documentation, and validation report.
- Warehouse mode: read-only; no schema or canonical table changes.
- Safety boundary: Preserve all `data/raw/`, `data/manual/`, uncommitted research products, canonical processed data, and historical audits/contracts. Do not rename broad directories in this pass.
