import pandas as pd

from build_historical_journal_legislator_crosswalk import build_crosswalk


def test_unique_surname_and_parenthetical_initial():
    shor = pd.DataFrame([
        {"name": "Smith, Alice", "party": "D", "st": "AL", "u_id": "a", "np_score": -.2,
         "senate1998": 1, "sdistrict1998": 1},
        {"name": "Little, Ted", "party": "D", "st": "AL", "u_id": "t", "np_score": .1,
         "senate1998": 1, "sdistrict1998": 2},
        {"name": "Little, Zeb", "party": "D", "st": "AL", "u_id": "z", "np_score": .2,
         "senate1998": 1, "sdistrict1998": 3},
    ])
    votes = pd.DataFrame([
        {"session_year": 1998, "member_name": "Smith", "member_name_norm": "SMITH"},
        {"session_year": 1998, "member_name": "Little (T)", "member_name_norm": "LITTLE T"},
    ])
    result = build_crosswalk(votes, shor, "senate")
    assert result.loc[result.member_name.eq("Smith"), "shor_u_id"].iat[0] == "a"
    assert result.loc[result.member_name.eq("Little (T)"), "shor_u_id"].iat[0] == "t"
