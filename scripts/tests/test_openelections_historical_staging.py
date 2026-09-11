from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_openelections_historical_staging import candidate_key, classify_office, normalize_party, vote_series


def test_office_and_embedded_district_classification():
    assert classify_office("State Representative - District 158") == ("house", "158")
    assert classify_office("State Senator - District 7") == ("senate", "7")
    assert classify_office("U.S. President And Vice President") == ("USP", None)
    assert classify_office("President of the United States") == ("USP", None)
    assert classify_office("Lieutenant Governor") == (None, None)


def test_party_normalization_is_conservative():
    assert normalize_party("(DEM") == "D"
    assert normalize_party("Republican") == "R"
    assert normalize_party("J. W. MORROW JR") is None
    assert candidate_key("Morrow, John W., Jr.") == candidate_key("JOHN W MORROW")


def test_georgia_modes_are_summed_once():
    frame = pd.DataFrame({"election_day_votes": [10], "advanced_votes": [5], "absentee_by_mail_votes": [2], "provisional_votes": [1]})
    votes, fields = vote_series(frame)
    assert votes.iloc[0] == 18
    assert fields == "election_day_votes+advanced_votes+absentee_by_mail_votes+provisional_votes"


def test_release_district_keys_and_source_provenance():
    root = Path(__file__).resolve().parents[2]
    output = root / "data/processed/precinct_history/openelections"
    districts = pd.read_csv(output / "openelections_legislative_district_party_totals.csv")
    observations = pd.read_csv(output / "openelections_legislative_precinct_candidate.csv.gz", low_memory=False)
    assert not districts.duplicated(["state", "year", "chamber", "district"]).any()
    assert observations[["source_file", "source_sha256", "source_row"]].notna().all().all()
    assert observations["district"].notna().all()
