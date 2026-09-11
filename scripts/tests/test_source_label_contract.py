"""Source normalization must not erase evidence behind ambiguous printed keys."""

import pandas as pd

from scripts.build_election_database import _observations


def test_observations_preserve_printed_labels_and_physical_cells():
    data = pd.DataFrame({
        "candidate": ["YES", "YES"], "precinct": ["P1", "P1"],
        "printed_candidate": ["YES", " YES "],
        "printed_precinct": ["P1", "P1 "], "votes": [3.0, 4.0],
        "source_sheet": ["29", "29"], "source_row": [4, 4],
        "source_column": [4, 6],
    })
    result = _observations(data, "alabama_sos", 1)
    for column in ("printed_candidate", "printed_precinct", "votes",
                   "source_sheet", "source_row", "source_column"):
        assert result[column].tolist() == data[column].tolist()
    assert result.candidate_key.tolist() == ["YES", "YES"]
    assert len(result) == 2


def test_absent_printed_labels_remain_unknown():
    result = _observations(pd.DataFrame({"candidate": ["Example"], "votes": [0]}),
                           "openelections", 2)
    assert result.printed_precinct.isna().all()
    assert result.printed_candidate.isna().all()
    assert result.votes.tolist() == [0]
