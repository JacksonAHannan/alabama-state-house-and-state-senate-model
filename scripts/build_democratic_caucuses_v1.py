#!/usr/bin/env python3
"""Build person-level ideological groupings of Alabama Democratic candidates.

Owner decisions (2026-09-11 grill, Q9-Q20): one career profile per person from
every ontology-v3 evidence channel (roll calls 1.0, sponsorship 1.2,
questionnaires 1.0, statements/endorsements lower) dated through the latest
available session (Q19a); clustering features are the eight ontology issue
families (Q10a); a person is clustered when at least 30% of the eligible
features are observed (Q11a); the number of groups is chosen by bootstrap
stability over k in 2-5 and labels are proposed from the profiles for owner
approval (Q12b); the universe is every Democratic general-election candidate
1994-2022 including uncontested seats (Q4a), Democrats only (Q20); historical
residual WAR (cycle and career-cumulative, Q14) is attached only after
clustering, so no outcome can inform a grouping.

58% of ontology-v3 evidence rows sit on primitive axes that carry no family
loading (tax burden, gun access, public spending, education funding, voting
access). Q10a excludes them from the clustering features, so the same solution
is refit on families-plus-eligible-axes and reported as a sensitivity rather
than silently adopted.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import KNNImputer, SimpleImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

import alabama_candidate_identity as identity
import ideology_ontology_v3 as ontology

ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = ROOT / "data" / "processed" / "elections"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
WAR = ROOT / "data" / "processed" / "war" / "alabama_historical_war_v1"
OUT = IDEOLOGY / "democratic_caucuses_v1"
CANDIDATES = ELECTIONS / "canonical_cmo_candidates.csv"
EVIDENCE = IDEOLOGY / "candidate_position_evidence_v3_all_sources.csv"
HISTORICAL_WAR = WAR / "candidate_cycle_war.csv"
HISTORICAL_MANIFEST = WAR / "manifest.json"
LABELS = ROOT / "data" / "manual" / "ideology" / "democratic_caucus_labels.csv"

METHODOLOGY_VERSION = "democratic_caucuses_v1_person_career"
CYCLES = (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022)
SEED = 20260911
POLE = 0.15
MIN_FEATURE_PEOPLE, MIN_POLE_PEOPLE = 30, 5
MIN_OBSERVED_SHARE = 0.30
MIN_CLUSTER_N, MIN_CLUSTER_SHARE = 12, 0.08
MAX_K, BOOTSTRAPS = 5, 60
LEGISLATIVE_SOURCES = {
    "legislative_vote", "bill_sponsorship", "bill_cosponsorship", "legislative_cosponsorship",
    "legislative_proposal", "legislative_position", "legislative_record", "legislative_advocacy",
    "bill_sponsorship_and_statement",
}
# Orientation used only to order clusters deterministically (+1 = the pole
# conventionally coded liberal). Families keep the ontology's within-family
# direction; issue-only axes list the first declared pole.
LIBERAL_DIRECTION = {
    "market_government_direction": 1.0, "material_support": 1.0, "labor_capital": 1.0,
    "social_liberty_equality": 1.0, "order_justice": -1.0, "immigration_inclusion": 1.0,
    "environment_resources": 1.0, "institutional_reform": 1.0,
    "axis:tax_burden": 1.0, "axis:public_spending": 1.0, "axis:public_employee_compensation": 1.0,
    "axis:education_public_funding": 1.0, "axis:voting_access": 1.0, "axis:gun_access": -1.0,
    "axis:gun_purchase_regulation": 1.0, "axis:business_subsidy": 0.0, "axis:economic_stimulus": 1.0,
    "axis:tax_distribution": 1.0, "axis:education_market_choice": -1.0, "axis:incarceration": -1.0,
    "axis:police_authority": -1.0, "axis:deficit_discipline": -1.0, "axis:election_integrity_controls": -1.0,
    "axis:gambling_policy": 0.0, "axis:confederate_commemoration": -1.0, "axis:religion_state": -1.0,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_universe() -> tuple[pd.DataFrame, dict[str, str]]:
    """Democratic candidate-cycles, with split 2022 identities folded together.

    A 2022 canonical row carries a source stub for both its name and its
    `person_id`, so 25 sitting Democrats appeared as two people - one career up
    to 2018 and a separate 2022 person - which split their issue evidence
    across two partial profiles. Names come from verified adjudications and a
    fold happens only on an exact unique name.
    """
    candidates = pd.read_csv(CANDIDATES, low_memory=False)
    democrats = candidates[candidates.canonical_party.eq("D") & candidates.year.isin(CYCLES)].copy()
    democrats = democrats.rename(columns={"year": "cycle"})
    if democrats.canonical_candidate_id.duplicated().any():
        raise ValueError("Democratic candidate-cycle identifiers are not unique")
    if democrats.person_id.isna().any() or democrats.person_id.astype(str).str.strip().eq("").any():
        raise ValueError("Every Democratic candidate-cycle needs a person_id")
    democrats = identity.career_identity(identity.resolve_names(democrats))
    folds = {row.person_id: row.career_person_id for row in democrats.itertuples()
             if row.person_id != row.career_person_id}
    democrats["source_person_id"] = democrats.person_id
    democrats["person_id"] = democrats.career_person_id
    democrats["canonical_name"] = democrats.resolved_name.fillna(democrats.canonical_name)
    return democrats, folds


def signed_evidence(evidence: pd.DataFrame) -> pd.DataFrame:
    """Return one signed observation per evidence row on a family or issue-only axis."""
    frame = evidence.copy()
    has_family = frame.family.notna() & frame.family.astype(str).str.strip().ne("") & frame.family_contribution.notna()
    frame["feature"] = np.where(has_family, frame.family, "axis:" + frame.primitive_axis.astype(str))
    frame["value"] = frame.family_contribution.astype(float)
    axis_rows = frame[~has_family]
    directions = {}
    for axis, pole in axis_rows[["primitive_axis", "policy_pole"]].drop_duplicates().itertuples(index=False):
        try:
            directions[(axis, pole)] = ontology.primitive_axis_direction(axis, pole)
        except ValueError:
            directions[(axis, pole)] = None
    direction = axis_rows.apply(lambda r: directions.get((r.primitive_axis, r.policy_pole)), axis=1)
    frame.loc[axis_rows.index, "value"] = axis_rows.position_value.astype(float) * direction.astype(float)
    frame = frame[frame.value.notna()].copy()
    frame["weight"] = frame.evidence_weight.astype(float).clip(lower=1e-6)
    frame["legislative"] = frame.source_type.isin(LEGISLATIVE_SOURCES)
    return frame


def person_features(signed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Weighted mean signed position per person and feature, with evidence counts."""
    signed = signed.assign(wv=signed.value * signed.weight)
    grouped = signed.groupby(["person_id", "feature"])
    table = grouped.agg(weight=("weight", "sum"), wv=("wv", "sum"), records=("evidence_id", "size"),
                        sources=("source_type", "nunique"),
                        legislative_records=("legislative", "sum")).reset_index()
    table["position"] = table.wv / table.weight
    wide = table.pivot(index="person_id", columns="feature", values="position")
    return wide, table.drop(columns="wv")


