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

## Common commands

```powershell
python scripts/build_site.py
python -m pytest -q
python scripts/audit_repository_paths.py
```

The public site is generated into `docs/`. Standalone copies are written under
`artifacts/site/`; they are conveniences rather than canonical source files.
