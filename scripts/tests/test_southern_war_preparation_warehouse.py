from contextlib import closing
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import load_southern_war_preparation_warehouse as mod
from warehouse import connect


def test_scoped_finance_export_is_read_only_and_preserves_siblings(tmp_path):
    from warehouse import database_path, file_sha256
    database = database_path()
    before = database.stat()
    sibling = tmp_path / "build_manifest.json"
    sibling.write_text("preserve upstream build evidence", encoding="utf-8")
    manifest = mod.export_finance_only(output_dir=tmp_path)
    output = tmp_path / manifest["output"]
    with closing(connect(readonly=True)) as connection:
        expected = mod.read_finance_training(connection)
    pd.testing.assert_frame_equal(
        pd.read_csv(output, low_memory=False, dtype={"district": str}), expected, check_dtype=False,
    )
    assert manifest["output_sha256"] == file_sha256(output)
    assert manifest["validation"]["incomplete_numeric_features"] == 0
    assert sibling.read_text(encoding="utf-8") == "preserve upstream build evidence"
    assert {p.name for p in tmp_path.iterdir()} == {
        sibling.name, output.name, output.with_suffix(".manifest.json").name,
    }
    assert database.stat().st_mtime_ns == before.st_mtime_ns


def test_scoped_finance_export_rejects_unmasked_input_without_overwriting(tmp_path):
    import sqlite3
    import pytest
    database = tmp_path / "fixture.sqlite"
    frame = pd.DataFrame([{
        "state_code": "AL", "cycle": 2022, "chamber": "lower", "district": "1",
        "finance_complete": 0, "democratic_fundraising": 10,
        "republican_fundraising": None, "log_fundraising_ratio_d_to_r": None,
    }])
    with sqlite3.connect(database) as connection:
        frame.to_sql("mart_southern_war_training_with_finance", connection, index=False)
    output = tmp_path / "southern_war_training_with_finance.csv"
    output.write_text("previous export", encoding="utf-8")
    with pytest.raises(ValueError, match="Incomplete finance"):
        mod.export_finance_only(database, tmp_path)
    assert output.read_text(encoding="utf-8") == "previous export"


def test_model_outcome_selection_is_unique_and_preserves_final_stage_rules():
    panel = mod.read_panel()
    with closing(connect(readonly=True)) as connection:
        outcomes = mod.select_model_outcomes(connection, "TEST-RUN", panel, "TEST-PANEL")
    assert len(outcomes) == 4582
    assert not outcomes.duplicated(mod.KEYS).any()
    assert outcomes.dem_votes.gt(0).all()
    assert outcomes.rep_votes.gt(0).all()

    texas_56 = outcomes[
        outcomes.state_code.eq("TX")
        & outcomes.cycle.eq(2024)
        & outcomes.chamber.eq("lower")
        & outcomes.district.eq("56")
    ]
    assert len(texas_56) == 1
    assert texas_56.iloc[0].selection_status == "external_validated_panel_fallback"

    virginia_33 = outcomes[
        outcomes.state_code.eq("VA")
        & outcomes.cycle.eq(2019)
        & outcomes.chamber.eq("upper")
        & outcomes.district.eq("33")
    ]
    assert virginia_33.empty  # two Republican candidates; no fictional aggregation

    louisiana = outcomes[outcomes.state_code.eq("LA") & outcomes.cycle.isin([2019, 2023])]
    assert len(louisiana) == 41
    assert set(louisiana.election_stage) == {"general", "other"}


def test_regular_2016_2024_schedule_is_exact_and_excludes_specials():
    schedule = mod.scheduled_war_keys_2016_2024()
    assert len(schedule) == 116
    assert {state for state, _, _ in schedule} == {
        "AL", "AR", "FL", "GA", "KY", "LA", "MO", "MS", "NC", "OK", "SC", "TN", "TX", "VA",
    }
    assert ("SC", 2018, "upper") not in schedule
    assert ("MS", 2023, "lower") in schedule
    assert ("VA", 2023, "upper") in schedule


