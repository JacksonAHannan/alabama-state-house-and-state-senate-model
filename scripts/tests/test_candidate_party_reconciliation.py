import pandas as pd

from scripts.build_war_database import consolidate_cross_party_candidate_aliases


def test_cross_party_surname_fragment_is_merged_into_full_name():
    source=pd.DataFrame([
        {"cycle":2014,"chamber":"senate","district":30,"candidate":"Chambliss, Jr.",
         "candidate_code":"Chambliss, Jr.","party":"D","votes":2020.0},
        {"cycle":2014,"chamber":"senate","district":30,"candidate":"Clyde Chambliss, Jr.",
         "candidate_code":"Clyde Chambliss, Jr.","party":"R","votes":20896.0},
    ])
    result,audit=consolidate_cross_party_candidate_aliases(source)
    assert result[["candidate","party","votes"]].to_dict("records")==[
        {"candidate":"Clyde Chambliss, Jr.","party":"R","votes":22916.0}]
    assert audit.fragment_party.tolist()==["D"]


def test_distinct_cross_party_candidates_are_preserved():
    source=pd.DataFrame([
        {"cycle":2014,"chamber":"house","district":1,"candidate":"Greg Burdine",
         "candidate_code":"Greg Burdine","party":"D","votes":4652.0},
        {"cycle":2014,"chamber":"house","district":1,"candidate":"Phillip Pettus",
         "candidate_code":"Phillip Pettus","party":"R","votes":4933.0},
    ])
    result,audit=consolidate_cross_party_candidate_aliases(source)
    assert len(result)==2
    assert audit.empty
