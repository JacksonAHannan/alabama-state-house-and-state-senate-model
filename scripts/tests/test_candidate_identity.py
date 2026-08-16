import pandas as pd

from scripts.build_candidate_identity import (
    apply_incumbency_roster,
    apply_validated_incumbency_transitions,
    candidate_score,
    opposing_party_alias,
)

def test_candidate_score_rewards_name_and_vote_agreement():
    name,vote,total=candidate_score("Greg Burdine",7083,"Greg Burdine",7083)
    assert (name,vote,total)==(100.0,100.0,100.0)

def test_candidate_score_can_link_shortened_ballot_alias():
    name,vote,total=candidate_score("Burdine",3000,"Greg Burdine",3000)
    assert name>=75 and vote==100 and total>=80

def test_opposing_party_alias_blocks_phantom_candidate():
    pool=pd.DataFrame([{"canonical_name":"Mike Holmes","canonical_party":"R"}])
    found,score,margin,conflict=opposing_party_alias("Holmes","D",pool)
    assert conflict
    assert found.candidate=="Mike Holmes"
    assert score>=88

def test_same_party_alias_is_not_a_conflict():
    pool=pd.DataFrame([{"canonical_name":"Mike Holmes","canonical_party":"R"}])
    *_,conflict=opposing_party_alias("Holmes","R",pool)
    assert not conflict

def test_prior_winner_roster_overlays_missing_incumbent_annotation():
    canonical=pd.DataFrame([
        {"year":2014,"chamber":"house","district":98,"canonical_party":"D",
         "canonical_name":"Napoleon Bracy, Jr.",
         "canonical_candidate_id":"AL-2014-house-98-D-BRACY","incumbent":False},
        {"year":2014,"chamber":"house","district":98,"canonical_party":"R",
         "canonical_name":"Wayne E. Biggs",
         "canonical_candidate_id":"AL-2014-house-98-R-BIGGS","incumbent":False},
    ])
    roster=pd.DataFrame([
        {"cycle":2014,"chamber":"house","district":98,
         "incumbent_candidate":"Napoleon Bracy Jr","incumbent_party":"D"}
    ])

    result=apply_incumbency_roster(canonical,roster)

    assert bool(result.loc[result.canonical_party.eq("D"),"incumbent"].iloc[0])
    assert not bool(result.loc[result.canonical_party.eq("R"),"incumbent"].iloc[0])

def test_validated_transition_accepts_middle_name_expansion_not_shared_first_name():
    canonical=pd.DataFrame([
        {"year":2022,"chamber":"house","district":32,"canonical_party":"D",
         "canonical_name":"Barbara Bigsby Boyd",
         "canonical_candidate_id":"AL-2022-house-32-D-BOYD","incumbent":False},
        {"year":2022,"chamber":"house","district":40,"canonical_party":"D",
         "canonical_name":"Barbara Smith",
         "canonical_candidate_id":"AL-2022-house-40-D-SMITH","incumbent":False},
    ])
    transitions=pd.DataFrame([
        {"cycle":2022,"chamber":"house","prior_party":"D",
         "current_incumbent_match":"Barbara Boyd",
         "transition_status":"continuing_incumbent"}
    ])

    result=apply_validated_incumbency_transitions(canonical,transitions)

    assert bool(result.loc[result.canonical_name.eq("Barbara Bigsby Boyd"),"incumbent"].iloc[0])
    assert not bool(result.loc[result.canonical_name.eq("Barbara Smith"),"incumbent"].iloc[0])
