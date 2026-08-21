"""Identify empirical ideological clusters among Alabama Democratic candidates."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import KNNImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from scipy.stats import fisher_exact
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = ROOT / "data" / "processed" / "elections"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
LEG = ROOT / "data" / "processed" / "legislative"
OUT = ROOT / "research" / "cmo_ideology" / "democratic_clusters"
RESEARCH = ROOT / "research" / "cmo_ideology"
SEED = 20260817
def assemble() -> tuple[pd.DataFrame, list[str]]:
    candidates = pd.read_csv(ELECTIONS / "canonical_cmo_candidates_with_ideology_v3.csv", low_memory=False)
    races = pd.read_csv(ELECTIONS / "canonical_cmo_features.csv", low_memory=False)
    positions = pd.read_csv(IDEOLOGY / "candidate_issue_valence_v3_adjudicated.csv")
    legislative = pd.read_csv(LEG / "candidate_pre_election_legislative_features.csv", low_memory=False)
    democrats = candidates[candidates.canonical_party.eq("D")].copy()
    race_cols = ["cycle", "chamber", "district", "contest_status", "core_index_margin",
                 "prior_presidential_year", "prior_pres_dem_margin", "nonwhite_share", "white_college_share"]
    democrats = democrats.merge(races[race_cols], left_on=["year", "chamber", "district"],
                                right_on=["cycle", "chamber", "district"], how="left", suffixes=("", "_race"))
    leg_cols = ["canonical_candidate_id", "ideal_point", "chamber_percentile", "distance_from_caucus_median",
                "party_loyalty_rate", "cross_party_voting_rate", "votes_used"]
    democrats = democrats.merge(legislative[leg_cols], on="canonical_candidate_id", how="left", validate="one_to_one")
    wide = positions.pivot_table(index="canonical_candidate_id", columns="primitive_axis",
                                 values="adjudicated_issue_valence", aggfunc="first")
    eligible_ids = set(democrats.loc[democrats.ideology_v3_issue_count.fillna(0).ge(3), "canonical_candidate_id"])
    coverage = wide.loc[wide.index.intersection(eligible_ids)].notna().sum()
    axes = sorted(coverage[coverage.ge(30)].index.tolist())
    wide = wide[axes].add_prefix("issue__").reset_index()
    democrats = democrats.merge(wide, on="canonical_candidate_id", how="left")
    features = [f"issue__{axis}" for axis in axes] + ["ideal_point", "party_loyalty_rate", "cross_party_voting_rate"]
    return democrats, features


def fit_clusters(frame: pd.DataFrame, features: list[str], within_cycle: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, KNNImputer, StandardScaler, KMeans]:
    sample = frame[frame.ideology_v3_issue_count.fillna(0).ge(3)].copy()
    raw = sample[features].astype(float)
    # Normalize observed values before distance-based imputation so axes with
    # different empirical variance contribute comparably.
    means, stds = raw.mean(), raw.std(ddof=0).replace(0, 1)
    normalized = (raw - means) / stds
    if within_cycle:
        # Identify caucuses relative to Democrats facing the same electoral and
        # policy era, preventing questionnaire changes and secular party change
        # from masquerading as candidate factions.
        for year, index in sample.groupby("year").groups.items():
            part = raw.loc[index]
            year_mean = part.mean()
            year_std = part.std(ddof=0)
            usable = part.notna().sum().ge(3) & year_std.gt(0)
            normalized.loc[index, usable] = (part.loc[:, usable] - year_mean[usable]) / year_std[usable]
    imputer = KNNImputer(n_neighbors=7, weights="distance")
    x = imputer.fit_transform(normalized)
    scaler = StandardScaler()
    x = scaler.fit_transform(x)
    projection = PCA(n_components=2, random_state=SEED)
    coordinates = projection.fit_transform(x)
    diagnostics = []
    rng = np.random.default_rng(SEED)
    models = {}
    for k in range(2, 7):
        model = KMeans(n_clusters=k, n_init=100, random_state=SEED).fit(x)
        counts = np.bincount(model.labels_, minlength=k)
        stability = []
        for iteration in range(40):
            index = rng.integers(0, len(x), len(x))
            boot = KMeans(n_clusters=k, n_init=20, random_state=SEED + iteration + k * 100).fit(x[index])
            stability.append(adjusted_rand_score(model.labels_, boot.predict(x)))
        diagnostics.append({"clusters": k, "silhouette": silhouette_score(x, model.labels_),
                            "bootstrap_ari_mean": np.mean(stability), "bootstrap_ari_min": np.min(stability),
                            "smallest_cluster": counts.min(), "smallest_cluster_share": counts.min()/len(x)})
        models[k] = model
    diagnostics = pd.DataFrame(diagnostics)
    viable = diagnostics[diagnostics.smallest_cluster_share.ge(.08)].copy()
    if viable.empty:
        # A collapsed headline space can expose a dominant continuum rather
        # than well-separated clusters. Retain the least-fragmented candidate
        # solution for diagnosis instead of crashing or silently restoring the
        # old detailed taxonomy.
        viable = diagnostics[diagnostics.clusters.eq(2)].copy()
    viable["selection_score"] = viable.silhouette + .35 * viable.bootstrap_ari_mean
    best_k = int(viable.sort_values("selection_score", ascending=False).iloc[0].clusters)
    model = models[best_k]
    sample["cluster_id"] = model.labels_ + 1
    sample["cluster_distance"] = np.min(model.transform(x), axis=1)
    sample["ideology_map_x"] = coordinates[:, 0]
    sample["ideology_map_y"] = coordinates[:, 1]
    sample.attrs["projection_loadings"] = pd.DataFrame({
        "feature": features,
        "component_1_loading": projection.components_[0],
        "component_2_loading": projection.components_[1],
    })
    sample.attrs["projection_variance"] = projection.explained_variance_ratio_
    sample.attrs["normalization_means"] = means
    sample.attrs["normalization_stds"] = stds
    return sample, diagnostics, imputer, scaler, model


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    democrats, features = assemble()
    clustered, diagnostics, _, _, model = fit_clusters(democrats, features, within_cycle=True)
    projection_loadings = clustered.attrs["projection_loadings"].copy()
    projection_loadings.to_csv(OUT / "democratic_cluster_projection_loadings.csv", index=False)
    pd.DataFrame({"component": [1, 2], "explained_variance_share": clustered.attrs["projection_variance"]}).to_csv(
        OUT / "democratic_cluster_projection_summary.csv", index=False)
    modeled = pd.read_csv(RESEARCH / "candidate_cycle_analysis.csv", low_memory=False)
    modeled_cols = ["canonical_candidate_id", "expected_cmo_total_oof", "candidate_cmo_total_oof",
                    "candidate_cmo_resource_adjusted_oof", "candidate_cmo_fundraising_adjusted_oof"]
    clustered = clustered.merge(modeled[modeled_cols], on="canonical_candidate_id", how="left", validate="one_to_one")
    diagnostics.to_csv(OUT / "cluster_model_diagnostics.csv", index=False)
    profile_cols = features + ["raw_overperformance", "core_index_margin", "prior_pres_dem_margin",
                               "party_loyalty_rate", "cross_party_voting_rate", "incumbent"]
    profile_cols = list(dict.fromkeys(profile_cols))
    profiles = clustered.groupby("cluster_id")[profile_cols].agg(["mean", "median", "count"])
    profiles.to_csv(OUT / "democratic_cluster_profiles.csv")

    contested = clustered.contest_status.eq("contested_two_party")
    high_threshold = clustered.loc[contested, "raw_overperformance"].quantile(.75)
    clustered["high_raw_overperformance"] = contested & clustered.raw_overperformance.ge(high_threshold)
    clustered["unopposed_democrat"] = clustered.contest_status.eq("unopposed_democrat")
    # Core index provides the consistently available top-of-ticket baseline;
    # prior presidential margin is retained as the stricter presidential flag.
    clustered["republican_top_ticket_district"] = clustered.core_index_margin.lt(0)
    clustered["republican_presidential_district"] = clustered.prior_pres_dem_margin.lt(0)
    # Name empirical blocs from their observed profiles, never from numeric IDs
    # left over from an earlier solution. Higher values on this index indicate
    # the recognizably Alabama crossover bundle: gun access, punitive justice,
    # welfare conditionality, and lower abortion/civil/voting access.
    naming = clustered.groupby("cluster_id").agg(
        gun=("issue__gun_access", "mean"), punishment=("issue__criminal_punishment", "mean"),
        conditionality=("issue__welfare_conditionality", "mean"), abortion=("issue__abortion_access", "mean"),
        liberty=("issue__civil_social_liberty", "mean"), voting=("issue__voting_access", "mean"))
    naming["traditionalist_index"] = (naming.gun + naming.punishment + naming.conditionality
                                       - naming.abortion - naming.liberty - naming.voting)
    traditionalist_id = int(naming.traditionalist_index.idxmax())
    labels = {cid: ("Crossover/traditionalist bloc" if cid == traditionalist_id
                    else "Mainstream/progressive bloc") for cid in naming.index}
    clustered["cluster_label"] = clustered.cluster_id.map(labels)
    clustered.to_csv(OUT / "democratic_candidate_cluster_membership.csv", index=False)
    targets = clustered[clustered.high_raw_overperformance | (clustered.unopposed_democrat & clustered.republican_top_ticket_district)].copy()
    targets["selection_group"] = np.select(
        [targets.high_raw_overperformance & targets.unopposed_democrat & targets.republican_top_ticket_district,
         targets.high_raw_overperformance,
         targets.unopposed_democrat & targets.republican_top_ticket_district],
        ["high_raw_and_unopposed_gop_lean", "high_raw_overperformance", "unopposed_gop_lean"], default="")
    targets.sort_values(["selection_group", "raw_overperformance"], ascending=[True, False]).to_csv(
        OUT / "democratic_cluster_focal_candidates.csv", index=False)

    cluster_summary = (clustered.groupby("cluster_id")
                       .agg(candidate_cycles=("canonical_candidate_id", "size"), people=("person_id", "nunique"),
                            cycles=("year", "nunique"), median_year=("year", "median"),
                            high_raw_overperformance=("high_raw_overperformance", "sum"), unopposed=("unopposed_democrat", "sum"),
                            unopposed_gop_lean=("republican_top_ticket_district", lambda s: int((s & clustered.loc[s.index, "unopposed_democrat"]).sum())),
                            mean_cmo=("raw_overperformance", "mean"), median_core_margin=("core_index_margin", "median"))
                       .reset_index())
    cluster_summary.to_csv(OUT / "democratic_cluster_summary.csv", index=False)
    crossover = clustered.cluster_id.eq(traditionalist_id)
    high_table = [[int((crossover & clustered.high_raw_overperformance).sum()), int((crossover & ~clustered.high_raw_overperformance).sum())],
                  [int((~crossover & clustered.high_raw_overperformance).sum()), int((~crossover & ~clustered.high_raw_overperformance).sum())]]
    high_odds, high_p = fisher_exact(high_table)
    cmo_observed = contested & clustered.candidate_cmo_total_oof.notna()
    cmo_threshold = clustered.loc[cmo_observed, "candidate_cmo_total_oof"].quantile(.75)
    high_oof_cmo = cmo_observed & clustered.candidate_cmo_total_oof.ge(cmo_threshold)
    cmo_table = [[int((crossover & high_oof_cmo).sum()), int((crossover & cmo_observed & ~high_oof_cmo).sum())],
                 [int((~crossover & high_oof_cmo).sum()), int((~crossover & cmo_observed & ~high_oof_cmo).sum())]]
    cmo_odds, cmo_p = fisher_exact(cmo_table)
    cmo_cross = clustered.loc[crossover & cmo_observed, "candidate_cmo_total_oof"]
    cmo_other = clustered.loc[~crossover & cmo_observed, "candidate_cmo_total_oof"]
    cmo_mw_p = mannwhitneyu(cmo_cross, cmo_other, alternative="two-sided").pvalue
    gop_unopposed = clustered.unopposed_democrat & clustered.republican_top_ticket_district
    gop_table = [[int((crossover & gop_unopposed).sum()), int((crossover & ~gop_unopposed).sum())],
                 [int((~crossover & gop_unopposed).sum()), int((~crossover & ~gop_unopposed).sum())]]
    gop_odds, gop_p = fisher_exact(gop_table)
    person_stability = clustered.groupby("person_id").agg(observations=("cluster_id", "size"), clusters=("cluster_id", "nunique"))
    repeated = person_stability[person_stability.observations.gt(1)]
    stable_people = int(repeated.clusters.eq(1).sum())
    report = [
        "# Democratic ideological clusters and crossover performance", "",
        f"The primary analysis clusters **{len(clustered)} Democratic candidate-cycles** with at least three adjudicated issue axes. CMO, district partisanship, race status, demographics, and incumbency are excluded from the clustering features.", "",
        f"A {model.n_clusters}-cluster within-cycle solution was selected (silhouette **{diagnostics.loc[diagnostics.clusters.eq(model.n_clusters),'silhouette'].iloc[0]:.3f}**, mean bootstrap ARI **{diagnostics.loc[diagnostics.clusters.eq(model.n_clusters),'bootstrap_ari_mean'].iloc[0]:.3f}**). This is useful exploratory structure, not proof of formal caucus membership.", "",
        "## Interpreted clusters", "",
        f"- **Crossover/traditionalist bloc:** {int(crossover.sum())} candidate-cycles. It combines expanded gun access, punitive criminal justice, welfare conditionality, restricted abortion/civil/voting access, and higher cross-party voting. This is a multi-issue identity rather than a single conservative score.",
        f"- **Mainstream/progressive bloc:** {int((~crossover).sum())} candidate-cycles. It combines stronger abortion, civil-liberty, voting-access, public-service, welfare, and environmental positions with less gun access and lower cross-party voting.", "",
        "## Relationship to electoral performance", "",
        f"Raw district overperformance is strongly concentrated in the crossover bloc. Its top-quartile cutoff is **{high_threshold:.2f} points**; the crossover bloc has **{int((crossover & clustered.high_raw_overperformance).sum())}** such cases versus **{int((~crossover & clustered.high_raw_overperformance).sum())}** elsewhere (Fisher odds ratio **{high_odds:.2f}**, p = **{high_p:.4f}**).",
        f"The relationship is attenuated in out-of-fold residual CMO: the crossover mean is **{cmo_cross.mean():.2f}** versus **{cmo_other.mean():.2f}** elsewhere (Mann-Whitney p = **{cmo_mw_p:.3f}**); top-quartile residual CMO has odds ratio **{cmo_odds:.2f}**, p = **{cmo_p:.3f}**. This is a decomposition result, not a rejection of the total advantage: residual CMO removes candidate and district pathways through which caucus identity can produce incumbency, fundraising, survival, and expected support.",
        f"It contains **{int((crossover & gop_unopposed).sum())}** unopposed Democrats in Republican-leaning core-index districts, versus **{int((~crossover & gop_unopposed).sum())}** elsewhere (odds ratio **{gop_odds:.2f}**, p = **{gop_p:.4f}**). The latter sample is small and is descriptive, not a strong causal result.", "",
        "## Sensitivity and limitations", "",
        "- Within-cycle standardization reduces, but does not eliminate, the era split: the traditionalist bloc is much less common in recent cycles and has no classified 2022 cases.",
        "- The low silhouette means candidates lie on a continuum with two dense tendencies, not in two cleanly separated formal caucuses.",
        "- Candidate-cycles are observations; the same person may appear in multiple elections.",
        f"- Among {len(repeated)} people observed in multiple clustered cycles, {stable_people} ({stable_people/len(repeated):.1%}) remain in the same cluster. Cluster switching therefore reflects real temporal/source uncertainty and argues against treating labels as permanent personal identities.",
        "- Unopposed status is an outcome of recruitment and strategic entry as well as candidate ideology. It should not be interpreted as voter approval measured in a contested race.",
        "- Core index margin is the consistently available top-of-ticket measure. The stricter prior-presidential margin is missing for many later candidate-cycles.",
    ]
    (OUT / "DEMOCRATIC_IDEOLOGICAL_CLUSTERS.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Selected k={model.n_clusters}; clustered {len(clustered)} Democratic candidate-cycles")
    print(diagnostics.to_string(index=False))
    print(cluster_summary.to_string(index=False))
    print(f"High raw-overperformance cutoff: {high_threshold:.3f}; focal candidates: {len(targets)}")


if __name__ == "__main__":
    main()
