#!/usr/bin/env python3
"""Publish the exact 2016-2024 Southern WAR completeness audit."""
from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from load_southern_war_preparation_warehouse import scheduled_war_keys_2016_2024
from warehouse import ROOT, connect, file_sha256

OUT = ROOT / "data/processed/source_audits"
DOC = ROOT / "project_docs/audits/SOUTHERN_WAR_2016_2024_COMPLETENESS.md"
DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
WORKBOOK = ROOT / "data/raw/candidates/southern_state_legislative_incumbents_2016_2026.xlsx"
WAR_MANIFEST = ROOT / "data/processed/war/finance_free_southern_war/build_manifest.json"
INCUMBENCY_MANIFEST = ROOT / "data/processed/source_audits/southern_incumbency_2016_2024_manifest.json"
GENERIC_BALLOT_MANIFEST = ROOT / "data/processed/source_audits/virginia_generic_ballot_environment_manifest.json"


def workbook_inventory() -> dict[str, object]:
    book = pd.ExcelFile(WORKBOOK)
    populated = pd.read_excel(WORKBOOK, sheet_name="Incumbents")
    populated = populated[populated.notna().any(axis=1)].copy()
    historical = pd.read_excel(WORKBOOK, sheet_name="Election_Cycles")
    historical = historical[historical.notna().any(axis=1)].copy()
    states = sorted({str(value).strip().upper() for value in populated.get("State", []) if pd.notna(value)})
    cycles = sorted({int(value) for value in populated.get("Year", []) if pd.notna(value)})
    return {
        "sheets": book.sheet_names,
        "populated_incumbency_rows": len(populated),
        "populated_states": states,
        "populated_cycles": cycles,
        "election_cycle_sheet_nonblank_rows": len(historical),
    }


