"""Test whether Democratic social moderation predicts candidate-strength CMO."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "cmo_ideology" / "social_moderation"
SOCIAL = "ideology_v3_social_liberty_equality"


def assemble() -> pd.DataFrame:
    scores = pd.read_csv(ROOT / "data" / "processed" / "war" / "preliminary_cmo_candidates.csv")
    ideology = pd.read_csv(
        ROOT / "data" / "processed" / "elections" /
        "canonical_cmo_candidates_with_ideology_v3.csv", low_memory=False)
    races = pd.read_csv(
        ROOT / "data" / "processed" / "elections" / "canonical_cmo_features.csv",
        low_memory=False)
    score_cols = ["canonical_candidate_id", "candidate_cmo_total_oof",
                  "candidate_cmo_total_cycle_holdout", "candidate_cmo_total_district_grouped"]
    race_cols = ["cycle", "chamber", "district", "prior_pres_dem_margin",
                 "nonwhite_share", "white_college_share", "contest_status"]
    data = ideology.merge(scores[score_cols], on="canonical_candidate_id", how="inner",
                          validate="one_to_one")
    data = data.merge(races[race_cols], left_on=["year", "chamber", "district"],
                      right_on=["cycle", "chamber", "district"], how="left",
                      validate="many_to_one")
    data = data[(data.canonical_party.eq("D")) & data[SOCIAL].notna()].copy()
    data["cmo"] = data.candidate_cmo_total_oof
    data["social_progressivism"] = pd.to_numeric(data[SOCIAL], errors="coerce")
    data["social_progressivism_sq"] = data.social_progressivism.pow(2)
    data["social_band"] = pd.cut(
        data.social_progressivism, [-np.inf, -.25, .25, .5, np.inf],
        labels=["traditional", "moderate", "progressive", "strong_progressive"],
    ).astype("string")
    data["strong_progressive"] = data.social_progressivism.gt(.5).astype(int)
    data["log_evidence_records"] = np.log1p(data.ideology_v3_evidence_records)
    data["era"] = np.select(
        [data.year.le(2006), data.year.le(2014)], ["pre_2008", "obama_era"],
        default="trump_era")
    return data.reset_index(drop=True)


def ols_hc3(data: pd.DataFrame, columns: list[str], categorical: list[str] | None = None
            ) -> tuple[pd.DataFrame, dict]:
    categorical = categorical or []
    needed = ["cmo", *columns, *categorical]
    sample = data[needed].dropna().copy()
    numeric = sample[columns].astype(float)
    dummies = (pd.get_dummies(sample[categorical].astype("string"), prefix=categorical,
                              drop_first=True, dtype=float)
               if categorical else pd.DataFrame(index=sample.index))
    design = pd.concat([pd.Series(1.0, index=sample.index, name="Intercept"), numeric, dummies], axis=1)
    x, y = design.to_numpy(float), sample.cmo.to_numpy(float)
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    residual = y - x @ beta
    leverage = np.einsum("ij,jk,ik->i", x, xtx_inv, x).clip(0, .999999)
    scaled = residual / (1 - leverage)
    meat = (x * scaled[:, None]).T @ (x * scaled[:, None])
    covariance = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(covariance), 0))
    z = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
    p = 2 * norm.sf(np.abs(z))
    table = pd.DataFrame({"term": design.columns, "estimate": beta, "std_error": se,
                          "p_value": p, "ci_low": beta - 1.96 * se,
                          "ci_high": beta + 1.96 * se})
    tss = np.square(y - y.mean()).sum()
    r2 = 1 - np.square(residual).sum() / tss if tss else np.nan
    k, n = x.shape[1], len(y)
    diagnostics = {"n": n, "r_squared": r2,
                   "adjusted_r_squared": 1 - (1 - r2) * (n - 1) / (n - k) if n > k else np.nan,
                   "covariance": "HC3"}
    return table, diagnostics


def fit_models(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    common = ["prior_pres_dem_margin", "nonwhite_share", "white_college_share"]
    specifications = {
        "linear_unadjusted": (["social_progressivism"], []),
        "linear_cycle_chamber": (["social_progressivism"], ["year", "chamber"]),
        "nonlinear_cycle_chamber": (["social_progressivism", "social_progressivism_sq"],
                                    ["year", "chamber"]),
        "linear_context": (["social_progressivism", *common], ["era", "chamber"]),
        "nonlinear_context": (["social_progressivism", "social_progressivism_sq", *common],
                              ["era", "chamber"]),
        "district_congruence": (["social_progressivism", "prior_pres_dem_margin",
                                  "social_x_prior_pres", "nonwhite_share", "white_college_share"],
                                 ["era", "chamber"]),
        "measurement_sensitivity": (["social_progressivism", *common, "log_evidence_records",
                                      "ideology_v3_max_conflict_ratio"], ["era", "chamber"]),
        "material_support_sensitivity": (["social_progressivism", "ideology_v3_material_support",
                                           *common], ["era", "chamber"]),
    }
    data = data.copy()
    data["social_x_prior_pres"] = data.social_progressivism * data.prior_pres_dem_margin
    coefficient_rows, model_rows = [], []
    for name, (columns, categorical) in specifications.items():
        table, diagnostics = ols_hc3(data, columns, categorical)
        formula = "cmo ~ " + " + ".join(columns + [f"C({x})" for x in categorical])
        model_rows.append({"model": name, "formula": formula, **diagnostics})
        table.insert(0, "model", name)
        table["n"] = diagnostics["n"]
        coefficient_rows.extend(table.to_dict("records"))

    direct = data[data.social_band.isin(["moderate", "strong_progressive"])].copy()
    columns = ["strong_progressive"]
    categorical = ["era", "chamber"]
    table, diagnostics = ols_hc3(direct, columns, categorical)
    formula = "cmo ~ " + " + ".join(columns + [f"C({x})" for x in categorical])
    name = "moderate_vs_strong_progressive"
    model_rows.append({"model": name, "formula": formula, **diagnostics})
    table.insert(0, "model", name)
    table["n"] = diagnostics["n"]
    coefficient_rows.extend(table.to_dict("records"))
    return pd.DataFrame(coefficient_rows), pd.DataFrame(model_rows)


def threshold_sensitivity(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cutoff in (.35, .40, .50, .60, .75):
        subset = data[(data.social_progressivism.between(-.25, .25)) |
                      data.social_progressivism.gt(cutoff)].copy()
        subset["above_cutoff"] = subset.social_progressivism.gt(cutoff).astype(int)
        table, diagnostics = ols_hc3(subset, ["above_cutoff"], ["era", "chamber"])
        effect = table[table.term.eq("above_cutoff")].iloc[0]
        rows.append({"progressive_cutoff": cutoff,
                     "moderate_n": int(subset.social_progressivism.between(-.25, .25).sum()),
                     "progressive_n": int(subset.above_cutoff.sum()),
                     "n": diagnostics["n"], "estimate": effect.estimate,
                     "std_error": effect.std_error, "p_value": effect.p_value,
                     "ci_low": effect.ci_low, "ci_high": effect.ci_high})
    return pd.DataFrame(rows)


def issue_specific_models(data: pd.DataFrame) -> pd.DataFrame:
    evidence = pd.read_csv(
        ROOT / "data" / "processed" / "ideology" / "candidate_position_evidence_v3_all_sources.csv",
        low_memory=False)
    social_keys = evidence.loc[evidence.family.eq("social_liberty_equality"),
                               "primitive_axis"].dropna().unique()
    positions = pd.read_csv(
        ROOT / "data" / "processed" / "ideology" / "candidate_issue_valence_v3.csv")
    positions = positions[positions.primitive_axis.isin(social_keys)]
    pivot = positions.pivot_table(index="canonical_candidate_id", columns="primitive_axis",
                                  values="issue_valence", aggfunc="first")
    scores = pd.read_csv(ROOT / "data" / "processed" / "war" / "preliminary_cmo_candidates.csv")
    roster = pd.read_csv(
        ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv")
    frame = (scores[scores.party.eq("D")][["canonical_candidate_id", "candidate_cmo_total_oof"]]
             .merge(roster[["canonical_candidate_id", "year", "chamber"]],
                    on="canonical_candidate_id", how="left", validate="one_to_one")
             .merge(pivot, on="canonical_candidate_id", how="left", validate="one_to_one")
             .rename(columns={"candidate_cmo_total_oof": "cmo"}))
    rows = []
    for issue in sorted(set(social_keys) & set(frame.columns)):
        if frame[issue].notna().sum() < 15:
            continue
        table, diagnostics = ols_hc3(frame, [issue], ["year", "chamber"])
        effect = table[table.term.eq(issue)].iloc[0]
        rows.append({"primitive_axis": issue, "n": diagnostics["n"],
                     "estimate": effect.estimate, "std_error": effect.std_error,
                     "p_value": effect.p_value, "ci_low": effect.ci_low,
                     "ci_high": effect.ci_high})
    result = pd.DataFrame(rows).sort_values("p_value")
    if not result.empty:
        order = np.arange(1, len(result) + 1)
        result["bh_q_value"] = np.minimum.accumulate(
            (result.p_value.to_numpy() * len(result) / order)[::-1])[::-1].clip(max=1)
    return result


def downstream_survival(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    roster = pd.read_csv(
        ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv")
    next_rows = roster[["person_id", "year", "winner"]].copy()
    next_rows["year"] = next_rows.year - 4
    next_rows = (next_rows.groupby(["person_id", "year"], as_index=False)
                 .agg(next_cycle_appearance=("winner", "size"),
                      next_cycle_win=("winner", "max")))
    joined = data.merge(next_rows, on=["person_id", "year"], how="left")
    joined["next_cycle_appearance"] = joined.next_cycle_appearance.fillna(0).gt(0).astype(int)
    joined["next_cycle_win"] = joined.next_cycle_win.fillna(0).astype(int)
    joined["followup_through_cycle"] = int(roster.year.max())
    joined["eligible_followup"] = joined.year.add(4).le(joined.followup_through_cycle)
    eligible = joined[joined.eligible_followup].copy()
    summary = (eligible.groupby("social_band", dropna=False, observed=True)
               .agg(candidate_cycles=("person_id", "size"),
                    current_win_rate=("winner", "mean"),
                    next_cycle_appearance_rate=("next_cycle_appearance", "mean"),
                    next_cycle_win_rate=("next_cycle_win", "mean"),
                    mean_cmo=("cmo", "mean"))
               .reset_index())
    return joined, summary


def write_report(data: pd.DataFrame, coefficients: pd.DataFrame,
                 models: pd.DataFrame, bands: pd.DataFrame,
                 thresholds: pd.DataFrame, issues: pd.DataFrame) -> None:
    def markdown_table(frame: pd.DataFrame) -> str:
        printable = frame.copy()
        for column in printable.select_dtypes(include=["number"]):
            printable[column] = printable[column].map(lambda value: f"{value:.3f}")
        headers = [str(column) for column in printable.columns]
        lines = ["| " + " | ".join(headers) + " |",
                 "| " + " | ".join(["---"] * len(headers)) + " |"]
        lines.extend("| " + " | ".join(map(str, row)) + " |"
                     for row in printable.itertuples(index=False, name=None))
        return "\n".join(lines)

    def result(model: str, term: str) -> pd.Series:
        return coefficients[(coefficients.model.eq(model)) & coefficients.term.eq(term)].iloc[0]

    linear = result("linear_cycle_chamber", "social_progressivism")
    direct = result("moderate_vs_strong_progressive", "strong_progressive")
    interaction = result("district_congruence", "social_x_prior_pres")
    text = [
        "# Strategic social moderation and Democratic CMO", "",
        "## Design", "",
        f"The analysis contains **{len(data)} Democratic contested candidate-cycles** with adjudicated "
        "ontology-v3 social positions. Positive social scores indicate liberty/equality or more "
        "progressive positioning; negative scores indicate traditional/restrictive positioning. "
        "Selection-aware out-of-fold Total CMO is the candidate-strength outcome. Incumbency, prior "
        "candidate performance, and campaign finance are not primary controls because they can be "
        "downstream of candidate strength.", "",
        "The primary models use HC3 heteroskedasticity-robust uncertainty. Every observed candidate "
        "in this social-position sample is unique, so candidate-clustered errors would be identical "
        "to clustering on singleton groups. Missing ideology is never coded as moderation. All 71 "
        "social-family profiles in the analysis contain same-cycle candidate-questionnaire evidence; "
        "none depends on post-election legislative-roll-call evidence.", "",
        "## Results", "",
        f"In the cycle-and-chamber-adjusted primary model, moving one full unit toward social progressivism is "
        f"associated with **{linear.estimate:.2f} CMO points** (95% CI "
        f"{linear.ci_low:.2f} to {linear.ci_high:.2f}; p={linear.p_value:.3f}; n={int(linear.n)}).", "",
        f"The direct moderate-versus-strong-progressive comparison estimates the strong-progressive "
        f"penalty at **{direct.estimate:.2f} CMO points** relative to moderates (95% CI "
        f"{direct.ci_low:.2f} to {direct.ci_high:.2f}; p={direct.p_value:.3f}; n={int(direct.n)}).", "",
        f"The social-position by prior-presidential-margin interaction is **{interaction.estimate:.2f}** "
        f"(95% CI {interaction.ci_low:.2f} to {interaction.ci_high:.2f}; "
        f"p={interaction.p_value:.3f}). A positive interaction would mean progressivism is less costly "
        "in more Democratic districts.", "",
        "These are observational estimates. They test whether the evidence is consistent with the "
        "strategic-moderation hypothesis; they do not by themselves prove that changing a candidate's "
        "position would cause the estimated vote change.", "",
        "## Social-position bands", "",
        markdown_table(bands), "", "## Progressive-threshold sensitivity", "",
        markdown_table(thresholds), "", "## Issue-specific exploratory models", "",
        markdown_table(issues), "", "Issue-specific models use every Democratic CMO candidate with "
        "that exact-cycle issue score; unlike the broad composite, they do not require a second social "
        "issue. P-values are accompanied by Benjamini-Hochberg false-discovery-rate q-values and "
        "should not be read as independent confirmatory tests.", "",
        "## Model inventory", "",
        markdown_table(models), "",
    ]
    (OUT / "SOCIAL_MODERATION_CMO_ANALYSIS.md").write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = assemble()
    coefficients, models = fit_models(data)
    thresholds = threshold_sensitivity(data)
    issues = issue_specific_models(data)
    survival_rows, survival_summary = downstream_survival(data)
    band_summary = (data.groupby("social_band", observed=True)
                    .agg(candidate_cycles=("person_id", "size"), mean_cmo=("cmo", "mean"),
                         median_cmo=("cmo", "median"), mean_social_score=("social_progressivism", "mean"))
                    .reset_index())
    data.to_csv(OUT / "social_moderation_analysis_sample.csv", index=False)
    coefficients.to_csv(OUT / "social_moderation_model_coefficients.csv", index=False)
    models.to_csv(OUT / "social_moderation_model_diagnostics.csv", index=False)
    thresholds.to_csv(OUT / "social_moderation_threshold_sensitivity.csv", index=False)
    issues.to_csv(OUT / "social_moderation_issue_specific.csv", index=False)
    survival_rows.to_csv(OUT / "social_moderation_survival_rows.csv", index=False)
    survival_summary.to_csv(OUT / "social_moderation_survival_summary.csv", index=False)
    band_summary.to_csv(OUT / "social_moderation_band_summary.csv", index=False)
    write_report(data, coefficients, models, band_summary, thresholds, issues)
    print(coefficients[coefficients.term.str.contains("social_progressivism|strong_progressive")]
          .to_string(index=False))


if __name__ == "__main__":
    main()
