import pandas as pd

from download_ballotpedia_candidate_pages import (
    candidate_links, match_cycle, quarantine_page_cycle_collisions,
)
from extract_ballotpedia_candidate_evidence import extract_sections
from ideology_ontology_v3 import validate_primitive


def test_election_index_candidate_links_exclude_district_pages():
    text = """[District 3](https://ballotpedia.org/Alabama_House_of_Representatives_District_3)
    [Wesley Thompson](https://ballotpedia.org/Wesley_Thompson)
    [Kerry Underwood](https://ballotpedia.org/Kerry_Underwood#Campaign_themes)"""
    links = candidate_links(text)
    assert links == {
        "WESLEY THOMPSON": "https://ballotpedia.org/Wesley_Thompson",
        "KERRY UNDERWOOD": "https://ballotpedia.org/Kerry_Underwood",
    }


def test_candidate_matching_is_exact_and_cycle_specific():
    candidates = pd.DataFrame([{
        "canonical_candidate_id":"C22", "person_id":"P22", "year":2022,
        "chamber":"house", "district":"3", "canonical_party":"R",
        "canonical_name":"GSL003RUND", "effective_name":"Kerry Underwood",
        "name_key":"KERRY UNDERWOOD",
    }])
    result = match_cycle(candidates, {"KERRY UNDERWOOD":"https://ballotpedia.org/Kerry_Underwood"})[0]
    assert result["accepted"]
    assert result["match_method"] == "exact_election_index_name"


def test_sections_keep_campaign_year_and_scorecard_links_separate():
    text = """## Biography
Candidate biography.
## Campaign themes
### 2022
#### Ballotpedia survey responses
Candidate-authored policy answer.
## Scorecards
### 2024
[NFIB](https://example.org/nfib.pdf)
## Footnotes
1. [Campaign site](https://example.org/candidate)
## See also
Ignore this.
"""
    rows = extract_sections(text)
    keyed = {(row["section"], row["subsection_year"]):row["section_text"] for row in rows}
    assert "Candidate-authored" in keyed[("Campaign themes", "2022")]
    assert "NFIB" in keyed[("Scorecards", "2024")]
    assert "Campaign site" in keyed[("Footnotes", "")]


def test_adjudicated_ballotpedia_positions_use_valid_ontology_and_cycles():
    frame = pd.read_csv("data/manual/ideology/ballotpedia_candidate_position_adjudications.csv")
    assert frame.adjudication_status.eq("adjudicated").all()
    assert frame.temporal_status.eq("pre_or_during_election").all()
    for row in frame.itertuples(index=False):
        validate_primitive(row.primitive_axis, row.policy_pole)
        assert str(row.election_cycle) in row.canonical_candidate_id


def test_duplicate_person_page_is_retained_only_for_supported_district():
    crosswalk = pd.DataFrame([
        {"election_year":2014,"ballotpedia_url":"https://ballotpedia.org/Jack_Williams",
         "chamber":"house","district":"47","matched_name":"Jack Williams","accepted":True,
         "review_required":False,"match_method":"exact"},
        {"election_year":2014,"ballotpedia_url":"https://ballotpedia.org/Jack_Williams",
         "chamber":"house","district":"102","matched_name":"Jack Williams","accepted":True,
         "review_required":False,"match_method":"exact"},
    ])
    links = {("house","47"): {"JACK WILLIAMS":"https://ballotpedia.org/Jack_Williams"}}
    result = quarantine_page_cycle_collisions(crosswalk, links)
    assert result.loc[0,"accepted"]
    assert not result.loc[1,"accepted"]


def test_extracted_scorecards_obey_identity_and_temporal_guards():
    ratings = pd.read_csv("data/processed/ideology/ballotpedia_candidate_scorecard_ratings.csv").fillna("")
    assert pd.to_numeric(ratings.rating).between(0, 100).all()
    matched = ratings[ratings.canonical_candidate_id.ne("")].copy()
    assert (pd.to_numeric(matched.rating_year) <= pd.to_numeric(matched.election_cycle)).all()
    district = matched[matched.district.ne("")]
    assert (pd.to_numeric(district.district) == pd.to_numeric(district.district_num)).all()


def test_ballotpedia_endorsements_are_not_silently_issue_scored():
    signals = pd.read_csv("data/processed/ideology/ballotpedia_candidate_coalition_signals.csv").fillna("")
    eligible = signals.model_eligible_same_cycle.astype(str).str.lower().eq("true")
    assert eligible.sum() == 5
    assert signals.ideological_position_assigned.astype(str).str.lower().eq("false").all()


def test_only_explicitly_mapped_external_scorecard_enters_issue_evidence():
    evidence = pd.read_csv("data/processed/ideology/candidate_position_evidence_v3_all_sources.csv").fillna("")
    external = evidence[evidence.adjudication_authority.eq("external_scorecard_explicit_ontology_mapping")]
    assert len(external) == 62
    assert external.source_provider.eq("The Club for Growth").all()
    assert external.primitive_axis.eq("market_governance").all()