def test_workbook_reconciles_2026_incumbency_and_retains_the_one_conflict():
    with closing(connect(readonly=True)) as connection:
        roster = mod.alabama_2026_roster(connection, "TEST-RUN")
    assert len(roster) == 140
    assert int(roster.incumbent_ran.sum()) == 122
    assert int(roster.open_seat.sum()) == 18
    conflict = roster[roster.comparison_status.eq("workbook_supported_correction")]
    assert len(conflict) == 1
    row = conflict.iloc[0]
    assert (row.chamber, row.district, row.incumbent_name) == ("upper", "9", "Wes Kitchens")
    assert row.review_status == "proposed"


def test_finance_free_training_export_has_declared_gates():
    path = mod.OUT / "southern_war_training_no_finance.csv"
    frame = pd.read_csv(path, low_memory=False)
    manifest = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "data/processed/source_audits/southern_war_2016_2024_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert len(frame) == 4582
    assert frame.finance_status.eq("excluded_not_ready").all()
    assert not any("fundrais" in column.lower() or "expend" in column.lower() for column in frame.columns)
    assert int(frame.training_status.eq("strict_war_ready_no_finance").sum()) == int(
        manifest["totals"]["strict_ready"]
    )
    assert int(frame.training_status.eq("research_war_ready_no_finance").sum()) == int(
        manifest["totals"]["research_ready"]
    )


def test_published_2016_2024_audit_reconciles_election_and_finance_coverage():
    root = Path(__file__).resolve().parents[2]
    detail = pd.read_csv(root / "data/processed/source_audits/southern_war_2016_2024_coverage.csv")
    manifest = json.loads(
        (root / "data/processed/source_audits/southern_war_2016_2024_manifest.json").read_text(encoding="utf-8")
    )
    assert len(detail) == 116
    assert detail.election_history_loaded.all()
    assert int(detail.model_valid_outcomes.sum()) == 4582
    assert int(detail.missing_context.sum()) == 0
    assert int(detail.missing_baseline.sum()) == 0
    assert int(detail.missing_incumbency.sum()) == 0
    assert int(detail.finance_complete_outcomes.sum()) == int(
        manifest["totals"]["finance_complete_outcomes"]
    )
    assert manifest["scope"]["excluded_states"] == ["DE", "MD", "WV"]
    assert manifest["totals"]["foreign_key_violations"] == 0


def test_warehouse_includes_schema_16_release_and_validated_run():
    with closing(connect(readonly=True)) as connection:
        versions = {
            row[0] for row in connection.execute("SELECT version FROM warehouse_schema_version")
        }
        assert 16 in versions
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        run = connection.execute(
            "SELECT status FROM warehouse_build_run "
            "WHERE target='southern_war_preparation_no_finance' "
            "ORDER BY started_at_utc DESC LIMIT 1"
        ).fetchone()
        assert run == ("validated",)


def test_finance_included_training_interface_preserves_missingness():
    path = mod.OUT / "southern_war_training_with_finance.csv"
    frame = pd.read_csv(path, low_memory=False)
    manifest = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "data/processed/source_audits/southern_war_2016_2024_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert len(frame) == 4582
    assert int(frame.finance_complete.sum()) == int(
        manifest["totals"]["finance_complete_outcomes"]
    )
    assert int(frame.evaluation_status.eq("strict_war_ready_with_finance").sum()) == int(
        manifest["totals"]["strict_war_finance_complete"]
    )
    assert int(frame.evaluation_status.eq("research_war_ready_with_finance").sum()) == int(
        manifest["totals"]["research_war_finance_complete"]
    )
    missing = frame.finance_complete.eq(0)
    assert frame.loc[missing, [
        "democratic_fundraising", "republican_fundraising",
        "log_fundraising_ratio_d_to_r",
    ]].isna().all().all()
