from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_tennessee_1998_precinct_staging import canonical_county, cell_integer, district_number, has_total_marker, integer_token


def test_integer_token_handles_report_zero_and_commas_conservatively():
    assert integer_token("1,137") == 1137
    assert integer_token("。") == 0
    assert integer_token("O") == 0
    assert integer_token("12-A") is None


def test_cell_integer_reassembles_split_and_punctuated_digits():
    def item(text, x):
        return {"text": text, "x0": x, "x1": x + 10, "confidence": 0.9}
    assert cell_integer([item("1,", 10), item("731", 25)])[0] == 1731
    assert cell_integer([item("4.64", 10)])[0] == 464
    assert cell_integer([item("E6", 10)])[0] == 86


def test_county_names_are_canonicalized_without_discarding_uncertainty():
    assert canonical_county(".. BLOUNT")[0] == "BLOUNT"
    assert canonical_county("NOINN")[0] == "UNION"
    assert canonical_county("HLINS")[0] == "SMITH"
    assert canonical_county("LIHM")[0] == "WHITE"
    assert canonical_county("NOSNHOF")[0] == "JOHNSON"


def test_ocr_corrupted_total_markers_are_still_excluded():
    assert has_total_marker("COUNTY TOTAD")
    assert has_total_marker("COUNTY ZOTAL")
    assert not has_total_marker("TOTALITY CHURCH")


def test_district_number_reassembles_ocr_punctuation():
    assert district_number("DISTRICT 1.3", 33) == 13
    assert district_number("DISTRICT 13", 33) == 13
    assert district_number("DISTRICT 9 5", 99) == 95
    assert district_number("DISTRICT TOTAL", 99) is None


def test_staged_keys_votes_and_totals_exclusions():
    root = Path(__file__).resolve().parents[2]
    base = root / "data/processed/precinct_history/tennessee_1998"
    legislative = pd.read_csv(base / "tennessee_1998_legislative_precinct_turnout.csv")
    governor = pd.read_csv(base / "tennessee_1998_governor_precinct.csv")
    assert not legislative.duplicated(["state", "year", "county", "precinct", "chamber", "district"]).any()
    assert not governor.duplicated(["state", "year", "county", "precinct"]).any()
    assert legislative["legislative_turnout"].ge(0).all()
    assert governor[["dem_votes", "rep_votes"]].ge(0).all(axis=None)
    assert not legislative["precinct"].str.contains("TOTAL|CANDIDATE", case=False, na=False).any()
    assert not governor["precinct"].str.contains("TOTAL|CANDIDATE", case=False, na=False).any()


def test_release_gate_requires_finite_close_reconciliation():
    root = Path(__file__).resolve().parents[2]
    audit = pd.read_csv(root / "data/processed/precinct_history/tennessee_1998/tennessee_1998_legislative_reconciliation.csv")
    eligible = audit.loc[audit["model_eligible"].eq(True)]
    assert len(eligible) > 0
    assert eligible[["legislative_turnout", "klarner_total_votes"]].notna().all(axis=None)
    tolerance = eligible["klarner_total_votes"].mul(0.01).clip(lower=10)
    assert eligible["vote_delta"].abs().le(tolerance).all()


def test_report_sequence_assigns_complete_legislative_district_inventory():
    root = Path(__file__).resolve().parents[2]
    headers = pd.read_csv(root / "data/processed/precinct_history/tennessee_1998/tennessee_1998_district_header_audit.csv")
    house = headers.loc[headers["report"].eq("house"), "assigned_district"].tolist()
    senate = headers.loc[headers["report"].eq("senate"), "assigned_district"].tolist()
    assert house == list(range(1, 100))
    assert sorted(set(senate)) == sorted([8] + list(range(1, 34, 2)))
    assert senate.count(8) == 1
    assert senate.count(9) == 1
    row = headers.loc[(headers["report"].eq("senate")) & headers["assigned_district"].eq(13)]
    assert row["ocr_header"].iloc[0] == "DISTRICT 1.3"


def test_source_verified_senate_33_shelby_continuation_is_retained():
    root = Path(__file__).resolve().parents[2]
    base = root / "data/processed/precinct_history/tennessee_1998"
    legislative = pd.read_csv(base / "tennessee_1998_legislative_precinct_turnout.csv")
    rows = legislative.loc[(legislative["chamber"].eq("senate")) & legislative["district"].eq(33)]
    assert len(rows) > 0
    assert set(rows["county"]) == {"SHELBY"}
    audit = pd.read_csv(base / "tennessee_1998_legislative_reconciliation.csv")
    row = audit.loc[(audit["chamber"].eq("senate")) & audit["district"].eq(33)].iloc[0]
    # The printed district total is exact, but incomplete precinct OCR remains
    # conservatively ineligible rather than being filled from the aggregate.
    assert row["reconciliation_status"] == "material_mismatch"
    assert not bool(row["model_eligible"])
    totals = pd.read_csv(base / "tennessee_1998_ocr_district_totals.csv")
    printed = totals.loc[(totals["chamber"].eq("senate")) & totals["district"].eq(33)]
    assert 23653 in set(printed["ocr_district_total"])
