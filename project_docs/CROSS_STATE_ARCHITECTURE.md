# Project architecture

## Purpose

This repository is one state node in a federated Southern legislative modeling
project. Repositories share contracts and concepts but retain state-local data,
adapters, audits, model runs, and publication history. This avoids a single
fragile warehouse while allowing pooled analysis through compatible exports.

## Architectural principles

1. **State adapters at the edge.** Provider and state-specific formats end at
   ingestion; canonical layers do not encode scraper quirks.
2. **Provenance before transformation.** Every record traces to an immutable
   source artifact and a versioned build.
3. **Evidence is appendable.** Conflicting observations coexist until an
   authority policy or documented adjudication resolves them.
4. **Unknown is not zero.** Missing, unopposed, suppressed, unavailable, and
   not-applicable values remain distinguishable.
5. **Geography is versioned.** District plans and Census vintages are explicit
   join dimensions, never ambient assumptions.
6. **Publication is downstream.** `docs/` may consume validated marts but can
   never serve as an upstream data source.

## Layers

```text
official/provider files
        |
        v
data/raw + source manifest
        |
        v
state adapters -> normalized source tables
        |
        v
canonical identities, contests, geography, finance, legislation
        |
        v
feature marts -> versioned model runs -> validation gates
        |
        +--> cross-state compatibility exports
        +--> docs/ and local artifacts
```

SQLite is the preferred state-local analytical warehouse. Binary source files
remain outside it; the database stores provenance, normalized records,
lineage, canonical views, features, model runs, and validation results.

## Canonical domains

- elections and candidates
- people, aliases, incumbency, and party history
- district plans and geographic crosswalks
- demographics and ecological-inference inputs
- campaign finance and candidate resources
- bills, sponsorships, amendments, roll calls, and member votes
- ideology evidence and scores
- polling and political environment
- forecasts, simulations, diagnostics, and publication exports

## Stable identifiers

State exports use durable namespaced identifiers. At minimum:

- `state_code`
- `chamber` (`lower` or `upper`)
- `district_id` plus `district_plan_id`
- `election_id`, `contest_id`, and `candidate_election_id`
- `person_id` and source-specific alias identifiers
- `source_file_id`, `build_run_id`, and `model_run_id`

Identifiers must not depend on display names or row order.

## Pipeline stages

1. Acquire and hash sources.
2. Parse through a state/provider adapter.
3. Validate source parity and structural constraints.
4. Resolve identities and geography while retaining evidence.
5. Build canonical views under declared authority policies.
6. Build leakage-safe feature marts.
7. Train/backtest with time-forward splits.
8. Gate publication on integrity, coverage, calibration, and reproducibility.
9. Export common cross-state tables and state-specific public products.

## Publication gates

No forecast is publishable unless:

- the build is reproducible from registered sources;
- all schema, key, reconciliation, and geographic-vintage checks pass;
- training features are available as of the forecast cutoff date;
- forward validation and calibration are documented;
- uncertainty includes model, data, and contest-status limitations;
- a model card identifies the exact code, data, and configuration versions.

## Cross-state governance

Changes to canonical names, keys, enums, or export semantics are architecture
changes. Document the proposed migration, preserve backward compatibility when
practical, and apply the same contract version across every state repository.
State-only fields belong in an extension table or namespaced metadata, not in a
silent fork of the shared schema.