def eligible_features(wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature in wide.columns:
        values = wide[feature].dropna()
        low, high = int((values < -POLE).sum()), int((values > POLE).sum())
        rows.append({"feature": feature, "people_observed": int(len(values)),
                     "people_low_pole": low, "people_high_pole": high,
                     "sd": float(values.std(ddof=0)) if len(values) else 0.0,
                     "eligible": len(values) >= MIN_FEATURE_PEOPLE and min(low, high) >= MIN_POLE_PEOPLE
                                 and values.std(ddof=0) > 0})
    return pd.DataFrame(rows).sort_values(["eligible", "people_observed"], ascending=[False, False])


def centre_within(column: pd.Series) -> pd.Series:
    """Standardize one feature inside an era block; constant or empty blocks pass through centred."""
    spread = column.std(ddof=0)
    return (column - column.mean()) / (spread if spread and spread > 0 else 1.0)


def prepare_matrix(sample: pd.DataFrame, features: list[str], method: str = "knn") -> np.ndarray:
    raw = sample[features].astype(float)
    normalized = (raw - raw.mean()) / raw.std(ddof=0).replace(0, 1)
    if method == "median":
        values = SimpleImputer(strategy="median").fit_transform(normalized)
    else:
        values = KNNImputer(n_neighbors=min(7, max(2, len(sample) - 1)), weights="distance").fit_transform(normalized)
    return StandardScaler().fit_transform(values)


def diagnostics_for_matrix(x: np.ndarray) -> tuple[pd.DataFrame, dict[int, KMeans]]:
    rng, rows, models = np.random.default_rng(SEED), [], {}
    for k in range(2, min(MAX_K, len(x) - 1) + 1):
        model = KMeans(n_clusters=k, n_init=100, random_state=SEED + k).fit(x)
        sizes, stability = np.bincount(model.labels_, minlength=k), []
        for iteration in range(BOOTSTRAPS):
            index = rng.integers(0, len(x), len(x))
            boot = KMeans(n_clusters=k, n_init=30, random_state=SEED + k * 100 + iteration).fit(x[index])
            stability.append(adjusted_rand_score(model.labels_, boot.predict(x)))
        rows.append({"clusters": k, "silhouette": float(silhouette_score(x, model.labels_)),
                     "bootstrap_ari_mean": float(np.mean(stability)),
                     "bootstrap_ari_p10": float(np.quantile(stability, .10)),
                     "smallest_cluster": int(sizes.min()), "smallest_cluster_share": float(sizes.min() / len(x))})
        models[k] = model
    return pd.DataFrame(rows), models


def choose_k(diagnostics: pd.DataFrame) -> int:
    viable = diagnostics[diagnostics.smallest_cluster.ge(MIN_CLUSTER_N)
                         & diagnostics.smallest_cluster_share.ge(MIN_CLUSTER_SHARE)].copy()
    if viable.empty:
        viable = diagnostics[diagnostics.clusters.eq(2)].copy()
    viable["selection_score"] = viable.silhouette + .30 * viable.bootstrap_ari_mean - .015 * (viable.clusters - 2)
    return int(viable.sort_values(["selection_score", "clusters"], ascending=[False, True]).iloc[0].clusters)


def order_clusters(sample: pd.DataFrame, features: list[str], labels: np.ndarray) -> dict[int, int]:
    """Map raw k-means labels to ranks 1..k from most to least liberal composite."""
    oriented = [f for f in features if LIBERAL_DIRECTION.get(f, 0.0) != 0.0]
    if not oriented:
        oriented = features
    z = (sample[oriented] - sample[oriented].mean()) / sample[oriented].std(ddof=0).replace(0, 1)
    composite = (z * pd.Series({f: LIBERAL_DIRECTION.get(f, 1.0) for f in oriented})).mean(axis=1)
    means = composite.groupby(labels).mean().sort_values(ascending=False)
    return {int(raw): rank for rank, raw in enumerate(means.index, start=1)}


def load_labels(k: int) -> dict[int, dict[str, str]]:
    if LABELS.exists():
        table = pd.read_csv(LABELS)
        if set(table.cluster_rank) == set(range(1, k + 1)) and table.get("solution_k", pd.Series([k])).eq(k).all():
            return {int(r.cluster_rank): {"label": r.label, "description": r.description}
                    for r in table.itertuples(index=False)}
    return {rank: {"label": f"Group {rank} (provisional)", "description": ""} for rank in range(1, k + 1)}


def attach_outcomes(universe: pd.DataFrame, membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    war = pd.read_csv(HISTORICAL_WAR, low_memory=False)[[
        "canonical_candidate_id", "candidate_cycle_war", "candidate_raw_gap",
        "candidate_structural_expected_gap", "scoring_scope", "lag_context_available",
        "candidate_federal_ticket_cmo", "candidate_presidential_ticket_cmo",
    ]]
    if war.canonical_candidate_id.duplicated().any():
        raise ValueError("Historical WAR candidate-cycle identifiers are not unique")
    cycles = universe.merge(war, on="canonical_candidate_id", how="left", validate="one_to_one")
    cycles["war_scored"] = cycles.candidate_cycle_war.notna()
    cycles = cycles.merge(membership[["person_id", "cluster_rank", "cluster_label"]], on="person_id",
                          how="left", validate="many_to_one")
    career = (cycles.groupby("person_id")
              .agg(cycles_total=("cycle", "size"), cycles_scored=("war_scored", "sum"),
                   cycles_unscored=("war_scored", lambda s: int((~s).sum())),
                   career_war=("candidate_cycle_war", lambda s: float(s.sum()) if s.notna().any() else np.nan),
                   mean_cycle_war=("candidate_cycle_war", "mean"),
                   first_cycle=("cycle", "min"), last_cycle=("cycle", "max"),
                   general_wins=("winner", "sum"), chambers=("chamber", lambda s: "/".join(sorted(set(s)))))
              .reset_index())
    career["cycles_scored"] = career.cycles_scored.astype(int)
    return cycles, career


def group_summary(cycles: pd.DataFrame, career: pd.DataFrame, labels: dict[int, dict[str, str]]) -> pd.DataFrame:
    rows = []
    for rank, meta in labels.items():
        members = career[career.cluster_rank.eq(rank)]
        scored = cycles[cycles.cluster_rank.eq(rank) & cycles.war_scored]
        all_cycles = cycles[cycles.cluster_rank.eq(rank)]
        war = scored.candidate_cycle_war
        se = float(war.std(ddof=1) / math.sqrt(len(war))) if len(war) > 1 else np.nan
        rows.append({
            "cluster_rank": rank, "cluster_label": meta["label"], "people": int(len(members)),
            "candidate_cycles": int(len(all_cycles)), "cycles_scored": int(len(scored)),
            "cycles_unscored": int(len(all_cycles) - len(scored)),
            "unscored_share": float(1 - len(scored) / len(all_cycles)) if len(all_cycles) else np.nan,
            "people_with_any_war": int(members.cycles_scored.gt(0).sum()),
            "cycle_war_mean": float(war.mean()) if len(war) else np.nan,
            "cycle_war_median": float(war.median()) if len(war) else np.nan,
            "cycle_war_se": se,
            "career_war_mean": float(members.career_war.mean()),
            "career_war_median": float(members.career_war.median()),
            "general_wins": int(all_cycles.winner.sum()),
        })
    return pd.DataFrame(rows)


def fit_spec(wide: pd.DataFrame, features: list[str]) -> dict:
    """Cluster every person observing enough of `features`; no outcome is consulted."""
    observed = wide[features].notna().sum(axis=1)
    minimum = max(3, math.ceil(len(features) * MIN_OBSERVED_SHARE))
    profile = wide.loc[observed.ge(minimum), features].copy()
    profile["features_observed"] = observed[profile.index]
    matrix = prepare_matrix(profile, features)
    diagnostics, models = diagnostics_for_matrix(matrix)
    k = choose_k(diagnostics)
    diagnostics["selected"] = diagnostics.clusters.eq(k)
    rank_map = order_clusters(profile, features, models[k].labels_)
    profile["cluster_rank"] = [rank_map[int(raw)] for raw in models[k].labels_]
    return {"features": features, "minimum": minimum, "observed": observed, "profile": profile,
            "diagnostics": diagnostics, "k": k}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    universe, identity_folds = load_universe()
    people = universe.groupby("person_id").agg(
        display_name=("canonical_name", "last"), cycles=("cycle", lambda s: "/".join(map(str, sorted(set(s))))),
        chambers=("chamber", lambda s: "/".join(sorted(set(s)))), first_cycle=("cycle", "min"),
        last_cycle=("cycle", "max"), candidate_cycles=("cycle", "size"), general_wins=("winner", "sum"),
        ever_incumbent=("incumbent", "max")).reset_index()

    evidence = pd.read_csv(EVIDENCE, low_memory=False)
    # Evidence is keyed by the source person, so it follows the same fold.
    evidence["person_id"] = evidence.person_id.replace(identity_folds)
    evidence = evidence[evidence.person_id.isin(people.person_id)].copy()
    signed = signed_evidence(evidence)
    wide, table = person_features(signed)
    inventory = eligible_features(wide)
    eligible = inventory[inventory.eligible].feature.tolist()
    features = [feature for feature in eligible if not feature.startswith("axis:")]
    if len(features) < 3:
        raise RuntimeError("fewer than three adequately covered two-sided issue families")

    primary = fit_spec(wide, features)
    profile, k, diagnostics = primary["profile"], primary["k"], primary["diagnostics"]
    minimum, observed = primary["minimum"], primary["observed"]
    labels = load_labels(k)
    labels_approved = not any(str(meta["label"]).endswith("(provisional)") for meta in labels.values())
    profile["cluster_label"] = profile.cluster_rank.map(lambda rank: labels[rank]["label"])

    unclustered = people[~people.person_id.isin(profile.index)].copy()
    unclustered["features_observed"] = unclustered.person_id.map(observed).fillna(0).astype(int)
    unclustered["reason"] = np.where(unclustered.features_observed.eq(0), "no_ontology_evidence",
                                     "below_minimum_features")

    # Sensitivity: imputation, missingness structure, legislative-only evidence, axis-augmented features.
    median_labels = KMeans(n_clusters=k, n_init=100, random_state=SEED + k).fit_predict(prepare_matrix(profile, features, "median"))
    missing_labels = KMeans(n_clusters=k, n_init=100, random_state=SEED + k).fit_predict(
        StandardScaler().fit_transform(profile[features].notna().astype(float)))
    leg_wide, _ = person_features(signed[signed.legislative])
    leg_common = [f for f in features if f in leg_wide.columns]
    leg_sample = leg_wide.reindex(profile.index)[leg_common]
    leg_ok = leg_sample.notna().sum(axis=1).ge(minimum)
    if leg_ok.sum() >= MIN_CLUSTER_N * k:
        leg_labels = KMeans(n_clusters=k, n_init=100, random_state=SEED + k).fit_predict(prepare_matrix(leg_sample[leg_ok], leg_common))
        leg_ari = float(adjusted_rand_score(profile.loc[leg_ok, "cluster_rank"], leg_labels))
    else:
        leg_ari = np.nan

    membership_cycles = people.set_index("person_id").candidate_cycles.reindex(profile.index)
    era_bucket = pd.cut(people.set_index("person_id").last_cycle.reindex(profile.index),
                        bins=[1993, 2004, 2015, 2023], labels=["1994_2002", "2006_2014", "2018_2022"])
    era_frame = profile[features].groupby(era_bucket, observed=False).transform(centre_within)
    era_labels = KMeans(n_clusters=k, n_init=100, random_state=SEED + k).fit_predict(prepare_matrix(era_frame, features))
    era_ranks = order_clusters(era_frame, features, era_labels)
    profile["era_normalized_cluster_rank"] = [era_ranks[int(raw)] for raw in era_labels]
    strict_minimum = max(minimum + 1, math.ceil(len(features) * 0.5))
    strict = profile.index[profile.features_observed.ge(strict_minimum)]
    if len(strict) >= MIN_CLUSTER_N * k:
        strict_labels = KMeans(n_clusters=k, n_init=100, random_state=SEED + k).fit_predict(
            prepare_matrix(profile.loc[strict], features))
        strict_ari = float(adjusted_rand_score(profile.loc[strict, "cluster_rank"], strict_labels))
    else:
        strict_ari = np.nan

    augmented = fit_spec(wide, eligible)
    shared = profile.index.intersection(augmented["profile"].index)
    augmented_row = augmented["diagnostics"][augmented["diagnostics"].selected].iloc[0]
    sensitivity = pd.DataFrame([{
        "clusters": k, "people": int(len(profile)), "features": len(features),
        "minimum_features_observed": minimum, "median_features_observed": float(profile.features_observed.median()),
        "knn_vs_median_ari": float(adjusted_rand_score(profile.cluster_rank, median_labels)),
        "position_vs_missingness_ari": float(adjusted_rand_score(profile.cluster_rank, missing_labels)),
        "all_source_vs_legislative_only_ari": leg_ari,
        "people_with_legislative_only_profile": int(leg_ok.sum()),
        "augmented_features": len(eligible), "augmented_people": int(len(augmented["profile"])),
        "augmented_clusters": int(augmented["k"]),
        "augmented_silhouette": float(augmented_row.silhouette),
        "augmented_bootstrap_ari_mean": float(augmented_row.bootstrap_ari_mean),
        "families_vs_augmented_ari": float(adjusted_rand_score(
            profile.loc[shared, "cluster_rank"], augmented["profile"].loc[shared, "cluster_rank"])),
        "families_vs_augmented_people": int(len(shared)),
        "era_normalized_ari": float(adjusted_rand_score(profile.cluster_rank, era_labels)),
        "threshold_min_features": strict_minimum, "threshold_people": int(len(strict)),
        "threshold_ari": strict_ari,
        "repeated_people_share": float(membership_cycles.gt(1).mean()),
    }])

    membership = profile.reset_index().merge(people, on="person_id", validate="one_to_one")
    membership["solution_k"] = k
    cycles, career = attach_outcomes(universe, membership)
    membership = membership.merge(career.drop(columns=["first_cycle", "last_cycle", "general_wins", "chambers"]),
                                  on="person_id", validate="one_to_one")
    career = career.merge(membership[["person_id", "cluster_rank", "cluster_label"]], on="person_id", how="left")

    group_profiles = profile.groupby("cluster_rank")[features].mean().reset_index()
    group_profiles.insert(1, "cluster_label", group_profiles.cluster_rank.map(lambda rank: labels[rank]["label"]))
    group_profiles.insert(2, "people", profile.cluster_rank.value_counts().sort_index().values)
    coverage = (table.merge(profile[["cluster_rank"]], left_on="person_id", right_index=True)
                .groupby(["cluster_rank", "feature"]).agg(people=("person_id", "nunique"),
                                                          records=("records", "sum"),
                                                          legislative_records=("legislative_records", "sum")).reset_index())
    summary = group_summary(cycles, career, labels)

    outputs = {
        "person_profiles.csv": profile.reset_index(),
        "person_membership.csv": membership,
        "member_cycles.csv": cycles,
        "person_career_war.csv": career,
        "group_profiles.csv": group_profiles,
        "group_summary.csv": summary,
        "group_feature_coverage.csv": coverage,
        "feature_inventory.csv": inventory,
        "person_feature_evidence.csv": table,
        "cluster_diagnostics.csv": diagnostics,
        "cluster_sensitivity.csv": sensitivity,
        "unclustered_people.csv": unclustered,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)

    historical = json.loads(HISTORICAL_MANIFEST.read_text(encoding="utf-8"))
    digest = hashlib.sha256("".join(sha256(OUT / name) for name in sorted(outputs)).encode()).hexdigest()[:20].upper()
    manifest = {
        "methodology_version": METHODOLOGY_VERSION,
        "caucus_run_id": f"AL-DEM-CAUCUS-V1-{digest}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "historical_war_run_id": historical["historical_war_run_id"],
        "configuration": {
            "unit": "person (career profile from all evidence dated through the latest available session)",
            "feature_spec": "ontology_v3_issue_families",
            "features": features, "feature_rule": {"min_people": MIN_FEATURE_PEOPLE, "min_pole_people": MIN_POLE_PEOPLE, "pole": POLE},
            "excluded_axis_features": [f for f in eligible if f.startswith("axis:")],
            "person_rule": {"min_observed_share": MIN_OBSERVED_SHARE, "min_features_observed": minimum},
            "k_range": [2, MAX_K], "selected_k": k, "bootstraps": BOOTSTRAPS, "seed": SEED,
            "min_cluster_n": MIN_CLUSTER_N, "min_cluster_share": MIN_CLUSTER_SHARE,
            "cycles": list(CYCLES), "party": "D", "labels_source": str(LABELS.relative_to(ROOT)) if labels_approved else "provisional",
        },
        "inputs": [{"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(p)}
                   for p in (CANDIDATES, EVIDENCE, HISTORICAL_WAR, HISTORICAL_MANIFEST) + ((LABELS,) if LABELS.exists() else ())],
        "code_hashes": {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p)
                        for p in (Path(__file__).resolve(), ROOT / "scripts" / "ideology_ontology_v3.py")},
        "outputs": [{"path": str((OUT / name).relative_to(ROOT)).replace("\\", "/"), "rows": int(len(frame)), "sha256": sha256(OUT / name)}
                    for name, frame in outputs.items()],
        "diagnostics": {
            "democratic_people": int(len(people)), "democratic_candidate_cycles": int(len(universe)),
            "people_with_evidence": int(wide.shape[0]), "people_clustered": int(len(profile)),
            "people_unclustered": int(len(unclustered)),
            "split_identities_folded": len(identity_folds),
            "evidence_rows_used": int(len(signed)), "evidence_rows_legislative": int(signed.legislative.sum()),
            "evidence_rows_family_mapped": int((~signed.feature.str.startswith("axis:")).sum()),
            "evidence_rows_axis_only": int(signed.feature.str.startswith("axis:").sum()),
            "candidate_cycles_scored": int(cycles.war_scored.sum()),
            "candidate_cycles_unscored": int((~cycles.war_scored).sum()),
            "selected_k": k, **{k_: float(v) for k_, v in diagnostics[diagnostics.selected].iloc[0].drop(["clusters", "selected"]).items()},
            **sensitivity.iloc[0].drop(["clusters"]).to_dict(),
        },
        # Approved labels are pinned to a solution size; if the selected k moves,
        # they no longer describe these groups and the run is not publishable.
        "status": "descriptive_groupings" if labels_approved else "descriptive_groupings_labels_pending_owner_review",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"{manifest['caucus_run_id']}: people={len(people)} clustered={len(profile)} k={k} features={len(features)} "
          f"silhouette={manifest['diagnostics']['silhouette']:.3f} ari={manifest['diagnostics']['bootstrap_ari_mean']:.3f}")
    print(f"augmented sensitivity: features={len(eligible)} people={len(augmented['profile'])} k={augmented['k']} "
          f"silhouette={augmented_row.silhouette:.3f} cross-spec ARI={sensitivity.iloc[0].families_vs_augmented_ari:.3f} "
          f"on {len(shared)} shared people")
    print(summary.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
