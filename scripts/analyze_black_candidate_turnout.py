"""Estimate turnout differences associated with a Black legislative candidate.

The analysis never infers race from a candidate's name or photograph. It uses
only the reviewed crosswalk in data/manual/candidates/candidate_race_ethnicity.csv.
Until that crosswalk has adequate coverage, the script builds a review queue and
stops before publishing an effect estimate.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = ROOT / "data" / "processed" / "elections"
DEMOGRAPHICS = ROOT / "data" / "processed" / "demographics"
MANUAL = ROOT / "data" / "manual" / "candidates" / "candidate_race_ethnicity.csv"
EXTERNAL = ELECTIONS / "validation" / "reflective_democracy_candidate_matches.csv"
RDH_2022 = ELECTIONS / "validation" / "rdh_2022_candidate_demographic_matches.csv"
OUT = ELECTIONS / "validation"
CYCLES = (2014, 2018, 2022)
ALLOWED_IDENTITIES = {"black", "non_black", "multiracial_black"}


def load_labels(path: Path = MANUAL) -> pd.DataFrame:
    manual = pd.read_csv(path, dtype=str).fillna("")
    external_frames = []
    for source_path in (EXTERNAL, RDH_2022):
        if source_path.exists():
            source = pd.read_csv(source_path, dtype=str).fillna("")
            external_frames.append(source[[column for column in manual.columns if column in source.columns]])
    external = pd.concat(external_frames, ignore_index=True, sort=False) if external_frames else pd.DataFrame()
    # Version-controlled manual decisions override external research coding.
    labels = pd.concat([external, manual], ignore_index=True, sort=False).fillna("")
    labels = labels.drop_duplicates("canonical_candidate_id", keep="last")
    if labels.canonical_candidate_id.duplicated().any():
        raise ValueError("candidate race crosswalk contains duplicate canonical_candidate_id values")
    reviewed = labels.review_status.str.lower().isin({"approved", "approved_external_dataset"})
    invalid = reviewed & ~labels.race_ethnicity.str.lower().isin(ALLOWED_IDENTITIES)
    if invalid.any():
        bad = labels.loc[invalid, "race_ethnicity"].unique().tolist()
        raise ValueError(f"approved rows have invalid race_ethnicity values: {bad}")
    labels["black_candidate_reviewed"] = np.where(
        reviewed,
        labels.race_ethnicity.str.lower().isin({"black", "multiracial_black"}).astype(float),
        np.nan,
    )
    return labels


def build_review_queue(candidates: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    current = candidates[candidates.year.isin(CYCLES)].copy()
    joined = current.merge(
        labels[["canonical_candidate_id", "race_ethnicity", "review_status"]],
        on="canonical_candidate_id", how="left", validate="one_to_one",
    )
    queue = joined[
        ~joined.review_status.fillna("").str.lower().isin({"approved", "approved_external_dataset"})
    ][[
        "canonical_candidate_id", "person_id", "year", "chamber", "district",
        "canonical_party", "canonical_name", "incumbent", "winner",
    ]].copy()
    queue["race_ethnicity"] = ""
    queue["black_candidate"] = ""
    queue["evidence_url"] = ""
    queue["evidence_quote"] = ""
    queue["evidence_date"] = ""
    queue["review_status"] = "pending"
    queue["reviewer"] = ""
    queue["notes"] = "Do not infer from name or appearance; require reliable biographical evidence."
    return queue.sort_values(["year", "chamber", "district", "canonical_party"])


def assemble_panel(candidates: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    candidates = candidates[candidates.year.isin(CYCLES)].copy()
    candidates = candidates.merge(
        labels[["canonical_candidate_id", "black_candidate_reviewed"]],
        on="canonical_candidate_id", how="left", validate="one_to_one",
    )
    candidates["label_known"] = candidates.black_candidate_reviewed.notna()
    candidates["black_candidate_reviewed"] = candidates.black_candidate_reviewed.fillna(0)

    race_labels = (candidates.groupby(["year", "chamber", "district"], as_index=False)
                   .agg(candidate_rows=("canonical_candidate_id", "size"),
                        candidate_labels_known=("label_known", "sum"),
                        any_black_candidate=("black_candidate_reviewed", "max"),
                        black_candidate_count=("black_candidate_reviewed", "sum")))
    dem = (candidates[candidates.canonical_party.eq("D")]
           .groupby(["year", "chamber", "district"], as_index=False)
           .agg(dem_candidate_known=("label_known", "all"),
                black_dem_candidate=("black_candidate_reviewed", "max")))
    race_labels = race_labels.merge(dem, on=["year", "chamber", "district"], how="left")
    race_labels["dem_candidate_known"] = np.where(
        race_labels.dem_candidate_known.isna(), True, race_labels.dem_candidate_known)
    race_labels["black_dem_candidate"] = race_labels.black_dem_candidate.fillna(0)
    race_labels["race_labels_complete"] = (
        race_labels.candidate_rows.eq(race_labels.candidate_labels_known))

    races = pd.read_csv(ELECTIONS / "canonical_cmo_features.csv")
    races = races[races.cycle.isin(CYCLES)].rename(columns={"cycle": "year"})
    panel = races.merge(race_labels, on=["year", "chamber", "district"], how="left",
                        validate="one_to_one")
    panel["prior_pres_dem_margin"] = np.select(
        [panel.year.eq(2014), panel.year.eq(2018), panel.year.eq(2022)],
        [panel.pres_2012_dem_margin, panel.pres_2016_dem_margin, panel.pres_2020_dem_margin],
        default=np.nan,
    )

    cvap = pd.read_csv(DEMOGRAPHICS / "rdh_historical_sld_cvap_2010_2022.csv")
    cvap = cvap[cvap.cycle.isin(CYCLES)].rename(columns={"cycle": "year", "total": "cvap_total"})
    panel = panel.merge(
        cvap[["year", "chamber", "district", "cvap_total", "cvap_black_share",
              "cvap_hispanic_share", "cvap_other_nonwhite_share", "cvap_moe_ratio"]],
        on=["year", "chamber", "district"], how="left", validate="one_to_one")

    offices = pd.read_csv(ELECTIONS / "canonical_cmo_district_office_baselines.csv")
    governor = offices[offices.cycle.isin(CYCLES) & offices.office.eq("Governor")].copy()
    governor["governor_two_party_votes"] = governor.D + governor.R
    governor = governor.rename(columns={"cycle": "year"})
    panel = panel.merge(
        governor[["year", "chamber", "district", "governor_two_party_votes",
                  "baseline_fallback_share"]].rename(
                      columns={"baseline_fallback_share": "governor_fallback_share"}),
        on=["year", "chamber", "district"], how="left", validate="one_to_one")

    panel["legislative_turnout_cvap"] = panel.two_party_votes / panel.cvap_total
    panel["legislative_to_governor_retention"] = (
        panel.two_party_votes / panel.governor_two_party_votes)
    panel["contested_dr"] = panel.war_eligible.astype(int)
    panel["dem_incumbent_i"] = panel.dem_incumbent.astype(int)
    panel["rep_incumbent_i"] = panel.rep_incumbent.astype(int)
    panel["district_family"] = panel.chamber.astype(str) + "-" + panel.district.astype(str)
    return panel


def adjusted_effect(data: pd.DataFrame, treatment: str, outcome: str) -> dict[str, float]:
    """Regression-adjusted marginal contrast with an overlap diagnostic."""
    numeric = [
        "cvap_black_share", "cvap_hispanic_share", "white_college_share",
        "prior_pres_dem_margin", "dem_incumbent_i", "rep_incumbent_i",
    ]
    categorical = ["year", "chamber"]
    needed = [treatment, outcome, *numeric, *categorical]
    sample = data.dropna(subset=[treatment, outcome]).copy()
    if sample[treatment].nunique() < 2:
        raise ValueError(f"{treatment} has no treated/untreated variation")

    transform = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                           ("scale", StandardScaler())]), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
    ])
    propensity = Pipeline([
        ("features", transform),
        ("model", LogisticRegression(C=0.5, max_iter=2000)),
    ])
    propensity.fit(sample[numeric + categorical], sample[treatment])
    score = propensity.predict_proba(sample[numeric + categorical])[:, 1]

    outcome_features = numeric + categorical + [treatment]
    outcome_transform = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                           ("scale", StandardScaler())]), numeric + [treatment]),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
    ])
    model = Pipeline([("features", outcome_transform), ("model", Ridge(alpha=10.0))])
    model.fit(sample[outcome_features], sample[outcome])
    treated = sample[outcome_features].copy()
    untreated = sample[outcome_features].copy()
    treated[treatment] = 1
    untreated[treatment] = 0
    individual_effect = model.predict(treated) - model.predict(untreated)
    overlap = (score >= 0.1) & (score <= 0.9)
    return {
        "n": len(sample),
        "treated": int(sample[treatment].sum()),
        "untreated": int((1 - sample[treatment]).sum()),
        "adjusted_mean_difference": float(individual_effect.mean()),
        "overlap_n": int(overlap.sum()),
        "overlap_share": float(overlap.mean()),
        "propensity_min": float(score.min()),
        "propensity_max": float(score.max()),
    }


def effect_with_bootstrap(data: pd.DataFrame, treatment: str, outcome: str,
                          replicates: int = 50) -> dict[str, float]:
    point = adjusted_effect(data, treatment, outcome)
    sample = data.dropna(subset=[treatment, outcome]).copy()
    clusters = sample.district_family.dropna().unique()
    rng = np.random.default_rng(20260817)
    estimates = []
    for _ in range(replicates):
        chosen = rng.choice(clusters, size=len(clusters), replace=True)
        boot = pd.concat(
            [sample[sample.district_family.eq(cluster)] for cluster in chosen],
            ignore_index=True,
        )
        if boot[treatment].nunique() < 2:
            continue
        try:
            estimates.append(adjusted_effect(boot, treatment, outcome)["adjusted_mean_difference"])
        except ValueError:
            continue
    if len(estimates) < replicates * 0.8:
        point.update({"bootstrap_replicates": len(estimates), "bootstrap_se": np.nan,
                      "ci_low": np.nan, "ci_high": np.nan})
    else:
        values = np.asarray(estimates)
        point.update({"bootstrap_replicates": len(values),
                      "bootstrap_se": float(values.std(ddof=1)),
                      "ci_low": float(np.quantile(values, 0.025)),
                      "ci_high": float(np.quantile(values, 0.975))})
    return point


def run_analysis(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    complete = panel[panel.race_labels_complete.fillna(False)].copy()
    coverage = pd.DataFrame([
        {"metric": "district_cycles", "value": len(panel)},
        {"metric": "complete_candidate_identity_district_cycles", "value": len(complete)},
        {"metric": "complete_share", "value": len(complete) / len(panel) if len(panel) else 0},
        {"metric": "treated_any_black", "value": complete.any_black_candidate.sum()},
    ])
    if len(complete) / len(panel) < 0.9:
        return coverage, pd.DataFrame()

    rows = []
    for scope, data in [("all_races", complete),
                        ("contested_dr", complete[complete.contested_dr.eq(1)])]:
        for treatment in ["any_black_candidate", "black_dem_candidate"]:
            for outcome in ["legislative_turnout_cvap", "legislative_to_governor_retention"]:
                result = effect_with_bootstrap(data, treatment, outcome)
                rows.append({"scope": scope, "treatment": treatment, "outcome": outcome,
                             **result})
    return coverage, pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="Write descriptive partial-label estimates; never publication-ready.")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_csv(ELECTIONS / "canonical_cmo_candidates.csv")
    labels = load_labels()
    queue = build_review_queue(candidates, labels)
    queue.to_csv(OUT / "black_candidate_identity_review_queue.csv", index=False)
    panel = assemble_panel(candidates, labels)
    panel.to_csv(OUT / "black_candidate_turnout_panel.csv", index=False)
    coverage, estimates = run_analysis(panel)
    coverage.to_csv(OUT / "black_candidate_turnout_coverage.csv", index=False)
    if estimates.empty and not args.allow_incomplete:
        print(
            f"Identity review required: {len(queue)} candidate-cycle rows remain. "
            "No counterfactual estimate was published."
        )
        return
    if estimates.empty:
        complete = panel[panel.race_labels_complete.fillna(False)].copy()
        rows = []
        for scope, data in [
            ("partial_all_races_not_for_inference", complete),
            ("partial_contested_dr_not_for_inference", complete[complete.contested_dr.eq(1)]),
        ]:
            for treatment in ["any_black_candidate", "black_dem_candidate"]:
                for outcome in ["legislative_turnout_cvap", "legislative_to_governor_retention"]:
                    if data[treatment].nunique() == 2:
                        rows.append({"scope": scope, "treatment": treatment,
                                     "outcome": outcome,
                                     **effect_with_bootstrap(data, treatment, outcome)})
        estimates = pd.DataFrame(rows)
    estimates.to_csv(OUT / "black_candidate_turnout_estimates.csv", index=False)
    print(f"Wrote {len(estimates)} estimates from {len(panel)} district-cycle rows.")


if __name__ == "__main__":
    main()
