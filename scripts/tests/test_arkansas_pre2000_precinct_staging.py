from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_arkansas_pre2000_precinct_staging import classify_contest, normalize_party


def test_contest_labels_and_typo_are_classified():
    assert classify_contest("STATE REPRESENTATIVE DISTRICT 003") == ("SLDL", 3)
    assert classify_contest("STATE REPRESENTATVIE 49 DISTRICT") == ("SLDL", 49)
    assert classify_contest("STATE SENATE DISTRICT 25") == ("SLDU", 25)
    assert classify_contest("U.S. PRESIDENT & VICE PRESIDENT") == ("USP", None)
    assert classify_contest("U.S. SENATE") == ("USS", None)


def test_parties_are_conservative_and_unknown_text_is_not_a_candidate_party():
    assert normalize_party("Democrat") == "DEM"
    assert normalize_party("Republican") == "REP"
    assert normalize_party("Natural Law Party") == "OTH"
    assert normalize_party("Party Affiliation") is None


def test_generated_observations_have_valid_keys_and_no_totals_columns():
    root = Path(__file__).resolve().parents[2]
    path = root / "data/processed/precinct_history/arkansas_pre2000/arkansas_pre2000_precinct_observations.csv"
    data = pd.read_csv(path)
    keys = ["state", "year", "county", "precinct", "office", "district", "candidate", "party"]
    assert set(data["year"]) == {1994, 1996, 1998}
    assert {"SLDL", "SLDU"}.issubset(set(data["office"]))
    assert not data.duplicated(keys).any()
    assert data["votes"].ge(0).all()
    assert not data["precinct"].str.upper().isin(
        {"TOTAL", "TOTALS", "GRAND TOTAL", "SUBTOTAL", "SUBTOTALS", "FINAL REPORT", "DIFFERENCE"}
    ).any()


def test_legislative_release_gate_is_tied_to_klarner_reconciliation():
    root = Path(__file__).resolve().parents[2]
    audit = pd.read_csv(root / "data/processed/precinct_history/arkansas_pre2000/arkansas_pre2000_legislative_reconciliation.csv")
    eligible = audit.loc[audit["model_eligible"].eq(True)]
    assert len(eligible) >= 100
    assert set(eligible["reconciliation_status"]).issubset({"exact", "within_one_percent"})
    assert not audit.loc[audit["reconciliation_status"].eq("material_mismatch"), "model_eligible"].any()
    assert eligible[["klarner_dem_votes", "klarner_rep_votes", "sos_dem_votes", "sos_rep_votes"]].notna().all(axis=None)
