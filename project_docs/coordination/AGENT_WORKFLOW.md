# Dedicated agent workflow

## Purpose

The project is organized as a hub-and-spoke research program. A coordinating
agent decomposes work and integrates results; domain agents own bounded
pipelines; an independent validation agent controls release gates. The goal is
parallel progress without competing definitions of candidates, geography,
features, or published results.

The machine-readable role and path registry is
`agent_ownership.json`. Concurrent work is declared in `active_tasks.csv`.

## Roles

| Role | Primary responsibility | Typical deliverable |
|---|---|---|
| `orchestrator` | Scope work, assign owners, sequence dependencies, resolve cross-domain decisions | task contracts and integration brief |
| `source_provenance` | Acquire immutable sources, hashes, licenses, and extraction metadata | registered raw-source manifest |
| `elections_geography` | Election normalization, precinct identity, maps, VTD/block links, historical allocations | canonical-ready election/geography staging data |
| `people_finance` | Person/candidate identity, aliases, rosters, incumbency, committees, finance | reviewed identity/resource staging data |
| `legislative_ideology` | Bills, roll calls, sponsorship, Vote Smart, public positions, ideology features | evidence ledger and ideology mart inputs |
| `cmo_model` | Historical baselines, candidate margin overperformance, backtests, diagnostics | versioned CMO run candidate |
| `forecast_model` | 2026 environment, district forecast, uncertainty, simulations | versioned forecast run candidate |
| `web_product` | Dashboard code, accessibility, methodology presentation, publication exports | reviewed site build candidate |
| `warehouse_integrator` | Schema lifecycle, canonical views, migrations, atomic builds | validated warehouse version |
| `validation_release` | Independent QA, leakage checks, model gates, source audits, release approval | signed validation report |

## Standard work cycle

### 1. Intake and decomposition

The orchestrator writes one task contract per independently testable outcome.
Use `TASK_TEMPLATE.md`. A contract must identify one accountable role even when
several roles contribute.

Prefer tasks that produce a staging artifact or review packet. Avoid delegating
open-ended instructions such as "improve the model" or "clean the data."

### 2. Collision check

Before concurrent edits, add tasks to `active_tasks.csv`. Write scopes use
repository-relative paths and must be as narrow as practical. Run:

```powershell
python scripts/validate_agent_workflow.py
```

Two live tasks may read the same input. They may not claim overlapping write
scopes. The validator treats a parent directory and any child path as an
overlap.

### 3. Domain execution

The domain agent works only inside its contract. It may inspect upstream data
outside its owned paths, but changing another domain requires a revised
contract. It records exact commands, source cutoffs, row counts, hashes where
appropriate, and validation results.

Domain agents do not directly publish canonical warehouse objects. They hand a
schema proposal, migration/staging artifact, reconciliation audit, and tests to
the warehouse integrator.

### 4. Warehouse integration

The warehouse integrator is the sole canonical database writer. It verifies:

- stable keys and declared cardinality;
- provenance back to raw observations and manual decisions;
- authority and missing-value policies;
- schema version and ownership metadata;
- atomic build behavior;
- compatibility diffs for consumers being migrated.

The database should have one writer but may have many read-only consumers.

### 5. Independent validation

The validation agent did not implement the change being reviewed. It reruns the
contract checks and tests domain-specific release gates. At minimum it checks
source completeness, key uniqueness, join cardinality, leakage, subgroup error,
temporal validity, and before/after output diffs where relevant.

Failed gates return the task to its domain owner. A caveat is not a substitute
for a failed required gate unless the orchestrator explicitly changes the
release scope.

### 6. Handoff and close

Use `HANDOFF_TEMPLATE.md`. Set the ledger status to `review` while validation is
pending and `complete` only after acceptance. Remove or archive completed rows
periodically; Git history preserves the record.

## Dependency flow

```text
source_provenance
        |
        +--> elections_geography ----+
        +--> people_finance ---------+--> warehouse_integrator
        +--> legislative_ideology ---+            |
                                                   +--> cmo_model
                                                   +--> forecast_model
                                                           |
                                                           +--> web_product
                                                                   |
                                                           validation_release
```

Model work may experiment against read-only snapshots while upstream work is in
progress, but promotion must reference an integrated warehouse version and data
cutoff.

## Safe parallel work

- Source downloads for unrelated providers.
- Precinct research and legislative research in separate paths.
- CMO and forecast experiments reading the same frozen mart.
- UI prototypes using a frozen publication fixture.
- Independent validation while a different domain begins unrelated work.

## Work that must be serialized

- Canonical identity and authority changes.
- Warehouse migrations or replacement.
- Regeneration of shared marts and model headline outputs.
- Site publication into `docs/`.
- Changes to shared schemas, global configuration, or ownership rules.

## Suggested standing cadence

1. Orchestrator chooses the next dependency-unblocking tasks.
2. Domain agents work in parallel against a named snapshot.
3. Warehouse integrator publishes one coherent data version.
4. Model agents rerun against that version.
5. Validation agent issues pass/fail findings.
6. Web agent publishes only approved run IDs.

This cadence is event-driven rather than calendar-bound; small fixes need not
wait for a formal batch when their scope is isolated.

## First standing workstreams

- Historical elections and precinct geography.
- Candidate/person identity and finance reconciliation.
- Legislative evidence and multidimensional ideology.
- Historical CMO estimation and causal/descriptive research.
- 2026 forecast and polling environment.

The warehouse integrator and validation agent operate across all five, while
the web agent consumes only approved exports.
