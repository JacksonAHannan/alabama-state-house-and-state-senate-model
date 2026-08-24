"""Rebuild ideology/overperformance analysis around absolute candidate position.

The outcome remains ideology-blind. Positive candidate-directional outcomes mean
that either party ran ahead of the named baseline. Incumbency and finance enter
only explicitly labelled mediator/sensitivity specifications.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = ROOT / "data" / "processed" / "elections"
WAR = ROOT / "data" / "processed" / "war"
RESEARCH = ROOT / "research" / "cmo_ideology"
REPORT = ROOT / "project_docs" / "model" / "ABSOLUTE_IDEOLOGY_REBUILD.md"

OUTCOMES = [
    "candidate_cmo", "candidate_statewide_overperformance",
    "candidate_federal_overperformance", "candidate_presidential_overperformance",
]
ISSUE_DIRECTIONS = {
    "environment_resources": -1.0,
    "institutional_reform": -1.0,
    "labor_capital": -1.0,
    "market_government_direction": -1.0,
    "material_support": -1.0,
    "order_justice": 1.0,
    "social_liberty_equality": -1.0,
}
# ``model_issue_valence`` is +1 for the first pole declared in ontology v3.
# These signs orient selected scalar primitives so positive always means the
# conventionally more conservative Alabama position. Keeping guns, racial
# civil rights, sexual morality, and tax distribution separate prevents the
# earlier family rollups from conflating substantively different coalitions.
PRIMITIVE_DIRECTIONS = {
    "gun_access": 1.0, "gun_purchase_regulation": -1.0,
    "abortion_access": -1.0, "marriage_equality": -1.0,
    "civil_social_liberty": -1.0, "christian_sexual_morality": 1.0,
    "racial_civil_rights": -1.0, "anti_discrimination": -1.0,
    "religion_state": 1.0, "criminal_punishment": 1.0,
    "drug_criminalization": 1.0, "due_process": -1.0,
    "market_governance": -1.0, "tax_burden": -1.0,
    "tax_distribution": -1.0, "public_spending": -1.0,
    "deficit_discipline": 1.0, "welfare_generosity": -1.0,
    "welfare_conditionality": 1.0, "labor_capital_alignment": -1.0,
    "labor_rights": -1.0, "public_employee_compensation": -1.0,
    "education_public_funding": -1.0, "education_market_choice": 1.0,
    "environmental_protection": -1.0, "resource_development": 1.0,
    "conservation_preservation": -1.0, "immigration_access": -1.0,
    "immigration_enforcement": 1.0, "healthcare_access": -1.0,
    "government_ethics_transparency": -1.0, "voting_access": -1.0,
}


def zscore(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    scale = numeric.std(ddof=0)
    return (numeric - numeric.mean()) / scale if scale and np.isfinite(scale) else numeric * np.nan


def build_panel() -> pd.DataFrame:
    candidates = pd.read_csv(ELECTIONS / "canonical_cmo_candidates_with_ideology_v3.csv", low_memory=False)
    candidates = candidates[candidates.war_eligible.eq(True) & candidates.canonical_party.isin(["D", "R"])].copy()
    candidates = candidates.rename(columns={"year": "election_year", "canonical_party": "party"})
    # CMO v4 is the validated Split Ticket-style structural residual. Ideology
    # is excluded from its construction and enters only in this downstream
    # explanatory analysis.
    cmo = pd.read_csv(WAR / "cmo_v4_candidates.csv", low_memory=False)[
        ["canonical_candidate_id", "candidate_war_cmo"]
    ]
    if cmo.canonical_candidate_id.duplicated().any():
        raise ValueError("cmo_v4_candidates contains duplicate canonical_candidate_id values")
    quality = pd.read_csv(WAR / "cmo_v5_candidates.csv", low_memory=False)[
        ["canonical_candidate_id", "candidate_quality_index"]
    ]
    if quality.canonical_candidate_id.duplicated().any():
        raise ValueError("cmo_v5_candidates contains duplicate canonical_candidate_id values")
    races = pd.read_csv(WAR / "preliminary_cmo_races.csv", low_memory=False)
    federal = pd.read_csv(ELECTIONS / "historical_federal_district_baselines.csv")
    keys = ["cycle", "chamber", "district"]
    race_columns = keys + [
        "legislative_dem_margin", "statewide_index_margin", "prior_pres_dem_margin",
        "nonwhite_share", "white_college_share", "canonical_finance_complete",
        "canonical_log_fundraising_ratio_d_to_r",
    ]
    candidates = candidates.drop(columns=[column for column in race_columns if column not in keys and column in candidates],
                                 errors="ignore")
    panel = (candidates.merge(cmo, on="canonical_candidate_id", how="left", validate="one_to_one")
             .merge(quality, on="canonical_candidate_id", how="left", validate="one_to_one")
             .merge(races[race_columns], on=keys, how="left", validate="many_to_one")
             .merge(federal, on=keys, how="left", validate="many_to_one"))
    panel["party_direction"] = np.where(panel.party.eq("D"), 1.0, -1.0)
    panel["democratic_i"] = panel.party.eq("D").astype(int)
    panel["incumbent_i"] = panel.incumbent.fillna(False).astype(int)
    panel["democratic_x_incumbency"] = panel.democratic_i * panel.incumbent_i
    panel["candidate_cmo"] = panel.candidate_war_cmo
    panel["cmo_source"] = "cmo_v4_war_residual"
    panel["candidate_statewide_overperformance"] = panel.party_direction * (
        panel.legislative_dem_margin - panel.statewide_index_margin)
    panel["candidate_federal_overperformance"] = panel.party_direction * (
        panel.legislative_dem_margin - panel.federal_index_margin)
    panel["candidate_presidential_overperformance"] = panel.party_direction * (
        panel.legislative_dem_margin - panel.prior_pres_dem_margin)
    panel["candidate_finance_advantage"] = panel.party_direction * panel.canonical_log_fundraising_ratio_d_to_r
    panel["district_republicanism_z"] = zscore(-panel.federal_index_margin)
    panel["era"] = np.select(
        [panel.cycle.le(2006), panel.cycle.le(2014)],
        ["pre_2008", "2008_2014"], default="post_2016")

    # Reuse the reviewed two-party Shor crosswalk, but never require a Shor
    # match for issue-level analyses.
    shor_path = RESEARCH / "symmetric_incumbency_panel.csv"
    shor = pd.read_csv(shor_path, low_memory=False)[
        ["canonical_candidate_id", "shor_u_id", "shor_np_score", "absolute_np_z",
         "served_by_election", "first_observed_service_year"]
    ].drop_duplicates("canonical_candidate_id")
    panel = panel.merge(shor, on="canonical_candidate_id", how="left", validate="one_to_one")
    panel["absolute_conservatism_z"] = panel.absolute_np_z
    panel["party_directed_convergence"] = panel.party_direction * panel.absolute_conservatism_z
    panel["democratic_x_absolute"] = panel.democratic_i * panel.absolute_conservatism_z
    panel["democratic_x_convergence"] = panel.democratic_i * panel.party_directed_convergence

    for family, direction in ISSUE_DIRECTIONS.items():
        source = f"ideology_v3_{family}"
        conservative = f"issue_conservative_{family}"
        convergence = f"issue_convergence_{family}"
        congruence = f"issue_congruence_{family}"
        panel[conservative] = pd.to_numeric(panel[source], errors="coerce") * direction
        panel[convergence] = panel.party_direction * panel[conservative]
        panel[congruence] = panel[conservative] * panel.district_republicanism_z

    primitive = pd.read_csv(ELECTIONS.parent / "ideology" / "candidate_issue_valence_v3.csv",
                            low_memory=False)
    primitive = primitive[primitive.primitive_axis.isin(PRIMITIVE_DIRECTIONS)].copy()
    primitive["model_issue_valence"] = pd.to_numeric(primitive.model_issue_valence, errors="coerce")
    wide = primitive.pivot_table(index="canonical_candidate_id", columns="primitive_axis",
                                 values="model_issue_valence", aggfunc="first")
    wide.columns = [f"primitive_raw_{column}" for column in wide.columns]
    panel = panel.merge(wide.reset_index(), on="canonical_candidate_id", how="left", validate="one_to_one")
    primitive_features = {}
    for axis, direction in PRIMITIVE_DIRECTIONS.items():
        raw = f"primitive_raw_{axis}"
        conservative = f"primitive_conservative_{axis}"
        value = panel.get(raw, pd.Series(np.nan, index=panel.index)) * direction
        primitive_features[conservative] = value
        primitive_features[f"primitive_convergence_{axis}"] = panel.party_direction * value
        primitive_features[f"primitive_congruence_{axis}"] = value * panel.district_republicanism_z
    panel = pd.concat([panel, pd.DataFrame(primitive_features, index=panel.index)], axis=1)
    return panel


def fit(frame: pd.DataFrame, outcome: str, variables: list[str], specification: str,
        sample: str, focal_terms: list[str]) -> list[dict]:
    needed = [outcome, "person_id", *variables]
    data = frame.dropna(subset=needed).copy()
    result_base = {"sample": sample, "outcome": outcome, "specification": specification,
                   "n": len(data), "people": data.person_id.nunique()}
    if len(data) < max(18, len(variables) + 8):
        return [{**result_base, "term": term, "status": "underpowered"} for term in focal_terms]
    X = pd.DataFrame({"intercept": 1.0}, index=data.index)
    for variable in variables:
        if variable in {"cycle", "chamber"}:
            X = pd.concat([X, pd.get_dummies(data[variable].astype(str), prefix=variable,
                                             drop_first=True, dtype=float)], axis=1)
        else:
            X[variable] = pd.to_numeric(data[variable], errors="coerce")
    if any(term not in X or X[term].nunique() < 2 for term in focal_terms):
        return [{**result_base, "term": term, "status": "no_variation"} for term in focal_terms]
    A = X.to_numpy(float)
    y = data[outcome].to_numpy(float)
    inv = np.linalg.pinv(A.T @ A)
    beta = inv @ A.T @ y
    residual = y - A @ beta
    groups = pd.Categorical(data.person_id.astype(str)).codes
    unique = np.unique(groups)
    meat = np.zeros((A.shape[1], A.shape[1]))
    for group in unique:
        score = A[groups == group].T @ residual[groups == group]
        meat += np.outer(score, score)
    covariance = inv @ meat @ inv
    if len(unique) > 1 and len(data) > A.shape[1]:
        covariance *= len(unique) / (len(unique) - 1) * (len(data) - 1) / (len(data) - A.shape[1])
    se = np.sqrt(np.maximum(np.diag(covariance), 0))
    names = list(X.columns)
    rows = []
    for term in focal_terms:
        index = names.index(term)
        statistic = beta[index] / se[index] if se[index] else np.nan
        rows.append({**result_base, "term": term, "status": "estimated",
                     "coefficient": beta[index], "cluster_se": se[index],
                     "ci_low": beta[index] - 1.96 * se[index],
                     "ci_high": beta[index] + 1.96 * se[index],
                     "p_value": 2 * stats.t.sf(abs(statistic), max(len(unique) - 1, 1))})
    return rows


def run_absolute(panel: pd.DataFrame) -> pd.DataFrame:
    data = panel[panel.absolute_conservatism_z.notna()].copy()
    specifications = {
        # Total association deliberately omits incumbency and finance.
        "total_context": ["democratic_i", "absolute_conservatism_z", "democratic_x_absolute",
                          "nonwhite_share", "white_college_share", "cycle", "chamber"],
        "common_incumbency": ["democratic_i", "absolute_conservatism_z", "democratic_x_absolute",
                              "incumbent_i", "nonwhite_share", "white_college_share", "cycle", "chamber"],
        "party_specific_incumbency": ["democratic_i", "absolute_conservatism_z", "democratic_x_absolute",
                                      "incumbent_i", "democratic_x_incumbency", "nonwhite_share",
                                      "white_college_share", "cycle", "chamber"],
        "mediator_adjusted_incumbency_finance": ["democratic_i", "absolute_conservatism_z",
                                                  "democratic_x_absolute", "incumbent_i",
                                                  "democratic_x_incumbency", "candidate_finance_advantage",
                                                  "nonwhite_share", "white_college_share", "cycle", "chamber"],
        "party_directed_convergence": ["democratic_i", "party_directed_convergence",
                                       "democratic_x_convergence", "nonwhite_share",
                                       "white_college_share", "cycle", "chamber"],
    }
    rows: list[dict] = []
    for outcome in OUTCOMES:
        for label, variables in specifications.items():
            focal = (["party_directed_convergence", "democratic_x_convergence"]
                     if label == "party_directed_convergence"
                     else ["absolute_conservatism_z", "democratic_x_absolute"])
            if label == "common_incumbency":
                focal += ["incumbent_i"]
            elif label in {"party_specific_incumbency", "mediator_adjusted_incumbency_finance"}:
                focal += ["incumbent_i", "democratic_x_incumbency"]
            rows.extend(fit(data, outcome, variables, label, "all", focal))
        for party in ("D", "R"):
            sample = data[data.party.eq(party)]
            rows.extend(fit(sample, outcome,
                            ["absolute_conservatism_z", "nonwhite_share", "white_college_share",
                             "cycle", "chamber"], "party_total_context", party,
                            ["absolute_conservatism_z"]))
            rows.extend(fit(sample, outcome,
                            ["absolute_conservatism_z", "incumbent_i", "candidate_finance_advantage",
                             "nonwhite_share", "white_college_share", "cycle", "chamber"],
                            "party_mediator_adjusted", party, ["absolute_conservatism_z"]))
            rows.extend(fit(sample[sample.winner.eq(True)], outcome,
                            ["absolute_conservatism_z", "incumbent_i", "nonwhite_share",
                             "white_college_share", "cycle", "chamber"],
                            "party_winners_only", party, ["absolute_conservatism_z"]))
            rows.extend(fit(sample[sample.served_by_election.eq(True)], outcome,
                            ["absolute_conservatism_z", "incumbent_i", "nonwhite_share",
                             "white_college_share", "cycle", "chamber"],
                            "party_prior_service_only", party, ["absolute_conservatism_z"]))
            winsorized = sample.copy()
            lower, upper = winsorized[outcome].quantile([.025, .975])
            winsorized["winsorized_outcome"] = winsorized[outcome].clip(lower, upper)
            rows.extend(fit(winsorized, "winsorized_outcome",
                            ["absolute_conservatism_z", "nonwhite_share", "white_college_share",
                             "cycle", "chamber"], f"party_winsorized:{outcome}", party,
                            ["absolute_conservatism_z"]))
            for omitted_cycle in sorted(sample.cycle.unique()):
                leave_out = sample[~sample.cycle.eq(omitted_cycle)]
                rows.extend(fit(leave_out, outcome,
                                ["absolute_conservatism_z", "nonwhite_share", "white_college_share",
                                 "cycle", "chamber"], "party_leave_cycle_out",
                                f"{party}:omit_{omitted_cycle}", ["absolute_conservatism_z"]))
            for era, era_data in sample.groupby("era"):
                rows.extend(fit(era_data, outcome,
                                ["absolute_conservatism_z", "incumbent_i", "nonwhite_share",
                                 "white_college_share", "chamber"], "party_era_context",
                                f"{party}:{era}", ["absolute_conservatism_z"]))
    # CQI is a separate retrospective, partial-pooled candidate estimate. It
    # is included only in the era comparison requested for the public chart;
    # it does not replace the raw federal or presidential durability outcomes.
    for party in ("D", "R"):
        sample = data[data.party.eq(party)]
        for era, era_data in sample.groupby("era"):
            rows.extend(fit(era_data, "candidate_quality_index",
                            ["absolute_conservatism_z", "incumbent_i", "nonwhite_share",
                             "white_college_share", "chamber"], "party_era_context",
                            f"{party}:{era}", ["absolute_conservatism_z"]))
    return pd.DataFrame(rows)


def run_issues(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    measures = {
        **{f"family:{family}": (f"issue_conservative_{family}", f"issue_convergence_{family}", f"issue_congruence_{family}")
           for family in ISSUE_DIRECTIONS},
        **{f"primitive:{axis}": (f"primitive_conservative_{axis}", f"primitive_convergence_{axis}", f"primitive_congruence_{axis}")
           for axis in PRIMITIVE_DIRECTIONS},
    }
    for measure, (position, convergence, congruence) in measures.items():
        for party in ("D", "R"):
            sample = panel[panel.party.eq(party) & panel[position].notna()].copy()
            for outcome in OUTCOMES:
                rows.extend(fit(sample, outcome,
                                [position, "nonwhite_share", "white_college_share", "cycle", "chamber"],
                                f"issue_total:{measure}", party, [position]))
                rows.extend(fit(sample, outcome,
                                [position, "incumbent_i", "candidate_finance_advantage", "nonwhite_share",
                                 "white_college_share", "cycle", "chamber"],
                                f"issue_mediator_adjusted:{measure}", party, [position]))
                rows.extend(fit(sample, outcome,
                                [position, "district_republicanism_z", congruence, "nonwhite_share",
                                 "white_college_share", "cycle", "chamber"],
                                f"issue_district_congruence:{measure}", party, [position, congruence]))
                for era, era_data in sample.groupby("era"):
                    rows.extend(fit(era_data, outcome,
                                    [position, "nonwhite_share", "white_college_share", "chamber"],
                                    f"issue_era:{measure}", f"{party}:{era}", [position]))
        # A pooled convergence coefficient is retained only as a compact
        # descriptive summary; party-specific estimates remain primary.
        for outcome in OUTCOMES:
            rows.extend(fit(panel[panel[convergence].notna()], outcome,
                            ["democratic_i", convergence, "nonwhite_share", "white_college_share",
                             "cycle", "chamber"], f"issue_pooled_convergence:{measure}", "all",
                            [convergence]))
    result = pd.DataFrame(rows)
    primary = (result.specification.str.startswith("issue_total:primitive:")
               & result.outcome.isin(["candidate_federal_overperformance",
                                      "candidate_presidential_overperformance"])
               & result.status.eq("estimated"))
    result["primary_bh_q_value"] = np.nan
    result["congruence_bh_q_value"] = np.nan
    for party in ("D", "R"):
        selected = primary & result["sample"].eq(party)
        result.loc[selected, "primary_bh_q_value"] = bh(result.loc[selected, "p_value"])
        congruence = (result.specification.str.startswith("issue_district_congruence:primitive:")
                      & result.term.str.startswith("primitive_congruence_")
                      & result.outcome.isin(["candidate_federal_overperformance",
                                             "candidate_presidential_overperformance"])
                      & result.status.eq("estimated") & result["sample"].eq(party))
        result.loc[congruence, "congruence_bh_q_value"] = bh(result.loc[congruence, "p_value"])
    return result


def bh(values: pd.Series) -> np.ndarray:
    p = pd.to_numeric(values, errors="coerce").to_numpy(float)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = np.minimum.accumulate((ranked * len(ranked) / np.arange(1, len(ranked) + 1))[::-1])[::-1]
    result = np.empty(len(p))
    result[order] = np.minimum(adjusted, 1.0)
    return result


def coverage(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for party in ("D", "R"):
        sample = panel[panel.party.eq(party)]
        rows.append({"measure": "shor_absolute", "party": party,
                     "candidate_cycles": int(sample.absolute_conservatism_z.notna().sum()),
                     "people": int(sample.loc[sample.absolute_conservatism_z.notna(), "person_id"].nunique()),
                     "cycles": ",".join(map(str, sorted(sample.loc[sample.absolute_conservatism_z.notna(), "cycle"].unique())))})
        for family in ISSUE_DIRECTIONS:
            column = f"issue_conservative_{family}"
            observed = sample[column].notna()
            rows.append({"measure": family, "party": party,
                         "candidate_cycles": int(observed.sum()),
                         "people": int(sample.loc[observed, "person_id"].nunique()),
                         "cycles": ",".join(map(str, sorted(sample.loc[observed, "cycle"].unique())))})
        for axis in PRIMITIVE_DIRECTIONS:
            column = f"primitive_conservative_{axis}"
            observed = sample[column].notna()
            rows.append({"measure": f"primitive:{axis}", "party": party,
                         "candidate_cycles": int(observed.sum()),
                         "people": int(sample.loc[observed, "person_id"].nunique()),
                         "cycles": ",".join(map(str, sorted(sample.loc[observed, "cycle"].unique())))})
    return pd.DataFrame(rows)


def overlap_audit(panel: pd.DataFrame) -> pd.DataFrame:
    observed = panel.dropna(subset=["absolute_conservatism_z"])
    party_stats = (observed.groupby("party", as_index=False)
                   .agg(candidate_cycles=("canonical_candidate_id", "size"),
                        people=("person_id", "nunique"), mean=("absolute_conservatism_z", "mean"),
                        sd=("absolute_conservatism_z", "std"), minimum=("absolute_conservatism_z", "min"),
                        p10=("absolute_conservatism_z", lambda x: x.quantile(.1)),
                        median=("absolute_conservatism_z", "median"),
                        p90=("absolute_conservatism_z", lambda x: x.quantile(.9)),
                        maximum=("absolute_conservatism_z", "max")))
    lower = observed.groupby("party").absolute_conservatism_z.min().max()
    upper = observed.groupby("party").absolute_conservatism_z.max().min()
    party_stats["common_support_low"] = lower
    party_stats["common_support_high"] = upper
    party_stats["inside_common_support"] = party_stats.party.map(
        observed[observed.absolute_conservatism_z.between(lower, upper)].groupby("party").size()).fillna(0).astype(int)
    return party_stats


def selection_audit(panel: pd.DataFrame) -> pd.DataFrame:
    data = panel.copy()
    data["shor_observed"] = data.absolute_conservatism_z.notna()
    return (data.groupby(["party", "shor_observed"], as_index=False)
            .agg(candidate_cycles=("canonical_candidate_id", "size"),
                 people=("person_id", "nunique"), winner_share=("winner", "mean"),
                 incumbent_share=("incumbent_i", "mean"), mean_cmo=("candidate_cmo", "mean"),
                 mean_federal_overperformance=("candidate_federal_overperformance", "mean")))


def durability(panel: pd.DataFrame) -> pd.DataFrame:
    repeated = panel[panel.person_id.notna()].groupby(["person_id", "party"]).filter(lambda x: len(x) >= 2)
    rows = []
    measures = {"shor_absolute": "absolute_conservatism_z", **{
        f"family:{family}": f"issue_conservative_{family}" for family in ISSUE_DIRECTIONS}, **{
        f"primitive:{axis}": f"primitive_conservative_{axis}" for axis in PRIMITIVE_DIRECTIONS}}
    for label, column in measures.items():
        usable = repeated.dropna(subset=[column]).copy()
        for party in ("D", "R"):
            sample = usable[usable.party.eq(party)]
            person = (sample.groupby("person_id", as_index=False)
                      .agg(position=(column, "mean"), races=("cycle", "size"),
                           federal_mean=("candidate_federal_overperformance", "mean"),
                           presidential_mean=("candidate_presidential_overperformance", "mean")))
            for outcome in ("federal_mean", "presidential_mean"):
                if len(person) < 12 or person.position.nunique() < 3:
                    rows.append({"measure": label, "party": party, "outcome": outcome,
                                 "people": len(person), "status": "underpowered"})
                    continue
                slope, intercept, r, p, se = stats.linregress(person.position, person[outcome])
                rows.append({"measure": label, "party": party, "outcome": outcome,
                             "people": len(person), "status": "estimated", "coefficient": slope,
                             "standard_error": se, "p_value": p, "r_squared": r * r})
    return pd.DataFrame(rows)


def markdown(frame: pd.DataFrame) -> str:
    shown = frame.copy()
    for column in shown.select_dtypes(include="number"):
        shown[column] = shown[column].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
    return "\n".join(["| " + " | ".join(shown.columns) + " |",
                      "|" + "|".join(["---"] * len(shown.columns)) + "|",
                      *["| " + " | ".join(map(str, row)) + " |"
                        for row in shown.itertuples(index=False, name=None)]])


def write_report(panel: pd.DataFrame, estimates: pd.DataFrame, issues: pd.DataFrame,
                 audit: pd.DataFrame, overlap: pd.DataFrame, selection: pd.DataFrame,
                 durable: pd.DataFrame) -> None:
    absolute = estimates[(estimates.specification == "party_total_context")
                         & estimates.term.eq("absolute_conservatism_z")
                         & estimates.outcome.isin(["candidate_cmo", "candidate_federal_overperformance",
                                                   "candidate_presidential_overperformance"])]
    mediation = estimates[(estimates.specification.isin(["party_total_context", "party_mediator_adjusted"]))
                           & estimates.term.eq("absolute_conservatism_z")
                           & estimates.outcome.isin(["candidate_cmo", "candidate_federal_overperformance"])]
    incumbency = estimates[(estimates.specification.isin(["common_incumbency", "party_specific_incumbency"]))
                           & estimates.term.isin(["incumbent_i", "democratic_x_incumbency"])]
    era = estimates[(estimates.specification.eq("party_era_context"))
                    & estimates.term.eq("absolute_conservatism_z")
                    & estimates.outcome.isin(["candidate_cmo", "candidate_quality_index",
                                              "candidate_federal_overperformance"])]
    leave_out = estimates[(estimates.specification.eq("party_leave_cycle_out"))
                          & estimates.term.eq("absolute_conservatism_z")
                          & estimates["sample"].str.startswith("D:")
                          & estimates.outcome.isin(["candidate_cmo", "candidate_federal_overperformance"])]
    selection_sensitivity = estimates[(estimates.specification.isin(["party_winners_only", "party_prior_service_only"]))
                                      & estimates.term.eq("absolute_conservatism_z")
                                      & estimates.outcome.isin(["candidate_cmo", "candidate_federal_overperformance"])]
    issue_primary = issues[(issues.specification.str.startswith("issue_total:primitive:"))
                           & issues.outcome.isin(["candidate_federal_overperformance",
                                                  "candidate_presidential_overperformance"])]
    congruence = issues[(issues.specification.str.startswith("issue_district_congruence:"))
                        & issues.term.str.startswith("issue_congruence_")
                        & issues.outcome.eq("candidate_federal_overperformance")]
    lines = [
        "# Absolute ideology rebuild", "", "## Estimand", "",
        "The outcome is always ideology-blind: actual candidate margin minus an expected statewide, federal, presidential, or cross-fitted CMO baseline. Positive values mean that the candidate of either party ran ahead. Ideology is analyzed afterward and is never included in the construction of expected performance.", "",
        "`total_context` controls for district demographics, cycle, and chamber but deliberately omits incumbency and finance. `mediator_adjusted` adds those variables and therefore estimates a narrower direct association rather than the total electoral pathway.", "",
        "## Current reading", "",
        "- Absolute Shor–McCarty position produces a clear asymmetric result. More conservative Democrats run substantially ahead of every baseline. The Republican point estimates generally favor less conservative candidates, but they are too imprecise to establish a Republican moderation effect.",
        "- Among winners only, less conservative Republicans do have a significant corrected-CMO advantage, consistent with the proposed crossover story, but that result does not carry through to federal-relative performance or the prior-service-only sample. It is suggestive rather than a symmetric counterpart to the Democratic result.",
        "- A common incumbency effect is compatible with corrected CMO and statewide-ticket performance: the party-specific Democratic-minus-Republican increment is not distinguishable from zero. Federal-relative performance is different, with a larger Republican incumbency association in this selected sample. Consequently the common-incumbency result is a sensitivity analysis, not a universal fact.",
        "- Adding incumbency and finance does not remove the Democratic Shor relationship for CMO or federal-relative performance. Presidential-relative performance attenuates, partly because finance-complete cases are a smaller selected subset.",
        "- Primitive issue measures recover the substantive coalition more clearly than broad families. Democratic overperformance is associated with market autonomy, gun access, restrictive civil-social positions, and religion-state accommodation, while welfare generosity remains favorable in the opposite economic direction. This is closer to a culturally conservative, economically mixed or populist bundle than to one universal left-right axis.",
        "- The tax-burden signal remains unsuitable for interpretation as generic fiscal conservatism. It does not identify who bears a tax, and its direction conflicts with a simple low-tax story. Tax burden and tax distribution must remain separate.",
        "- District-congruence findings are exploratory. Several nominal interactions appear, but coverage and multiple comparisons are limiting; they should guide case research rather than enter a forecast.", "",
        "## Coverage", "", markdown(audit), "", "## Absolute-scale overlap", "", markdown(overlap), "",
        "The parties have limited common support on the absolute scale. Republican moderation estimates therefore rely on a narrow tail of the Republican distribution and should not be treated as a mirror-image test with equal power.", "",
        "## Selection into Shor–McCarty coverage", "", markdown(selection), "",
        "Shor coverage is a selected officeholder sample. Differences between observed and unobserved candidates quantify why these estimates describe successful legislative candidates rather than all people who ran.", "",
        "### Selection sensitivities", "", markdown(selection_sensitivity[["sample", "outcome", "specification", "n", "people", "coefficient", "cluster_se", "p_value", "status"]]), "",
        "## Absolute Shor–McCarty results", "",
        markdown(absolute[["sample", "outcome", "n", "people", "coefficient", "cluster_se", "ci_low", "ci_high", "p_value", "status"]]), "",
        "Positive coefficients mean moving right helps; negative coefficients mean moving left helps. The Democratic coefficients are positive across all primary outcomes. Republican coefficients generally point toward an advantage for moving left but remain imprecise.", "",
        "## Symmetric-incumbency sensitivity", "", markdown(incumbency[["outcome", "specification", "term", "n", "coefficient", "cluster_se", "p_value", "status"]]), "",
        "## Total association versus mediator adjustment", "",
        markdown(mediation[["sample", "outcome", "specification", "n", "coefficient", "cluster_se", "p_value", "status"]]), "",
        "## Issue-position results", "",
        "Positive coefficients mean that a more conservative absolute position is associated with greater candidate-directional overperformance. These estimates use only temporally eligible ideology-v3 evidence.", "",
        markdown(issue_primary[["sample", "outcome", "specification", "n", "people", "coefficient", "cluster_se", "p_value", "primary_bh_q_value", "status"]]), "",
        "## District congruence", "",
        "A positive congruence coefficient means conservative positioning becomes more favorable as the district federal baseline becomes more Republican, and liberal positioning becomes more favorable as it becomes more Democratic.", "",
        markdown(congruence[["sample", "specification", "n", "people", "coefficient", "cluster_se", "p_value", "congruence_bh_q_value", "status"]]), "",
        "## Era heterogeneity", "", markdown(era[["sample", "outcome", "n", "coefficient", "cluster_se", "p_value", "status"]]), "",
        "## Democratic leave-one-cycle-out stability", "", markdown(leave_out[["sample", "outcome", "n", "coefficient", "cluster_se", "p_value", "status"]]), "",
        "## Durable repeat-candidate evidence", "", markdown(durable), "",
        "## Interpretation rules", "",
        "- Party-specific estimates are primary; pooled convergence is descriptive only.",
        "- Federal and presidential outcomes are the primary durability tests.",
        "- Incumbency and finance are reported both as mechanisms and controls, never silently absorbed into expected performance.",
        "- Sparse issue families and era cells remain underpowered even when point estimates are large.",
        "- Shor scores are absolute and nationally bridged, but are career scores observed only for people who served.",
        "- No estimate in this report is automatically eligible for the production forecast.",
        "- Candidate margins already encode the arithmetic behind the crossover intuition: moving one voter from the opponent changes the two-party margin twice as much as adding one same-party voter. Aggregate results cannot identify whether an observed margin gain actually came from persuasion or differential turnout.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    RESEARCH.mkdir(parents=True, exist_ok=True)
    panel = build_panel()
    estimates = run_absolute(panel)
    issue_estimates = run_issues(panel)
    audit = coverage(panel)
    overlap = overlap_audit(panel)
    selection = selection_audit(panel)
    durable = durability(panel)
    panel.to_csv(RESEARCH / "absolute_rebuild_panel.csv", index=False)
    estimates.to_csv(RESEARCH / "absolute_rebuild_estimates.csv", index=False)
    issue_estimates.to_csv(RESEARCH / "absolute_rebuild_issue_estimates.csv", index=False)
    audit.to_csv(RESEARCH / "absolute_rebuild_coverage.csv", index=False)
    overlap.to_csv(RESEARCH / "absolute_rebuild_overlap.csv", index=False)
    selection.to_csv(RESEARCH / "absolute_rebuild_selection.csv", index=False)
    durable.to_csv(RESEARCH / "absolute_rebuild_durability.csv", index=False)
    write_report(panel, estimates, issue_estimates, audit, overlap, selection, durable)
    print(f"panel={len(panel)} shor={panel.absolute_conservatism_z.notna().sum()} issue_estimates={len(issue_estimates)}")


if __name__ == "__main__":
    main()
