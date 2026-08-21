# Candidate ideology ontology-v3 audit

This audit covers issue-specific candidate valence assembled without party-label imputation. Missing evidence remains missing.

## Current evidence

| source_type | records | candidates |
| --- | --- | --- |
| archived_campaign_platform | 7 | 1 |
| bill_cosponsorship | 2 | 1 |
| bill_sponsorship | 70 | 52 |
| bill_sponsorship_and_statement | 1 | 1 |
| campaign_ad | 5 | 2 |
| campaign_advertisement | 9 | 3 |
| campaign_commitment | 1 | 1 |
| campaign_literature | 1 | 1 |
| campaign_platform | 4 | 3 |
| campaign_release | 5 | 1 |
| campaign_statement | 1 | 1 |
| candidate_announcement | 15 | 6 |
| candidate_authored_column | 2 | 1 |
| candidate_biographical_action | 2 | 2 |
| candidate_biography | 3 | 3 |
| candidate_campaign_ad | 2 | 1 |
| candidate_campaign_platform | 3 | 2 |
| candidate_campaign_pledge | 2 | 1 |
| candidate_campaign_position | 3 | 2 |
| candidate_campaign_position_reported | 1 | 1 |
| candidate_campaign_statement | 4 | 3 |
| candidate_connection_survey | 1 | 1 |
| candidate_distinction | 1 | 1 |
| candidate_election_guide | 1 | 1 |
| candidate_forum | 8 | 3 |
| candidate_interview | 141 | 48 |
| candidate_legislative_statement | 1 | 1 |
| candidate_platform | 91 | 24 |
| candidate_platform_report | 2 | 1 |
| candidate_pledge | 2 | 2 |
| candidate_position_guide | 3 | 1 |
| candidate_profile | 9 | 6 |
| candidate_questionnaire | 9316 | 210 |
| candidate_race_profile | 4 | 2 |
| candidate_reelection_statement | 3 | 2 |
| candidate_reported_position | 12 | 5 |
| candidate_retrospective | 6 | 1 |
| candidate_statement | 9 | 6 |
| candidate_voter_guide | 16 | 8 |
| congressional_testimony | 1 | 1 |
| contemporaneous_profile | 1 | 1 |
| endorsement_profile | 1 | 1 |
| incumbent_public_statement | 1 | 1 |
| incumbent_record_reelection_statement | 3 | 1 |
| interest_group_award | 1 | 1 |
| interest_group_endorsement | 407 | 202 |
| interest_group_leadership | 2 | 1 |
| interest_group_rating | 1675 | 881 |
| interest_group_support | 1 | 1 |
| legislative_advocacy | 5 | 3 |
| legislative_agenda | 1 | 1 |
| legislative_agenda_statement | 2 | 1 |
| legislative_amendment | 2 | 2 |
| legislative_budget_action | 1 | 1 |
| legislative_budget_sponsorship | 3 | 3 |
| legislative_committee_vote | 1 | 1 |
| legislative_cosponsorship | 12 | 6 |
| legislative_disclosure_action | 1 | 1 |
| legislative_initiative | 1 | 1 |
| legislative_position | 11 | 8 |
| legislative_procedural_vote | 1 | 1 |
| legislative_proposal | 9 | 6 |
| legislative_record | 6 | 5 |
| legislative_record_campaign_statement | 2 | 1 |
| legislative_record_candidate_profile | 1 | 1 |
| legislative_record_summary | 1 | 1 |
| legislative_reform_leadership | 1 | 1 |
| legislative_rollcall | 19479 | 154 |
| legislative_sponsorship_and_statement | 2 | 2 |
| legislative_statement | 1 | 1 |
| legislative_vote | 4 | 4 |
| legislator_signed_column | 3 | 1 |
| new_member_campaign_profile | 3 | 1 |
| official_behavior | 1 | 1 |
| official_biography | 4 | 2 |
| party_candidate_profile | 1 | 1 |
| public_advocacy | 1 | 1 |
| public_official_action | 1 | 1 |
| public_statement | 129 | 56 |
| retrospective_candidate_position | 1 | 1 |
| retrospective_office_profile | 4 | 2 |
| secondary_source_synthesis | 3 | 2 |

## Candidate-cycle coverage

| election_cycle | candidates | profiles | issues |
| --- | --- | --- | --- |
| 1994.0 | 9 | 12 | 10 |
| 1998.0 | 124 | 1408 | 26 |
| 2002.0 | 146 | 928 | 30 |
| 2006.0 | 140 | 850 | 34 |
| 2010.0 | 183 | 919 | 47 |
| 2014.0 | 160 | 2082 | 52 |
| 2018.0 | 177 | 1847 | 53 |
| 2022.0 | 159 | 461 | 46 |

## Legislative audit

| v3_audit_status | rollcalls |
| --- | --- |
| excluded_after_substantive_text_review | 258 |
| excluded_fiscal_baseline_insufficient | 4107 |
| excluded_local_or_constituency_measure | 1893 |
| excluded_motion_relationship_insufficient | 472 |
| excluded_text_or_model_output_insufficient | 1935 |
| no_policy_topic | 22449 |
| procedural_or_amendment_excluded | 9577 |
| v3_direction_accepted | 1700 |

There are **8,507** candidate–issue profiles. **1,015** have substantial opposing evidence and are exported for review.

The legislative audit is corpus-wide but adjudication remains incomplete. Generic budgets, procedural motions, amendments without reviewed amendment text, and ambiguous omnibus measures are not assigned a policy pole.

## Known source gaps

- No structured biography corpus is downloaded locally.
- No structured Vote Smart public-statement corpus is downloaded locally.
- Broad ideological ratings and coalition endorsements are not converted into specific issue positions unless the organization has an explicit issue mapping.
- 1994 remains dependent on archival surveys, endorsement slates, newspapers, and historical journals; current Vote Smart evidence begins later.

Unmapped review queues contain **318 rating organizations** and **19 endorsement organizations**. Many should remain unmapped because their signals are broad or constituency-based rather than issue-specific.