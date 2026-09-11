import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from build_dime_finance_features import match_candidates, race_features


ROOT = Path(__file__).resolve().parents[2]


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


def test_dime_build_manifest_identifies_and_hashes_every_output():
    manifest=json.loads((ROOT/"data/processed/war/dime_finance_build_manifest.json").read_text())
    assert manifest["build_run_id"] and manifest["code_commit"]
    assert manifest["source"]["license_or_terms"]=="ODC-BY 1.0"
    assert manifest["source"]["retrieval_time_status"]=="unknown_existing_local_artifact"
    for relative,digest in manifest["outputs"].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest
