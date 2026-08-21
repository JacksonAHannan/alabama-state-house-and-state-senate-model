# Candidate issue research closure

The research loop is closed at diminishing returns. Missing evidence is retained as missing; it is never converted to a neutral or zero ideological score.

## Terminal accounting

- Modeled candidate-cycle rows: **1,564**
- Candidates with at least one temporally valid issue profile: **1,098**
- Searched with no recoverable issue evidence: **466**
- Residuals with a logged manual broad search: **326**
- Residuals closed by the structured Vote Smart, legislative, identity, and source sweep: **140**

### Residual identity status

| identity_status | candidates |
| --- | --- |
| full_name_official_roster | 48 |
| surname_only_unresolved_after_source_sweep | 86 |
| verified_manual_identity | 171 |
| verified_votesmart_identity | 161 |

## Temporal validity

All evidence remains in the archival evidence table. Only explicitly pre-election, same-cycle, or clearly historical pre-election statuses enter scores. Post-election, retrospective, and temporally unspecified career records are exported but excluded from scoring.

| temporal_status | temporal_model_eligible | evidence_records | candidates |
| --- | --- | --- | --- |
| career_record | False | 4 | 2 |
| career_record_before_election | True | 8 | 2 |
| historical_pre_election | True | 14 | 13 |
| historical_pre_election_record | True | 6 | 5 |
| post_election | False | 114 | 36 |
| post_election_adjacent | False | 4 | 3 |
| post_election_same_term | False | 5 | 5 |
| pre_or_during_election | True | 716 | 245 |
| pre_or_same_cycle_group_signal | True | 1988 | 929 |
| pre_or_same_cycle_legislative_action | True | 19479 | 154 |
| preexisting_position_reported_post_election | False | 1 | 1 |
| prior_public_record | True | 5 | 3 |
| recent_pre_election | True | 1 | 1 |
| retrospective_same_candidate | False | 3 | 1 |
| same_cycle_candidate_statement | True | 9142 | 190 |

## Minimum-evidence rule

- Issue score: at least 0.65 total evidence weight, conflict ratio below 0.50, and absolute valence above 0.15.
- Family score: at least two distinct issues and 1.50 total temporally valid evidence weight.
- Candidate model eligibility: at least three scored issues and two scored ideological families.

A lone mapped endorsement (weight 0.45) therefore cannot create an issue score by itself. One questionnaire answer can create an issue score, but not a broad family or candidate-level ideology estimate.

## Coverage by cycle

| cycle | candidates | candidates_observed | candidates_with_scored_issue | candidates_meeting_three_issue_floor | candidates_model_eligible | observed_share | three_issue_floor_share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1994 | 211 | 9 | 9 | 0 | 0 | 0.04265402843601896 | 0.0 |
| 1998 | 170 | 124 | 120 | 73 | 64 | 0.7294117647058823 | 0.4294117647058823 |
| 2002 | 213 | 146 | 140 | 52 | 42 | 0.6854460093896714 | 0.24413145539906103 |
| 2006 | 194 | 140 | 138 | 55 | 33 | 0.7216494845360825 | 0.28350515463917525 |
| 2010 | 203 | 183 | 179 | 52 | 22 | 0.9014778325123153 | 0.2561576354679803 |
| 2014 | 196 | 160 | 152 | 97 | 67 | 0.8163265306122449 | 0.49489795918367346 |
| 2018 | 204 | 177 | 175 | 116 | 48 | 0.8676470588235294 | 0.5686274509803921 |
| 2022 | 173 | 159 | 154 | 29 | 1 | 0.9190751445086706 | 0.1676300578034682 |

Full candidate and issue coverage tables, the terminal residual ledger, and every temporally excluded evidence record are written beside this report under `research/cmo_ideology/candidate_issue_research/`.