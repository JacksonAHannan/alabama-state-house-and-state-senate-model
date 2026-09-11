"""Build a post-2016 Southern legislative retraining readiness matrix.

This is a read-only audit of existing marts and immutable source files.  It
does not promote any source into the canonical warehouse or treat missing
observations as zero.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "data" / "processed" / "war" / "southern_war_panel_v1"
OUT_DIR = ROOT / "data" / "processed" / "source_audits"
REPORT_PATH = ROOT / "project_docs" / "audits" / "SOUTHERN_POST2016_RETRAINING_GAPS.md"

STATES = ["AL", "AR", "FL", "GA", "KY", "LA", "MS", "MO", "NC", "OK", "SC", "TN", "TX", "VA"]

# Regular general elections only.  Staggered Senate calendars are represented
# explicitly rather than assuming that both chambers run every two years.
SCHEDULE: dict[str, list[tuple[int, str]]] = {
    "AL": [(y, c) for y in (2018, 2022) for c in ("house", "senate")],
    "AR": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "FL": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "GA": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "KY": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "LA": [(y, c) for y in (2019, 2023) for c in ("house", "senate")],
    "MS": [(y, c) for y in (2019, 2023) for c in ("house", "senate")],
    "MO": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "NC": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "OK": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "SC": [(y, "house") for y in (2018, 2020, 2022, 2024)] + [(y, "senate") for y in (2020, 2024)],
    "TN": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "TX": [(y, c) for y in (2018, 2020, 2022, 2024) for c in ("house", "senate")],
    "VA": [(y, "house") for y in (2017, 2019, 2021, 2023)] + [(y, "senate") for y in (2019, 2023)],
}


# These bundles were inspected, not inferred solely from their filenames. A
# complete route contains legislative and same-cycle ticket votes at precinct
# level, sometimes in separately preserved official and RDH/VEST sources.
LOCAL_SOURCE_ROUTES: dict[tuple[str, int], tuple[str, str]] = {
    ("AR", 2024): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2024/ar24.zip",
    ),
    ("AR", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/arkansas_2022_openelections/counties/",
    ),
    ("FL", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/2022-gen-outputofficial.zip",
    ),
    ("FL", 2024): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/2024-gen-outputofficial1.zip",
    ),
    ("GA", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/ga_2022_gen_prec.zip",
    ),
    ("GA", 2024): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/ga_2024_gen_prec_csv.zip",
    ),
    ("KY", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2022/2022-ky-local-precinct-general.zip",
    ),
    ("KY", 2024): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2024/ky24.zip",
    ),
    ("LA", 2019): (
        "complete_bundle_downloaded",
        "data/raw/southern_sos_elections/LA/2019/",
    ),
    ("LA", 2023): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/la_2023_gen_prim_pber.zip",
    ),
    ("MS", 2023): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/ms_gen_2023_prec.zip",
    ),
    ("MO", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2022/2022-mo-local-precinct-general.zip",
    ),
    ("NC", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/results_pct_20221108.zip",
    ),
    ("NC", 2024): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/results_pct_20241105.zip",
    ),
    ("OK", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2022/2022-ok-local-precinct-general.zip",
    ),
    ("OK", 2024): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2024/ok24.zip",
    ),
    ("SC", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2022/2022-sc-local-precinct-general.zip",
    ),
    ("SC", 2024): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2024/sc24.zip",
    ),
    ("TN", 2022): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/tn_2022_gen_prec.zip",
    ),
    ("TN", 2024): (
        "complete_bundle_downloaded",
        "data/raw/historical_statewide_elections/medsl_github/2024/tn24.zip",
    ),
    ("VA", 2017): (
        "ticket_only_downloaded",
        "data/raw/southern_sos_elections/VA/va_vest_17.zip",
    ),
    ("VA", 2019): (
        "legislative_results_downloaded_no_ticket",
        "data/raw/southern_sos_elections/VA/",
    ),
    ("VA", 2021): (
        "ticket_only_downloaded",
        "data/raw/southern_sos_elections/VA/va_vest_21.zip",
    ),
    ("VA", 2023): (
        "legislative_results_downloaded_no_ticket",
        "data/raw/southern_sos_elections/VA/Election Results_2023.csv",
    ),
}


# Virginia had legislative-only general elections in these years.  A missing
# same-cycle statewide/federal ticket is a property of the election calendar,
# not a missing download.
NO_SAME_CYCLE_TICKET = {("VA", 2019), ("VA", 2023)}


DEMOGRAPHIC_UNIFIED_STATES = {"AR", "GA", "LA", "MS", "TN", "TX"}
ALABAMA_DEMOGRAPHIC_CYCLES = {2018, 2022}


def _bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    values = frame[column]
    if values.dtype == bool:
        return values
    return values.astype(str).str.lower().eq("true")


def _source_route(state: str, year: int, strict_ready: int, contested: int) -> tuple[str, str]:
    route = LOCAL_SOURCE_ROUTES.get((state, year))
    if route:
        path = ROOT / route[1]
        if not path.exists():
            raise FileNotFoundError(f"Audited local source disappeared: {route[1]}")
        return route
    if contested and strict_ready == contested:
        return "integrated_current_panel", ""
    if contested:
        return "partial_or_legislative_only_current", ""
    if state == "TX":
        return "integrated_texas_repository", "C:/Users/User/Documents/GitHub/texas-state-house-and-state-senate-model/"
    return "no_complete_local_bundle_identified", ""


def _demographic_status(state: str, year: int) -> tuple[str, int | None]:
    if state == "AL" and year in ALABAMA_DEMOGRAPHIC_CYCLES:
        return "state_specific_ready", year
    if state in DEMOGRAPHIC_UNIFIED_STATES:
        reference_year = 2024 if year == 2023 else year
        return "unified_ready", reference_year
    return "not_in_unified_mart", None


def _finance_status(state: str) -> str:
    if state == "AL":
        return "harmonized_ready"
    if state == "TX":
        return "processed_not_integrated"
    return "comparable_candidate_finance_missing"


def _next_action(
    *,
    outcome_status: str,
    baseline_status: str,
    incumbency_status: str,
    local_source_status: str,
    demographics_status: str,
    finance_status: str,
) -> str:
    actions: list[str] = []
    if outcome_status == "missing_current_panel":
        if local_source_status == "complete_bundle_downloaded":
            actions.append("normalize_local_outcomes")
        elif local_source_status == "legislative_results_downloaded_no_ticket":
            actions.append("normalize_local_outcomes")
        elif local_source_status == "ticket_only_downloaded":
            actions.append("acquire_legislative_outcomes")
        else:
            actions.append("acquire_legislative_outcomes")
    if baseline_status == "missing":
        if local_source_status == "complete_bundle_downloaded":
            actions.append("normalize_local_ticket_context")
        elif local_source_status == "ticket_only_downloaded":
            actions.append("normalize_local_ticket_context")
        else:
            actions.append("acquire_precinct_ticket_context")
    elif baseline_status == "synthetic_only":
        if local_source_status == "complete_bundle_downloaded":
            actions.append("replace_synthetic_baseline_from_local_bundle")
        else:
            actions.append("acquire_observed_ticket_context")
    elif baseline_status == "partial_observed":
        actions.append("adjudicate_unmatched_ticket_districts")
    elif baseline_status == "not_applicable_no_same_cycle_ticket":
        actions.append("define_offyear_baseline_policy")
    if incumbency_status == "experimental_only":
        actions.append("review_incumbency")
    elif incumbency_status == "accepted_partial":
        actions.append("complete_incumbency_review")
    elif incumbency_status == "missing":
        actions.append("build_incumbency")
    if demographics_status == "not_in_unified_mart":
        actions.append("build_harmonized_district_demographics")
    if finance_status == "processed_not_integrated":
        actions.append("integrate_candidate_finance")
    elif finance_status == "comparable_candidate_finance_missing":
        actions.append("acquire_harmonized_candidate_finance")
    return ";".join(dict.fromkeys(actions)) or "ready_for_retraining"


def build_matrix() -> pd.DataFrame:
    coverage = pd.read_csv(PANEL_DIR / "southern_war_panel_coverage.csv")
    panel = pd.read_csv(PANEL_DIR / "southern_war_panel.csv", low_memory=False)
    panel["outcome_eligible"] = _bool_series(panel, "outcome_eligible")
    panel["strict_incumbency_eligible"] = _bool_series(panel, "strict_incumbency_eligible")
    panel["strict_baseline_eligible"] = _bool_series(panel, "strict_baseline_eligible")
    panel["research_baseline_eligible"] = _bool_series(panel, "research_baseline_eligible")

    incumbency = (
        panel.loc[panel["outcome_eligible"]]
        .groupby(["state", "year", "chamber"], as_index=False)
        .agg(
            accepted_incumbency_races=("strict_incumbency_eligible", "sum"),
            observed_baseline_races=("strict_baseline_eligible", "sum"),
            research_baseline_races=("research_baseline_eligible", "sum"),
            incumbency_quality_values=("incumbency_quality", lambda x: "|".join(sorted(set(x.dropna().astype(str))))),
        )
    )
    coverage = coverage.merge(incumbency, on=["state", "year", "chamber"], how="left")
    lookup = coverage.set_index(["state", "year", "chamber"]).to_dict("index")

    rows: list[dict[str, object]] = []
    for state in STATES:
        for year, chamber in SCHEDULE[state]:
            current = lookup.get((state, year, chamber), {})
            outcome_rows = int(current.get("outcome_rows", 0) or 0)
            contested = int(current.get("contested_outcomes", 0) or 0)
            strict_war = int(current.get("strict_war_ready", 0) or 0)
            research_war = int(current.get("research_war_ready", 0) or 0)
            observed_baselines = int(current.get("observed_baseline_races", 0) or 0)
            research_baselines = int(current.get("research_baseline_races", 0) or 0)
            accepted_inc = int(current.get("accepted_incumbency_races", 0) or 0)

            if not outcome_rows:
                outcome_status = "missing_current_panel"
            elif year == 2024 and outcome_rows == contested:
                outcome_status = "contested_only_current"
            else:
                outcome_status = "current_panel"

            if contested and observed_baselines == contested:
                baseline_status = "complete_observed"
            elif observed_baselines:
                baseline_status = "partial_observed"
            elif contested and research_baselines == contested:
                baseline_status = "synthetic_only"
            else:
                baseline_status = "missing"
            if (state, year) in NO_SAME_CYCLE_TICKET:
                baseline_status = "not_applicable_no_same_cycle_ticket"

            if contested and accepted_inc == contested:
                incumbency_status = "accepted_complete"
            elif accepted_inc:
                incumbency_status = "accepted_partial"
            elif contested:
                incumbency_status = "experimental_only"
            else:
                incumbency_status = "missing"

            if contested and strict_war == contested and accepted_inc == contested:
                core_status = "ready"
            elif strict_war:
                core_status = "partial"
            elif contested and research_war == contested:
                core_status = "research_only"
            else:
                core_status = "not_ready"

            local_status, local_path = _source_route(state, year, strict_war, contested)
            demographics_status, demographics_reference_year = _demographic_status(state, year)
            finance_status = _finance_status(state)

            if core_status == "ready" and demographics_status != "not_in_unified_mart":
                basic_forecast_status = "ready"
            elif local_status == "complete_bundle_downloaded" or core_status in {"partial", "research_only"}:
                basic_forecast_status = "repairable_from_local_or_current_sources"
            else:
                basic_forecast_status = "not_ready"

            full_forecast_status = (
                "ready"
                if basic_forecast_status == "ready" and finance_status == "harmonized_ready"
                else "not_ready"
            )
            next_action = _next_action(
                outcome_status=outcome_status,
                baseline_status=baseline_status,
                incumbency_status=incumbency_status,
                local_source_status=local_status,
                demographics_status=demographics_status,
                finance_status=finance_status,
            )
            if core_status == "ready":
                priority = 3 if full_forecast_status != "ready" else 4
            elif local_status == "complete_bundle_downloaded":
                priority = 1
            elif local_status in {"ticket_only_downloaded", "legislative_results_downloaded_no_ticket"} or strict_war or research_war:
                priority = 2
            else:
                priority = 3

            rows.append(
                {
                    "state": state,
                    "year": year,
                    "chamber": chamber,
                    "outcome_rows_current": outcome_rows,
                    "contested_races_current": contested,
                    "outcome_status": outcome_status,
                    "observed_baseline_races": observed_baselines,
                    "research_baseline_races": research_baselines,
                    "baseline_status": baseline_status,
                    "accepted_incumbency_races": accepted_inc,
                    "accepted_incumbency_gap_known_current": (contested - accepted_inc) if contested else pd.NA,
                    "incumbency_status": incumbency_status,
                    "incumbency_quality_values": current.get("incumbency_quality_values", "") or "",
                    "local_source_status": local_status,
                    "local_source_path": local_path,
                    "demographics_status": demographics_status,
                    "demographics_reference_year": demographics_reference_year,
                    "finance_status": finance_status,
                    "strict_war_races_current": strict_war,
                    "research_war_races_current": research_war,
                    "strict_war_gap_known_current": (contested - strict_war) if contested else pd.NA,
                    "core_war_status": core_status,
                    "basic_forecast_status": basic_forecast_status,
                    "full_forecast_status": full_forecast_status,
                    "priority_tier": priority,
                    "next_action": next_action,
                }
            )

    result = pd.DataFrame(rows).sort_values(["priority_tier", "state", "year", "chamber"], kind="stable")
    assert len(result) == 96, f"Expected 96 scheduled rows, got {len(result)}"
    assert not result.duplicated(["state", "year", "chamber"]).any()
    assert set(result["state"]) == set(STATES)
    assert result[["outcome_rows_current", "contested_races_current", "observed_baseline_races"]].ge(0).all().all()
    return result


def build_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for state, group in matrix.groupby("state", sort=True):
        actions = Counter(
            action
            for value in group["next_action"]
            for action in str(value).split(";")
            if action and action != "ready_for_retraining"
        )
        records.append(
            {
                "state": state,
                "scheduled_state_cycle_chambers": len(group),
                "current_contested_races": int(group["contested_races_current"].sum()),
                "strict_war_races": int(group["strict_war_races_current"].sum()),
                "known_current_races_not_strict": int(pd.to_numeric(group["strict_war_gap_known_current"], errors="coerce").sum()),
                "core_war_ready": int(group["core_war_status"].eq("ready").sum()),
                "core_war_partial": int(group["core_war_status"].eq("partial").sum()),
                "core_war_research_only": int(group["core_war_status"].eq("research_only").sum()),
                "core_war_not_ready": int(group["core_war_status"].eq("not_ready").sum()),
                "downloaded_complete_bundles_to_normalize": int(
                    (
                        (group["local_source_status"] == "complete_bundle_downloaded")
                        & (group["core_war_status"] != "ready")
                        & group["next_action"].str.contains("normalize_local|replace_synthetic")
                    ).sum()
                ),
                "rows_needing_new_election_data": int(
                    group["next_action"].str.contains("acquire_legislative_outcomes|acquire_precinct_ticket_context|acquire_observed_ticket_context", regex=True).sum()
                ),
                "demographics_ready": int(group["demographics_status"].ne("not_in_unified_mart").sum()),
                "finance_ready": int(group["finance_status"].eq("harmonized_ready").sum()),
                "basic_forecast_ready": int(group["basic_forecast_status"].eq("ready").sum()),
                "full_forecast_ready": int(group["full_forecast_status"].eq("ready").sum()),
                "remaining_action_counts": "|".join(f"{key}:{value}" for key, value in sorted(actions.items())),
            }
        )
    result = pd.DataFrame(records)
    assert int(result["scheduled_state_cycle_chambers"].sum()) == len(matrix)
    assert int(result["core_war_ready"].sum()) == int(matrix["core_war_status"].eq("ready").sum())
    return result


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a small Markdown table without pandas' optional tabulate extra."""
    clean = frame.fillna("").astype(str)
    headers = list(clean.columns)
    rows = [headers, ["---"] * len(headers)] + clean.values.tolist()
    return "\n".join("| " + " | ".join(value.replace("|", "\\|") for value in row) + " |" for row in rows)


