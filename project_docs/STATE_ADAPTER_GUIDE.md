# State adapter guide

## Adapter boundary

Alabama and other Southern state/provider formats belong in adapter modules
under `scripts/` or validated companion-repository adapters. An adapter
may understand agency filenames, HTML structure, spreadsheet tabs, district
labels, local party abbreviations, and election terminology. Code downstream
of the adapter must consume canonical records defined in `DATA_CONTRACTS.md`.
Companion exports must declare their source authority, state, contract version,
and lineage before central ingestion; do not treat them as unqualified local
Alabama records or silently override existing source observations.

## Adding a source

1. Identify the official publisher and authoritative scope.
2. Save or register the exact artifact and compute SHA-256.
3. Add a small representative fixture that may legally be committed.
4. Write a parser that preserves original fields alongside normalized values.
5. Emit deterministic records with stable source identifiers.
6. Test malformed rows, duplicate keys, missing values, and changed layouts.
7. Reconcile counts and totals against the publisher's own summaries.
8. Register lineage from the source file through each derived asset.

## State configuration

`config/state.yaml` is descriptive configuration, not a place to hide factual
corrections. It should hold stable state identity, chamber labels, official
source entry points, and feature flags. Corrections and exceptions belong in
reviewable adjudication tables with evidence.

Alabama's repository identity is not the Southern analysis universe. Regional
loaders must use their explicit state and election-schedule contracts, preserving
odd-year elections, staggered chambers, and state-specific final-stage rules.

## Redistricting

Represent each enacted or court-ordered map as a distinct `district_plan_id`.
Record effective elections, source geometry, Census vintage, and known changes.
Crosswalks must state their construction method and weights. Never relabel an
old election onto a current map without an explicit modeled allocation.

## Completion checklist

A state adapter is production-ready only when it has fixtures, automated tests,
source manifests, reconciliation reports, geographic-vintage checks, identity
review queues, and documented failure/retry behavior.

