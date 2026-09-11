from pathlib import Path
import subprocess
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def rebuild():
    subprocess.run([sys.executable, "scripts/build_2026_incumbency.py"], cwd=ROOT, check=True)
    return pd.read_csv(ROOT / "data/processed/war/2026_candidate_incumbency.csv")


def test_sam_givhan_is_resolved_as_sd7_incumbent():
    candidates = rebuild()
    sd7 = candidates[(candidates.chamber.eq("senate")) & candidates.district.eq(7)]
    sam = sd7[sd7.candidate.eq("Sam Givhan")].squeeze()
    jared = sd7[sd7.candidate.eq("Jared Sluss")].squeeze()
    assert bool(sam.incumbent)
    assert sam.prior_winner_match == "Sam Givhan"
    assert sam.prior_winner_match_scope == "same_district_party"
    assert not bool(jared.incumbent)


def test_incumbency_is_unique_with_substantial_senate_coverage():
    candidates = rebuild()
    counts = candidates.groupby(["chamber", "district"]).incumbent.sum()
    assert counts.le(1).all()
    assert candidates[candidates.chamber.eq("senate")].incumbent.sum() >= 25
