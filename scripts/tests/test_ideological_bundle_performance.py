from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed" / "ideology"


def test_bundle_axes_have_genuine_two_sided_support():
    balance = pd.read_csv(OUT / "ideology_headline_pole_balance.csv")
    profiles = pd.read_csv(OUT / "ideological_bundle_profiles.csv")
    dimensions = set(profiles.columns) - {"bundle_id", "bundle_label", "n_candidates"}
    allowed = set(balance.loc[balance.variation_class.eq("two_sided_usable"), "headline_dimension"])
    assert dimensions
    assert dimensions <= allowed
    used = balance[balance.headline_dimension.isin(dimensions)]
    assert (used.minority_pole_count >= 10).all()
    assert (used.minority_pole_share >= .10).all()


def test_bundle_outputs_are_complete_and_non_tiny():
    assignments = pd.read_csv(OUT / "ideological_bundle_assignments.csv")
    performance = pd.read_csv(OUT / "ideological_bundle_performance.csv")
    assert assignments.canonical_candidate_id.is_unique
    assert assignments.groupby("bundle_id").size().min() >= 10
    assert set(performance.outcome) == {
        "presidential_overperformance", "federal_index_overperformance", "candidate_cmo_total_oof"
    }
