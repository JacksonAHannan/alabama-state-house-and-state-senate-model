# Alabama and Southern legislative research

This repository contains four products: the 2026 Alabama legislative forecast,
historical Alabama WAR maps, ideology and caucus analysis, and Southern
state-legislative WAR for 2016–2024. It hosts their shared central SQLite
warehouse while retaining explicit contracts with companion state repositories.

Start with [agent instructions](AGENTS.md),
[current product routes](project_docs/CANONICAL_PIPELINES.md), and the
[internal phased checklist](project_docs/PROJECT_COMPLETION_CHECKLIST.html).
The checklist is an internal working file, not part of the public website.

## Repository map

- `scripts/` — reproducible ingestion, modeling, validation, research, and site builds
- `scripts/tests/` — automated tests
- `data/raw/` — original source archives, with tracking decided source by source
- `data/processed/` — derived model inputs and outputs
- `research/cmo_ideology/` — evidence and research products; the directory name is historical
- `dashboard/` — CSS and JavaScript source for public pages
- `docs/` — deployable GitHub Pages site only
- `project_docs/` — model cards, methodology notes, audits, and development plans
- `artifacts/site/` — local standalone HTML builds
- `local_archive/` — unrelated or local-only material; ignored by Git

See [the detailed repository layout](project_docs/REPOSITORY_LAYOUT.md) before
adding a new source or generated artifact.

For substantial multi-outcome work, follow the
[phase-management and agent workflow](project_docs/coordination/AGENT_WORKFLOW.md).
It uses the existing checklist, selective delegation, bounded ownership,
evidence-based acceptance and interruption recovery. Small local changes need
no extra orchestration; warehouse writes and publication remain serialized.

## Safe starting checks

```powershell
& .venv/Scripts/python.exe scripts/audit_repository_paths.py
& .venv/Scripts/python.exe -m pytest --testmon -q
& .venv/Scripts/python.exe scripts/validate_agent_workflow.py
```

These checks do not refresh sources or publish outputs. The workflow check
reports ledger consistency, not whether a historical owner is still running.
Use the [testing policy](project_docs/CANONICAL_PIPELINES.md#testing-and-testmon)
for explicit data/SQL tests and full-suite fallbacks. Testmon selection alone
does not validate changed warehouse contents.
Use [Canonical pipelines](project_docs/CANONICAL_PIPELINES.md) to select a
product-specific stage and inspect its side effects. The superseded `build cmo`
dispatcher has been removed. Dispatcher `build forecast` and `build site` require
`--publish`; this acknowledges publication writes, not release approval.
The site target publishes across products rather than providing an isolated preview.

The public site is generated into `docs/`. Standalone copies are written under
`artifacts/site/`; they are conveniences rather than canonical source files.

## Reading older documentation

The [documentation audit](project_docs/audits/DOCUMENTATION_ARCHITECTURE_AUDIT_2026_09_05.md)
and its inventory distinguish maintained instructions, compatibility notes,
research snapshots, and run-scoped validation evidence. Old “current” or “PASS”
language applies to the named artifact/run, not automatically to today's release.
The [legacy asset registry](project_docs/legacy_asset_registry.csv) is a routing
aid, not permission to delete an input still consumed by a maintained builder.
