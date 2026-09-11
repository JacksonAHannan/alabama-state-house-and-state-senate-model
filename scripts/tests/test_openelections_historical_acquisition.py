from pathlib import Path
import hashlib
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquire_openelections_historical_gaps import EXPECTED_CYCLES, ROOT, selected_member


def test_selectors_reject_primaries_and_admit_verified_general_files():
    assert selected_member("AR", "2008/20081104__ar__general__precinct.csv")
    assert not selected_member("AR", "2008/20080520__ar__primary__precinct.csv")
    assert selected_member("GA", "2016/20161108__ga__general__appling__precinct.csv")
    assert not selected_member("GA", "2016/20160119__ga__special__general__precinct.csv")


def test_release_manifest_has_expected_cycles_and_matching_hashes():
    manifest = pd.read_csv(ROOT / "data/processed/source_audits/openelections_historical_gap_manifest.csv")
    observed = manifest.groupby("state")["election_year"].apply(lambda values: set(values)).to_dict()
    assert observed == EXPECTED_CYCLES
    assert manifest[["state", "election_year"]].drop_duplicates().shape[0] == sum(
        len(cycles) for cycles in EXPECTED_CYCLES.values()
    )
    assert manifest["election_stage"].eq("general").all()
    for row in manifest.itertuples():
        path = ROOT / row.local_path
        assert path.stat().st_size == row.size_bytes
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.sha256
