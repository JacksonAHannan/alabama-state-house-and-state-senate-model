# Repository layout and migration map

The August 2026 cleanup separated raw inputs, derived outputs, public pages,
research products, and documentation without deleting source material.

## Placement rules

| Material | Location |
|---|---|
| Original downloads and official source files | `data/raw/` |
| Reproducible derived tables | `data/processed/` |
| Ideology research and candidate evidence, including historical snapshots | `research/cmo_ideology/` |
| Executable pipelines | `scripts/` |
| Automated tests | `scripts/tests/` |
| Website source assets | `dashboard/` |
| GitHub Pages output | `docs/` |
| Standalone local HTML output | `artifacts/site/` |
| Model cards, methodology, and audits | `project_docs/` |
| Internal phased checklist and progress history | `project_docs/PROJECT_COMPLETION_CHECKLIST.html` only |
| Human adjudication evidence and reviewed exceptions | `data/manual/` |
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

## Canonical versus historical model products

The repository retains superseded processed model outputs for reproducibility.
Their presence does not make them valid inputs. Current entry points and
headline outputs are declared in `project_docs/CANONICAL_PIPELINES.md`; known
superseded products are listed in `project_docs/legacy_asset_registry.csv`.

The public historical pages consume the historical Alabama and Southern WAR
bundles identified in [Canonical pipelines](CANONICAL_PIPELINES.md). Older CMO
files may still be required compatibility inputs; neither their presence nor
their version number establishes publication status. Inspect actual consumers
before deleting or moving them. The hygiene audit checks a limited set of legacy
patterns; it is not a complete model-version or publication-freshness gate.

## Documentation lifecycle

Maintained instructions live at the root and in the architecture, contract,
pipeline-routing, layout and applicable workflow documents. Model/run reports,
validation notes, source acquisition records and completed task contracts retain
their original scope and date. Preserve run-linked bytes and historical review
evidence; do not rewrite an old PASS into a new release approval.

See the [documentation audit](audits/DOCUMENTATION_ARCHITECTURE_AUDIT_2026_09_05.md)
for document-by-document dispositions. `development/` contains earlier plans,
not a second live roadmap. The internal checklist is the sole phased task list;
it never goes into `docs/` or a public-site build.
