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

<!-- candidate-issue-research-restatement -->

## Restated accounting (2026-09-11)

Restatement run 2026-09-11T16:54:07Z (UTC). The closure account above is the 2026-08-17 terminal accounting, preserved as history; every disposition it recorded is carried in `prior_status` on the restated ledger. The tables below recompute the same disposition rule from the current evidence layer (`candidate_issue_valence_v3.csv`, `candidate_position_evidence_v3_all_sources.csv`); no evidence value is imputed and no missing cycle is converted to a score.

### Restated terminal accounting

- Modeled candidate-cycle rows: **1,564**
- Candidates with at least one temporally valid issue profile: **1,124**
- Searched with no recoverable issue evidence: **440**
- Cycles whose disposition changed since 2026-08-17: **26**
- Residuals with a logged manual broad search: **318**
- Residuals closed by the structured Vote Smart, legislative, identity, and source sweep: **122**

### Disposition changes since 2026-08-17

| canonical_candidate_id | cycle | chamber | district | canonical_party | prior_status | final_research_status | new_evidence_source_types |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AL-1998-house-24-D-BURKE | 1998 | house | 24 | D | searched_no_recoverable_evidence | evidence_recovered | legislative_vote |
| AL-1998-house-35-R-SIMS | 1998 | house | 35 | R | searched_no_recoverable_evidence | evidence_recovered | legislative_vote |
| AL-2002-house-55-D-MAJOR-ERIC | 2002 | house | 55 | D | searched_no_recoverable_evidence | evidence_recovered | legislative_vote |
| AL-2002-house-58-D-ROBINSON-OLIVER | 2002 | house | 58 | D | searched_no_recoverable_evidence | evidence_recovered | legislative_vote |
| AL-2010-house-1-D-GREG-BURDINE | 2010 | house | 1 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship |
| AL-2010-house-60-D-JUANDALYNN-LEE-LEE-GIVAN | 2010 | house | 60 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship |
| AL-2010-house-68-D-THOMAS-E-ACTION-JACKSON | 2010 | house | 68 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2010-house-70-D-CHRISTOPHER-JOHN-ENGLAND | 2010 | house | 70 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2010-house-83-D-GEORGE-TOOTIE-BANDY | 2010 | house | 83 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2010-house-84-D-BERRY-FORTE | 2010 | house | 84 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship |
| AL-2010-house-85-D-DEXTER-GRIMSLEY | 2010 | house | 85 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_cosponsorship |
| AL-2010-senate-9-R-CLAY-SCOFIELD | 2010 | senate | 9 | R | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship |
| AL-2014-house-32-D-BARBARA-BIGSBY-BOYD | 2014 | house | 32 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2014-house-68-D-THOMAS-E-ACTION-JACKSON | 2014 | house | 68 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2014-house-70-D-CHRISTOPHER-JOHN-ENGLAND | 2014 | house | 70 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2014-house-83-D-GEORGE-TOOTIE-BANDY | 2014 | house | 83 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2014-house-94-R-T-JOE-FAUST | 2014 | house | 94 | R | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2014-house-97-D-ADLINE-C-CLARKE | 2014 | house | 97 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2018-house-13-R-CONNIE-COONER-ROWE | 2018 | house | 13 | R | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2018-house-32-D-BARBARA-BIGSBY-BOYD | 2018 | house | 32 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2018-house-42-R-JAMES-M-JIMMY-MARTIN | 2018 | house | 42 | R | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2018-house-55-D-RODERICK-ROD-HAMPTON-SCOTT | 2018 | house | 55 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2018-house-68-D-THOMAS-E-ACTION-JACKSON | 2018 | house | 68 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2018-house-69-D-KELVIN-JAMICHAEL-LAWRENCE | 2018 | house | 69 | D | searched_no_recoverable_evidence | evidence_recovered | legislative_vote |
| AL-2018-house-70-D-CHRISTOPHER-JOHN-ENGLAND | 2018 | house | 70 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |
| AL-2018-house-82-D-PEBBLIN-WALKER-WARREN | 2018 | house | 82 | D | searched_no_recoverable_evidence | evidence_recovered | bill_sponsorship|legislative_vote |

### Restated residual identity status

| identity_status | candidates |
| --- | --- |
| full_name_official_roster | 31 |
| surname_only_unresolved_after_source_sweep | 86 |
| verified_manual_identity | 168 |
| verified_votesmart_identity | 155 |

### Restated temporal validity

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
| pre_or_during_election | True | 724 | 245 |
| pre_or_same_cycle_group_signal | True | 2050 | 929 |
| pre_or_same_cycle_legislative_action | True | 51800 | 569 |
| preexisting_position_reported_post_election | False | 1 | 1 |
| prior_public_record | True | 5 | 3 |
| recent_pre_election | True | 1 | 1 |
| retrospective_same_candidate | False | 3 | 1 |
| same_cycle_candidate_statement | True | 9142 | 190 |

### Restated minimum-evidence rule

- Issue score: at least 0.65 total evidence weight, conflict ratio below 0.50, and absolute valence above 0.15.
- Family score: at least two distinct issues and 1.50 total temporally valid evidence weight.
- Candidate model eligibility: at least three scored issues and two scored ideological families.

A lone mapped endorsement (weight 0.45) therefore cannot create an issue score by itself. One questionnaire answer can create an issue score, but not a broad family or candidate-level ideology estimate.

### Restated coverage by cycle

| cycle | candidates | candidates_observed | candidates_with_scored_issue | candidates_meeting_three_issue_floor | candidates_model_eligible | observed_share | three_issue_floor_share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1994 | 211 | 9 | 9 | 0 | 0 | 0.04265402843601896 | 0.0 |
| 1998 | 170 | 126 | 123 | 95 | 64 | 0.7411764705882353 | 0.5588235294117647 |
| 2002 | 213 | 148 | 147 | 100 | 42 | 0.6948356807511737 | 0.4694835680751174 |
| 2006 | 194 | 140 | 138 | 90 | 34 | 0.7216494845360825 | 0.4639175257731959 |
| 2010 | 203 | 191 | 187 | 140 | 63 | 0.9408866995073891 | 0.6896551724137931 |
| 2014 | 196 | 166 | 161 | 128 | 110 | 0.8469387755102041 | 0.6530612244897959 |
| 2018 | 204 | 185 | 185 | 147 | 103 | 0.9068627450980392 | 0.7205882352941176 |
| 2022 | 173 | 159 | 154 | 102 | 76 | 0.9190751445086706 | 0.5895953757225434 |

Full candidate and issue coverage tables, the terminal residual ledger, and every temporally excluded evidence record are written beside this report under `research/cmo_ideology/candidate_issue_research/`. Per-row history columns (`prior_status`, `new_evidence_source_types`, `restated_at_utc`) and the preserved 2026-08-17 ledger (`candidate_research_final_status.2026-08-17.csv`) carry the prior account.
