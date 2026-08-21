# Candidate position ontology v3

Ontology v3 separates source-faithful policy positions from derived ideological
families. It is the integration contract for Vote Smart responses, legislative
votes, sponsorships, public statements, candidate interviews, campaign
literature, and campaign websites.

Every evidence row records a policy primitive and pole, the candidate's stance
toward that policy, timing relative to the election, original source text and
URL, adjudication authority, confidence, and weight. A policy pole may have a
documented loading onto one of eight Alabama CMO families, remain issue-only, or
represent a categorical delivery mechanism. No universal progressive versus
conservative sign exists at the evidence layer.

The eight higher-order families are:

1. market autonomy versus government economic direction;
2. material-support restriction versus generosity;
3. capital/management versus labor alignment;
4. social restriction/traditionalism versus liberty and equality;
5. rehabilitation/due process versus punitive enforcement;
6. immigration restriction/national identity versus inclusion;
7. extraction/property priority versus environmental protection/preservation;
8. institutional control versus democratic reform.

Questionnaire evidence is currently emitted to
`candidate_position_evidence_v3_votesmart.csv`. Future source adapters must emit
the same columns using a distinct `evidence_id`. The combined ledger validates
the ontology version, primitive poles, family loadings, source types, timing,
stance codes, constituency tags, and evidence-ID uniqueness.

`family_contribution` equals the primitive pole's within-family direction times
the candidate's position value. This is not yet a final rating. Final scoring
must aggregate repeated evidence within a policy, control the influence of
multiple records from one source, enforce election timing, preserve missingness,
and disclose source coverage. Post-election evidence remains in the ledger but
must not leak backward into a contemporaneous candidate rating.

Business constituency is stored as nonexclusive tags such as `small_business`,
`large_business`, `labor_union`, or `extractive_industry`, rather than a bipolar
ideology score. Ordinal budget and tax answers retain fractional response values
and their policy domain. Federal-questionnaire supplemental primitives remain
available but do not automatically enlarge the Alabama CMO family vector.

The legacy progressive/conservative Vote Smart tables remain reproducible and
unchanged. They are not the authoritative input for the next multi-source
candidate re-rating.
