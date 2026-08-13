import pandas as pd

from validate_oe_precinct_totals import check_totals, validate_file


def test_check_totals_flags_a_mismatched_reported_total():
    data = pd.DataFrame(
        [
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Biden", "votes": 10},
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Trump", "votes": 20},
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Total", "votes": 999},
        ]
    )
    mismatches = check_totals(data, ["county", "office", "district", "precinct"], "candidate")
    assert len(mismatches) == 1
    assert mismatches.iloc[0]["reported_total"] == 999
    assert mismatches.iloc[0]["calculated_total"] == 30


def test_check_totals_passes_when_total_reconciles():
    data = pd.DataFrame(
        [
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Biden", "votes": 10},
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Trump", "votes": 20},
            {"county": "Autauga", "office": "President", "district": None, "precinct": "P1", "candidate": "Total", "votes": 30},
        ]
    )
    mismatches = check_totals(data, ["county", "office", "district", "precinct"], "candidate")
    assert mismatches.empty


def test_validate_file_checks_both_directions(tmp_path):
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,P1,President,,DEM,Biden,10\n"
        "Autauga,P1,President,,REP,Trump,20\n"
        "Autauga,P1,President,,,Total,30\n"
        "Autauga,Total,President,,,Biden,10\n"
        "Autauga,Total,President,,,Trump,20\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    mismatches = validate_file(path)
    assert mismatches.empty