def build() -> dict[str, object]:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    schedule = pd.DataFrame(
        sorted(scheduled_war_keys_2016_2024()),
        columns=["state_code", "cycle", "chamber"],
    )
    with closing(connect(readonly=True)) as connection:
        history = pd.read_sql_query(
            "SELECT DISTINCT state_code,cycle,chamber "
            "FROM qa_southern_legislative_final_competition_coverage "
            "WHERE cycle BETWEEN 2016 AND 2024",
            connection,
        )
        coverage = pd.read_sql_query(
            "SELECT * FROM qa_southern_war_training_no_finance_coverage",
            connection,
        )
        context = pd.read_sql_query(
            "SELECT state_code,cycle,chamber,"
            "SUM(strict_baseline_eligible) AS strict_baseline_rows,"
            "SUM(research_baseline_eligible) AS research_baseline_rows,"
            "SUM(strict_incumbency_eligible) AS strict_incumbency_rows,"
            "SUM(incumbency_balance IS NOT NULL) AS any_incumbency_rows "
            "FROM mart_southern_war_context_feature "
            "GROUP BY state_code,cycle,chamber",
            connection,
        )
        finance = pd.read_sql_query(
            "SELECT w.state_code,w.cycle,w.chamber,"
            "SUM(COALESCE(f.finance_complete,0)) AS finance_complete_outcomes,"
            "SUM(w.training_status='strict_war_ready_no_finance' AND COALESCE(f.finance_complete,0)=1) "
            "AS strict_war_finance_complete,"
            "SUM(w.training_status='research_war_ready_no_finance' AND COALESCE(f.finance_complete,0)=1) "
            "AS research_war_finance_complete "
            "FROM mart_southern_war_training_no_finance w "
            "LEFT JOIN mart_southern_race_finance f "
            "ON f.state_code=w.state_code AND f.cycle=w.cycle AND f.chamber=w.chamber "
            "AND f.district=w.district GROUP BY w.state_code,w.cycle,w.chamber",
            connection,
        )
        latest = connection.execute(
            "SELECT build_run_id,code_commit,validation_json,completed_at_utc "
            "FROM warehouse_build_run WHERE target='southern_war_preparation_no_finance' "
            "AND status='validated' ORDER BY completed_at_utc DESC LIMIT 1"
        ).fetchone()
        finance_latest = connection.execute(
            "SELECT build_run_id,code_commit,validation_json,completed_at_utc "
            "FROM warehouse_build_run WHERE target='southern_candidate_cycle_finance' "
            "AND status='validated' ORDER BY completed_at_utc DESC LIMIT 1"
        ).fetchone()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())

    history["election_history_loaded"] = True
    detail = schedule.merge(history, on=["state_code", "cycle", "chamber"], how="left", validate="one_to_one")
    detail["election_history_loaded"] = detail.election_history_loaded.fillna(False)
    detail = detail.merge(coverage, on=["state_code", "cycle", "chamber"], how="left", validate="one_to_one")
    detail = detail.merge(context, on=["state_code", "cycle", "chamber"], how="left", validate="one_to_one")
    detail = detail.merge(finance, on=["state_code", "cycle", "chamber"], how="left", validate="one_to_one")
    numeric = [
        "model_valid_outcomes", "context_rows", "strict_ready", "research_ready",
        "missing_context", "missing_baseline", "missing_incumbency", "model_source_fallbacks",
        "strict_baseline_rows", "research_baseline_rows", "strict_incumbency_rows", "any_incumbency_rows",
        "finance_complete_outcomes", "strict_war_finance_complete", "research_war_finance_complete",
    ]
    detail[numeric] = detail[numeric].fillna(0).astype(int)
    detail["strict_ready_rate"] = detail.strict_ready / detail.model_valid_outcomes.where(
        detail.model_valid_outcomes.gt(0)
    )
    detail["research_ready_rate"] = detail.research_ready / detail.model_valid_outcomes.where(
        detail.model_valid_outcomes.gt(0)
    )
    detail["coverage_class"] = "complete_no_contested_d_vs_r_outcomes"
    has_outcomes = detail.model_valid_outcomes.gt(0)
    detail.loc[has_outcomes & detail.strict_ready.eq(detail.model_valid_outcomes), "coverage_class"] = "strict_complete"
    detail.loc[has_outcomes & detail.strict_ready.lt(detail.model_valid_outcomes), "coverage_class"] = "research_complete"
    detail.loc[has_outcomes & (detail.strict_ready+detail.research_ready).lt(detail.model_valid_outcomes), "coverage_class"] = "incomplete"
    detail.loc[~detail.election_history_loaded, "coverage_class"] = "missing_election_history"

    state = detail.groupby("state_code", as_index=False).agg(
        scheduled_slices=("cycle", "size"),
        loaded_slices=("election_history_loaded", "sum"),
        model_valid_outcomes=("model_valid_outcomes", "sum"),
        strict_ready=("strict_ready", "sum"),
        research_ready=("research_ready", "sum"),
        missing_context=("missing_context", "sum"),
        missing_baseline=("missing_baseline", "sum"),
        missing_incumbency=("missing_incumbency", "sum"),
        strict_baseline_rows=("strict_baseline_rows", "sum"),
        strict_incumbency_rows=("strict_incumbency_rows", "sum"),
        finance_complete_outcomes=("finance_complete_outcomes", "sum"),
        strict_war_finance_complete=("strict_war_finance_complete", "sum"),
        research_war_finance_complete=("research_war_finance_complete", "sum"),
    )
    state["strict_ready_rate"] = state.strict_ready / state.model_valid_outcomes.where(state.model_valid_outcomes.gt(0))
    state["research_ready_rate"] = (
        state.strict_ready+state.research_ready
    ) / state.model_valid_outcomes.where(state.model_valid_outcomes.gt(0))
    state["finance_missing_outcomes"] = state.model_valid_outcomes-state.finance_complete_outcomes
    state["finance_coverage_rate"] = (
        state.finance_complete_outcomes / state.model_valid_outcomes.where(state.model_valid_outcomes.gt(0))
    )

    detail_path = OUT / "southern_war_2016_2024_coverage.csv"
    state_path = OUT / "southern_war_2016_2024_state_summary.csv"
    detail.to_csv(detail_path, index=False)
    state.to_csv(state_path, index=False)
    workbook = workbook_inventory()
    totals = {
        "scheduled_slices": len(detail),
        "loaded_slices": int(detail.election_history_loaded.sum()),
        "model_valid_outcomes": int(detail.model_valid_outcomes.sum()),
        "strict_ready": int(detail.strict_ready.sum()),
        "research_ready": int(detail.research_ready.sum()),
        "missing_context": int(detail.missing_context.sum()),
        "missing_baseline": int(detail.missing_baseline.sum()),
        "missing_incumbency": int(detail.missing_incumbency.sum()),
        "finance_complete_outcomes": int(detail.finance_complete_outcomes.sum()),
        "strict_war_finance_complete": int(detail.strict_war_finance_complete.sum()),
        "research_war_finance_complete": int(detail.research_war_finance_complete.sum()),
        "sqlite_integrity": integrity,
        "foreign_key_violations": foreign_keys,
    }
    manifest = {
        "contract_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline": "scripts/audit_southern_war_2016_2024.py",
        "warehouse_build_run_id": latest[0],
        "code_version": latest[1],
        "warehouse_validation": json.loads(latest[2]),
        "warehouse_finished_at_utc": latest[3],
        "finance_warehouse_build_run_id": finance_latest[0],
        "finance_code_version": finance_latest[1],
        "finance_warehouse_validation": json.loads(finance_latest[2]),
        "finance_warehouse_finished_at_utc": finance_latest[3],
        "scope": {
            "states": sorted(detail.state_code.unique()),
            "cycles": "regular elections 2016-2024; state-specific odd-year schedules retained",
            "excluded_states": ["DE", "MD", "WV"],
        },
        "totals": totals,
        "incumbency_workbook_inventory": workbook,
        "inputs": [
            {
                "path": str(DB.relative_to(ROOT)).replace("\\", "/"),
                "warehouse_build_run_id": latest[0],
                "note": "mutable warehouse identified by validated build run; database hash intentionally omitted",
            },
            {"path": str(WAR_MANIFEST.relative_to(ROOT)).replace("\\", "/"), "sha256": file_sha256(WAR_MANIFEST)},
            {"path": str(WORKBOOK.relative_to(ROOT)).replace("\\", "/"), "sha256": file_sha256(WORKBOOK)},
            {"path": str(INCUMBENCY_MANIFEST.relative_to(ROOT)).replace("\\", "/"), "sha256": file_sha256(INCUMBENCY_MANIFEST)},
            {"path": str(GENERIC_BALLOT_MANIFEST.relative_to(ROOT)).replace("\\", "/"), "sha256": file_sha256(GENERIC_BALLOT_MANIFEST)},
        ],
        "outputs": [
            str(detail_path.relative_to(ROOT)).replace("\\", "/"),
            str(state_path.relative_to(ROOT)).replace("\\", "/"),
            str(DOC.relative_to(ROOT)).replace("\\", "/"),
        ],
    }
    manifest_path = OUT / "southern_war_2016_2024_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    research_states = state[state.strict_ready.lt(state.model_valid_outcomes)]
    table_columns = [
        "state_code", "model_valid_outcomes", "strict_ready", "research_ready",
        "missing_context", "missing_baseline", "missing_incumbency",
    ]
    table_lines = [
        "| " + " | ".join(table_columns) + " |",
        "| " + " | ".join("---" for _ in table_columns) + " |",
    ]
    table_lines.extend(
        "| " + " | ".join(str(getattr(row, column)) for column in table_columns) + " |"
        for row in research_states[table_columns].itertuples(index=False)
    )
    table = "\n".join(table_lines)
    finance_columns = [
        "state_code", "model_valid_outcomes", "finance_complete_outcomes",
        "finance_missing_outcomes", "strict_war_finance_complete",
    ]
    finance_lines = [
        "| " + " | ".join(finance_columns) + " |",
        "| " + " | ".join("---" for _ in finance_columns) + " |",
    ]
    finance_lines.extend(
        "| " + " | ".join(str(getattr(row, column)) for column in finance_columns) + " |"
        for row in state[finance_columns].itertuples(index=False)
    )
    finance_table = "\n".join(finance_lines)
    DOC.write_text(
        "# Southern WAR completeness, 2016-2024\n\n"
        f"Generated by `scripts/audit_southern_war_2016_2024.py` from warehouse run "
        f"`{latest[0]}` at `{manifest['generated_at_utc']}`. Code version: `{latest[1]}`.\n\n"
        "## Scope and result\n\n"
        "The contractual South is AL, AR, FL, GA, KY, LA, MO, MS, NC, OK, SC, TN, TX, and VA. "
        "DE, MD, and WV are outside scope. The exact regular-election schedule contains "
        f"{totals['scheduled_slices']} state-cycle-chamber slices; {totals['loaded_slices']} are loaded in the canonical "
        "election warehouse. Special-election-only slices are excluded.\n\n"
        f"There are {totals['model_valid_outcomes']:,} contested D-versus-R district outcomes. "
        f"{totals['strict_ready']:,} pass the strict finance-free WAR gates and "
        f"{totals['research_ready']:,} additional outcomes pass the research gate. "
        f"Missing context: {totals['missing_context']}; missing baseline: {totals['missing_baseline']}; "
        f"missing incumbency: {totals['missing_incumbency']}.\n\n"
        "Strict readiness requires an observed/validated ticket baseline and reviewed or source-observed incumbency. "
        "Research readiness retains documented off-year/cross-election baselines and experimental exact-prior-winner "
        "incumbency, without silently promoting either to strict training.\n\n"
        "## Finance overlay\n\n"
        f"The separate validated finance warehouse has complete Democratic and Republican fundraising for "
        f"{totals['finance_complete_outcomes']:,} of the {totals['model_valid_outcomes']:,} WAR outcomes. "
        f"Of those, {totals['strict_war_finance_complete']:,} also pass the strict election/context gates and "
        f"{totals['research_war_finance_complete']:,} pass the research election/context gate. "
        "`mart_southern_war_training_with_finance` exposes this exact-key overlay; incomplete finance remains "
        "null and explicitly labeled. The finance-free training mart remains available for full-sample sensitivity.\n\n"
        f"{finance_table}\n\n"
        "The source-specific repair queue is "
        "`data/processed/source_audits/southern_finance_remaining_gap_queue.csv`.\n\n"
        "## Remaining strict-gate states\n\n"
        f"{table}\n\n"
        "Virginia 2019 and 2023 use the election-day national generic congressional ballot average because no "
        "same-year statewide/federal ticket exists. Virginia 2017 and 2021 retain same-year governor context but "
        "remain research-only where precinct membership is allocated across elections. Modern races without "
        "complete source-backed open-seat evidence also remain research-only.\n\n"
        "## Incumbency evidence\n\n"
        f"The supplied workbook has {workbook['populated_incumbency_rows']} populated incumbency rows, covering "
        f"{', '.join(workbook['populated_states']) or 'no states'} in "
        f"{', '.join(map(str, workbook['populated_cycles'])) or 'no cycles'}. Its Election_Cycles sheet contains "
        f"{workbook['election_cycle_sheet_nonblank_rows']} nonblank schedule rows, but those are not historical "
        "candidate-incumbency observations. Historical evidence is built separately from content-addressed "
        "Ballotpedia and Wikipedia snapshots, provider flags, prior-winner continuity, and approved adjudications. "
        "Florida 2020 SD-20 is explicitly open after Tom Lee's retirement effective November 3, 2020; source "
        "absence is never treated as an open seat.\n\n"
        "## Reproducible artifacts\n\n"
        "- `data/processed/source_audits/southern_war_2016_2024_coverage.csv`\n"
        "- `data/processed/source_audits/southern_war_2016_2024_state_summary.csv`\n"
        "- `data/processed/source_audits/southern_war_2016_2024_manifest.json`\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build()["totals"], indent=2))
