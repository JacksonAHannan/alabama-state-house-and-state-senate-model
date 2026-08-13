from io import StringIO

import pandas as pd

from oe_normalize import (
    is_pseudocandidate,
    load_oe,
    normalize_for_match,
    normalize_name,
    norm_party,
)


def test_norm_party_maps_known_variants():
    assert norm_party("D") == "D"
    assert norm_party("dem") == "D"
    assert norm_party("Democrat") == "D"
    assert norm_party("R") == "R"
    assert norm_party("rep") == "R"
    assert norm_party("Republican") == "R"


def test_norm_party_defaults_unknown_to_other():
    assert norm_party("IND") == "O"
    assert norm_party("") == "O"
    assert norm_party(None) == "O"


def test_is_pseudocandidate_matches_known_labels():
    assert is_pseudocandidate("Over Votes")
    assert is_pseudocandidate("Under Votes")
    assert is_pseudocandidate("Write-in")
    assert is_pseudocandidate("Write-ins")
    assert not is_pseudocandidate("Jane Smith")


def test_normalize_name_expands_abbreviations_and_strips_punctuation():
    assert normalize_name("St. Mark's Ch") == "SAINT MARK S CHURCH"
    assert normalize_name("1st Baptist Ch") == "FIRST BAPTIST CHURCH"
    assert normalize_name("Smith & Jones VFD") == "SMITH AND JONES VOLUNTEER FIRE DEPARTMENT"


def test_normalize_for_match_strips_leading_codes_and_machine_suffixes():
    assert normalize_for_match("101 - Midway Baptist Church") == "MIDWAY BAPTIST CHURCH"
    assert normalize_for_match("Midway Baptist Church #2") == "MIDWAY BAPTIST CHURCH"
    assert normalize_for_match("Midway Baptist Church Box 3") == "MIDWAY BAPTIST CHURCH"


def test_load_oe_normalizes_types_and_keys(tmp_path):
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,Precinct 1,State House,10,DEM,Jane Smith,120\n"
        "Autauga,Precinct 1,State House,10,REP,John Doe,\n"
        "Autauga,Precinct 1,President,,DEM,Joe Biden,150\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    data = load_oe(path)

    assert data.loc[0, "votes"] == 120.0
    assert data.loc[1, "votes"] == 0.0  # blank vote count coerced to 0
    assert data.loc[0, "district"] == 10.0
    assert pd.isna(data.loc[2, "district"])
    assert data.loc[0, "party_norm"] == "D"
    assert data.loc[1, "party_norm"] == "R"
    assert data.loc[0, "county_key"] == "AUTAUGA"
    assert data.loc[0, "precinct_key"] == "PRECINCT 1"
