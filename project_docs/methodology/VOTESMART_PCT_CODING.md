# Vote Smart PCT ideology coding

## Purpose

This layer converts candidate-supplied Vote Smart Political Courage Test and
National Political Awareness Test answers into transparent candidate-cycle
features. It does not infer positions from election performance, party, later
votes, ratings, or endorsements.

The raw questionnaire wording remains authoritative. Every distinct year-item
appears in `votesmart_pct_item_crosswalk.csv`, including items that are not
scored.

Substantive positions without a defensible left/right direction are exported
separately in `votesmart_pct_position_only_responses.csv`. This preserves them
for issue-specific analyses without contaminating the ideology dimensions.

## Direction convention

Within every coded dimension, `+1` denotes the conventionally more conservative
position and `-1` the conventionally more progressive position. Zero denotes a
balance among the scored policy items; it does not necessarily mean that the
candidate described themself as moderate.

The initial dimensions are:

- abortion position;
- guns position;
- economic ideology;
- labor position;
- social ideology;
- education position;
- environment position;
- health-care position; and
- criminal-justice position.

This convention is a measurement choice, not a claim that these dimensions form
one universal left-right scale.

## Item mapping

Rules operate on normalized original option text. Each mapped item receives:

```text
policy_key
dimension
affirmative_direction
coding_confidence
coding_status
```

Specific policy rules precede broad rules. Examples include concealed carry,
gun-purchase restrictions, abortion funding, parental-notification rules,
minimum wage, private-sector regulation, vouchers, same-sex marriage, and
Medicaid expansion.

Items remain unmapped when their ideological direction is ambiguous or depends
on missing context. This includes legislative priorities, `other` responses,
candidate-written text, transportation and agriculture appropriations, and
administrative-policy questions without a stable cross-year interpretation.
Campaign-process positions such as term limits, contribution limits, and ballot
initiatives are substantively useful candidate positions, but are not forced
onto a left-right scale merely to increase coverage.

## Response coding

For explicit yes/no questions, a negative answer reverses the affirmative item
direction. For historical checkbox questionnaires, an `X` scores the selected
policy option. A blank checkbox is missing, not opposition. `Undecided`, empty,
and unrecognized responses remain missing.

Some later forms directly answer `Pro-life` or `Pro-choice`; those labels are
coded directly. Ordinal budget and tax answers preserve intensity on a scale
from `Greatly Increase` (`+1` response direction) through `Maintain` (`0`) to
`Greatly Decrease` or `Eliminate` (`-1`). The item's policy direction then maps
that response to the dimension convention. For example, increasing K-12
funding is progressive while decreasing it is conservative. Medium-confidence
labels identify categories such as sin taxes and law-enforcement spending where
the conventional direction is less universal.

## Aggregation

Candidate scores are constructed in two stages:

1. average response items within a policy key;
2. average policy-key scores within a dimension.

This prevents long batteries of nearly identical questions from dominating a
dimension merely because one questionnaire vintage contained more items.

Features are joined to canonical candidates only when the questionnaire year
equals the candidate election year. A 1998 response is never backfilled into a
1994 feature, even if the canonical person identity is known.

## Initial build status

The current deterministic pass maps 528 of 1,729 distinct year-items, scores
10,582 candidate responses, and produces 187 same-election candidate-cycle
profiles. The expanded pass includes ordinal budget/tax batteries and reviewed
rules for education, welfare, health care, environmental policy, and criminal
justice. Another 2,473 responses are retained as position-only evidence.
Unmapped items are a review queue, not a claim that the remaining questions
lack ideological content.

Identity resolution explicitly distinguishes respondents outside the canonical
two-party CMO universe from unresolved identities. Six unique same-year,
same-chamber, same-district, same-party nickname or middle-name aliases were
accepted after review. Third-party candidates remain in the raw PCT corpus but
are not attached to a Democratic or Republican canonical candidate.

The low PCT response rate is a selection mechanism. PCT-derived features must
therefore be modeled with missingness indicators and reported coverage; missing
candidates must not be assigned the party or questionnaire mean.

## Ideology-atlas integration

The public ideology atlas now treats Vote Smart PCT dimensions as a distinct,
candidate-supplied evidence type. For a focal candidate it may use the latest
scored questionnaire no later than the focal election, while preserving the
questionnaire year and labeling an earlier-cycle response. Later questionnaires
never leak backward. Among the current 30 focal overperformers, four have usable
pre-election profiles: Craig Ford, Jody Letson, Larry Means, and Felicia
Stewart. The other 26 remain missing; they are not assigned zero or a caucus
average. Vote Smart has no scored 1994 candidate-cycle profiles, so 1994 remains
an explicit coverage gap rather than an ideology category.

## Local-model review layer

Unmapped items are ranked by the number of observed selected responses and
candidate coverage. Two local Ollama models (`qwen3.5:9b` and
`ministral-3:8b`) independently draft a dimension, affirmative direction,
scorability decision, policy key, confidence, and source-grounded explanation.
The source quote is checked mechanically against the supplied questionnaire
text.

Model output is a review aid only. It is never automatically merged into the
scoring crosswalk. Agreement is evaluated on dimension, direction, and
scorability; generated policy-key labels are excluded because synonymous labels
are not a substantive disagreement.

The review layer enforces an 8-billion-parameter minimum. The current models are
the locally installed 9B Qwen and 8B Ministral models; smaller models are not
used for this task. In the first ten-item pilot, only one item achieved agreement
on the three core fields, and seven of ten passed quote verification for both
models. A subsequent 50-item institutional-policy tranche produced no core
agreements and 22 joint quote-verification failures. Much of that disagreement
came from attempts to force campaign-process questions onto a generic ideology
scale. The result supports using these models to surface possible mappings and
disagreements, while retaining controlled rules and human adjudication as the
authority.
