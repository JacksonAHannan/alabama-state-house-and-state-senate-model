import sqlite3

import audit_southern_outcome_rebuild_parity as parity


def make(path, outcome_votes, third_party, run):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE mart_southern_war_outcome(war_outcome_id TEXT PRIMARY KEY, build_run_id TEXT, state_code TEXT, dem_votes INTEGER, third_party_votes INTEGER, source_file_id TEXT)")
        connection.execute("CREATE TABLE mart_southern_war_context_feature(context_feature_id TEXT PRIMARY KEY, build_run_id TEXT, baseline_dem_margin REAL)")
        connection.execute("CREATE TABLE mart_alabama_2026_incumbency_roster(roster_id TEXT PRIMARY KEY, build_run_id TEXT, incumbent_ran INTEGER)")
        connection.execute("INSERT INTO mart_southern_war_outcome VALUES ('AL-1', ?, 'AL', ?, ?, ?)", (run, outcome_votes, third_party, "SRC" if run == "new" else None))
        connection.execute("INSERT INTO mart_southern_war_outcome VALUES ('GA-1', ?, 'GA', 10, 0, 'SRC-GA')", (run,))
        connection.execute("INSERT INTO mart_southern_war_context_feature VALUES ('CTX-1', ?, 1.5)", (run,))
        connection.execute("INSERT INTO mart_alabama_2026_incumbency_roster VALUES ('R-1', ?, 1)", (run,))


def test_parity_passes_when_only_expected_alabama_fields_change(tmp_path):
    before, after = tmp_path / "before.sqlite", tmp_path / "after.sqlite"
    make(before, 100, 0, "old")
    make(after, 103, 9, "new")
    result = parity.audit(before, after)
    assert result["status"] == "passed"
    assert result["identical_context_and_roster"]
    changed = result["tables"][parity.OUTCOME]["changed"]
    assert set(changed) == {"AL-1"}
    assert changed["AL-1"]["dem_votes"] == {"before": 100, "after": 103}
    assert changed["AL-1"]["source_file_id"] == {"before": None, "after": "SRC"}
    assert result["tables"][parity.OUTCOME]["changed_fields"] == ["dem_votes", "source_file_id", "third_party_votes"]
    assert before.stat().st_mtime_ns and after.stat().st_mtime_ns


def test_parity_reviews_unexpected_state_or_context_changes(tmp_path):
    before, after = tmp_path / "before.sqlite", tmp_path / "after.sqlite"
    make(before, 100, 0, "old")
    make(after, 100, 0, "new")
    with sqlite3.connect(after) as connection:
        connection.execute("UPDATE mart_southern_war_outcome SET dem_votes=11 WHERE war_outcome_id='GA-1'")
    assert parity.audit(before, after)["status"] == "review"
    with sqlite3.connect(after) as connection:
        connection.execute("UPDATE mart_southern_war_outcome SET dem_votes=10 WHERE war_outcome_id='GA-1'")
        connection.execute("UPDATE mart_southern_war_context_feature SET baseline_dem_margin=2.0")
    result = parity.audit(before, after)
    assert result["status"] == "review" and not result["identical_context_and_roster"]


def test_cli_reports_and_exit_codes(tmp_path, capsys):
    before, after = tmp_path / "before.sqlite", tmp_path / "after.sqlite"
    make(before, 100, 0, "old")
    make(after, 103, 9, "new")
    report = tmp_path / "report.json"
    assert parity.main(["--backup", str(before), "--database", str(after), "--report", str(report)]) == 0
    assert report.exists() and "outcome_rows_changed" in capsys.readouterr().out
    assert parity.main(["--backup", str(before), "--database", str(after), "--expected-states", "GA"]) == 1
