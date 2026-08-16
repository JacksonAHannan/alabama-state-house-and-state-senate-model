import pandas as pd

from link_historical_rollcalls_to_acts import build_links


def test_only_overlapping_year_and_unique_act_is_eligible():
    rollcalls = pd.DataFrame([
        {"rollcall_id": "r1", "session": "1998 Regular", "session_year": 1998, "bill_type": "HB", "bill_number": 12,
         "motion_type": "final_passage", "count_valid": True},
        {"rollcall_id": "r2", "session": "1999 Regular", "session_year": 1999, "bill_type": "HB", "bill_number": 12,
         "motion_type": "amendment_or_concurrence", "count_valid": True},
    ])
    acts = pd.DataFrame([
        {"act_id": "a1", "act_year": 1998, "act_number": 5, "act_citation": "98-5", "measure_type": "H",
         "measure_number": 12, "title": "Example"},
    ])
    links = build_links(rollcalls, acts)
    assert links.loc[links.rollcall_id.eq("r1"), "act_link_status"].iat[0] == "unique_act_match"
    assert bool(links.loc[links.rollcall_id.eq("r1"), "analytical_eligibility"].iat[0])
    assert links.loc[links.rollcall_id.eq("r2"), "act_link_status"].iat[0] == "no_act_match"
