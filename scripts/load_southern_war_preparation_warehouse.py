#!/usr/bin/env python3
"""Prepare finance-free Southern WAR outcomes, context, and 2026 incumbency."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from contextlib import closing
from pathlib import Path

import pandas as pd

from alabama_certified_bridge import alabama_certified_outcome_fields, bridge_lookup
from warehouse import (
    ROOT,
    begin_run,
    connect,
    database_path,
    file_sha256,
    finish_run,
    git_commit,
    initialize,
    register_source_file,
    register_table,
    utcnow,
)

SCHEMA = Path(__file__).with_name("warehouse_southern_war_preparation_schema.sql")
PANEL = ROOT / "data/processed/war/southern_war_panel_v1/southern_war_panel.csv"
PANEL_MANIFEST = ROOT / "data/processed/war/southern_war_panel_v1/build_manifest.json"
INCUMBENCY_WORKBOOK = (
    ROOT / "data/raw/candidates/southern_state_legislative_incumbents_2016_2026.xlsx"
)
EXISTING_2026_RACE_INCUMBENCY = ROOT / "data/processed/war/2026_race_incumbency.csv"
OUT = ROOT / "data/processed/war/finance_free_southern_war"
AUDIT = ROOT / "data/processed/source_audits"
KEYS = ["state_code", "cycle", "chamber", "district"]
FINANCE_COLUMNS = [
    "democratic_fundraising", "republican_fundraising", "log_fundraising_ratio_d_to_r",
]
FINANCE_QUERY = (
    "SELECT * FROM mart_southern_war_training_with_finance "
    "ORDER BY state_code,cycle,chamber,CAST(district AS INTEGER),district"
)


def scheduled_war_keys_2016_2024() -> set[tuple[str, int, str]]:
    """Return the prespecified regular-election schedule at chamber grain."""
    keys: set[tuple[str, int, str]] = set()
    for state in ("AR", "FL", "GA", "KY", "MO", "NC", "OK", "TN", "TX"):
        for cycle in (2016, 2018, 2020, 2022, 2024):
            keys.update({(state, cycle, "lower"), (state, cycle, "upper")})
    for cycle in (2018, 2022):
        keys.update({("AL", cycle, "lower"), ("AL", cycle, "upper")})
    for state in ("LA", "MS"):
        for cycle in (2019, 2023):
            keys.update({(state, cycle, "lower"), (state, cycle, "upper")})
    for cycle in (2016, 2018, 2020, 2022, 2024):
        keys.add(("SC", cycle, "lower"))
    for cycle in (2016, 2020, 2024):
        keys.add(("SC", cycle, "upper"))
    for cycle in (2017, 2019, 2021, 2023):
        keys.add(("VA", cycle, "lower"))
    for cycle in (2019, 2023):
        keys.add(("VA", cycle, "upper"))
    if len(keys) != 116:
        raise AssertionError(f"Southern 2016-2024 schedule contract changed unexpectedly: {len(keys)}")
    return keys


def stable_id(prefix: str, *parts: object) -> str:
    token = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(token.encode()).hexdigest()[:20].upper()}"


def clean(value: object) -> str:
    return "" if pd.isna(value) else re.sub(r"\s+", " ", str(value)).strip()


def normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def normalized_district(value: object) -> str:
    text = clean(value)
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return str(int(float(text)))
    return text.upper()


def nullable(value: object) -> object | None:
    return None if pd.isna(value) or value == "" else value


def unique_official_candidate_sources(connection) -> dict[str, str]:
    """Resolve 1:0..1 scalar lineage without hiding additional/unregistered links."""
    return dict(connection.execute("""
        SELECT b.candidate_election_id, MIN(b.source_file_id)
        FROM bridge_southern_candidate_result_source b
        LEFT JOIN warehouse_source_file f USING(source_file_id)
        GROUP BY b.candidate_election_id
        HAVING COUNT(*)=1 AND COUNT(f.source_file_id)=1
    """))


def observation_source_file(group: pd.DataFrame, official_sources: dict[str, str]) -> str | None:
    """A contest scalar describes every contributing row, including third parties."""
    if group.empty or group.source_family.nunique(dropna=False) != 1:
        return None
    sources = (
        group.candidate_result_id.map(official_sources)
        if group.source_family.iloc[0] == "official_state"
        else group.source_file_id
    )
    if sources.isna().any() or sources.eq("").any() or sources.nunique() != 1:
        return None
    return str(sources.iloc[0])


def integer_flag(value: object) -> int:
    if pd.isna(value):
        return 0
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "yes", "y"})
    return int(bool(value))


def optional_incumbent(value: object) -> int | None:
    if pd.isna(value):
        return None
    numeric = int(float(value))
    if numeric not in {0, 1}:
        raise ValueError(f"Invalid incumbent value {value!r}")
    return numeric


def party_family(value: object) -> str:
    token = clean(value).upper()
    return {"D": "democratic", "R": "republican", "I": "independent"}.get(token, "other")


def election_day(year: int) -> str:
    # First Tuesday after the first Monday in November.
    import datetime as dt

    day = dt.date(year, 11, 1)
    while not (day.weekday() == 1 and day.day >= 2):
        day += dt.timedelta(days=1)
    return day.isoformat()


def read_panel() -> pd.DataFrame:
    frame = pd.read_csv(PANEL, low_memory=False)
    frame = frame[frame.year.between(2016, 2024)].copy()
    frame["state_code"] = frame.state.astype(str).str.upper()
    frame["cycle"] = pd.to_numeric(frame.year, errors="raise").astype(int)
    frame["chamber"] = frame.chamber.map({"house": "lower", "senate": "upper"})
    frame["district"] = frame.district.map(normalized_district)
    if frame[KEYS].isna().any().any() or frame.duplicated(KEYS).any():
        raise ValueError("Southern WAR panel is not unique at state/cycle/chamber/district")
    return frame


def select_model_outcomes(
    connection, run_id: str, panel: pd.DataFrame, panel_source_id: str
) -> pd.DataFrame:
    final_keys = pd.read_sql_query(
        """SELECT state_code,cycle,chamber,district,election_stage,
                  MIN(election_date) AS election_date,
                  MIN(district_plan_id) AS district_plan_id,
                  MIN(geography_vintage) AS geography_vintage,
                  MIN(observation_set_id) AS canonical_observation_set_id,
                  COUNT(DISTINCT observation_set_id) AS canonical_set_count
           FROM fact_southern_legislative_final_candidate_election
           WHERE cycle BETWEEN 2016 AND 2024
           GROUP BY state_code,cycle,chamber,district,election_stage""",
        connection,
    )
    if not final_keys.canonical_set_count.eq(1).all():
        raise ValueError("Final-stage fact has multiple canonical observation sets per contest")
    final_keys["district"] = final_keys.district.map(normalized_district)

    observations = pd.read_sql_query(
        """SELECT * FROM all_southern_legislative_candidate_election_observations
           WHERE cycle BETWEEN 2016 AND 2024 AND validation_status='passed'""",
        connection,
    )
    observations["district"] = observations.district.map(normalized_district)
    join_keys = KEYS + ["election_stage"]
    observations = observations.merge(
        final_keys[join_keys + ["canonical_observation_set_id"]],
        on=join_keys,
        how="inner",
        validate="many_to_one",
    )
    observations["votes"] = pd.to_numeric(observations.votes, errors="coerce")
    quality = {
        row[0]: json.loads(row[1])
        for row in connection.execute(
            "SELECT observation_set_id,quality_flags_json "
            "FROM source_southern_legislative_observation_set"
        )
    }
    official_sources = unique_official_candidate_sources(connection)
    # Alabama canonical contests carry no observation-level source file. After the
    # certified-canvass authority decision, their scalar source file and third-party
    # total come from the reviewed canonical/certified bridge, which must agree.
    bridge_candidates, bridge_sets = bridge_lookup(connection)

    candidates: list[dict] = []
    for observation_set_id, group in observations.groupby("observation_set_id", sort=False):
        flags = quality.get(observation_set_id, {})
        dem = group[
            group.party_family.eq("democratic") & group.votes.fillna(0).gt(0)
        ]
        rep = group[
            group.party_family.eq("republican") & group.votes.fillna(0).gt(0)
        ]
        eligible = (
            len(dem) == 1
            and len(rep) == 1
            and group.votes.notna().all()
            and not bool(flags.get("dontuse", False))
            and not bool(flags.get("uncont", False))
            and flags.get("source_etype") in {None, "g"}
        )
        if not eligible:
            continue
        first = group.iloc[0]
        dem_row, rep_row = dem.iloc[0], rep.iloc[0]
        total_votes = int(group.votes.sum())
        dem_votes, rep_votes = int(dem_row.votes), int(rep_row.votes)
        source_file = observation_source_file(group, official_sources)
        third_party_votes = total_votes - dem_votes - rep_votes
        quality_flags = dict(flags)
        if first.source_family == "alabama_canonical":
            if bridge_candidates is None:
                quality_flags["alabama_certified_bridge"] = "absent"
            else:
                source_file, third_party_votes, bridge_flags = alabama_certified_outcome_fields(
                    group, bridge_candidates, bridge_sets
                )
                quality_flags.update(bridge_flags)
        candidates.append(
            {
                **{key: first[key] for key in KEYS},
                "election_stage": first.election_stage,
                "election_date": nullable(first.election_date),
                "district_plan_id": nullable(first.district_plan_id),
                "geography_vintage": first.geography_vintage,
                "observation_set_id": observation_set_id,
                "canonical_observation_set_id": first.canonical_observation_set_id,
                "dem_candidate_result_id": dem_row.candidate_result_id,
                "rep_candidate_result_id": rep_row.candidate_result_id,
                "dem_candidate_name": dem_row.candidate_name,
                "rep_candidate_name": rep_row.candidate_name,
                "dem_votes": dem_votes,
                "rep_votes": rep_votes,
                "two_party_votes": dem_votes + rep_votes,
                "third_party_votes": third_party_votes,
                "legislative_dem_margin": 100 * (dem_votes - rep_votes) / (dem_votes + rep_votes),
                "source_provider": first.source_provider,
                "source_family": first.source_family,
                "source_file_id": source_file,
                "authority_rank": int(first.authority_rank),
                "source_quality_flags_json": json.dumps(quality_flags, sort_keys=True),
                "observed_vote_rows": int(group.votes.notna().sum()),
                "candidate_rows": len(group),
            }
        )

    selected = pd.DataFrame(candidates)
    selected = selected.sort_values(
        KEYS + ["authority_rank", "observed_vote_rows", "candidate_rows", "observation_set_id"],
        ascending=[True, True, True, True, True, False, False, True],
    ).drop_duplicates(KEYS, keep="first")
    selected["selection_status"] = selected.apply(
        lambda row: "canonical_model_eligible"
        if row.observation_set_id == row.canonical_observation_set_id
        else "model_eligible_fallback",
        axis=1,
    )

    # Texas's companion repository is an explicitly validated upstream. It can
    # fill a Texas regular contest absent from the central regular-stage key,
    # but this is not a generic permission to reuse panel rows for other states.
    existing_keys = set(selected[KEYS].itertuples(index=False, name=None))
    texas = panel[
        panel.state_code.eq("TX")
        & panel.outcome_eligible.astype("boolean").fillna(False)
        & panel.outcome_source.fillna("").str.startswith("Texas official returns normalized")
        & pd.to_numeric(panel.dem_votes, errors="coerce").gt(0)
        & pd.to_numeric(panel.rep_votes, errors="coerce").gt(0)
        & panel.dem_candidate.notna()
        & panel.rep_candidate.notna()
    ]
    external_rows = []
    for row in texas.itertuples():
        key = (row.state_code, int(row.cycle), row.chamber, row.district)
        if key in existing_keys:
            continue
        dem_votes, rep_votes = int(row.dem_votes), int(row.rep_votes)
        observation_set_id = stable_id("WARSET", *key, "texas_companion")
        external_rows.append(
            {
                "state_code": "TX",
                "cycle": int(row.cycle),
                "chamber": row.chamber,
                "district": row.district,
                "election_stage": "general",
                "election_date": election_day(int(row.cycle)),
                "district_plan_id": f"TX-{row.cycle}-{row.chamber}-reported-unknown-vintage",
                "geography_vintage": "provider-reported; plan vintage unverified",
                "observation_set_id": observation_set_id,
                "canonical_observation_set_id": None,
                "dem_candidate_result_id": stable_id("WARCAND", observation_set_id, "D"),
                "rep_candidate_result_id": stable_id("WARCAND", observation_set_id, "R"),
                "dem_candidate_name": row.dem_candidate,
                "rep_candidate_name": row.rep_candidate,
                "dem_votes": dem_votes,
                "rep_votes": rep_votes,
                "two_party_votes": dem_votes + rep_votes,
                "third_party_votes": max(0, int(row.stage_total_votes) - dem_votes - rep_votes)
                if pd.notna(row.stage_total_votes)
                else 0,
                "legislative_dem_margin": 100 * (dem_votes - rep_votes) / (dem_votes + rep_votes),
                "source_provider": "Texas companion state-legislative model repository",
                "source_family": "texas_official_upstream",
                "source_file_id": panel_source_id,
                "authority_rank": 15,
                "source_quality_flags_json": json.dumps(
                    {"validated_panel_outcome": True, "central_regular_stage_absent": True},
                    sort_keys=True,
                ),
                "selection_status": "external_validated_panel_fallback",
            }
        )
    selected = pd.concat([selected, pd.DataFrame(external_rows)], ignore_index=True, sort=False)
    if selected.duplicated(KEYS).any():
        raise ValueError("Model outcome selection is not one row per contest")
    selected["war_outcome_id"] = [stable_id("WAROUT", *key) for key in selected[KEYS].itertuples(index=False, name=None)]
    selected["build_run_id"] = run_id
    selected["validation_status"] = "passed"
    return selected


def context_features(panel: pd.DataFrame, run_id: str, source_file_id: str) -> pd.DataFrame:
    rows = []
    for row in panel.itertuples():
        dem_inc = optional_incumbent(row.dem_incumbent)
        rep_inc = optional_incumbent(row.rep_incumbent)
        balance = None if pd.isna(row.incumbency_balance) else int(float(row.incumbency_balance))
        if balance not in {None, -1, 0, 1}:
            raise ValueError(f"Invalid incumbency balance for {row.state_code} {row.cycle}")
        rows.append(
            {
                "context_feature_id": stable_id("WARCTX", row.state_code, row.cycle, row.chamber, row.district),
                "build_run_id": run_id,
                "source_file_id": source_file_id,
                "state_code": row.state_code,
                "cycle": int(row.cycle),
                "chamber": row.chamber,
                "district": row.district,
                "baseline_dem_margin": nullable(row.baseline_dem_margin),
                "baseline_source": nullable(row.baseline_source),
                "baseline_office": nullable(row.baseline_office),
                "baseline_class": nullable(row.baseline_class),
                "baseline_quality": nullable(row.baseline_quality),
                "baseline_coverage": nullable(row.baseline_coverage),
                "baseline_source_path": nullable(row.baseline_source_path),
                "strict_baseline_eligible": integer_flag(row.strict_baseline_eligible),
                "research_baseline_eligible": integer_flag(row.research_baseline_eligible),
                "dem_incumbent": dem_inc,
                "rep_incumbent": rep_inc,
                "incumbency_balance": balance,
                "incumbency_source": nullable(row.incumbency_source),
                "incumbency_quality": clean(row.incumbency_quality) or "missing",
                "strict_incumbency_eligible": integer_flag(row.strict_incumbency_eligible),
                "source_panel_observation_id": nullable(row.observation_id),
            }
        )
    result = pd.DataFrame(rows)
    if result.duplicated(KEYS).any():
        raise ValueError("Context features violate the declared one-row contest grain")
    return result


def alabama_2026_roster(connection, run_id: str) -> pd.DataFrame:
    workbook = pd.read_excel(INCUMBENCY_WORKBOOK, sheet_name="Incumbents")
    workbook = workbook[workbook.Coverage_Status.eq("Populated")].copy()
    if len(workbook) != 140 or set(workbook.State) != {"AL"} or set(workbook.Year) != {2026}:
        raise ValueError("Only the populated Alabama 2026 workbook tranche may be promoted")
    workbook["state_code"] = "AL"
    workbook["cycle"] = 2026
    workbook["chamber"] = workbook.Chamber.map({"House": "lower", "Senate": "upper"})
    workbook["district"] = workbook.District.map(normalized_district)
    workbook["name_key"] = workbook.Incumbent.map(normalized_name)
    workbook["incumbent_ran"] = workbook.Incumbent_Ran.map({"Yes": 1, "No": 0})
    workbook["open_seat"] = workbook.Open_Seat.map({"Yes": 1, "No": 0})
    if workbook[["chamber", "incumbent_ran", "open_seat"]].isna().any().any():
        raise ValueError("Workbook has an unrecognized chamber or Yes/No value")
    if not (workbook.incumbent_ran + workbook.open_seat).eq(1).all():
        raise ValueError("Workbook incumbent-running and open-seat flags conflict")

    evidence = pd.read_sql_query(
        """SELECT * FROM source_southern_incumbency_evidence
           WHERE state_code='AL' AND cycle=2026""",
        connection,
    )
    evidence["name_key"] = evidence.incumbent_name.map(normalized_name)
    evidence["district"] = evidence.district.map(normalized_district)
    joined = workbook.merge(
        evidence[["incumbency_evidence_id", "cycle", "state_code", "chamber", "district", "name_key"]],
        on=["cycle", "state_code", "chamber", "district", "name_key"],
        how="left",
        validate="one_to_one",
    )
    if joined.incumbency_evidence_id.isna().any() or len(evidence) != 140:
        raise ValueError("Warehouse incumbency evidence does not reproduce the workbook")

    existing = pd.read_csv(EXISTING_2026_RACE_INCUMBENCY)
    existing["state_code"] = "AL"
    existing["cycle"] = pd.to_numeric(existing.cycle, errors="raise").astype(int)
    existing["chamber"] = existing.chamber.map({"house": "lower", "senate": "upper"})
    existing["district"] = existing.district.map(normalized_district)
    joined = joined.merge(
        existing[["cycle", "state_code", "chamber", "district", "incumbency_status"]],
        on=KEYS,
        how="left",
        validate="one_to_one",
    )

    rows = []
    for row in joined.itertuples():
        workbook_status = "incumbent_running" if row.incumbent_ran else "open"
        if pd.isna(row.incumbency_status):
            comparison, review = "existing_roster_unavailable", "proposed"
            rationale = "No existing race-level incumbency observation; populated workbook supplies provisional evidence."
        elif row.incumbency_status == workbook_status:
            comparison, review = "agrees", "approved"
            rationale = "Populated workbook and existing candidate-derived race roster agree."
        else:
            comparison, review = "workbook_supported_correction", "proposed"
            rationale = (
                f"Populated workbook identifies {row.Incumbent} as running, while the existing "
                f"candidate-derived race roster reports {row.incumbency_status}; retain correction for review."
            )
        family = party_family(row.Party)
        dem_inc = int(row.incumbent_ran and family == "democratic")
        rep_inc = int(row.incumbent_ran and family == "republican")
        rows.append(
            {
                "roster_id": stable_id("AL26INC", row.chamber, row.district),
                "build_run_id": run_id,
                "incumbency_evidence_id": row.incumbency_evidence_id,
                "cycle": 2026,
                "state_code": "AL",
                "chamber": row.chamber,
                "district": row.district,
                "incumbent_name": row.Incumbent,
                "party_family": family,
                "incumbent_ran": int(row.incumbent_ran),
                "open_seat": int(row.open_seat),
                "dem_incumbent": dem_inc,
                "rep_incumbent": rep_inc,
                "incumbency_balance": dem_inc - rep_inc,
                "existing_roster_status": nullable(row.incumbency_status),
                "comparison_status": comparison,
                "review_status": review,
                "resolution_rationale": rationale,
                "evidence_method": row.Method,
                "evidence_url": nullable(row.Roster_Source_URL),
            }
        )
    result = pd.DataFrame(rows)
    if result.duplicated(["cycle", "state_code", "chamber", "district"]).any():
        raise ValueError("Alabama 2026 incumbency roster is not one row per seat")
    return result


def insert_frame(connection, table: str, frame: pd.DataFrame) -> None:
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    values = []
    for row in frame.to_dict("records"):
        values.append(tuple(None if pd.isna(row.get(column)) else row.get(column) for column in columns))
    connection.executemany(
        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
        values,
    )


def read_finance_training(connection) -> pd.DataFrame:
    frame = pd.read_sql_query(FINANCE_QUERY, connection)
    if frame.empty or frame[KEYS].isna().any().any() or frame.duplicated(KEYS).any():
        raise ValueError("Finance export requires nonempty unique race keys")
    if frame.loc[~frame.finance_complete.eq(1), FINANCE_COLUMNS].notna().any().any():
        raise ValueError("Incomplete finance rows contain numeric features; repair the source view")
    return frame


def export_finance_only(database: Path | None = None, output_dir: Path = OUT) -> dict:
    """Refresh one compatibility CSV, not its warehouse or sibling exports."""
    with closing(connect(database, readonly=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        frame = read_finance_training(connection)
        view_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='mart_southern_war_training_with_finance'"
        ).fetchone()[0]
        source_runs = sorted(frame.build_run_id.dropna().unique().tolist())
        for run_id in source_runs:
            run = connection.execute(
                "SELECT status FROM warehouse_build_run WHERE build_run_id=?", (run_id,)
            ).fetchone()
            if run != ("validated",):
                raise ValueError(f"Unvalidated finance export source run: {run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "southern_war_training_with_finance.csv"
    manifest_path = output.with_suffix(".manifest.json")
    payload = frame.to_csv(index=False).encode("utf-8")
    manifest = {
        "contract_version": 1,
        "generated_at_utc": utcnow(),
        "pipeline": Path(__file__).relative_to(ROOT).as_posix(),
        "pipeline_sha256": file_sha256(Path(__file__)),
        "code_version": git_commit(),
        "operation": "export_finance_only",
        "database": (database or database_path()).resolve().name,
        "source_view": "mart_southern_war_training_with_finance",
        "source_view_sql_sha256": hashlib.sha256(view_sql.encode()).hexdigest(),
        "source_query": FINANCE_QUERY,
        "warehouse_run_ids": source_runs,
        "previous_output_sha256": file_sha256(output) if output.exists() else None,
        "output": output.name,
        "output_sha256": hashlib.sha256(payload).hexdigest(),
        "rows": len(frame),
        "incomplete_rows": int((~frame.finance_complete.eq(1)).sum()),
        "validation": {"unique_race_keys": True, "incomplete_numeric_features": 0},
        "scope": "This file only; upstream runs, sibling exports and publications are not revalidated.",
    }
    # The sidecar hash detects interruption between these two file replacements.
    temporary = output.with_suffix(".csv.tmp")
    temporary.write_bytes(payload)
    temporary.replace(output)
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    return manifest


def export(database: Path | None, run_id: str) -> dict:
    with closing(connect(database, readonly=True)) as connection:
        training = pd.read_sql_query(
            "SELECT * FROM mart_southern_war_training_no_finance ORDER BY state_code,cycle,chamber,CAST(district AS INTEGER)",
            connection,
        )
        coverage = pd.read_sql_query(
            "SELECT * FROM qa_southern_war_training_no_finance_coverage ORDER BY state_code,cycle,chamber",
            connection,
        )
        training_with_finance = read_finance_training(connection)
        finance_coverage = pd.read_sql_query(
            "SELECT * FROM qa_southern_war_training_with_finance_coverage "
            "ORDER BY state_code,cycle,chamber", connection,
        )
        roster = pd.read_sql_query(
            "SELECT * FROM mart_alabama_2026_incumbency_roster ORDER BY chamber,CAST(district AS INTEGER)",
            connection,
        )
        run = connection.execute(
            "SELECT code_commit,validation_json FROM warehouse_build_run WHERE build_run_id=?", (run_id,)
        ).fetchone()
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    training.to_csv(OUT / "southern_war_training_no_finance.csv", index=False)
    coverage.to_csv(OUT / "southern_war_training_no_finance_coverage.csv", index=False)
    training_with_finance.to_csv(OUT / "southern_war_training_with_finance.csv", index=False)
    finance_coverage.to_csv(OUT / "southern_war_training_with_finance_coverage.csv", index=False)
    roster.to_csv(OUT / "alabama_2026_incumbency_roster.csv", index=False)
    roster[roster.comparison_status.ne("agrees")].to_csv(
        OUT / "alabama_2026_incumbency_review.csv", index=False
    )
    manifest = {
        "contract_version": 1,
        "pipeline": "scripts/load_southern_war_preparation_warehouse.py",
        "build_run_id": run_id,
        "code_version": run[0],
        "finance_included": True,
        "finance_missingness_policy": (
            "Finance remains null unless both candidate observations and identities are complete; "
            "the finance-free interface remains available for sensitivity analysis."
        ),
        "validation": json.loads(run[1]),
        "inputs": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": file_sha256(path)}
            for path in [PANEL, PANEL_MANIFEST, INCUMBENCY_WORKBOOK, EXISTING_2026_RACE_INCUMBENCY]
        ],
    }
    (OUT / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def build(database: Path | None = None) -> dict:
    panel = read_panel()
    with closing(connect(database)) as connection:
        initialize(connection)
        required = {
            "all_southern_legislative_candidate_election_observations",
            "fact_southern_legislative_final_candidate_election",
            "source_southern_incumbency_evidence",
        }
        available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        if not required.issubset(available):
            raise RuntimeError(f"Required warehouse inputs missing: {sorted(required-available)}")
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run_id = begin_run(
            connection,
            "southern_war_preparation_no_finance",
            {
                "cycles": "2016-2024 outcomes/context plus Alabama 2026 incumbency",
                "finance_included": True,
                "outcome_rule": "exactly one positive-vote D and R; provider dontuse/uncont excluded",
                "alabama_contest_totals": (
                    "canonical candidates bridged to certified canvass cells; scalar source file and "
                    "third-party votes from the bridged certified set; disagreement fails the build"
                ),
            },
        )
        panel_source_id = register_source_file(
            connection,
            provider="Project Southern WAR panel v1",
            path=PANEL,
            media_type="text/csv",
            license_name="internal derived research artifact",
            extraction_status="normalized",
            authoritative_scope="Versioned realized ticket-baseline and incumbency context",
        )
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM mart_southern_war_outcome")
        connection.execute("DELETE FROM mart_southern_war_context_feature")
        connection.execute("DELETE FROM mart_alabama_2026_incumbency_roster")

        outcomes = select_model_outcomes(connection, run_id, panel, panel_source_id)
        contexts = context_features(panel, run_id, panel_source_id)
        roster = alabama_2026_roster(connection, run_id)
        insert_frame(connection, "mart_southern_war_outcome", outcomes)
        insert_frame(connection, "mart_southern_war_context_feature", contexts)
        insert_frame(connection, "mart_alabama_2026_incumbency_roster", roster)

        training_status = dict(
            connection.execute(
                "SELECT training_status,COUNT(*) FROM mart_southern_war_training_no_finance GROUP BY 1"
            ).fetchall()
        )
        finance_training_status = dict(
            connection.execute(
                "SELECT evaluation_status,COUNT(*) "
                "FROM mart_southern_war_training_with_finance GROUP BY 1"
            ).fetchall()
        )
        history_schedule = {
            (row[0], int(row[1]), row[2])
            for row in connection.execute(
                "SELECT DISTINCT state_code,cycle,chamber "
                "FROM qa_southern_legislative_final_competition_coverage "
                "WHERE cycle BETWEEN 2016 AND 2024"
            )
        }
        expected_schedule = scheduled_war_keys_2016_2024()
        missing_scheduled = sorted(expected_schedule-history_schedule)
        outcome_schedule = set(outcomes[["state_code", "cycle", "chamber"]].itertuples(index=False, name=None))
        unscheduled_outcomes = sorted(outcome_schedule-expected_schedule)
        validation = {
            "model_valid_outcomes": len(outcomes),
            "context_feature_rows": len(contexts),
            "strict_ready_no_finance": training_status.get("strict_war_ready_no_finance", 0),
            "research_ready_no_finance": training_status.get("research_war_ready_no_finance", 0),
            "missing_context": training_status.get("missing_context", 0),
            "missing_baseline": training_status.get("missing_baseline", 0),
            "missing_incumbency": training_status.get("missing_incumbency", 0),
            "strict_ready_with_finance": finance_training_status.get("strict_war_ready_with_finance", 0),
            "research_ready_with_finance": finance_training_status.get("research_war_ready_with_finance", 0),
            "war_ready_finance_unobserved": finance_training_status.get("war_ready_finance_unobserved", 0),
            "scheduled_state_cycle_chambers_expected": len(expected_schedule),
            "scheduled_state_cycle_chambers_observed": len(expected_schedule & history_schedule),
            "missing_scheduled_state_cycle_chambers": missing_scheduled,
            "unscheduled_model_outcome_slices": unscheduled_outcomes,
            "alabama_2026_incumbency_rows": len(roster),
            "alabama_2026_incumbents_running": int(roster.incumbent_ran.sum()),
            "alabama_2026_open_seats": int(roster.open_seat.sum()),
            "alabama_2026_workbook_supported_corrections": int(
                roster.comparison_status.eq("workbook_supported_correction").sum()
            ),
            "finance_included": True,
            "foreign_key_violations": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
        }
        if (
            validation["foreign_key_violations"]
            or len(outcomes) == 0
            or len(contexts) != len(panel)
            or missing_scheduled
            or unscheduled_outcomes
            or validation["missing_context"]
            or validation["missing_baseline"]
            or len(roster) != 140
            or validation["alabama_2026_incumbents_running"]
            + validation["alabama_2026_open_seats"]
            != 140
        ):
            raise ValueError(f"Finance-free WAR preparation validation failed: {validation}")

        register_table(
            connection, "mart_southern_war_outcome", "mart", __file__,
            "war_outcome_id", "Model-valid whole-source set, then canonical authority; explicit Texas companion fallback", "replace",
            "Final regular-cycle D-versus-R legislative outcomes for WAR",
        )
        register_table(
            connection, "mart_southern_war_context_feature", "mart", __file__,
            "context_feature_id", "Versioned Southern WAR panel baseline and incumbency context", "replace",
            "Realized ticket baseline and incumbency features without finance",
        )
        register_table(
            connection, "mart_southern_war_training_no_finance", "mart", __file__,
            "war_outcome_id", "1:0..1 outcome/context join; no finance imputation", "view",
            "Finance-free Southern WAR training interface",
        )
        register_table(
            connection, "mart_southern_war_training_with_finance", "mart", __file__,
            "war_outcome_id", "1:0..1 exact race-key finance join; no finance imputation", "view",
            "Southern WAR training interface with incumbency and fundraising",
        )
        register_table(
            connection, "mart_alabama_2026_incumbency_roster", "mart", __file__,
            "roster_id", "Populated workbook evidence with existing-roster comparison", "replace",
            "Alabama 2026 seat-level incumbency and open-seat evidence",
        )
        register_table(
            connection, "qa_southern_war_training_no_finance_coverage", "qa", __file__,
            "state_code + cycle + chamber", "Observed readiness; missing context remains explicit", "view",
            "Finance-free WAR training readiness by state, cycle, and chamber",
        )
        register_table(
            connection, "qa_southern_war_training_with_finance_coverage", "qa", __file__,
            "state_code + cycle + chamber", "Separates WAR readiness from complete finance observation", "view",
            "WAR and finance readiness by state, cycle, and chamber",
        )
        finish_run(connection, run_id, validation)
        connection.commit()
    return export(database, run_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    parser.add_argument("--export-finance-only", action="store_true",
                        help="Read-only warehouse query; refresh only the finance CSV and its sidecar")
    args = parser.parse_args()
    result = export_finance_only(args.database) if args.export_finance_only else build(args.database)
    print(json.dumps(result["validation"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
