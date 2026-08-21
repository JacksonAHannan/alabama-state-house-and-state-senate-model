"""Build thesis-led evidence marts for ideology and Democratic overperformance."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "data" / "processed" / "elections" / "validation"
OUT = ROOT / "data" / "processed" / "ideology"

ORIENTATION = {
    "social_traditionalism": 1,
    "punitive_law_and_order": 1,
    "market_and_development_autonomy": 1,
    "gun_rights": 1,
    "labor_power": -1,
}


def clustered_fit(frame: pd.DataFrame, outcome: str, terms: list[str]) -> dict:
    cols = [outcome, "person_id", *terms]
    d = frame[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if len(d) < len(terms) + 12:
        return {"n": len(d), "coefficient": np.nan, "se": np.nan, "ci_low": np.nan, "ci_high": np.nan, "p_value": np.nan}
    x = np.column_stack([np.ones(len(d)), d[terms].to_numpy(float)]); y = d[outcome].to_numpy(float)
    inv = np.linalg.pinv(x.T @ x); beta = inv @ x.T @ y; resid = y - x @ beta
    groups = d.person_id.fillna(pd.Series(d.index.astype(str), index=d.index)).astype(str).to_numpy()
    meat = np.zeros_like(inv)
    for group in np.unique(groups):
        idx = np.flatnonzero(groups == group); score = x[idx].T @ resid[idx]; meat += np.outer(score, score)
    g = len(np.unique(groups)); correction = (g/(g-1))*((len(d)-1)/max(len(d)-x.shape[1],1)) if g > 1 else 1
    cov = correction * inv @ meat @ inv; se = np.sqrt(np.maximum(np.diag(cov), 0)); dof = max(g-1, 1)
    tcrit = stats.t.ppf(.975, dof); p = 2*stats.t.sf(abs(beta[1]/se[1]), dof) if se[1] else np.nan
    return {"n": len(d), "coefficient": beta[1], "se": se[1], "ci_low": beta[1]-tcrit*se[1],
            "ci_high": beta[1]+tcrit*se[1], "p_value": p}


def clustered_terms(frame: pd.DataFrame, outcome: str, terms: list[str]) -> pd.DataFrame:
    d = frame[[outcome, "person_id", *terms]].replace([np.inf, -np.inf], np.nan).dropna().copy()
    x = np.column_stack([np.ones(len(d)), d[terms].to_numpy(float)]); y = d[outcome].to_numpy(float)
    inv = np.linalg.pinv(x.T @ x); beta = inv @ x.T @ y; resid = y-x@beta
    groups = d.person_id.fillna(pd.Series(d.index.astype(str), index=d.index)).astype(str).to_numpy(); meat=np.zeros_like(inv)
    for group in np.unique(groups):
        idx=np.flatnonzero(groups==group); score=x[idx].T@resid[idx]; meat+=np.outer(score,score)
    g=len(np.unique(groups)); correction=(g/(g-1))*((len(d)-1)/max(len(d)-x.shape[1],1)) if g>1 else 1
    se=np.sqrt(np.maximum(np.diag(correction*inv@meat@inv),0)); dof=max(g-1,1); tcrit=stats.t.ppf(.975,dof)
    return pd.DataFrame({"term": terms, "n": len(d), "coefficient": beta[1:], "se": se[1:],
                         "ci_low": beta[1:]-tcrit*se[1:], "ci_high": beta[1:]+tcrit*se[1:],
                         "p_value": 2*stats.t.sf(np.divide(abs(beta[1:]),se[1:],out=np.full(len(terms),np.nan),where=se[1:]>0),dof)})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    long = pd.read_csv(VALID / "headline_ideology_panel.csv", low_memory=False)
    long = long[long.canonical_party.eq("D")].copy()
    base = long.drop_duplicates("canonical_candidate_id").copy()
    wide = long.pivot_table(index="canonical_candidate_id", columns="headline_dimension", values="stance", aggfunc="first")
    oriented = pd.DataFrame({axis: wide[axis] * sign for axis, sign in ORIENTATION.items() if axis in wide})
    score = oriented.mean(axis=1, skipna=True)
    count = oriented.notna().sum(axis=1)
    conservative = pd.DataFrame({"canonical_candidate_id": score.index, "conservative_fit_score": score,
                                 "conservative_fit_dimensions": count}).reset_index(drop=True)
    conservative.loc[conservative.conservative_fit_dimensions.lt(3), "conservative_fit_score"] = np.nan
    panel = base.merge(conservative, on="canonical_candidate_id", how="left", validate="one_to_one")
    panel.to_csv(OUT / "ideology_thesis_candidate_panel.csv", index=False)

    controls = ["nonwhite_share", "white_college_share", "senate_i"] + [c for c in panel if c.startswith("cycle_")]
    rows = []
    for outcome in ["federal_index_overperformance", "presidential_overperformance"]:
        for label, subset in [
            ("all", panel), ("majority_white", panel[panel.majority_white.eq(1)]),
            ("nonincumbents", panel[panel.incumbent_i.eq(0)]), ("incumbents", panel[panel.incumbent_i.eq(1)]),
            ("pre_2008", panel[panel.era.eq("pre_2008")]), ("2008_2014", panel[panel.era.eq("2008_2014")]),
            ("post_2016", panel[panel.era.eq("post_2016")]),
        ]:
            result = clustered_fit(subset, outcome, ["conservative_fit_score", *[c for c in controls if c in subset]])
            rows.append({"outcome": outcome, "sensitivity": label, **result})
        for cycle in sorted(panel.cycle.dropna().unique()):
            subset = panel[panel.cycle.ne(cycle)]
            result = clustered_fit(subset, outcome, ["conservative_fit_score", *controls])
            rows.append({"outcome": outcome, "sensitivity": f"exclude_{int(cycle)}", **result})
    pd.DataFrame(rows).to_csv(OUT / "ideology_thesis_sensitivity.csv", index=False)

    # Direct structural-break test, rather than interpreting separate models by eye.
    interactions = []
    for outcome in ["federal_index_overperformance", "presidential_overperformance"]:
        d = panel[[outcome, "person_id", "conservative_fit_score", "post_2008", "post_2016",
                   "nonwhite_share", "white_college_share", "senate_i"]].dropna().copy()
        d["fit_x_post_2008"] = d.conservative_fit_score * d.post_2008
        d["fit_x_post_2016"] = d.conservative_fit_score * d.post_2016
        xcols = ["conservative_fit_score", "fit_x_post_2008", "fit_x_post_2016", "post_2008", "post_2016",
                 "nonwhite_share", "white_college_share", "senate_i"]
        fitted = clustered_terms(d, outcome, xcols)
        fitted = fitted[fitted.term.isin(["conservative_fit_score", "fit_x_post_2008", "fit_x_post_2016"])]
        interactions.extend([{"outcome": outcome, **row} for row in fitted.to_dict("records")])
    pd.DataFrame(interactions).to_csv(OUT / "ideology_thesis_era_interactions.csv", index=False)

    # Forest-plot effects use realistic 25th-to-75th percentile contrasts and
    # orient selected axes so the conservative/traditional pole is always right.
    estimates = pd.read_csv(VALID / "headline_ideology_estimates.csv")
    # The narrative chart describes the historical issue-performance
    # association. Adjusted estimates remain in the explorer as a sensitivity,
    # rather than silently replacing the descriptive estimand used throughout
    # the earlier issue tournament.
    estimates = estimates[(estimates.outcome.eq("federal_index_overperformance")) &
                          estimates.specification.eq("pooled")].copy()
    forest = []
    for row in estimates.itertuples(index=False):
        values = long.loc[long.headline_dimension.eq(row.headline_dimension), "stance"].dropna()
        iqr = values.quantile(.75) - values.quantile(.25)
        orient = ORIENTATION.get(row.headline_dimension, 1)
        forest.append({"dimension": row.headline_dimension, "specification": "pooled_historical_association",
                       "n": row.n, "orientation": orient, "iqr": iqr,
                       "iqr_effect": row.coefficient * iqr * orient, "ci_low": min(row.ci_low*iqr*orient, row.ci_high*iqr*orient),
                       "ci_high": max(row.ci_low*iqr*orient, row.ci_high*iqr*orient), "q_value": row.bh_q_value})
    pd.DataFrame(forest).to_csv(OUT / "ideology_thesis_issue_forest.csv", index=False)

    # Nearest-neighbor descriptive matches: high versus low conservative fit
    # within cycle and chamber, balanced on baseline and demographics.
    matched = panel.dropna(subset=["conservative_fit_score", "federal_index_margin", "nonwhite_share", "white_college_share",
                                   "federal_index_overperformance"]).copy()
    low_cut, high_cut = matched.conservative_fit_score.quantile([.33, .67])
    lows = matched[matched.conservative_fit_score.le(low_cut)].copy(); highs = matched[matched.conservative_fit_score.ge(high_cut)].copy()
    pairs = []
    used: set[str] = set()
    for h in highs.sort_values("conservative_fit_score", ascending=False).itertuples(index=False):
        candidates = lows[(lows.cycle.eq(h.cycle)) & (lows.chamber.eq(h.chamber)) & ~lows.canonical_candidate_id.isin(used)].copy()
        if candidates.empty: continue
        candidates["distance"] = (((candidates.federal_index_margin-h.federal_index_margin)/15)**2 +
                                  ((candidates.nonwhite_share-h.nonwhite_share)/.20)**2 +
                                  ((candidates.white_college_share-h.white_college_share)/.12)**2)
        lo = candidates.sort_values("distance").iloc[0]
        if lo.distance > 4: continue
        used.add(lo.canonical_candidate_id)
        pairs.append({"cycle": h.cycle, "chamber": h.chamber, "high_candidate": h.canonical_name,
                      "high_id": h.canonical_candidate_id, "high_score": h.conservative_fit_score,
                      "high_overperformance": h.federal_index_overperformance, "low_candidate": lo.canonical_name,
                      "low_id": lo.canonical_candidate_id, "low_score": lo.conservative_fit_score,
                      "low_overperformance": lo.federal_index_overperformance, "match_distance": lo.distance,
                      "paired_difference": h.federal_index_overperformance-lo.federal_index_overperformance})
    pd.DataFrame(pairs).to_csv(OUT / "ideology_thesis_matched_pairs.csv", index=False)

    # Operationalize durability in Republican federal territory.
    d = panel[panel.conservative_fit_score.notna()].copy()
    d["won_while_federal_republican"] = d.winner.eq(1) & d.federal_index_margin.lt(0)
    d["federal_deficit_at_win"] = np.where(d.won_while_federal_republican, -d.federal_index_margin, np.nan)
    d["observed_cycles"] = d.groupby("person_id").cycle.transform("nunique")
    first_gop = d[d.federal_index_margin.lt(0)].groupby("person_id").cycle.min()
    d["first_observed_federal_republican_cycle"] = d.person_id.map(first_gop)
    d["cycles_after_federal_republican"] = np.where(d.cycle.ge(d.first_observed_federal_republican_cycle),
                                                     (d.cycle-d.first_observed_federal_republican_cycle)/4, np.nan)
    d.to_csv(OUT / "ideology_thesis_durability.csv", index=False)

    cases = (d[d.won_while_federal_republican & d.federal_index_overperformance.notna()]
             .sort_values(["federal_index_overperformance", "cycle"], ascending=[False, False])
             .drop_duplicates("person_id").head(8))
    cases.to_csv(OUT / "ideology_thesis_case_studies.csv", index=False)
    print(f"candidate panel={len(panel)}, conservative-fit={panel.conservative_fit_score.notna().sum()}, pairs={len(pairs)}, cases={len(cases)}")


if __name__ == "__main__":
    main()
