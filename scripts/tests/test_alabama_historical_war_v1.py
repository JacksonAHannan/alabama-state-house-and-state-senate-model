from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/war/alabama_historical_war_v1"
PUBLISHED = ROOT / "data/processed/war/alabama_war_v1"
KEYS = ["cycle", "chamber", "district"]
EXCLUSIONS = ROOT / "data/manual/elections/alabama_historical_war_exclusions.csv"
EXCLUDED = "excluded_by_adjudication"


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, low_memory=False)


def test_historical_coverage_and_arithmetic() -> None:
    races = load("race_war.csv")
    candidates = load("candidate_cycle_war.csv")
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    # 1994 party-label repair (ALABAMA-1994-PARTY-LABELS-20261004): 72 -> 66 1994 D-vs-R races.
    assert len(races) == manifest["diagnostics"]["race_rows"] == 504
    assert len(candidates) == 2 * len(races)
    assert set(races.cycle) == {1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022}
    assert not races.duplicated(KEYS).any()
    assert not candidates.duplicated(KEYS + ["canonical_party"]).any()
    scored = races[races.scoring_scope.ne(EXCLUDED)]
    np.testing.assert_allclose(
        scored.war, scored.raw_gap - scored.fitted_structural_expected_gap, atol=1e-9
    )
    paired = candidates[candidates.scoring_scope.ne(EXCLUDED)].pivot(
        index=KEYS, columns="canonical_party", values="candidate_cycle_war")
    assert paired.notna().all().all()
    np.testing.assert_allclose(paired.D, -paired.R, atol=1e-9)


def test_exclusions_withhold_war_only_for_adjudicated_races() -> None:
    races = load("race_war.csv")
    candidates = load("candidate_cycle_war.csv")
    exclusions = pd.read_csv(EXCLUSIONS)
    assert not exclusions.exclusion_id.duplicated().any()
    assert exclusions[["reason", "evidence", "decided_by", "decided_at_utc"]].notna().all().all()
    excluded = races[races.scoring_scope.eq(EXCLUDED)]
    assert set(map(tuple, excluded[KEYS].values)) == set(map(tuple, exclusions[KEYS].values))
    assert excluded.war.isna().all() and excluded.exclusion_id.isin(exclusions.exclusion_id).all()
    assert races[races.scoring_scope.ne(EXCLUDED)].war.notna().all()
    withheld = candidates[candidates.scoring_scope.eq(EXCLUDED)]
    assert len(withheld) == 2 * len(exclusions) and withheld.candidate_cycle_war.isna().all()
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["diagnostics"]["excluded_races"] == len(exclusions)
    assert "data/manual/elections/alabama_historical_war_exclusions.csv" in manifest["input_hashes"]


def test_pre2016_scores_are_modern_model_backcasts() -> None:
    races = load("race_war.csv")
    historical = races[races.cycle.le(2014)]
    # 412 + 2002 House 27 (Marshall repair) - 6 net 1994 races (1994 party-label repair)
    assert len(historical) == 407
    exclusions = pd.read_csv(EXCLUSIONS)
    listed = historical.set_index(KEYS).index.isin(exclusions.set_index(KEYS).index)
    assert historical[~listed].scoring_scope.eq("post2016_southern_model_backcast").all()
    assert historical[listed].scoring_scope.eq(EXCLUDED).all()
    np.testing.assert_allclose(
        historical.fitted_structural_expected_gap,
        historical.modern_backcast_structural_expected_gap,
        atol=1e-12,
    )
    source = (ROOT / "scripts/build_alabama_historical_war_v1.py").read_text(encoding="utf-8")
    assert 'SPECIFICATION = "decaying_lag"' in source
    assert "ALPHA = 100.0" in source
    assert "modern.cycle.gt(2016).all()" in source


def test_2018_and_2022_exactly_preserve_published_alabama_war() -> None:
    historical = load("race_war.csv")
    current = pd.read_csv(PUBLISHED / "race_war.csv", low_memory=False)
    current["chamber"] = current.chamber.map({"lower": "house", "upper": "senate"})
    joined = historical[historical.cycle.gt(2016)].merge(
        current[KEYS + ["war", "fitted_structural_expected_gap"]],
        on=KEYS,
        suffixes=("_historical", "_published"),
        validate="one_to_one",
    )
    assert len(joined) == 97
    np.testing.assert_allclose(joined.war_historical, joined.war_published, atol=1e-12)
    np.testing.assert_allclose(
        joined.fitted_structural_expected_gap_historical,
        joined.fitted_structural_expected_gap_published,
        atol=1e-12,
    )
    assert historical.loc[
        historical.cycle.gt(2016), "scoring_scope"
    ].eq("published_same_cycle_residual").all()


def test_candidate_display_names_cannot_come_from_finance_committees() -> None:
    candidates = load("candidate_cycle_war.csv")
    assert set(candidates.display_name_source) == {
        "canonical_alabama_election_candidate", "verified_candidate_research_alias"
    }
    committee = re.compile(
        r"committee|campaign|friends of|\bfor (?:house|senate|representative)\b|\bpac\b",
        re.IGNORECASE,
    )
    assert not candidates.candidate_name.astype(str).str.contains(committee, na=False).any()
    source_id = re.compile(r"^[A-Z]{3}\d{3}[A-Z]{4,}$")
    assert not candidates.candidate_name.astype(str).str.fullmatch(source_id, na=False).any()
    expected = {
        "AL-2022-house-12-D-GSL012DFIE": "James C. Fields Jr.",
        "AL-2022-house-27-D-GSL027DNEU": "Herb Neu",
        "AL-2022-house-47-D-GSL047DCOL": "Christian Coleman",
    }
    actual = candidates.set_index("canonical_candidate_id").candidate_name.to_dict()
    assert {key: actual[key] for key in expected} == expected
    original = candidates.set_index("canonical_candidate_id").source_candidate_name.to_dict()
    assert original["AL-2022-house-12-D-GSL012DFIE"] == "GSL012DFIE"
    source = (ROOT / "scripts/build_alabama_historical_war_v1.py").read_text(encoding="utf-8")
    assert "provider_candidate_name" not in source
    assert "committee_id" not in source


def test_manifest_records_extrapolation_and_no_pooling_or_finance() -> None:
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["configuration"]["training_cutoff_rule"] == "cycle > 2016"
    assert manifest["configuration"]["candidate_pooling"] is False
    assert manifest["configuration"]["finance_in_war"] is False
    assert manifest["configuration"]["committee_names_allowed"] is False
    assert manifest["configuration"]["identifier_shaped_names_allowed"] is False
    assert manifest["diagnostics"]["race_rows"] == 504
    assert manifest["diagnostics"]["committee_like_candidate_names"] == 0
    assert manifest["diagnostics"]["identifier_shaped_candidate_names"] == 0
    assert manifest["diagnostics"]["verified_display_name_adjudications"] > 0
    assert manifest["status"] == "validated_historical_backcast_with_extrapolation_warning"
