"""Render the merged Alabama Democratic caucus page from the person-level groupings.

One page replaces the former `ideology-performance.html` / `caucuses.html` pair
(owner decision Q13a). Its only analytical input is the `democratic_caucuses_v1`
run: groups are formed from issue evidence alone and residual WAR is attached
afterwards, so nothing here re-estimates a model. The page must show the
coverage funnel, the per-group unscored share and the cluster sensitivity, since
the groups are descriptive tendencies rather than formal caucus membership.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.southern_war_release_gate import require_alabama_historical_release
except ModuleNotFoundError:
    from southern_war_release_gate import require_alabama_historical_release

try:
    from scripts import alabama_candidate_identity as identity
except ImportError:  # pragma: no cover - direct script execution
    import alabama_candidate_identity as identity

try:
    from scripts import ideology_ontology_v3 as ontology
except ImportError:  # pragma: no cover - direct script execution
    import ideology_ontology_v3 as ontology

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "site" / "ideology-performance.html"
CAUCUS = ROOT / "data" / "processed" / "ideology" / "democratic_caucuses_v1"
EVIDENCE = ROOT / "data" / "processed" / "ideology" / "candidate_position_evidence_v3_all_sources.csv"
LABELS = ROOT / "data" / "manual" / "ideology" / "democratic_caucus_labels.csv"
HISTORICAL_WAR_DIR = ROOT / "data" / "processed" / "war" / "alabama_historical_war_v1"
PUBLISHED_ALABAMA_MANIFEST = ROOT / "data" / "processed" / "war" / "alabama_war_v1" / "manifest.json"
DECISION = ROOT / "project_docs" / "audits" / "SOUTHERN_V3_RELEASE_DECISION.json"
ALIASES = ROOT / "data" / "manual" / "ideology" / "candidate_research_aliases.csv"
SOURCE_ID_PATTERN = re.compile(r"^[A-Z]{3}\d{3}[A-Z]{4,}$")

FAMILY_LABELS = {
    "market_government_direction": "Role of government",
    "material_support": "Material support",
    "labor_capital": "Labor and capital",
    "social_liberty_equality": "Social liberty and equality",
    "order_justice": "Order and justice",
    "immigration_inclusion": "Immigration",
    "environment_resources": "Environment and resources",
    "institutional_reform": "Institutions",
}
POLE_LABELS = {
    "market_autonomy": "Market autonomy", "government_direction": "Government direction",
    "restriction": "Restriction", "generosity": "Generosity",
    "capital_management": "Capital and management", "labor": "Labor",
    "traditional_restriction": "Traditional restriction", "liberty_equality": "Liberty and equality",
    "rehabilitation_due_process": "Rehabilitation and due process", "punitive_enforcement": "Punitive enforcement",
    "restriction_national_identity": "Restriction", "inclusion": "Inclusion",
    "extraction_property_priority": "Extraction and property", "protection_preservation": "Protection",
    "institutional_control": "Institutional control", "democratic_reform": "Democratic reform",
}
# The pole of each family that Alabama politics conventionally codes as liberal.
LIBERAL_POLE = {
    "market_government_direction": 1, "material_support": 1, "labor_capital": 1,
    "social_liberty_equality": 1, "order_justice": 0, "immigration_inclusion": 1,
    "environment_resources": 1, "institutional_reform": 1,
}
# Teal, mint, gold, brown and charcoal: no party, brand or WAR hue, separable under
# simulated deuteranopia and protanopia, and paired with distinct mark shapes.
GROUP_COLORS = ["#167a6c", "#b8d8c8", "#c9a227", "#7a4b1e", "#3b3b3b"]


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


def resolve_public_names(cycles: pd.DataFrame) -> pd.DataFrame:
    """One publishable name per person.

    Source identifiers are never published. Where no verified adjudication
    supplies a name, the person is described by the seat actually on record and
    flagged as unresolved rather than given a guessed one.
    """
    frame = identity.resolve_names(
        cycles[["person_id", "canonical_candidate_id", "canonical_name",
                "cycle", "chamber", "district"]].copy())
    named = frame[frame.name_source.ne("unresolved_source_stub")]
    resolved = named.sort_values("cycle").groupby("person_id").resolved_name.last()
    latest = frame.sort_values("cycle").groupby("person_id").last()
    seat = ("Unnamed " + latest.cycle.astype(str) + " "
            + latest.chamber.astype(str).str.upper().str[0] + "D-"
            + latest.district.astype(str) + " Democrat")
    names = pd.DataFrame({
        "name": resolved.reindex(latest.index).fillna(seat),
        "identityResolved": resolved.reindex(latest.index).notna(),
    })
    if names.name.map(identity.is_stub_name).any():
        raise ValueError("Identifier-shaped public candidate names are prohibited")
    return names


def evidence_channels(signed_people: set[str]) -> pd.DataFrame:
    evidence = pd.read_csv(EVIDENCE, low_memory=False,
                           usecols=["person_id", "source_type", "source_provider", "evidence_id"])
    evidence = evidence[evidence.person_id.isin(signed_people)]
    channel = np.where(evidence.source_type.astype(str).str.contains("legislative|bill|sponsor", case=False),
                       "Legislative record", evidence.source_provider.fillna("Other"))
    return (evidence.assign(channel=channel)
            .groupby("channel", as_index=False)
            .agg(evidence_rows=("evidence_id", "size"), people=("person_id", "nunique"))
            .sort_values("evidence_rows", ascending=False))


@lru_cache(maxsize=1)
def payload() -> dict:
    require_alabama_historical_release(
        HISTORICAL_WAR_DIR / "manifest.json", PUBLISHED_ALABAMA_MANIFEST, DECISION
    )
    manifest = json.loads((CAUCUS / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "descriptive_groupings":
        raise ValueError(f"Caucus run is not approved for rendering: {manifest['status']}")
    families = manifest["configuration"]["features"]

    members = pd.read_csv(CAUCUS / "person_membership.csv")
    cycles = pd.read_csv(CAUCUS / "member_cycles.csv", low_memory=False)
    summary = pd.read_csv(CAUCUS / "group_summary.csv")
    profiles = pd.read_csv(CAUCUS / "group_profiles.csv")
    person_profiles = pd.read_csv(CAUCUS / "person_profiles.csv")
    unclustered = pd.read_csv(CAUCUS / "unclustered_people.csv")
    sensitivity = pd.read_csv(CAUCUS / "cluster_sensitivity.csv").iloc[0]
    diagnostics = pd.read_csv(CAUCUS / "cluster_diagnostics.csv")
    labels = pd.read_csv(LABELS)

    names = resolve_public_names(cycles)
    members["name"] = members.person_id.map(names.name)
    members["identityResolved"] = members.person_id.map(names.identityResolved).astype(bool)
    if members.name.isna().any():
        raise ValueError("Every grouped person needs a publishable name")
    observed = person_profiles.set_index("person_id")[families].notna()

    group_rows = []
    for row in summary.itertuples(index=False):
        described = labels[labels.cluster_rank.eq(row.cluster_rank)].iloc[0]
        member_ids = members[members.cluster_rank.eq(row.cluster_rank)].person_id
        profile = profiles[profiles.cluster_rank.eq(row.cluster_rank)].iloc[0]
        group_rows.append({
            "rank": int(row.cluster_rank), "label": row.cluster_label,
            "description": described.description, "evidence": described.evidence,
            "people": int(row.people), "candidateCycles": int(row.candidate_cycles),
            "cyclesScored": int(row.cycles_scored), "cyclesUnscored": int(row.cycles_unscored),
            "unscoredShare": float(row.unscored_share), "generalWins": int(row.general_wins),
            "cycleWarMean": None if pd.isna(row.cycle_war_mean) else float(row.cycle_war_mean),
            "cycleWarMedian": None if pd.isna(row.cycle_war_median) else float(row.cycle_war_median),
            "cycleWarSe": None if pd.isna(row.cycle_war_se) else float(row.cycle_war_se),
            "careerWarMedian": None if pd.isna(row.career_war_median) else float(row.career_war_median),
            "profile": [{
                "family": family, "label": FAMILY_LABELS[family],
                "value": None if pd.isna(profile[family]) else float(profile[family]),
                "people": int(observed.loc[observed.index.isin(member_ids), family].sum()),
            } for family in families],
        })

    # Only grouped people appear in the performance view; ungrouped candidate-cycles
    # stay in the coverage counts so the omission is visible rather than silent.
    scored = cycles[cycles.war_scored & cycles.cluster_rank.notna()]
    member_rows = members.assign(
        eraGroup=members.era_normalized_cluster_rank.astype(int),
        chambers=members.chambers.astype(str),
    )[["person_id", "name", "identityResolved", "chambers", "cycles", "first_cycle", "last_cycle",
       "cluster_rank", "cluster_label", "features_observed", "cycles_total", "cycles_scored",
       "cycles_unscored", "career_war", "mean_cycle_war", "eraGroup"]]

    composition = (cycles.dropna(subset=["cluster_rank"])
                   .groupby(["cycle", "cluster_rank"], as_index=False)
                   .agg(n=("canonical_candidate_id", "size")))

    return {
        "schemaVersion": 4,
        "run": {
            "caucusRunId": manifest["caucus_run_id"],
            "generatedAt": manifest["generated_at_utc"],
            "historicalWarRunId": manifest["historical_war_run_id"],
            "labelsSource": manifest["configuration"]["labels_source"],
        },
        "families": [{
            "key": family, "label": FAMILY_LABELS[family],
            "negativePole": POLE_LABELS[ontology.FAMILIES[family][0]],
            "positivePole": POLE_LABELS[ontology.FAMILIES[family][1]],
            "liberalPole": "positive" if LIBERAL_POLE[family] else "negative",
        } for family in families],
        "groups": group_rows,
        "colors": GROUP_COLORS,
        "members": records(member_rows),
        # Per-person family positions in `families` order, for the scatter and member detail.
        "positions": {row.person_id: [None if pd.isna(getattr(row, family)) else round(float(getattr(row, family)), 4)
                                      for family in families]
                      for row in person_profiles.itertuples()},
        "warCycles": records(scored[["person_id", "cycle", "chamber", "district",
                                     "cluster_rank", "candidate_cycle_war", "winner"]]),
        "composition": records(composition),
        "coverage": {
            "people": int(manifest["diagnostics"]["democratic_people"]),
            "peopleWithEvidence": int(manifest["diagnostics"]["people_with_evidence"]),
            "peopleClustered": int(manifest["diagnostics"]["people_clustered"]),
            "peopleWithUnresolvedIdentity": int((~members.identityResolved).sum()),
            "candidateCycles": int(manifest["diagnostics"]["democratic_candidate_cycles"]),
            "cyclesScored": int(manifest["diagnostics"]["candidate_cycles_scored"]),
            "cyclesUnscored": int(manifest["diagnostics"]["candidate_cycles_unscored"]),
            "unclustered": records(unclustered.groupby("reason", as_index=False)
                                   .agg(people=("person_id", "size"))),
            "channels": records(evidence_channels(set(person_profiles.person_id)
                                                  | set(unclustered.person_id))),
        },
        "diagnostics": {
            "clusters": int(manifest["configuration"]["selected_k"]),
            "features": len(families),
            "silhouette": float(manifest["diagnostics"]["silhouette"]),
            "bootstrapAri": float(manifest["diagnostics"]["bootstrap_ari_mean"]),
            "bootstrapAriP10": float(manifest["diagnostics"]["bootstrap_ari_p10"]),
            "selection": records(diagnostics),
        },
        "sensitivity": [
            {"test": "Resampling stability",
             "statistic": float(manifest["diagnostics"]["bootstrap_ari_mean"]),
             "reading": "Membership recurs under bootstrap resampling."},
            {"test": "Evidence threshold (≥4 of 8 families)",
             "statistic": float(sensitivity.threshold_ari),
             "reading": f"Robust on the {int(sensitivity.threshold_people)} people with fuller records."},
            {"test": "Imputation (KNN vs median)", "statistic": float(sensitivity.knn_vs_median_ari),
             "reading": "Sensitive: members near boundaries move."},
            {"test": "Missingness structure", "statistic": float(sensitivity.position_vs_missingness_ari),
             "reading": "Low value is good: groups are not an artefact of who has evidence."},
            {"test": "Legislative evidence only", "statistic": float(sensitivity.all_source_vs_legislative_only_ari),
             "reading": "Sensitive: questionnaire and endorsement evidence shapes the partition."},
            {"test": "Era-normalized features", "statistic": float(sensitivity.era_normalized_ari),
             "reading": "Sensitive: era level explains much of the partition."},
            {"test": "Issue selection (families vs families+axes)", "statistic": float(sensitivity.families_vs_augmented_ari),
             "reading": "Sensitive: excluded primitive axes would regroup members."},
        ],
        "repeatedPeopleShare": float(sensitivity.repeated_people_share),
    }


def build() -> str:
    data = json.dumps(payload(), separators=(",", ":"), allow_nan=False)
    assets = ROOT / "dashboard"
    return ((assets / "ideology_page.html").read_text(encoding="utf-8")
            .replace("__COMPONENTS_CSS__", (assets / "site_components.css").read_text(encoding="utf-8"))
            .replace("__DATA__", data)
            .replace("__JS__", (assets / "ideology_page.js").read_text(encoding="utf-8")))


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
