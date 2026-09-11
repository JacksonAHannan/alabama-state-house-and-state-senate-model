"""Test common incumbency and absolute Shor–McCarty ideology across parties."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:
    from analyze_historical_shor_mccarty_cmo import RAW, ROOT, choose_match, normalize, service_years
except ModuleNotFoundError:  # Imported as scripts.* by pytest.
    from scripts.analyze_historical_shor_mccarty_cmo import RAW, ROOT, choose_match, normalize, service_years

WAR = ROOT / "data" / "processed" / "war"
FEDERAL = ROOT / "data" / "processed" / "elections" / "historical_federal_district_baselines.csv"
OUT = ROOT / "research" / "cmo_ideology"
REPORT = ROOT / "project_docs" / "model" / "SYMMETRIC_INCUMBENCY_IDEOLOGY.md"


def build_matches() -> pd.DataFrame:
    candidates = pd.read_csv(WAR / "preliminary_cmo_candidates.csv", low_memory=False)
    candidates = candidates[candidates.cycle.between(1998, 2018)].copy()
    source = pd.read_csv(RAW, sep="\t", low_memory=False)
    rows: list[dict] = []
    for party, candidate_rows in candidates.groupby("party"):
        party_source = source[source.st.eq("AL") & source.party.eq(party)].copy()
        party_source["normalized_name"] = party_source.name.map(normalize)
        for candidate in candidate_rows.itertuples(index=False):
            values = pd.Series(candidate._asdict())
            match, method, similarity, note = choose_match(values, party_source)
            base = {key: values[key] for key in ["cycle", "chamber", "district", "party", "candidate", "canonical_candidate_id", "person_id", "incumbent", "winner", "candidate_cmo_total_oof"]}
            if match is None:
                rows.append({**base, "match_status": method, "match_method": "none", "similarity": similarity, "suggested_source_name": note})
                continue
            same_id = party_source[party_source.u_id.eq(match.u_id)]
            scores = pd.to_numeric(same_id.np_score, errors="coerce").dropna().unique()
            if len(scores) != 1:
                rows.append({**base, "match_status": "ambiguous_multiple_scores", "match_method": method, "similarity": similarity, "suggested_source_name": match["name"]})
                continue
            years = service_years(match)
            rows.append({
                **base, "match_status": "matched", "match_method": method, "similarity": similarity,
                "suggested_source_name": match["name"], "shor_u_id": match.u_id,
                "shor_np_score": float(scores[0]), "served_by_election": any(year <= int(values.cycle) for year in years),
                "first_observed_service_year": min(years) if years else np.nan,
            })
    return pd.DataFrame(rows)


def build_panel(matches: pd.DataFrame) -> pd.DataFrame:
    races = pd.read_csv(WAR / "preliminary_cmo_races.csv", low_memory=False)
    federal = pd.read_csv(FEDERAL)
    columns = ["cycle", "chamber", "district", "legislative_dem_margin", "statewide_index_margin", "prior_pres_dem_margin",
               "nonwhite_share", "white_college_share", "canonical_finance_complete", "canonical_log_fundraising_ratio_d_to_r"]
    panel = (matches[matches.match_status.eq("matched")]
             .merge(races[columns], on=["cycle", "chamber", "district"], validate="many_to_one")
             .merge(federal, on=["cycle", "chamber", "district"], how="left", validate="many_to_one"))
    panel["democratic_i"] = panel.party.eq("D").astype(int)
    panel["incumbent_i"] = panel.incumbent.fillna(False).astype(int)
    panel["party_direction"] = np.where(panel.party.eq("D"), 1.0, -1.0)
    panel["candidate_cmo"] = panel.candidate_cmo_total_oof
    panel["candidate_statewide_overperformance"] = panel.party_direction * (panel.legislative_dem_margin - panel.statewide_index_margin)
    panel["candidate_federal_overperformance"] = panel.party_direction * (panel.legislative_dem_margin - panel.federal_index_margin)
    panel["candidate_presidential_overperformance"] = panel.party_direction * (panel.legislative_dem_margin - panel.prior_pres_dem_margin)
    panel["candidate_finance_advantage"] = panel.party_direction * panel.canonical_log_fundraising_ratio_d_to_r
    panel["candidate_federal_baseline"] = panel.party_direction * panel.federal_index_margin
    baseline_sd = panel.candidate_federal_baseline.std(ddof=0)
    panel["baseline_hostility_z"] = -(panel.candidate_federal_baseline - panel.candidate_federal_baseline.mean()) / baseline_sd
    source = pd.read_csv(RAW, sep="\t", low_memory=False)
    national = pd.to_numeric(source.np_score, errors="coerce").dropna()
    panel["absolute_np_z"] = (panel.shor_np_score - national.mean()) / national.std(ddof=0)
    party_references = {
        party: np.sort(pd.to_numeric(group.np_score, errors="coerce").dropna().to_numpy())
        for party, group in source.groupby("party")
    }
    panel["national_party_conservative_percentile"] = panel.apply(
        lambda row: 100 * np.searchsorted(party_references[row.party], row.shor_np_score, side="right") / len(party_references[row.party]), axis=1)
    panel["democratic_x_ideology"] = panel.democratic_i * panel.absolute_np_z
    # Higher values mean movement toward the opposite party/ideological center:
    # rightward for Democrats and leftward for Republicans.
    panel["cross_party_moderation"] = panel.party_direction * panel.absolute_np_z
    panel["democratic_x_moderation"] = panel.democratic_i * panel.cross_party_moderation
    panel["center_proximity"] = -panel.shor_np_score.abs() / national.std(ddof=0)
    panel["democratic_x_center_proximity"] = panel.democratic_i * panel.center_proximity
    panel["moderation_x_hostility"] = panel.cross_party_moderation * panel.baseline_hostility_z
    panel["democratic_x_incumbency"] = panel.democratic_i * panel.incumbent_i
    return panel


def fit(frame: pd.DataFrame, outcome: str, terms: list[str], label: str, sample: str = "all") -> tuple[dict, pd.DataFrame]:
    needed = [outcome, "shor_u_id", *terms]
    data = frame.dropna(subset=needed).copy()
    X = pd.DataFrame({"intercept": 1.0}, index=data.index)
    for term in terms:
        if term in {"cycle", "chamber"}:
            X = pd.concat([X, pd.get_dummies(data[term].astype(str), prefix=term, drop_first=True, dtype=float)], axis=1)
        else:
            X[term] = pd.to_numeric(data[term], errors="coerce")
    A = X.to_numpy(float); y = data[outcome].to_numpy(float)
    if len(data) <= A.shape[1] + 2:
        return {"sample": sample, "outcome": outcome, "specification": label, "n": len(data), "status": "underpowered"}, pd.DataFrame()
    inv = np.linalg.pinv(A.T @ A); beta = inv @ A.T @ y; residual = y - A @ beta
    groups = pd.Categorical(data.shor_u_id).codes; unique = np.unique(groups); meat = np.zeros((A.shape[1], A.shape[1]))
    for group in unique:
        score = A[groups == group].T @ residual[groups == group]
        meat += np.outer(score, score)
    covariance = inv @ meat @ inv
    if len(unique) > 1:
        covariance *= len(unique) / (len(unique) - 1) * (len(data) - 1) / (len(data) - A.shape[1])
    se = np.sqrt(np.maximum(np.diag(covariance), 0)); names = list(X.columns)
    term_rows = []
    for index, name in enumerate(names):
        statistic = beta[index] / se[index] if se[index] else np.nan
        term_rows.append({"sample": sample, "outcome": outcome, "specification": label, "term": name,
                          "coefficient": beta[index], "cluster_se": se[index],
                          "ci_low": beta[index] - 1.96 * se[index], "ci_high": beta[index] + 1.96 * se[index],
                          "p_value": 2 * stats.t.sf(abs(statistic), df=max(len(unique) - 1, 1))})
    summary = {"sample": sample, "outcome": outcome, "specification": label, "n": len(data), "people": len(unique), "status": "estimated"}
    return summary, pd.DataFrame(term_rows), covariance, names, beta


def linear_combination(term_rows: pd.DataFrame, covariance: np.ndarray, names: list[str], beta: np.ndarray,
                       terms: dict[str, float], label: str) -> dict:
    weights = np.zeros(len(names))
    for term, weight in terms.items():
        if term in names:
            weights[names.index(term)] = weight
    estimate = float(weights @ beta); se = float(np.sqrt(max(weights @ covariance @ weights, 0)))
    statistic = estimate / se if se else np.nan
    return {"contrast": label, "coefficient": estimate, "cluster_se": se, "ci_low": estimate - 1.96 * se,
            "ci_high": estimate + 1.96 * se, "p_value": float(2 * stats.norm.sf(abs(statistic)))}


def run_models(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    outcomes = ["candidate_cmo", "candidate_statewide_overperformance", "candidate_federal_overperformance", "candidate_presidential_overperformance"]
    specs = {
        "party_specific_incumbency": ["democratic_i", "incumbent_i", "democratic_x_incumbency", "cycle", "chamber"],
        "party_specific_incumbency_plus_ideology": ["democratic_i", "incumbent_i", "democratic_x_incumbency", "absolute_np_z", "democratic_x_ideology", "cycle", "chamber"],
        "party_specific_plus_ideology_context": ["democratic_i", "incumbent_i", "democratic_x_incumbency", "absolute_np_z", "democratic_x_ideology", "nonwhite_share", "white_college_share", "cycle", "chamber"],
        "common_incumbency_absolute_ideology": ["democratic_i", "incumbent_i", "absolute_np_z", "democratic_x_ideology", "cycle", "chamber"],
        "common_plus_district_context": ["democratic_i", "incumbent_i", "absolute_np_z", "democratic_x_ideology", "nonwhite_share", "white_college_share", "cycle", "chamber"],
        "common_plus_context_finance": ["democratic_i", "incumbent_i", "absolute_np_z", "democratic_x_ideology", "nonwhite_share", "white_college_share", "candidate_finance_advantage", "cycle", "chamber"],
        "common_cross_party_moderation": ["democratic_i", "incumbent_i", "cross_party_moderation", "nonwhite_share", "white_college_share", "cycle", "chamber"],
        "party_specific_cross_party_moderation": ["democratic_i", "incumbent_i", "cross_party_moderation", "democratic_x_moderation", "nonwhite_share", "white_college_share", "cycle", "chamber"],
        "party_specific_moderation_plus_finance": ["democratic_i", "incumbent_i", "cross_party_moderation", "democratic_x_moderation", "nonwhite_share", "white_college_share", "candidate_finance_advantage", "cycle", "chamber"],
        "common_center_proximity": ["democratic_i", "incumbent_i", "center_proximity", "nonwhite_share", "white_college_share", "cycle", "chamber"],
        "party_specific_center_proximity": ["democratic_i", "incumbent_i", "center_proximity", "democratic_x_center_proximity", "nonwhite_share", "white_college_share", "cycle", "chamber"],
    }
    summaries, terms, contrasts = [], [], []
    for outcome in outcomes:
        for label, variables in specs.items():
            result = fit(panel, outcome, variables, label)
            summary, detail = result[0], result[1]
            summaries.append(summary)
            if detail.empty:
                continue
            covariance, names, beta = result[2:]
            terms.append(detail)
            if "democratic_x_incumbency" in variables:
                for contrast in [
                    linear_combination(detail, covariance, names, beta, {"incumbent_i": 1}, "Republican incumbency"),
                    linear_combination(detail, covariance, names, beta, {"incumbent_i": 1, "democratic_x_incumbency": 1}, "Democratic incumbency"),
                    linear_combination(detail, covariance, names, beta, {"democratic_x_incumbency": 1}, "Democratic-minus-Republican incumbency"),
                ]:
                    contrasts.append({"sample": "all", "outcome": outcome, "specification": label, **contrast})
            if "absolute_np_z" in variables:
                for contrast in [
                    linear_combination(detail, covariance, names, beta, {"absolute_np_z": 1}, "Republican absolute-ideology slope"),
                    linear_combination(detail, covariance, names, beta, {"absolute_np_z": 1, "democratic_x_ideology": 1}, "Democratic absolute-ideology slope"),
                    linear_combination(detail, covariance, names, beta, {"democratic_x_ideology": 1}, "Democratic-minus-Republican ideology slope"),
                ]:
                    contrasts.append({"sample": "all", "outcome": outcome, "specification": label, **contrast})
            if "cross_party_moderation" in variables:
                democratic_terms = {"cross_party_moderation": 1}
                if "democratic_x_moderation" in variables:
                    democratic_terms["democratic_x_moderation"] = 1
                for contrast in [
                    linear_combination(detail, covariance, names, beta, {"cross_party_moderation": 1}, "Republican movement toward center"),
                    linear_combination(detail, covariance, names, beta, democratic_terms, "Democratic movement toward center"),
                    linear_combination(detail, covariance, names, beta, {"democratic_x_moderation": 1}, "Democratic-minus-Republican moderation slope") if "democratic_x_moderation" in variables else None,
                ]:
                    if contrast is not None:
                        contrasts.append({"sample": "all", "outcome": outcome, "specification": label, **contrast})
            if "center_proximity" in variables:
                democratic_terms = {"center_proximity": 1}
                if "democratic_x_center_proximity" in variables:
                    democratic_terms["democratic_x_center_proximity"] = 1
                for contrast in [
                    linear_combination(detail, covariance, names, beta, {"center_proximity": 1}, "Republican center proximity"),
                    linear_combination(detail, covariance, names, beta, democratic_terms, "Democratic center proximity"),
                ]:
                    contrasts.append({"sample": "all", "outcome": outcome, "specification": label, **contrast})

    # Swing-voter hypothesis: moderation should matter more when the candidate's
    # federal baseline is less favorable. Estimate that interaction separately
    # by party so Alabama's very different party distributions do not pool it.
    for party in ("D", "R"):
        sample = panel[panel.party.eq(party)]
        for outcome in outcomes:
            result = fit(sample, outcome, ["incumbent_i", "cross_party_moderation", "baseline_hostility_z", "moderation_x_hostility", "nonwhite_share", "white_college_share", "cycle", "chamber"], "party_moderation_x_baseline_hostility", party)
            summaries.append(result[0])
            terms.append(result[1])

    # Estimate incumbency among Republicans, then impose that common effect on
    # both parties and test ideology among Democrats after removing it.
    calibrated = []
    for outcome in outcomes:
        republican = panel[panel.party.eq("R")]
        result = fit(republican, outcome, ["incumbent_i", "absolute_np_z", "nonwhite_share", "white_college_share", "cycle", "chamber"], "republican_incumbency_calibration", "Republicans")
        summaries.append(result[0]); terms.append(result[1])
        incumbent_beta = result[4][result[3].index("incumbent_i")]
        adjusted = panel[panel.party.eq("D")].copy()
        adjusted["republican_calibrated_outcome"] = adjusted[outcome] - incumbent_beta * adjusted.incumbent_i
        second = fit(adjusted, "republican_calibrated_outcome", ["absolute_np_z", "nonwhite_share", "white_college_share", "cycle", "chamber"], f"republican_calibrated_{outcome}", "Democrats")
        summaries.append(second[0]); terms.append(second[1])
        row = second[1].loc[second[1].term.eq("absolute_np_z")].iloc[0]
        calibrated.append({"outcome": outcome, "republican_incumbency_coefficient": incumbent_beta,
                           "democratic_ideology_after_common_incumbency": row.coefficient,
                           "cluster_se": row.cluster_se, "p_value": row.p_value,
                           "democratic_n": second[0]["n"], "republican_n": result[0]["n"]})
    return pd.DataFrame(summaries), pd.concat(terms, ignore_index=True), pd.DataFrame(contrasts), pd.DataFrame(calibrated)


def markdown(frame: pd.DataFrame) -> str:
    shown = frame.copy()
    for column in shown.select_dtypes(include=["number"]).columns:
        shown[column] = shown[column].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
    return "\n".join(["| " + " | ".join(shown.columns) + " |", "|" + "|".join(["---"] * len(shown.columns)) + "|",
                      *["| " + " | ".join(str(value) for value in row) + " |" for row in shown.itertuples(index=False, name=None)]])


def democratic_terciles(panel: pd.DataFrame) -> pd.DataFrame:
    democrats = panel[panel.party.eq("D")].copy()
    democrats["alabama_democratic_third"] = pd.qcut(democrats.shor_np_score, 3, labels=["liberal", "middle", "conservative"], duplicates="drop")
    return (democrats.groupby("alabama_democratic_third", observed=True)
            .agg(candidate_cycles=("canonical_candidate_id", "size"), mean_absolute_np=("shor_np_score", "mean"),
                 median_absolute_np=("shor_np_score", "median"), mean_national_democratic_percentile=("national_party_conservative_percentile", "mean"))
            .reset_index())


def write_report(matches: pd.DataFrame, panel: pd.DataFrame, terms: pd.DataFrame, contrasts: pd.DataFrame, calibrated: pd.DataFrame, terciles: pd.DataFrame) -> None:
    coverage = matches.groupby(["cycle", "party", "match_status"]).size().unstack(fill_value=0).reset_index()
    positions = panel.groupby(["party", "incumbent_i"]).agg(candidate_cycles=("canonical_candidate_id", "size"), people=("shor_u_id", "nunique"), mean_absolute_np=("shor_np_score", "mean"), median_absolute_np=("shor_np_score", "median"), mean_national_party_conservative_percentile=("national_party_conservative_percentile", "mean")).reset_index()
    national = pd.read_csv(RAW, sep="\t", low_memory=False)
    national_positions = (national.groupby("party").agg(national_legislators=("u_id", "nunique"),
                          national_mean_np=("np_score", "mean"), national_median_np=("np_score", "median")).reset_index())
    incumbency = terms[(terms.specification.isin(["party_specific_incumbency", "party_specific_incumbency_plus_ideology", "party_specific_plus_ideology_context"])) & terms.term.isin(["incumbent_i", "democratic_x_incumbency"])]
    incumbency_contrasts = contrasts[contrasts.specification.eq("party_specific_plus_ideology_context") & contrasts.contrast.str.contains("incumbency")]
    focal = contrasts[contrasts.specification.eq("common_plus_district_context")]
    moderation = contrasts[contrasts.specification.isin(["common_cross_party_moderation", "party_specific_cross_party_moderation", "party_specific_moderation_plus_finance"])]
    proximity = contrasts[contrasts.specification.isin(["common_center_proximity", "party_specific_center_proximity"])]
    hostility = terms[(terms.specification.eq("party_moderation_x_baseline_hostility")) & terms.term.isin(["cross_party_moderation", "moderation_x_hostility"])]
    lines = ["# Symmetric incumbency and absolute ideology", "", "## Design", "",
             "Candidate-directional performance is positive when either party's candidate runs ahead of the named baseline. The party-specific model estimates Republican incumbency and a Democratic-minus-Republican incumbency interaction. The constrained model removes that interaction and estimates ideology on the national absolute Shor–McCarty scale.", "",
             "## Match coverage", "", markdown(coverage), "", "## Absolute ideological position", "", markdown(positions), "",
             "For comparison, the complete national source distribution is:", "", markdown(national_positions), "",
             "Even Alabama's internally liberal Democratic third is relatively conservative within the national Democratic distribution:", "", markdown(terciles), "",
             "## Is incumbency different by party?", "", markdown(incumbency[["outcome", "specification", "term", "coefficient", "cluster_se", "ci_low", "ci_high", "p_value"]]), "",
             "The fully contextualized party-specific incumbency contrasts are:", "", markdown(incumbency_contrasts[["outcome", "contrast", "coefficient", "cluster_se", "ci_low", "ci_high", "p_value"]]), "",
             "For each outcome, `incumbent_i` is the Republican incumbency estimate and `democratic_x_incumbency` is the additional Democratic effect. Failure to reject the interaction is not proof of equality, but it tests whether the one-sided pattern is statistically required by this selected Shor sample.", "",
             "## Common incumbency plus absolute ideology", "", markdown(focal[["outcome", "contrast", "coefficient", "cluster_se", "ci_low", "ci_high", "p_value"]]), "",
             "## Cross-party moderation", "", "Higher moderation means a Democrat moves right or a Republican moves left on the same absolute scale.", "", markdown(moderation[["outcome", "specification", "contrast", "coefficient", "cluster_se", "ci_low", "ci_high", "p_value"]]), "",
             "## Proximity to the absolute midpoint", "", markdown(proximity[["outcome", "specification", "contrast", "coefficient", "cluster_se", "ci_low", "ci_high", "p_value"]]), "",
             "## Does moderation matter more in electorally hostile districts?", "", markdown(hostility[["sample", "outcome", "term", "coefficient", "cluster_se", "ci_low", "ci_high", "p_value"]]), "",
             "The hostility interactions do not support the proposed mechanism that moderation becomes more valuable as the candidate's federal baseline becomes harder. For Democrats the interaction estimates are small and imprecise. For Republicans they point in the opposite direction and remain marginal rather than conclusive. This does not negate a crossover mechanism; it means this selected legislator sample cannot locate it through this district-hostility interaction.", "",
             "## Republican-calibrated incumbency", "", markdown(calibrated), "",
             "## Interpretation", "", "Absolute ideology materially changes the conclusion. Moving right on the national scale is strongly associated with Democratic overperformance on corrected CMO, statewide-ticket, federal, and presidential outcomes. The analogous estimate for Republicans moving left is not distinguishable from zero. A pooled cross-party moderation coefficient therefore should not be described as a symmetric finding: it is primarily a Democratic result. The Democratic relationship survives imposing the Republican incumbency coefficient, which is consistent with ideology contributing to the durable advantage that helped conservative Democrats become and remain incumbents rather than incumbency explaining the whole pattern.", "",
             "## Limits", "", "- Shor–McCarty coverage is conditional on legislative service and therefore strongly selects incumbents and winners.",
             "- The absolute score is nationally bridged but career-level; it is not a contemporaneous campaign-position measure.",
             "- A common incumbency coefficient is a transparent identifying assumption, not an established fact.",
             "- Finance and incumbency are possible mediators of ideological fit, so controlled estimates answer a narrower question than total overperformance."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    matches = build_matches(); panel = build_panel(matches)
    summaries, terms, contrasts, calibrated = run_models(panel)
    terciles = democratic_terciles(panel)
    matches.to_csv(OUT / "symmetric_incumbency_matches.csv", index=False)
    matches[matches.match_status.ne("matched")].to_csv(OUT / "symmetric_incumbency_review_queue.csv", index=False)
    panel.to_csv(OUT / "symmetric_incumbency_panel.csv", index=False)
    summaries.to_csv(OUT / "symmetric_incumbency_model_summary.csv", index=False)
    terms.to_csv(OUT / "symmetric_incumbency_model_terms.csv", index=False)
    contrasts.to_csv(OUT / "symmetric_incumbency_ideology_contrasts.csv", index=False)
    calibrated.to_csv(OUT / "symmetric_incumbency_republican_calibration.csv", index=False)
    terciles.to_csv(OUT / "symmetric_incumbency_absolute_ideology_terciles.csv", index=False)
    write_report(matches, panel, terms, contrasts, calibrated, terciles)
    print(matches.groupby(["party", "match_status"]).size().to_string())
    print(calibrated.to_string(index=False))


if __name__ == "__main__":
    main()
