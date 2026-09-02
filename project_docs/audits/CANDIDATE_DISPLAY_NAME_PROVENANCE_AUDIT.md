# Candidate display-name provenance audit

Date: 2026-09-01

## Finding

The election and finance warehouse candidate-name fields are not contaminated
with committee identities. A separate defect left identifier-shaped source
labels in some canonical historical election rows, including three Democratic
2022 rows that reached the Ideology & Caucus page.

The source finance table intentionally retains two different identities:

- `candidate_name` is the canonical election candidate identity.
- `provider_candidate_name` is the provider's filing identity and may be a
  committee, campaign, PAC, or candidate spelling.

The current warehouse contains committee-like values in
`provider_candidate_name`, as expected, but zero committee-like values in the
canonical `candidate_name` fields of the finance source table, accepted finance
mart, or final-stage election fact.

## Correction

The historical WAR publisher and Ideology & Caucus publisher now join WAR by
`canonical_candidate_id` and use canonical election identity as the primary
public-name authority. When the canonical value is identifier-shaped, the
publisher requires an evidence-backed adjudication with a `verified_` identity status from
`data/manual/ideology/candidate_research_aliases.csv`, preserves the malformed
value as `source_candidate_name`, and publishes the verified person's name.
Finance provider names, committee names, and committee IDs are never selected
as display names.

Both public builders fail if a committee-like or unresolved identifier-shaped
identity reaches their public candidate-name field. Provider identity remains preserved separately in the
warehouse for lineage and reconciliation, and a dedicated regression test
audits the source, mart, and public boundaries.

## Validation

- Historical public WAR payload: 1,018 candidate-cycle rows; zero
  committee-like or identifier-shaped display names.
- Ideology & Caucus payload: 311 candidate-cycle rows; zero committee-like
  or identifier-shaped display names. The corrected 2022 names include James
  C. Fields Jr., Herb Neu, and Christian Coleman.
- Warehouse source, mart, and final election fact canonical-name fields: zero
  committee-like values.
- Provider identity retains committee-form values by design and is explicitly
  prohibited as a display-name source.
