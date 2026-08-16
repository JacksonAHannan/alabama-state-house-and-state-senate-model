import numpy as np
import pandas as pd

from build_dime_finance_features import match_candidates, race_features


def test_dime_match_uses_district_party_and_surname_for_name_variants():
    candidates=pd.DataFrame([{"canonical_candidate_id":"C1","year":2010,"chamber":"senate",
        "district":28,"party":"D","candidate":"Billy Beasley"}])
    dime=pd.DataFrame([{"cycle":2010,"chamber":"senate","district_num":28,"party_letter":"D",
        "name":"beasley, william m billy","lname":"beasley","dime_recipient_cycle_id":"D1",
        "total.receipts":858539.0}])
    result=match_candidates(candidates,dime).iloc[0]
    assert result.review_status=="accepted"
    assert result.match_method=="district_party_surname"
    assert result.total_receipts==858539.0


def test_unobserved_finance_is_not_converted_to_zero_or_complete():
    candidate=pd.DataFrame([
        {"cycle":2010,"chamber":"house","district":1,"party":"D","total_resources_raised":1000.0,
         "source_name":"DIME"},
        {"cycle":2010,"chamber":"house","district":1,"party":"R","total_resources_raised":np.nan,
         "source_name":None},
    ])
    result=race_features(candidate).iloc[0]
    assert not result.finance_complete
    assert np.isnan(result.rep_resources)
    assert np.isnan(result.log_resource_ratio_d_to_r)

