"""Build analysis-ready CMO/ideology tables and matched comparison leads."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
WAR = ROOT / "data" / "processed" / "war"
ELECTIONS = ROOT / "data" / "processed" / "elections"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
DIMENSIONS = ["economic_ideology", "social_ideology", "guns_position", "abortion_position", "labor_position"]
ELECTION_DATES = {
    2010: pd.Timestamp("2010-11-02"),
    2014: pd.Timestamp("2014-11-04"),
    2018: pd.Timestamp("2018-11-06"),
    2022: pd.Timestamp("2022-11-08"),
}


def mark_temporal_eligibility(ledger: pd.DataFrame) -> pd.DataFrame:
    """Flag evidence usable in an election-specific quantitative code."""
    ledger = ledger.copy()
    ledger["evidence_date_parsed"] = pd.to_datetime(ledger.evidence_date, errors="coerce")
    ledger["election_date"] = ledger.election_cycle.map(ELECTION_DATES)
    ledger["temporally_eligible"] = (
        ledger.evidence_date_parsed.notna()
        & ledger.election_date.notna()
        & ledger.evidence_date_parsed.le(ledger.election_date)
        & ~ledger.review_status.fillna("").str.contains("post_election|retrospective", case=False)
    )
    return ledger


def main():
    scores = pd.read_csv(WAR / "preliminary_cmo_candidates.csv")
    scores = scores[scores.party.eq("D")].copy()
    scores["candidate"] = scores.candidate.str.strip()
    features = pd.read_csv(ELECTIONS / "canonical_cmo_features.csv")
    data = scores.merge(features, on=["cycle", "chamber", "district"], how="left", validate="many_to_one")
    geography_path = RESEARCH / "cmo_geography_sensitivity.csv"
    if geography_path.exists():
        geography = pd.read_csv(geography_path)[[
            "canonical_candidate_id", "cmo_geography_low", "cmo_geography_high",
            "cmo_geography_mean", "cmo_geography_range",
        ]]
        data = data.merge(geography, on="canonical_candidate_id", how="left", validate="one_to_one")

    methods = ["candidate_cmo_total_oof", "candidate_cmo_total_cycle_holdout", "candidate_cmo_total_district_grouped"]
    data["robust_cmo_median"] = data[methods].median(axis=1)
    data["cmo_method_range"] = data[methods].max(axis=1) - data[methods].min(axis=1)
    data["robust_positive"] = data[methods].min(axis=1).gt(0)
    data["district_context"] = np.select(
        [data.nonwhite_share.ge(.5), data.nonwhite_share.lt(.25) & data.white_college_share.lt(.25),
         data.nonwhite_share.lt(.25) & data.white_college_share.ge(.25)],
        ["majority_nonwhite", "majority_white_lower_college", "majority_white_higher_college"],
        default="mixed_or_demographics_missing",
    )

    legislative_path = IDEOLOGY / "candidate_ideology_full_universe.csv"
    if legislative_path.exists():
        legislative = pd.read_csv(legislative_path)
        keep = ["canonical_candidate_id", "legislative_ideology_available",
                "coverage_status", "identity_match_method", "behavioral_ideology",
                "chamber_percentile", "distance_from_caucus_median", "votes_used",
                "participation_rate"]
        keep += [column for column in legislative if column.startswith("legislative_issue_")]
        legislative = legislative[[column for column in keep if column in legislative]].drop_duplicates(
            "canonical_candidate_id")
        legislative = legislative.rename(columns={
            "coverage_status":"legislative_ideology_coverage_status",
            "identity_match_method":"legislative_ideology_match_method",
            "chamber_percentile":"legislative_ideology_chamber_percentile",
            "votes_used":"legislative_ideology_votes_used",
            "participation_rate":"legislative_ideology_participation_rate",
        })
        data = data.merge(legislative,on="canonical_candidate_id",how="left",validate="one_to_one")

    ledger = pd.read_csv(RESEARCH / "evidence_ledger.csv")
    ledger["numeric_code"] = pd.to_numeric(ledger.coded_value, errors="coerce")
    ledger = mark_temporal_eligibility(ledger)
    coded = ledger[
        ledger.dimension.isin(DIMENSIONS)
        & ledger.numeric_code.notna()
        & ledger.temporally_eligible
    ].copy()
    dimension = coded.pivot_table(
        index=["person_id", "election_cycle"], columns="dimension",
        values="numeric_code", aggfunc="median"
    )
    dimension["available_issue_dimensions"] = dimension.notna().sum(axis=1)
    dimension["issue_ideology_mean"] = dimension[DIMENSIONS].mean(axis=1, skipna=True)
    data = data.merge(
        dimension.reset_index(), left_on=["person_id", "cycle"],
        right_on=["person_id", "election_cycle"], how="left", suffixes=("", "_coded")
    ).drop(columns="election_cycle", errors="ignore")

    # Candidate-supplied Vote Smart PCT evidence remains a parallel source.
    # It is never blended into the hand-reviewed evidence median, and missing
    # questionnaires are never assigned a neutral score.
    pct_path = IDEOLOGY / "votesmart_pct_candidate_cycle_features.csv"
    if pct_path.exists():
        pct = pd.read_csv(pct_path)
        pct_dimensions = [
            "abortion_position", "criminal_justice_position", "economic_ideology",
            "education_position", "environment_position", "government_reform_position",
            "guns_position", "healthcare_position", "labor_position", "social_ideology",
        ]
        keep = ["canonical_candidate_id", "votesmart_candidate_id", "election_year",
                "pct_dimensions_scored", "pct_policies_scored", "pct_response_items_scored"] + pct_dimensions
        pct = pct[keep].drop_duplicates("canonical_candidate_id")
        pct = pct.rename(columns={column: f"votesmart_pct_{column}" for column in pct_dimensions})
        data = data.merge(pct, on="canonical_candidate_id", how="left", validate="one_to_one")
        data["votesmart_pct_available"] = data.pct_dimensions_scored.notna()
        data["votesmart_pct_exact_cycle"] = data.election_year.eq(data.cycle) & data.votesmart_pct_available
        pct_score_columns = [f"votesmart_pct_{column}" for column in pct_dimensions]
        data["votesmart_pct_dimension_mean"] = data[pct_score_columns].mean(axis=1, skipna=True)

        relationship_rows = []
        scopes = {"all_cycles": data}
        scopes.update({f"cycle_{cycle}": part for cycle, part in data.groupby("cycle")})
        scopes.update({
            "pre_2008": data[data.cycle.le(2006)],
            "obama_era_2010_2014": data[data.cycle.between(2010, 2014)],
            "trump_era_2018_2022": data[data.cycle.ge(2018)],
        })
        for scope, part in scopes.items():
            for column in pct_score_columns + ["votesmart_pct_dimension_mean"]:
                observed = part[[column, "candidate_cmo_total_oof"]].dropna()
                relationship_rows.append({
                    "scope": scope, "dimension": column.removeprefix("votesmart_pct_"),
                    "candidate_cycles": len(observed),
                    "spearman_rho": (observed[column].corr(
                        observed.candidate_cmo_total_oof, method="spearman")
                        if len(observed) >= 5 and observed[column].nunique() > 1 else np.nan),
                    "coverage_share": len(observed) / len(part) if len(part) else np.nan,
                    "interpretation": "descriptive_candidate_supplied_not_causal",
                })
        pd.DataFrame(relationship_rows).to_csv(
            RESEARCH / "votesmart_pct_cmo_relationships.csv", index=False)

        (data.groupby("cycle", as_index=False)
         .agg(cmo_democratic_candidate_cycles=("cycle", "size"),
              exact_cycle_pct_profiles=("votesmart_pct_available", "sum"),
              mean_dimensions_scored=("pct_dimensions_scored", "mean"))
         .assign(coverage_share=lambda x: x.exact_cycle_pct_profiles / x.cmo_democratic_candidate_cycles)
         .to_csv(RESEARCH / "votesmart_pct_cmo_coverage.csv", index=False))
    data.to_csv(RESEARCH / "candidate_cycle_analysis.csv", index=False)

    coverage = (ledger.groupby(["person_id", "candidate"], as_index=False)
                .agg(evidence_items=("dimension", "size"), dimensions_coded=("dimension", "nunique"),
                     high_confidence_items=("confidence", lambda x: x.eq("high").sum()),
                     sources=("source_url", "nunique"),
                     temporally_eligible_items=("temporally_eligible", "sum")))
    coverage.to_csv(RESEARCH / "evidence_coverage.csv", index=False)

    # Create comparison leads, not causal matches. Within cycle/chamber and
    # incumbency status, find a substantially lower-CMO Democrat with the most
    # similar modeled expectation, statewide baseline, race, and education mix.
    match_features = ["expected_cmo_total_oof", "core_index_margin", "nonwhite_share", "white_college_share"]
    pairs=[]
    focals=data.sort_values("candidate_cmo_total_oof", ascending=False).head(15)
    for focal in focals.itertuples(index=False):
        pool=data[(data.cycle.eq(focal.cycle)) & (data.chamber.eq(focal.chamber)) &
                  (data.incumbent.eq(focal.incumbent)) &
                  (data.candidate_cmo_total_oof.le(focal.candidate_cmo_total_oof-10)) &
                  (~data.person_id.eq(focal.person_id))].copy()
        if pool.empty:
            continue
        dist=np.zeros(len(pool))
        used=[]
        for col in match_features:
            series=data.loc[data.cycle.eq(focal.cycle),col]
            scale=series.std()
            fv=getattr(focal,col)
            if pd.isna(fv) or pd.isna(scale) or scale==0:
                continue
            vals=pool[col].fillna(series.median())
            dist += ((vals-fv)/scale).pow(2).to_numpy()
            used.append(col)
        pool["match_distance"]=np.sqrt(dist)
        match=pool.sort_values("match_distance").iloc[0]
        pairs.append({
            "focal_person_id":focal.person_id,"focal_candidate":focal.candidate,"cycle":focal.cycle,
            "chamber":focal.chamber,"district":focal.district,"focal_cmo":focal.candidate_cmo_total_oof,
            "focal_context":focal.district_context,"comparison_person_id":match.person_id,
            "comparison_candidate":match.candidate,"comparison_district":match.district,
            "comparison_cmo":match.candidate_cmo_total_oof,"comparison_context":match.district_context,
            "cmo_difference":focal.candidate_cmo_total_oof-match.candidate_cmo_total_oof,
            "match_distance":match.match_distance,"features_used":";".join(used),
        })
    pd.DataFrame(pairs).to_csv(RESEARCH / "matched_comparisons.csv", index=False)
    print(f"Wrote {len(data)} candidate-cycle rows, {len(coverage)} researched candidates, and {len(pairs)} comparison leads")


if __name__ == "__main__":
    main()
