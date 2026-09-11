import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/war/post2016_southern_war_v4"
KEYS = ["state_code", "cycle", "chamber", "district"]


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, low_memory=False)


def test_acs_is_complete_for_every_strict_input_race():
    races = load("race_war.csv")
    assert len(races) == 2800
    assert races.demographics_complete.all()
    assert races[["nonwhite_share", "white_college_share"]].notna().all().all()
    assert races.nonwhite_share.between(0, 1).all()
    assert races.white_college_share.between(0, 1).all()


def test_missing_presidential_context_is_not_zero_filled_or_scored():
    races = load("race_war.csv")
    incomplete = races[~races.presidential_context_complete]
    assert len(incomplete) > 0
    assert incomplete.war.isna().all()
    assert incomplete.fitted_structural_expected_gap.isna().all()
    assert incomplete[["older_pres_margin", "recent_pres_margin", "current_pres_margin"]].isna().any(axis=1).all()


def test_scored_war_is_the_race_residual_and_candidates_are_orientations():
    races = load("race_war.csv")
    scored = races[races.model_eligible]
    assert len(scored) == 2769
    assert not races.duplicated(KEYS).any()
    np.testing.assert_allclose(
        scored.raw_gap,
        scored.legislative_dem_margin - scored.environment_baseline_margin,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        scored.war,
        scored.raw_gap - scored.fitted_structural_expected_gap,
        atol=1e-10,
    )
    candidates = load("candidate_cycle_war.csv")
    oriented = candidates.pivot(index="war_outcome_id", columns="canonical_party", values="candidate_cycle_war")
    race_war = races.set_index("war_outcome_id").war.reindex(oriented.index)
    np.testing.assert_allclose(oriented.D, race_war, equal_nan=True)
    np.testing.assert_allclose(oriented.R, -race_war, equal_nan=True)
    assert candidates.score_identification.eq("race_differential_party_orientation").all()


def test_manifest_excludes_finance_and_candidate_history_and_blocks_publication():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["finance_included"] is False
    assert manifest["candidate_history_included"] is False
    assert manifest["diagnostics"]["headline_scored_races"] < manifest["diagnostics"]["strict_input_races"]
    assert manifest["diagnostics"]["max_war_reconciliation_error"] == 0.0
    for name in ("race_war.csv", "candidate_cycle_war.csv", "coverage.csv"):
        frame = load(name)
        assert frame.model_run_id.eq(manifest["model_run_id"]).all()
        assert frame.code_version.notna().all()
    forbidden = {"finance", "fundraising", "candidate_war", "prior_candidate"}
    assert not forbidden.intersection(manifest["features"])
    with sqlite3.connect(ROOT / "data/processed/elections/alabama_elections.sqlite") as connection:
        allocation_run = connection.execute(
            """SELECT build_run_id FROM warehouse_build_run
               WHERE target='southern_presidential_district_allocations'
                 AND status='validated'
               ORDER BY started_at_utc DESC LIMIT 1"""
        ).fetchone()[0]
        vest_allocation_run = connection.execute(
            """SELECT build_run_id FROM warehouse_build_run
               WHERE target='southern_2016_vest_plan_allocation'
                 AND status='validated'
               ORDER BY started_at_utc DESC LIMIT 1"""
        ).fetchone()[0]
        mississippi_allocation_run = connection.execute(
            """SELECT build_run_id FROM warehouse_build_run
               WHERE target='mississippi_2012_partial_plan_allocations'
                 AND status='validated'
               ORDER BY started_at_utc DESC LIMIT 1"""
        ).fetchone()[0]
    assert manifest["context_allocation_run_id"] == allocation_run
    assert manifest["vest_context_allocation_run_id"] == vest_allocation_run
    assert manifest["mississippi_2012_context_allocation_run_id"] == mississippi_allocation_run


def test_only_remaining_presidential_context_gap_is_reviewed_mississippi_2019():
    races = load("race_war.csv")
    incomplete = races[~races.presidential_context_complete]
    assert len(incomplete) == 31
    assert set(incomplete.state_code) == {"MS"}
    assert set(incomplete.cycle) == {2019}
    assert set(incomplete.chamber) == {"lower", "upper"}
    assert incomplete.war.isna().all()


def test_2020_on_2022_plan_inventory_uses_the_central_warehouse():
    inventory = load("presidential_margin_inventory.csv")
    rows = inventory[
        inventory.presidential_year.eq(2020)
        & inventory.source_plan_label.eq(
            "RDH 2020 block results joined to RDH 2022 BAF"
        )
    ]
    assert len(rows) == 2_266
    assert rows.state_code.nunique() == 14
    assert rows.presidential_source_path.eq(
        "warehouse:fact_southern_presidential_district_result"
    ).all()


def test_2016_on_2022_plan_inventory_uses_validated_vest_allocation():
    inventory = load("presidential_margin_inventory.csv")
    rows = inventory[
        inventory.presidential_year.eq(2016)
        & inventory.source_plan_label.eq(
            "VEST 2016 precinct votes weighted by 2020 block VAP to RDH 2022 BAF"
        )
    ]
    assert len(rows) == 2_266
    assert rows.state_code.nunique() == 14
    assert rows.presidential_source_path.eq(
        "warehouse:fact_southern_presidential_district_result"
    ).all()


def test_acs_and_presidential_source_manifests_are_auditable():
    acs = pd.read_csv(ROOT / "data/processed/source_audits/southern_war_v4_acs_manifest.csv")
    assert len(acs) == 70
    assert acs.source_file_id.is_unique
    assert acs.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    presidential = pd.read_csv(
        ROOT / "data/processed/source_audits/southern_war_v4_presidential_manifest.csv"
    )
    assert len(presidential) == 23
    blocked = presidential[presidential.ingest_status.eq("requires_authenticated_download")]
    assert len(blocked) == 14
    assert blocked.sha256.isna().all()
    supplements = presidential[presidential.election_cycle.astype(str).eq("2012")]
    assert set(supplements.state_code) == {"FL", "GA", "MS", "NC", "VA"}
    assert supplements.ingest_status.eq("acquired").all()
    assert supplements.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    assert supplements.retrieved_at.notna().all()
    national = presidential[presidential.source_file_id.isin({
        "RDH-NATIONAL-2020-PRES-BLOCKS",
        "NYT-NATIONAL-2024-PRES-PRECINCT-RESULTS",
        "NYT-NATIONAL-2024-PRES-PRECINCT-GEOMETRY",
    })]
    assert len(national) == 3
    assert national.ingest_status.eq("acquired").all()
    assert national.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
