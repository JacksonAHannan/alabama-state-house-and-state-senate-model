"""Audit ideological support and identify candidate bundles without sparse-axis artifacts."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "data" / "processed" / "elections" / "validation"
OUT = ROOT / "data" / "processed" / "ideology"
DOC = ROOT / "project_docs" / "model" / "IDEOLOGICAL_BUNDLE_PERFORMANCE.md"
POLE = 0.15


def markdown(frame: pd.DataFrame) -> str:
    shown = frame.copy()
    for col in shown.select_dtypes(include=["number"]):
        shown[col] = shown[col].map(lambda x: "" if pd.isna(x) else f"{x:.2f}")
    shown = shown.fillna("").astype(str)
    return "\n".join(["| " + " | ".join(shown.columns) + " |",
                      "|" + "|".join(["---"] * len(shown.columns)) + "|",
                      *["| " + " | ".join(row) + " |" for row in shown.to_numpy()]])


def variation_table(df: pd.DataFrame, dimension: str, by_era: bool = False) -> pd.DataFrame:
    keys = [dimension] + (["era"] if by_era else [])
    rows = []
    for key, g in df.groupby(keys, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        x = pd.to_numeric(g["stance"], errors="coerce").dropna()
        neg, pos = int((x < -POLE).sum()), int((x > POLE).sum())
        mid = int((x.abs() <= POLE).sum())
        n = len(x); minor = min(neg, pos)
        minor_share = minor / n if n else np.nan
        if n < 20 or minor < 3:
            cls = "sparse"
        elif minor >= 10 and minor_share >= .10:
            cls = "two_sided_usable"
        elif minor >= 5:
            cls = "weakly_two_sided"
        else:
            cls = "one_sided"
        row = dict(zip(keys, key))
        row.update(n=n, negative_pole=neg, middle=mid, positive_pole=pos,
                   minority_pole_count=minor, minority_pole_share=minor_share,
                   stance_mean=x.mean(), stance_sd=x.std(), stance_min=x.min(),
                   stance_q25=x.quantile(.25), stance_median=x.median(),
                   stance_q75=x.quantile(.75), stance_max=x.max(), variation_class=cls)
        rows.append(row)
    return pd.DataFrame(rows)


def name_bundle(profile: pd.Series) -> str:
    ranked = profile.abs().sort_values(ascending=False).head(2).index
    parts = []
    for col in ranked:
        direction = "high" if profile[col] >= 0 else "low"
        parts.append(f"{direction} {col.replace('_', ' ')}")
    return " + ".join(parts)


def choose_clusters(z: np.ndarray) -> tuple[int, list[dict]]:
    trials = []
    for k in range(2, min(6, len(z) - 1) + 1):
        model = KMeans(n_clusters=k, random_state=42, n_init=50).fit(z)
        sizes = np.bincount(model.labels_)
        score = silhouette_score(z, model.labels_) if sizes.min() >= 10 else np.nan
        trials.append({"k": k, "silhouette": score, "minimum_cluster_size": int(sizes.min())})
    valid = [r for r in trials if np.isfinite(r["silhouette"])]
    if not valid:
        raise RuntimeError("No defensible bundle solution has at least 10 candidates per cluster")
    return max(valid, key=lambda r: r["silhouette"])["k"], trials


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True); VALID.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(VALID / "headline_ideology_panel.csv", low_memory=False)
    headline = variation_table(panel, "headline_dimension")
    headline_era = variation_table(panel, "headline_dimension", by_era=True)
    headline.to_csv(OUT / "ideology_headline_pole_balance.csv", index=False)
    headline_era.to_csv(OUT / "ideology_headline_pole_balance_by_era.csv", index=False)

    # Primitive-axis audit uses the adjudicated score and the same candidate universe.
    issue = pd.read_csv(OUT / "candidate_issue_valence_v3_adjudicated.csv", low_memory=False)
    universe = panel[["canonical_candidate_id", "era"]].drop_duplicates()
    issue = universe.merge(issue, on="canonical_candidate_id", how="inner")
    issue = issue.rename(columns={"adjudicated_issue_valence": "stance"})
    primitive = variation_table(issue, "primitive_axis")
    primitive_era = variation_table(issue, "primitive_axis", by_era=True)
    primitive.to_csv(OUT / "ideology_issue_pole_balance.csv", index=False)
    primitive_era.to_csv(OUT / "ideology_issue_pole_balance_by_era.csv", index=False)

    # Bundle construction is deliberately stricter than exploratory regressions:
    # both poles need >=10 observations and >=10% of the measured sample.
    usable = headline.loc[headline.variation_class.eq("two_sided_usable"), "headline_dimension"].tolist()
    wide = panel[panel.headline_dimension.isin(usable)].pivot_table(
        index="canonical_candidate_id", columns="headline_dimension", values="stance", aggfunc="first")
    minimum = max(3, int(np.ceil(len(usable) / 2)))
    wide = wide[wide.notna().sum(axis=1) >= minimum]
    medians = wide.median(); filled = wide.fillna(medians)
    scaler = StandardScaler(); z = scaler.fit_transform(filled)
    k, trials = choose_clusters(z)
    model = KMeans(n_clusters=k, random_state=42, n_init=100).fit(z)
    assignments = pd.DataFrame({"canonical_candidate_id": wide.index, "bundle_id": model.labels_ + 1,
                                "dimensions_observed": wide.notna().sum(axis=1).values,
                                "dimensions_used": len(usable)})
    standardized = pd.DataFrame(z, index=wide.index, columns=usable).assign(bundle_id=model.labels_ + 1)
    profiles = standardized.groupby("bundle_id")[usable].mean()
    labels = {idx: name_bundle(row) for idx, row in profiles.iterrows()}
    assignments["bundle_label"] = assignments.bundle_id.map(labels)
    profiles.insert(0, "bundle_label", [labels[i] for i in profiles.index])
    profiles.insert(1, "n_candidates", assignments.bundle_id.value_counts().sort_index())
    assignments.to_csv(OUT / "ideological_bundle_assignments.csv", index=False)
    profiles.reset_index().to_csv(OUT / "ideological_bundle_profiles.csv", index=False)
    pd.DataFrame(trials).to_csv(OUT / "ideological_bundle_k_selection.csv", index=False)

    base_cols = ["canonical_candidate_id", "person_id", "cycle", "chamber", "era",
                 "presidential_overperformance", "federal_index_overperformance", "candidate_cmo_total_oof"]
    outcomes = panel[base_cols].drop_duplicates("canonical_candidate_id")
    joined = assignments.merge(outcomes, on="canonical_candidate_id", how="left")
    joined.to_csv(OUT / "ideological_bundle_candidate_performance.csv", index=False)
    composition = (joined.groupby(["bundle_id", "bundle_label", "era"], dropna=False).size()
                   .rename("n").reset_index())
    composition["within_bundle_share"] = composition["n"] / composition.groupby("bundle_id")["n"].transform("sum")
    composition.to_csv(OUT / "ideological_bundle_era_composition.csv", index=False)
    perf = []
    for scope, g0 in [("all", joined), *[(f"era:{e}", g) for e, g in joined.groupby("era")]]:
        for bid, g in g0.groupby("bundle_id"):
            for outcome in ["presidential_overperformance", "federal_index_overperformance", "candidate_cmo_total_oof"]:
                x = pd.to_numeric(g[outcome], errors="coerce").dropna()
                perf.append({"scope": scope, "bundle_id": bid, "bundle_label": labels[bid], "outcome": outcome,
                             "n": len(x), "mean": x.mean(), "median": x.median(), "sd": x.std(),
                             "standard_error": x.std()/np.sqrt(len(x)) if len(x)>1 else np.nan,
                             "ci_low": x.mean()-1.96*x.std()/np.sqrt(len(x)) if len(x)>1 else np.nan,
                             "ci_high": x.mean()+1.96*x.std()/np.sqrt(len(x)) if len(x)>1 else np.nan})
    performance = pd.DataFrame(perf)
    performance.to_csv(OUT / "ideological_bundle_performance.csv", index=False)

    top = performance[(performance.scope == "all") & (performance.outcome == "federal_index_overperformance")].sort_values("mean", ascending=False)
    lines = ["# Ideological bundle performance", "",
             "This analysis first audits whether an issue contains meaningful observations at both poles. Sparse and one-sided headline dimensions are excluded from clustering, so absence of one viewpoint cannot manufacture a candidate archetype.", "",
             f"The selected solution has **{k} bundles**, uses **{len(usable)} headline dimensions**, and requires at least **{minimum} observed dimensions** per candidate. Missing retained dimensions are median-imputed only for cluster assignment; reported profiles and election outcomes remain observed data.", "",
             "## Dimensions retained", "", ", ".join(usable) or "None", "",
             "## Dimensions excluded", "", ", ".join(headline.loc[~headline.headline_dimension.isin(usable), 'headline_dimension']) or "None", "",
             "## Overall performance versus federal baseline", "",
             markdown(top[["bundle_label","n","mean","median","ci_low","ci_high"]]), "",
             "## Interpretation limits", "",
             "Bundles are descriptive clusters, not causal effects. Their apparent performance may reflect geography, candidate selection, era, and uneven evidence coverage. Era-specific results with small n should be treated as exploratory."]
    DOC.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(headline[["headline_dimension","n","negative_pole","middle","positive_pole","variation_class"]].to_string(index=False))
    print("\nSelected k:", k, "usable:", usable)
    print("\n", top[["bundle_label","n","mean","median","ci_low","ci_high"]].to_string(index=False))


if __name__ == "__main__":
    main()
