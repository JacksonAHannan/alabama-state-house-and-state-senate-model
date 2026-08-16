# Repository layout and migration map

The August 2026 cleanup separated raw inputs, derived outputs, public pages,
research products, and documentation without deleting source material.

## Placement rules

| Material | Location |
|---|---|
| Original downloads and official source files | `data/raw/` |
| Reproducible derived tables | `data/processed/` |
| CMO ideology research and candidate memos | `research/cmo_ideology/` |
| Executable pipelines | `scripts/` |
| Automated tests | `scripts/tests/` |
| Website source assets | `dashboard/` |
| GitHub Pages output | `docs/` |
| Standalone local HTML output | `artifacts/site/` |
| Model cards, methodology, and audits | `project_docs/` |
| Tool-managed or unrelated local files | ignored local directories |

## Migrated legacy paths

| Previous path | Current path |
|---|---|
| `Results and Shapefiles/` | `data/raw/alabama_elections_and_geography/` |
| `Candidate Financial Information/` | `data/raw/finance/alabama/` |
| `Candidate Information/` | `data/raw/candidates/legacy_2022/` |
| `data-GiFps.csv` | `data/raw/polling/nate_silver_pollster_ratings.csv` |
| `data/raw/Shor-McCarty Ideological Data/` | `data/raw/ideology/shor_mccarty_aggregate_2023/` |
| downloaded Split Ticket pages | `data/raw/reference_pages/` |
| root-level generated model HTML | `artifacts/site/` |
| root-level model documentation | `project_docs/` |
| `docs/superpowers/` | `project_docs/development/` |

The `docs/` directory is reserved for files intended to be publicly deployed by
GitHub Pages. The canonical definitions of generated pages remain their Python,
CSS, and JavaScript sources.

The project-wide SQLite warehouse architecture, lifecycle rules, and current
migration boundary are documented in `project_docs/WAREHOUSE_ARCHITECTURE.md`.
Its machine-readable asset catalog is `project_docs/data_catalog.csv`.
