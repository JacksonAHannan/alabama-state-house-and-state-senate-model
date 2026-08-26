"""Discover party-specific ideological groupings using the current ideology panel."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import KNNImputer, SimpleImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
OUT = RESEARCH / "democratic_clusters"
PANEL = RESEARCH / "absolute_rebuild_panel.csv"
CMO = ROOT / "data" / "processed" / "war" / "cmo_v4_candidates.csv"
SEED, POLE = 20260821, 0.15
MIN_FEATURE_N, MIN_POLE_N, MIN_CLUSTER_N, MIN_CLUSTER_SHARE = 30, 5, 12, 0.08


def issue_columns(frame: pd.DataFrame, party: str) -> list[str]:
    sample, columns = frame[frame.party.eq(party)], []
    for column in frame.columns:
        if not column.startswith("primitive_conservative_"):
            continue
        values = pd.to_numeric(sample[column], errors="coerce").dropna()
        if len(values) < MIN_FEATURE_N or values.std(ddof=0) == 0:
            continue
        if min(int((values < -POLE).sum()), int((values > POLE).sum())) >= MIN_POLE_N:
            columns.append(column)
    return sorted(columns)


def eligible_sample(frame: pd.DataFrame, party: str, features: list[str]) -> pd.DataFrame:
    sample = frame[frame.party.eq(party)].copy()
    minimum = max(3, int(np.ceil(len(features) * 0.30)))
    sample["cluster_dimensions_observed"] = sample[features].notna().sum(axis=1)
    return sample[sample.cluster_dimensions_observed.ge(minimum)].copy()


def prepare_matrix(sample: pd.DataFrame, features: list[str], method: str = "knn", within_era: bool = False) -> np.ndarray:
    raw = sample[features].astype(float)
    normalized = (raw - raw.mean()) / raw.std(ddof=0).replace(0, 1)
    if within_era:
        for _, index in sample.groupby("era").groups.items():
            part = raw.loc[index]
            usable = part.notna().sum().ge(3) & part.std(ddof=0).gt(0)
            normalized.loc[index, usable] = (part.loc[:, usable] - part.loc[:, usable].mean()) / part.loc[:, usable].std(ddof=0)
    if method == "median":
        values = SimpleImputer(strategy="median").fit_transform(normalized)
    else:
        values = KNNImputer(n_neighbors=min(7, max(2, len(sample) - 1)), weights="distance").fit_transform(normalized)
    return StandardScaler().fit_transform(values)


def diagnostics_for_matrix(x: np.ndarray, max_k: int = 6) -> tuple[pd.DataFrame, dict[int, KMeans]]:
    rng, rows, models = np.random.default_rng(SEED), [], {}
    for k in range(2, min(max_k, len(x) - 1) + 1):
        model = KMeans(n_clusters=k, n_init=100, random_state=SEED + k).fit(x)
        sizes, stability = np.bincount(model.labels_, minlength=k), []
        for iteration in range(60):
            index = rng.integers(0, len(x), len(x))
            boot = KMeans(n_clusters=k, n_init=30, random_state=SEED + k * 100 + iteration).fit(x[index])
            stability.append(adjusted_rand_score(model.labels_, boot.predict(x)))
        rows.append({"clusters": k, "silhouette": silhouette_score(x, model.labels_),
                     "bootstrap_ari_mean": np.mean(stability), "bootstrap_ari_p10": np.quantile(stability, .10),
                     "smallest_cluster": int(sizes.min()), "smallest_cluster_share": sizes.min() / len(x)})
        models[k] = model
    return pd.DataFrame(rows), models


def choose_k(diagnostics: pd.DataFrame) -> int:
    viable = diagnostics[diagnostics.smallest_cluster.ge(MIN_CLUSTER_N)
                         & diagnostics.smallest_cluster_share.ge(MIN_CLUSTER_SHARE)].copy()
    if viable.empty:
        viable = diagnostics[diagnostics.clusters.eq(2)].copy()
    viable["selection_score"] = viable.silhouette + .30 * viable.bootstrap_ari_mean - .015 * (viable.clusters - 2)
    return int(viable.sort_values(["selection_score", "clusters"], ascending=[False, True]).iloc[0].clusters)


def clean_axis(column: str) -> str:
    return column.removeprefix("primitive_conservative_").replace("_", " ")


def cluster_labels(profiles: pd.DataFrame, party: str) -> dict[int, str]:
    if party == "D":
        cultural = profiles[[c for c in profiles if any(x in c for x in
            ("abortion_access", "civil_social_liberty", "gun_access", "criminal_punishment"))]].mean(axis=1)
        traditional = int(cultural.idxmax())
        progressive = int(cultural.idxmin())
        labels = {
            traditional: "Traditionalist-populist Democrats",
            progressive: "Progressive-modern Democrats",
        }
        middle = [int(i) for i in cultural.sort_values().index if int(i) not in labels]
        for position, cluster_id in enumerate(middle, start=1):
            labels[cluster_id] = ("Bridge-coalition Democrats" if len(middle) == 1
                                  else f"Bridge-coalition Democrats {position}")
        return labels
    overall = profiles.mean(axis=1)
    moderate = int(overall.idxmin())
    remaining = profiles.drop(index=moderate)
    business_axes = [c for c in profiles if c.endswith("market_governance") or c.endswith("labor_capital_alignment")]
    business = int(remaining[business_axes].mean(axis=1).idxmax())
    return {int(i): ("Moderate pre-realignment Republicans" if int(i) == moderate else
                     "Business conservatives" if int(i) == business else
                     "Social and institutional conservatives") for i in profiles.index}


def fit_party(panel: pd.DataFrame, party: str):
    features = issue_columns(panel, party)
    if len(features) < 3:
        raise RuntimeError(f"{party}: fewer than three adequately covered two-sided issues")
    sample = eligible_sample(panel, party, features)
    x = prepare_matrix(sample, features)
    diagnostics, models = diagnostics_for_matrix(x)
    chosen = choose_k(diagnostics)
    sample["cluster_id"] = models[chosen].labels_ + 1
    sample["cluster_party"], sample["cluster_dimensions_used"], sample["cluster_solution_k"] = party, len(features), chosen
    observed = sample.groupby("cluster_id")[features].mean()
    labels = cluster_labels(observed, party)
    sample["cluster_label"] = sample.cluster_id.map(labels)
    profiles = observed.copy()
    profiles.insert(0, "cluster_label", [labels[int(i)] for i in profiles.index])
    profiles.insert(1, "candidate_cycles", sample.cluster_id.value_counts().sort_index())
    profiles.insert(2, "people", sample.groupby("cluster_id").person_id.nunique())
    profiles = profiles.reset_index().assign(party=party, dimensions_used=len(features))
    alternate = KMeans(n_clusters=chosen, n_init=100, random_state=SEED + chosen).fit_predict(
        prepare_matrix(sample, features, "median"))
    within_era = KMeans(n_clusters=chosen, n_init=100, random_state=SEED + chosen).fit_predict(
        prepare_matrix(sample, features, "knn", within_era=True))
    missingness = StandardScaler().fit_transform(sample[features].notna().astype(float))
    missingness_labels = KMeans(n_clusters=chosen, n_init=100, random_state=SEED + chosen).fit_predict(missingness)
    sensitivity = pd.DataFrame([{"party": party, "clusters": chosen,
        "knn_vs_median_ari": adjusted_rand_score(sample.cluster_id - 1, alternate),
        "absolute_vs_within_era_ari": adjusted_rand_score(sample.cluster_id - 1, within_era),
        "position_vs_missingness_ari": adjusted_rand_score(sample.cluster_id - 1, missingness_labels),
        "candidate_cycles": len(sample), "features": len(features),
        "minimum_dimensions_observed": int(sample.cluster_dimensions_observed.min()),
        "median_dimensions_observed": sample.cluster_dimensions_observed.median()}])
    diagnostics.insert(0, "party", party)
    diagnostics["selected"], diagnostics["features"] = diagnostics.clusters.eq(chosen), len(features)
    return sample, diagnostics, profiles, sensitivity


def performance_summary(assignments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    outcomes = ["candidate_cmo", "candidate_federal_overperformance", "candidate_presidential_overperformance"]
    for (party, cluster_id, label), group in assignments.groupby(["party", "cluster_id", "cluster_label"]):
        for outcome in outcomes:
            values = pd.to_numeric(group[outcome], errors="coerce").dropna()
            rows.append({"party": party, "cluster_id": cluster_id, "cluster_label": label, "outcome": outcome,
                         "n": len(values), "mean": values.mean(), "median": values.median(), "sd": values.std(),
                         "standard_error": values.std()/np.sqrt(len(values)) if len(values) > 1 else np.nan})
    return pd.DataFrame(rows)


def write_report(assignments, diagnostics, profiles, sensitivity, performance) -> None:
    lines = ["# Empirical ideological groupings in Alabama legislative caucuses", "",
             "Clusters are fit separately by party from absolute, temporally eligible issue positions. CMO, election results, incumbency, fundraising, demographics, district partisanship, and era are excluded from clustering and attached only afterward.", ""]
    for party, name in [("D", "Democratic"), ("R", "Republican")]:
        selected = diagnostics[diagnostics.party.eq(party) & diagnostics.selected].iloc[0]
        sens = sensitivity[sensitivity.party.eq(party)].iloc[0]
        lines += [f"## {name} solution", "",
                  f"Selected **{int(selected.clusters)} clusters** among **{int(sens.candidate_cycles)} candidate-cycles**, using **{int(sens.features)} two-sided issue dimensions**. Silhouette is **{selected.silhouette:.3f}**; mean bootstrap ARI is **{selected.bootstrap_ari_mean:.3f}**; KNN-versus-median-imputation ARI is **{sens.knn_vs_median_ari:.3f}**; absolute-versus-within-era ARI is **{sens.absolute_vs_within_era_ari:.3f}**; position-versus-missingness ARI is **{sens.position_vs_missingness_ari:.3f}**.", ""]
        for row in profiles[profiles.party.eq(party)].itertuples(index=False):
            lines.append(f"- **{row.cluster_label}:** {int(row.candidate_cycles)} candidate-cycles and {int(row.people)} people.")
        lines += ["", "### CMO attached after clustering", ""]
        for row in performance[performance.party.eq(party) & performance.outcome.eq("candidate_cmo")].itertuples(index=False):
            lines.append(f"- **{row.cluster_label}:** mean {row.mean:+.2f}, median {row.median:+.2f}, n={int(row.n)}.")
        if sens.knn_vs_median_ari < .50 or sens.absolute_vs_within_era_ari < .35:
            lines += ["", "**Robustness warning:** this discrete solution changes substantially under alternate imputation or within-era normalization. Treat the labels as a description of historical tendencies, not stable caucus membership."]
        lines.append("")
    lines += ["## Interpretation limits", "", "- Low silhouettes indicate a continuum rather than formal caucuses.",
              "- Issue evidence is more common for officeholders and is not missing at random.",
              "- Candidate-cycles repeat people; person persistence and era composition are separate outputs.",
              "- Performance differences are descriptive; electoral outcomes never determine assignment."]
    (OUT / "DEMOCRATIC_IDEOLOGICAL_CLUSTERS.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(PANEL, low_memory=False)
    results = [fit_party(panel, party) for party in ("D", "R")]
    assignments = pd.concat([r[0] for r in results], ignore_index=True)
    diagnostics = pd.concat([r[1] for r in results], ignore_index=True)
    profiles = pd.concat([r[2] for r in results], ignore_index=True)
    sensitivity = pd.concat([r[3] for r in results], ignore_index=True)
    performance = performance_summary(assignments)
    era = assignments.groupby(["party", "cluster_id", "cluster_label", "era"], dropna=False).size().rename("n").reset_index()
    era["within_cluster_share"] = era.n / era.groupby(["party", "cluster_id"]).n.transform("sum")
    repeated = assignments.groupby(["party", "person_id"], dropna=False).agg(
        observations=("cluster_id", "size"), distinct_clusters=("cluster_id", "nunique")).reset_index()
    repeated = repeated[repeated.observations.gt(1)]
    persistence = repeated.groupby("party").agg(repeated_people=("person_id", "size"),
        stable_people=("distinct_clusters", lambda x: int(x.eq(1).sum()))).reset_index()
    persistence["stable_share"] = persistence.stable_people / persistence.repeated_people
    cmo = pd.read_csv(CMO, usecols=["canonical_candidate_id", "candidate_war_cmo"]).rename(columns={"candidate_war_cmo":"published_cmo_v4"})
    check = assignments[["canonical_candidate_id", "candidate_cmo"]].merge(cmo, on="canonical_candidate_id", how="left", validate="one_to_one")
    check["difference"] = check.candidate_cmo - check.published_cmo_v4
    if check.published_cmo_v4.isna().any() or check.difference.abs().max() > 1e-9:
        raise ValueError("Clustering panel CMO does not match current CMO v4")
    assignments.to_csv(OUT / "democratic_candidate_cluster_membership.csv", index=False)
    diagnostics.to_csv(OUT / "cluster_model_diagnostics.csv", index=False)
    profiles.to_csv(OUT / "democratic_cluster_profiles.csv", index=False)
    sensitivity.to_csv(OUT / "cluster_sensitivity.csv", index=False)
    performance.to_csv(OUT / "democratic_cluster_summary.csv", index=False)
    era.to_csv(OUT / "cluster_era_composition.csv", index=False)
    persistence.to_csv(OUT / "cluster_person_persistence.csv", index=False)
    check.to_csv(OUT / "cluster_cmo_v4_check.csv", index=False)
    write_report(assignments, diagnostics, profiles, sensitivity, performance)
    print(diagnostics[diagnostics.selected].to_string(index=False))
    print("\n", performance[performance.outcome.eq("candidate_cmo")].to_string(index=False))


if __name__ == "__main__":
    main()
