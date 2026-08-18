# State adapter guide

## Adapter boundary

Alabama source formats belong in adapter modules under `scripts/`. An adapter
may understand agency filenames, HTML structure, spreadsheet tabs, district
labels, local party abbreviations, and election terminology. Code downstream
of the adapter must consume canonical records defined in `DATA_CONTRACTS.md`.

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

## Redistricting

Represent each enacted or court-ordered map as a distinct `district_plan_id`.
Record effective elections, source geometry, Census vintage, and known changes.
Crosswalks must state their construction method and weights. Never relabel an
old election onto a current map without an explicit modeled allocation.

## Completion checklist

A state adapter is production-ready only when it has fixtures, automated tests,
source manifests, reconciliation reports, geographic-vintage checks, identity
review queues, and documented failure/retry behavior.

