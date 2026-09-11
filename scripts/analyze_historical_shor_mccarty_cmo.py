"""Extend Shor–McCarty/overperformance analysis across available Alabama cycles.

The national individual file has Alabama service flags only from 1996 onward.
Accordingly, 1998–2018 are the headline years. 1994 matches are retained only
as a later-observed sensitivity tier and never enter headline inference.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ideology" / "shor_mccarty_individual_legislators_1993_2018.tsv"
WAR = ROOT / "data" / "processed" / "war"
FEDERAL = ROOT / "data" / "processed" / "elections" / "historical_federal_district_baselines.csv"
OUT = ROOT / "research" / "cmo_ideology"
REPORT = ROOT / "project_docs" / "model" / "HISTORICAL_SHOR_MCCARTY_CMO.md"

ALIASES = {
    "jody john letson": "john letson",
    "john letson": "john letson",
    "keahey marc": "george keahey",
    "beasley billy": "beasley william",
    "davis figures vivian": "figures vivian",
    "johnny mack morrow": "johnny morrow",
    "murphree": "murphee",
    "guin ken": "guin james",
    "jack page": "john page",
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = re.sub(r"\([^)]*\)|\b(jr|sr|ii|iii|iv)\b", " ", text, flags=re.I)
    tokens = re.findall(r"[a-z]+", text.lower())
    return " ".join(sorted(tokens))


def service_years(row: pd.Series, chamber: str | None = None) -> list[int]:
    chambers = (chamber,) if chamber else ("house", "senate")
    return [
        year for year in range(1993, 2019)
        if any(pd.to_numeric(row.get(f"{c}{year}"), errors="coerce") == 1 for c in chambers)
    ]


def district_at(row: pd.Series, chamber: str, year: int) -> float:
    return pd.to_numeric(row.get(f"{chamber[0]}district{year}" if chamber == "house" else f"sdistrict{year}"), errors="coerce")


def active(row: pd.Series, chamber: str, year: int) -> bool:
    return pd.to_numeric(row.get(f"{chamber}{year}"), errors="coerce") == 1


def compatible_name(candidate_name: str, source_name: str) -> bool:
    left = set(normalize(candidate_name).split())
    right = set(normalize(source_name).split())
    return bool(left & right)


def surname(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    if "," in text:
        text = text.split(",", 1)[0]
    tokens = re.findall(r"[a-z]+", text)
    tokens = [token for token in tokens if token not in {"jr", "sr", "ii", "iii", "iv"}]
    return tokens[-1] if tokens else ""


def choose_match(candidate: pd.Series, source: pd.DataFrame) -> tuple[pd.Series | None, str, float, str]:
    query = normalize(candidate.candidate)
    query = ALIASES.get(query, query)
    exact = source[source.normalized_name.eq(query)]
    if len(exact) == 1:
        return exact.iloc[0], "normalized_exact", 100.0, ""
    if len(exact) > 1:
        cycle = int(candidate.cycle)
        reference_year = 1996 if cycle == 1994 else min(cycle, 2018)
        roster_exact = exact[exact.apply(
            lambda row: active(row, candidate.chamber, reference_year)
            and district_at(row, candidate.chamber, reference_year) == float(candidate.district), axis=1)]
        if len(roster_exact) == 1:
            method = "later_1996_exact_roster" if cycle == 1994 else "election_year_exact_roster"
            return roster_exact.iloc[0], method, 100.0, ""
        unique_scores = pd.to_numeric(exact.np_score, errors="coerce").dropna().unique()
        if len(unique_scores) == 1:
            return exact.iloc[0], "normalized_exact_duplicate_score", 100.0, ""
        return None, "ambiguous_exact", 100.0, "multiple exact-name source scores"

    surname_matches = source[source.name.map(surname).eq(surname(candidate.candidate))]
    if len(surname_matches) == 1 and (bool(candidate.winner) or bool(candidate.incumbent)):
        selected = surname_matches.iloc[0]
        similarity = float(fuzz.WRatio(query, selected.normalized_name))
        if similarity >= 80:
            return selected, "winner_or_incumbent_unique_surname", similarity, ""

    cycle = int(candidate.cycle)
    reference_year = 1996 if cycle == 1994 else cycle
    roster = source[source.apply(
        lambda row: active(row, candidate.chamber, reference_year)
        and district_at(row, candidate.chamber, reference_year) == float(candidate.district), axis=1)]
    roster = roster[roster.name.map(lambda name: compatible_name(candidate.candidate, name))]
    if len(roster) == 1 and bool(candidate.winner):
        method = "later_1996_roster_name" if cycle == 1994 else "election_year_roster_name"
        return roster.iloc[0], method, float(fuzz.WRatio(query, roster.iloc[0].normalized_name)), ""

    scored = source.assign(similarity=source.normalized_name.map(lambda name: fuzz.WRatio(query, name)))
    scored = scored.sort_values("similarity", ascending=False)
    if len(scored):
        best = scored.iloc[0]
        second = float(scored.iloc[1].similarity) if len(scored) > 1 else 0.0
        if float(best.similarity) >= 95 and float(best.similarity) - second >= 3 and compatible_name(candidate.candidate, best["name"]):
            return best, "high_confidence_name", float(best.similarity), ""
        return None, "fuzzy_review", float(best.similarity), str(best["name"])
    return None, "unmatched", np.nan, ""


def build_crosswalk() -> pd.DataFrame:
    candidates = pd.read_csv(WAR / "preliminary_cmo_candidates.csv", low_memory=False)
    candidates = candidates[candidates.party.eq("D") & candidates.cycle.le(2018)].copy()
    source = pd.read_csv(RAW, sep="\t", low_memory=False)
    source = source[source.st.eq("AL") & source.party.eq("D")].copy()
    source["normalized_name"] = source.name.map(normalize)
    rows = []
    for candidate in candidates.itertuples(index=False):
        c = pd.Series(candidate._asdict())
        match, method, similarity, note = choose_match(c, source)
        base = {key: c[key] for key in ["cycle", "chamber", "district", "candidate", "canonical_candidate_id", "person_id", "incumbent", "winner"]}
        if match is None:
            rows.append({**base, "match_status": method, "match_method": "none", "similarity": similarity, "suggested_source_name": note})
            continue
        scores = pd.to_numeric(source[source.u_id.eq(match.u_id)].np_score, errors="coerce").dropna().unique()
        if len(scores) != 1:
            rows.append({**base, "match_status": "ambiguous_multiple_scores", "match_method": method, "similarity": similarity, "suggested_source_name": match["name"]})
            continue
        years = service_years(match)
        same_chamber_years = service_years(match, c.chamber)
        served_by = any(year <= int(c.cycle) for year in years)
        first_year = min(years) if years else np.nan
        temporal = "pre_election_service_available" if served_by else "later_observed_service_only"
        if int(c.cycle) == 1994:
            temporal = "1994_later_observed_sensitivity"
        reference_year = 1996 if int(c.cycle) == 1994 else min(int(c.cycle), 2018)
        reference = source[source.apply(lambda row: active(row, c.chamber, reference_year), axis=1)]
        reference_scores = pd.to_numeric(reference.np_score, errors="coerce").dropna()
        score = float(scores[0])
        rows.append({
            **base, "match_status": "matched", "match_method": method, "similarity": similarity,
            "suggested_source_name": match["name"], "shor_u_id": match.u_id, "shor_np_score": score,
            "shor_democratic_caucus_percentile": float((reference_scores <= score).mean() * 100) if len(reference_scores) else np.nan,
            "reference_year": reference_year, "reference_caucus_n": len(reference_scores),
            "first_observed_service_year": first_year, "pre_election_service_years": sum(year <= int(c.cycle) for year in years),
            "pre_election_same_chamber_years": sum(year <= int(c.cycle) for year in same_chamber_years),
            "served_by_election": served_by, "temporal_status": temporal,
        })
    return pd.DataFrame(rows)


def cluster_ols(frame: pd.DataFrame, outcome: str, controls: list[str]) -> dict:
    needed = [outcome, "shor_np_z", "person_id", *controls]
    data = frame.copy()
    for column in needed:
        if column != "person_id":
            data[column] = pd.to_numeric(data[column], errors="coerce") if column not in {"cycle", "chamber"} else data[column]
    data = data.dropna(subset=needed).copy()
    result = {"outcome": outcome, "n": len(data), "people": data.person_id.nunique()}
    if len(data) < 15 or data.person_id.nunique() < 10:
        return {**result, "status": "underpowered"}
    X = pd.DataFrame({"intercept": 1.0, "shor_np_z": data.shor_np_z}, index=data.index)
    for column in controls:
        if column in {"cycle", "chamber"}:
            X = pd.concat([X, pd.get_dummies(data[column].astype(str), prefix=column, drop_first=True, dtype=float)], axis=1)
        else:
            X[column] = pd.to_numeric(data[column], errors="coerce")
    A = X.to_numpy(float); y = data[outcome].to_numpy(float)
    inv = np.linalg.pinv(A.T @ A); beta = inv @ A.T @ y; resid = y - A @ beta
    groups = pd.Categorical(data.person_id).codes; unique = np.unique(groups); meat = np.zeros((A.shape[1], A.shape[1]))
    for group in unique:
        score = A[groups == group].T @ resid[groups == group]
        meat += np.outer(score, score)
    covariance = inv @ meat @ inv
    if len(unique) > 1 and len(data) > A.shape[1]:
        covariance *= len(unique) / (len(unique) - 1) * (len(data) - 1) / (len(data) - A.shape[1])
    position = list(X.columns).index("shor_np_z")
    standard_error = float(np.sqrt(max(covariance[position, position], 0)))
    coefficient = float(beta[position]); statistic = coefficient / standard_error if standard_error else np.nan
    p_value = float(2 * stats.t.sf(abs(statistic), df=max(len(unique) - 1, 1)))
    return {**result, "status": "estimated", "coefficient_per_sd": coefficient, "cluster_se": standard_error,
            "ci_low": coefficient - 1.96 * standard_error, "ci_high": coefficient + 1.96 * standard_error, "p_value": p_value}


def analyze(crosswalk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = pd.read_csv(WAR / "preliminary_cmo_candidates.csv", low_memory=False)
    candidates = candidates[candidates.party.eq("D")]
    races = pd.read_csv(WAR / "preliminary_cmo_races.csv", low_memory=False)
    race_columns = ["cycle", "chamber", "district", "prior_pres_dem_margin", "legislative_dem_margin", "nonwhite_share", "white_college_share", "canonical_finance_complete", "canonical_log_fundraising_ratio_d_to_r"]
    federal = pd.read_csv(FEDERAL)
    panel = (crosswalk[crosswalk.match_status.eq("matched")]
             .merge(candidates[["canonical_candidate_id", "candidate_cmo_total_oof"]], on="canonical_candidate_id", validate="one_to_one")
             .merge(races[race_columns], on=["cycle", "chamber", "district"], validate="many_to_one")
             .merge(federal, on=["cycle", "chamber", "district"], how="left", validate="many_to_one"))
    panel["presidential_overperformance"] = panel.legislative_dem_margin - panel.prior_pres_dem_margin
    panel["federal_index_overperformance"] = panel.legislative_dem_margin - panel.federal_index_margin
    panel["incumbent_i"] = panel.incumbent.fillna(False).astype(int)
    panel["finance_complete_i"] = panel.canonical_finance_complete.fillna(0).astype(int)
    panel["federal_source_tier"] = np.where(panel.federal_allocation_method.eq("canonical_geographic_weight"), "canonical", "provisional_fallback")
    panel["era"] = np.select([panel.cycle.le(2006), panel.cycle.le(2014)], ["pre_2008", "2008_2014"], default="post_2016")
    headline = panel[panel.cycle.between(1998, 2018)].copy()
    mean = headline.shor_np_score.mean(); sd = headline.shor_np_score.std(ddof=0)
    panel["shor_np_z"] = (panel.shor_np_score - mean) / sd
    specifications = {
        "cycle_chamber_total": ["cycle", "chamber"],
        "plus_district_context": ["cycle", "chamber", "nonwhite_share", "white_college_share"],
        "plus_incumbency": ["cycle", "chamber", "nonwhite_share", "white_college_share", "incumbent_i"],
        "plus_incumbency_finance": ["cycle", "chamber", "nonwhite_share", "white_college_share", "incumbent_i", "canonical_log_fundraising_ratio_d_to_r"],
    }
    samples = {
        "headline_1998_2018": panel[panel.cycle.between(1998, 2018)],
        "pre_election_service": panel[panel.cycle.between(1998, 2018) & panel.served_by_election.eq(True)],
        "canonical_federal_geography": panel[panel.cycle.between(1998, 2018) & panel.federal_source_tier.eq("canonical")],
        "1994_later_observed_sensitivity": panel[panel.cycle.eq(1994)],
    }
    rows = []
    for sample_name, sample in samples.items():
        for outcome in ["candidate_cmo_total_oof", "federal_index_overperformance", "presidential_overperformance"]:
            for specification, controls in specifications.items():
                rows.append({"sample": sample_name, "specification": specification, **cluster_ols(sample, outcome, controls)})
    for era, sample in panel[panel.cycle.between(1998, 2018)].groupby("era"):
        for outcome in ["candidate_cmo_total_oof", "federal_index_overperformance", "presidential_overperformance"]:
            rows.append({"sample": f"era:{era}", "specification": "chamber_total", **cluster_ols(sample, outcome, ["chamber"])})
    estimates = pd.DataFrame(rows)
    headline = panel[panel.cycle.between(1998, 2018)].copy()
    headline["ideology_tercile"] = pd.qcut(headline.shor_np_score, 3, labels=["liberal", "middle", "conservative"], duplicates="drop")
    grouped = (headline.groupby("ideology_tercile", observed=True)
               .agg(candidate_cycles=("canonical_candidate_id", "size"), people=("person_id", "nunique"),
                    mean_cmo=("candidate_cmo_total_oof", "mean"), median_cmo=("candidate_cmo_total_oof", "median"),
                    mean_federal=("federal_index_overperformance", "mean"), median_federal=("federal_index_overperformance", "median"),
                    mean_presidential=("presidential_overperformance", "mean"), median_presidential=("presidential_overperformance", "median"))
               .reset_index())
    return panel, estimates, grouped


def write_report(crosswalk: pd.DataFrame, panel: pd.DataFrame, estimates: pd.DataFrame, grouped: pd.DataFrame) -> None:
    def table(frame: pd.DataFrame) -> str:
        shown = frame.copy()
        for column in shown.select_dtypes(include=["number"]).columns:
            shown[column] = shown[column].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
        header = "| " + " | ".join(shown.columns) + " |"
        rule = "|" + "|".join(["---"] * len(shown.columns)) + "|"
        rows = ["| " + " | ".join(str(value).replace("|", "/") for value in row) + " |" for row in shown.itertuples(index=False, name=None)]
        return "\n".join([header, rule, *rows])
    head = estimates[(estimates["sample"] == "headline_1998_2018") & (estimates.specification.isin(["cycle_chamber_total", "plus_district_context", "plus_incumbency", "plus_incumbency_finance"]))]
    sensitivity = estimates[
        estimates["sample"].isin(["pre_election_service", "canonical_federal_geography", "1994_later_observed_sensitivity"])
        & estimates.specification.eq("cycle_chamber_total")
    ]
    coverage = (crosswalk.groupby(["cycle", "match_status"]).size().unstack(fill_value=0).reset_index())
    era = estimates[(estimates["sample"].str.startswith("era:")) & estimates.specification.eq("chamber_total")]
    lines = [
        "# Historical Shor–McCarty ideology and Democratic overperformance", "",
        "## Scope", "",
        "The headline analysis covers matched Democratic candidate-cycles from 1998 through 2018. Alabama service flags in the individual Shor–McCarty file begin in 1996, so 1994 is retained only as a later-observed sensitivity tier. Career ideal points may incorporate post-election votes even when pre-election service is observed.", "",
        f"The full candidate crosswalk contains **{len(crosswalk)}** Democratic candidate-cycles through 2018, with **{int(crosswalk.match_status.eq('matched').sum())}** accepted matches. The headline analytical panel contains **{len(panel[panel.cycle.between(1998, 2018)])}** rows and **{panel.loc[panel.cycle.between(1998, 2018), 'person_id'].nunique()}** people.", "",
        "## Coverage", "", table(coverage), "", "## Ideology terciles", "", table(grouped), "",
        "## Headline sequential decomposition", "", table(head[["outcome", "specification", "n", "people", "coefficient_per_sd", "cluster_se", "ci_low", "ci_high", "p_value", "status"]]), "",
        "`cycle_chamber_total` preserves the total relationship. District context, incumbency, and finance are then introduced sequentially; attenuation may represent confounding or removal of pathways through which ideological fit helped candidates survive, become incumbents, and raise money.", "",
        "## Temporal and source-quality sensitivities", "", table(sensitivity[["sample", "outcome", "n", "people", "coefficient_per_sd", "cluster_se", "p_value", "status"]]), "",
        "## Era results", "", table(era[["sample", "outcome", "n", "people", "coefficient_per_sd", "cluster_se", "p_value", "status"]]), "",
        "## Interpretation limits", "",
        "- Shor–McCarty is a one-dimensional career roll-call score, not a cycle-specific social-conservatism measure.",
        "- Challengers who never served cannot receive a Shor score, creating survivor selection.",
        "- The 1994 sensitivity tier uses people observed from 1996 onward and is not contemporaneous evidence.",
        "- Pre-2010 federal district baselines include provisional geographic allocations; the canonical-geography sample is reported separately.",
        "- These estimates are descriptive associations, not causal effects.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    crosswalk = build_crosswalk()
    panel, estimates, grouped = analyze(crosswalk)
    crosswalk.to_csv(OUT / "historical_shor_mccarty_crosswalk.csv", index=False)
    crosswalk[crosswalk.match_status.ne("matched")].to_csv(OUT / "historical_shor_mccarty_review_queue.csv", index=False)
    panel.to_csv(OUT / "historical_shor_mccarty_analysis_panel.csv", index=False)
    estimates.to_csv(OUT / "historical_shor_mccarty_estimates.csv", index=False)
    grouped.to_csv(OUT / "historical_shor_mccarty_terciles.csv", index=False)
    write_report(crosswalk, panel, estimates, grouped)
    print(crosswalk.groupby(["cycle", "match_status"]).size().unstack(fill_value=0).to_string())
    print(estimates[(estimates["sample"] == "headline_1998_2018") & estimates.specification.eq("cycle_chamber_total")].to_string(index=False))


if __name__ == "__main__":
    main()
