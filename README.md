# Alabama legislative models

This repository contains Jackson Hannan's Alabama legislative Candidate Margin
Overperformance research, 2026 House and Senate forecast, and legislator issue
research.

## Repository map

- `scripts/` — reproducible ingestion, modeling, validation, research, and site builds
- `scripts/tests/` — automated tests
- `data/raw/` — original source archives, with tracking decided source by source
- `data/processed/` — derived model inputs and outputs
- `research/cmo_ideology/` — legislator and ideology research products
- `dashboard/` — CSS and JavaScript source for public pages
- `docs/` — deployable GitHub Pages site only
- `project_docs/` — model cards, methodology notes, audits, and development plans
- `artifacts/site/` — local standalone HTML builds
- `local_archive/` — unrelated or local-only material; ignored by Git

See [the detailed repository layout](project_docs/REPOSITORY_LAYOUT.md) before
adding a new source or generated artifact.

For coordinated or parallel agent work, follow the
[dedicated agent workflow](project_docs/coordination/AGENT_WORKFLOW.md). It
defines domain ownership, task and handoff contracts, the single-writer
warehouse rule, and independent release gates.

## Common commands

```powershell
python scripts/project.py build cmo
python scripts/project.py build forecast
python scripts/project.py build site
python scripts/project.py audit
python scripts/project.py test
python scripts/validate_agent_workflow.py
```

These are the canonical entry points. Do not infer the current model from an
older script or CSV that happens to remain in the repository. See
[Canonical pipelines](project_docs/CANONICAL_PIPELINES.md) and the
[legacy asset registry](project_docs/legacy_asset_registry.csv).

The public site is generated into `docs/`. Standalone copies are written under
`artifacts/site/`; they are conveniences rather than canonical source files.