def write_report(matrix: pd.DataFrame, summary: pd.DataFrame) -> None:
    core_counts = matrix["core_war_status"].value_counts().to_dict()
    local_repair = matrix[
        (matrix["core_war_status"] != "ready")
        & matrix["local_source_status"].isin(
            ["complete_bundle_downloaded", "ticket_only_downloaded", "legislative_results_downloaded_no_ticket"]
        )
        & matrix["next_action"].str.contains("normalize_local|replace_synthetic")
    ]
    acquire = matrix[
        matrix["next_action"].str.contains(
            "acquire_legislative_outcomes|acquire_precinct_ticket_context|acquire_observed_ticket_context", regex=True
        )
    ]

    lines = [
        "# Southern post-2016 legislative retraining gaps",
        "",
        "Generated by `scripts/audit_southern_post2016_retraining_gaps.py` from the current read-only Southern WAR panel and inspected local source files.",
        "",
        "## Scope and readiness rules",
        "",
        "The universe is 96 scheduled state-cycle-chamber general elections in AL, AR, FL, GA, KY, LA, MS, MO, NC, OK, SC, TN, TX, and VA from 2017 through 2024. `Core WAR ready` requires contested Democratic/Republican outcomes, an observed same-cycle federal or statewide district baseline, and accepted incumbency for every current contested race. `Basic forecast ready` additionally requires harmonized district demographics. `Full forecast ready` additionally requires comparable candidate finance.",
        "",
        "A downloaded ZIP is not counted as integrated. Synthetic presidential or environment estimates are research-only and are not counted as observed ticket context. Missing finance is not converted to zero.",
        "",
        "## Headline",
        "",
        f"- Core WAR ready now: **{core_counts.get('ready', 0)} of {len(matrix)}** state-cycle-chambers.",
        f"- Strict WAR-ready contested races now: **{int(matrix['strict_war_races_current'].sum()):,} of {int(matrix['contested_races_current'].sum()):,} currently observed contests**.",
        f"- Partial observed coverage: **{core_counts.get('partial', 0)}**.",
        f"- Research-only coverage: **{core_counts.get('research_only', 0)}**.",
        f"- Not ready in the current panel: **{core_counts.get('not_ready', 0)}**.",
        f"- Non-ready rows with useful local election bundles already downloaded: **{len(local_repair)}**.",
        f"- Rows still requiring at least one newly acquired election-result component: **{len(acquire)}**.",
        f"- Full forecast ready under the strict finance definition: **{int(matrix['full_forecast_status'].eq('ready').sum())} of {len(matrix)}**.",
        "",
        "## State summary",
        "",
        _markdown_table(summary[
            [
                "state",
                "scheduled_state_cycle_chambers",
                "current_contested_races",
                "strict_war_races",
                "core_war_ready",
                "core_war_partial",
                "core_war_research_only",
                "core_war_not_ready",
                "downloaded_complete_bundles_to_normalize",
                "rows_needing_new_election_data",
                "demographics_ready",
                "finance_ready",
                "full_forecast_ready",
            ]
        ]),
        "",
        "## First queue: normalize what is already local",
        "",
        _markdown_table(local_repair[
            ["state", "year", "chamber", "core_war_status", "local_source_status", "local_source_path", "next_action"]
        ]),
        "",
        "## Second queue: acquire or repair election inputs",
        "",
        _markdown_table(acquire[
            ["state", "year", "chamber", "outcome_status", "baseline_status", "incumbency_status", "next_action"]
        ]),
        "",
        "## Supporting-feature gaps",
        "",
        "Alabama has state-specific demographics and harmonized finance for its scheduled cycles. Texas has unified demographics and a processed historical finance table in the sibling repository, but that finance has not yet been integrated into this Southern mart. AR, GA, LA, MS, and TN have unified demographic rows but no comparable candidate-finance panel. FL, KY, MO, NC, OK, SC, and VA still need harmonized district demographics as well as comparable candidate finance.",
        "",
        "## Outputs",
        "",
        "- `data/processed/source_audits/southern_post2016_legislative_gap_matrix.csv`: full 96-row audit.",
        "- `data/processed/source_audits/southern_post2016_legislative_gap_summary.csv`: state summary and action counts.",
        "",
        "## Limitations",
        "",
        "The current 2024 MEDSL legislative files frequently contain only contested legislative races, so `contested_only_current` does not mean a complete ballot universe. The matrix evaluates readiness of the observed contested training sample, not uncontested-seat completeness. Louisiana outcomes come from the SOS two-stage precinct exports; modern ticket context comes from the separate RDH/VEST bundles and is selected to match each district's final election stage. Candidate finance is intentionally held to a stricter standard than election outcomes because cross-state filing systems and definitions are not yet harmonized.",
        "",
        "Virginia 2019 and 2023 were legislative-only general elections, so no same-cycle statewide or federal ticket baseline exists to acquire. Their remaining baseline gap is methodological. The supplied Virginia 2025 file contains all 100 House districts and statewide races and can be added as a later validation cycle, but 2025 is outside this audit's through-2024 training window.",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix = build_matrix()
    summary = build_summary(matrix)
    matrix.to_csv(OUT_DIR / "southern_post2016_legislative_gap_matrix.csv", index=False)
    summary.to_csv(OUT_DIR / "southern_post2016_legislative_gap_summary.csv", index=False)
    write_report(matrix, summary)
    print(
        f"Wrote {len(matrix)} scheduled rows; "
        f"core ready={int(matrix.core_war_status.eq('ready').sum())}, "
        f"local repair queue={int(((matrix.core_war_status != 'ready') & matrix.local_source_status.isin(['complete_bundle_downloaded', 'ticket_only_downloaded', 'legislative_results_downloaded_no_ticket']) & matrix.next_action.str.contains('normalize_local|replace_synthetic')).sum())}."
    )


if __name__ == "__main__":
    main()
