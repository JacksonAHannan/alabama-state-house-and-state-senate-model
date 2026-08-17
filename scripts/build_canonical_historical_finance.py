"""Build source-prioritized historical candidate and race finance marts.

The mart deliberately distinguishes an observed zero from an unmatched candidate.
DIME is authoritative for 1998-2010 and Alabama FCPA PCC summaries for 2014-2022.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
ELECTIONS = ROOT / "data" / "processed" / "elections"
MANUAL = ROOT / "data" / "manual" / "finance"
DOC = ROOT / "project_docs" / "audits" / "HISTORICAL_FINANCE_RECOVERY.md"
SMOOTHING_DOLLARS = 500.0
KEY = ["cycle", "chamber", "district", "party"]


def candidate_universe() -> pd.DataFrame:
    candidates = pd.read_csv(ELECTIONS / "canonical_cmo_candidates.csv").rename(
        columns={"year": "cycle", "canonical_party": "party", "canonical_name": "candidate"}
    )
    races = pd.read_csv(WAR / "preliminary_cmo_races.csv", usecols=["cycle", "chamber", "district", "war_eligible"])
    candidates = candidates.merge(
        races[races.war_eligible.astype(bool)].drop(columns="war_eligible"),
        on=["cycle", "chamber", "district"], how="inner", validate="many_to_one"
    )
    return candidates[candidates.party.isin(["D", "R"])].copy()


def dime_rows() -> pd.DataFrame:
    dime = pd.read_csv(WAR / "dime_candidate_finance_matches.csv")
    dime = dime[dime.review_status.eq("accepted") & dime.year.between(1998, 2010)].copy()
    dime = dime.rename(columns={"year": "cycle", "total_receipts": "total_fundraising"})
    dime["finance_observation_status"] = "observed_positive"
    dime.loc[dime.total_fundraising.eq(0), "finance_observation_status"] = "observed_zero"
    dime["source_name"] = "DIME/FollowTheMoney recipient totals"
    dime["source_measure"] = "total_receipts"
    dime["source_priority"] = 1
    dime["aggregation_status"] = "accepted_candidate_match"
    return dime


def fcpa_rows() -> pd.DataFrame:
    fcpa = pd.read_csv(WAR / "fcpa_candidate_cycle_finance.csv")
    fcpa = fcpa[fcpa.cycle.between(2014, 2022)].copy()
    fcpa = fcpa.rename(columns={"fundraising_total": "total_fundraising"})
    fcpa["finance_observation_status"] = np.where(
        fcpa.aggregation_status.eq("committee_found_no_cycle_activity"), "observed_zero", "observed_positive"
    )
    fcpa["source_name"] = "Alabama FCPA principal campaign committee summaries"
    fcpa["source_measure"] = "cash_contributions_plus_other_receipts"
    fcpa["source_priority"] = 1
    return fcpa


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    universe = candidate_universe()
    dime = dime_rows()
    fcpa = fcpa_rows()

    # DIME is candidate-ID keyed; FCPA is uniquely candidate-cycle/district/party keyed.
    left = universe.rename(columns={"canonical_candidate_id": "universe_candidate_id"})
    dime_part = dime[["canonical_candidate_id", "total_fundraising", "finance_observation_status",
                      "source_name", "source_measure", "source_priority", "aggregation_status",
                      "match_score", "match_margin"]]
    out = left.merge(dime_part, left_on="universe_candidate_id", right_on="canonical_candidate_id", how="left", validate="one_to_one")
    out["canonical_candidate_id"] = out.universe_candidate_id
    fcpa_part = fcpa[[*KEY, "total_fundraising", "finance_observation_status", "source_name",
                      "source_measure", "source_priority", "aggregation_status"]].assign(
                          match_score=np.nan, match_margin=np.nan)
    out = out.merge(fcpa_part, on=KEY, how="left", validate="one_to_one", suffixes=("", "_fcpa"))
    use_fcpa = out.cycle.ge(2014)
    for col in ["total_fundraising", "finance_observation_status", "source_name", "source_measure",
                "source_priority", "aggregation_status", "match_score", "match_margin"]:
        other = f"{col}_fcpa"
        if other in out:
            out.loc[use_fcpa, col] = out.loc[use_fcpa, other]
            out = out.drop(columns=other)
    out["finance_observation_status"] = out.finance_observation_status.fillna("unknown_unmatched")
    out["source_name"] = out.source_name.fillna("none")
    out["source_measure"] = out.source_measure.fillna("unknown")
    out["aggregation_status"] = out.aggregation_status.fillna("unmatched")
    keep = ["canonical_candidate_id", "cycle", "chamber", "district", "party", "candidate",
            "total_fundraising", "finance_observation_status", "source_name", "source_measure",
            "aggregation_status", "match_score", "match_margin"]
    candidate = out[keep].sort_values(KEY).reset_index(drop=True)

    wide = candidate.pivot(index=["cycle", "chamber", "district"], columns="party",
                           values="total_fundraising").rename(columns={"D": "dem_fundraising", "R": "rep_fundraising"}).reset_index()
    statuses = candidate.pivot(index=["cycle", "chamber", "district"], columns="party",
                               values="finance_observation_status").rename(columns={"D": "dem_finance_status", "R": "rep_finance_status"}).reset_index()
    sources = candidate.pivot(index=["cycle", "chamber", "district"], columns="party",
                              values="source_name").rename(columns={"D": "dem_finance_source", "R": "rep_finance_source"}).reset_index()
    race = wide.merge(statuses, on=["cycle", "chamber", "district"], validate="one_to_one").merge(
        sources, on=["cycle", "chamber", "district"], validate="one_to_one")
    race["canonical_finance_complete"] = race[["dem_fundraising", "rep_fundraising"]].notna().all(axis=1).astype(int)
    race["canonical_log_fundraising_ratio_d_to_r"] = np.where(
        race.canonical_finance_complete.eq(1),
        np.log((race.dem_fundraising + SMOOTHING_DOLLARS) / (race.rep_fundraising + SMOOTHING_DOLLARS)),
        np.nan,
    )
    race["finance_smoothing_dollars"] = SMOOTHING_DOLLARS

    coverage = race.groupby("cycle", as_index=False).agg(
        eligible_races=("district", "size"), complete_races=("canonical_finance_complete", "sum")
    )
    coverage["coverage_rate"] = coverage.complete_races / coverage.eligible_races
    return candidate, race.sort_values(["cycle", "chamber", "district"]), coverage


def write_review_and_archival(candidate: pd.DataFrame) -> None:
    MANUAL.mkdir(parents=True, exist_ok=True)
    review = candidate[candidate.finance_observation_status.eq("unknown_unmatched")].copy()
    review["resolution"] = "pending_manual_or_archival_research"
    review.to_csv(WAR / "canonical_historical_finance_review.csv", index=False)
    archival = review[review.cycle.eq(1994)][["canonical_candidate_id", "cycle", "chamber", "district", "party", "candidate"]].copy()
    archival["requested_record"] = "candidate PCC receipts/summary for full election cycle"
    archival["preferred_authority"] = "Alabama Secretary of State FCPA archive; ADAH if transferred"
    archival["missing_is_zero"] = False
    archival.to_csv(MANUAL / "historical_finance_archival_requests.csv", index=False)


def write_doc(coverage: pd.DataFrame, candidate: pd.DataFrame) -> None:
    lines = [
        "# Historical Finance Recovery", "",
        "This mart makes finance selection explicit: DIME/FollowTheMoney recipient totals are used for 1998-2010, "
        "and Alabama FCPA principal-campaign-committee summaries are used for 2014-2022. Missing candidates remain unknown; "
        "only an identified committee with no cycle activity is treated as an observed zero.", "",
        f"Fundraising ratios use a ${SMOOTHING_DOLLARS:,.0f} additive constant on both sides.", "",
        "| Cycle | Complete races | Eligible races | Coverage |", "|---:|---:|---:|---:|",
    ]
    for row in coverage.itertuples(index=False):
        lines.append(f"| {row.cycle} | {row.complete_races} | {row.eligible_races} | {row.coverage_rate:.1%} |")
    observed = candidate.finance_observation_status.ne("unknown_unmatched").sum()
    lines += ["", f"Candidate observations recovered: {observed}/{len(candidate)} ({observed/len(candidate):.1%}).", "",
              "The unresolved queue is written to `canonical_historical_finance_review.csv`. The 1994 cases are also "
              "written to a separate archival-request manifest; public historical records are the remaining avenue for that cycle."]
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    candidate, race, coverage = build()
    candidate.to_csv(WAR / "canonical_historical_finance_candidates.csv", index=False)
    race.to_csv(WAR / "canonical_historical_finance_races.csv", index=False)
    coverage.to_csv(WAR / "canonical_historical_finance_coverage.csv", index=False)
    write_review_and_archival(candidate)
    write_doc(coverage, candidate)
    print(coverage.to_string(index=False, formatters={"coverage_rate": "{:.1%}".format}))


if __name__ == "__main__":
    main()
