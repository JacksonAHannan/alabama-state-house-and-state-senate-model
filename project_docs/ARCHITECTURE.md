# Architecture entry point

The repository's architecture is split across two maintained documents:

- `CROSS_STATE_ARCHITECTURE.md` defines the federated Southern-state contracts,
  layers, identifiers, and publication gates.
- `WAREHOUSE_ARCHITECTURE.md` defines the Alabama-hosted central SQLite
  warehouse, lifecycle controls, canonical domains, and schema migrations.

Pipeline changes must read both documents together. If their guidance
conflicts, the cross-state contract controls public interfaces and the
warehouse document controls local storage and lifecycle implementation.

Use [Canonical pipelines](CANONICAL_PIPELINES.md) for current product routing
and the [internal checklist](PROJECT_COMPLETION_CHECKLIST.html) for phased work.
Earlier design plans and run reports are not alternative architecture instructions;
their status is recorded in the
[documentation audit](audits/DOCUMENTATION_ARCHITECTURE_AUDIT_2026_09_05.md).
