# Canonical pipelines

This file is the repository's short source-of-truth index. Historical scripts
and processed outputs are retained for reproducibility, but they are not valid
defaults merely because they still exist.

| Product | Canonical command | Headline output |
|---|---|---|
| Historical CMO | `python scripts/project.py build cmo` | `data/processed/war/cmo_v4_candidates.csv` |
| 2026 forecast page | `python scripts/project.py build forecast` | `docs/index.html` |
| Complete public site | `python scripts/project.py build site` | `docs/` |
| Repository audit | `python scripts/project.py audit` | pass/fail console report |
| Complete tests | `python scripts/project.py test` | pytest report |

## Current CMO definition

CMO v4 is the only current CMO product. It is the candidate-oriented residual
from a Split Ticket-style model of the legislative-minus-ticket margin gap.
CMO v2, CMO v3, preliminary CMO, and Fundamentals+ CMO remain historical
research products under `data/processed/`; no public or canonical consumer may
select them by file existence.

## Publication boundary

`docs/` is output only. Upstream scripts must read canonical warehouse views,
versioned marts, or reviewed research products. The site publishes only the
approved v4 CMO exports needed by the current pages.
