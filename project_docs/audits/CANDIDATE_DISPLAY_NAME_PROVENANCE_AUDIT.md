# Candidate display-name provenance audit

Date: 2026-09-01

## Finding

The election and finance warehouse candidate-name fields are not contaminated
with committee identities. The apparent corruption came from treating the
finance provider identity as a public display-name candidate.

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
`canonical_candidate_id` and preserve election identity as the sole public
candidate-name authority. Finance provider names, committee names, and
committee IDs are never selected as display names.

Both public builders fail if a committee-like identity reaches their canonical
candidate-name field. Provider identity remains preserved separately in the
warehouse for lineage and reconciliation, and a dedicated regression test
audits the source, mart, and public boundaries.

## Validation

- Historical public WAR payload: 1,018 candidate-cycle rows; zero
  committee-like display names.
- Ideology & Caucus payload: 311 candidate-cycle rows; zero committee-like
  display names.
- Warehouse source, mart, and final election fact canonical-name fields: zero
  committee-like values.
- Provider identity retains committee-form values by design and is explicitly
  prohibited as a display-name source.
