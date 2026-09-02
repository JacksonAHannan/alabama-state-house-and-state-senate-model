"""Build the three-group ideology and caucus analysis page.

This is the current public-facing analysis contract.  It treats the empirical
clusters as descriptive regions in issue space, keeps WAR separate from raw
ticket overperformance, and labels the Shor–McCarty analysis as a distinct
continuous measurement.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.build_caucus_analysis_page import payload as cluster_payload
    from scripts.build_ideology_thesis_page import payload as ideology_payload
except ModuleNotFoundError:
    from build_caucus_analysis_page import payload as cluster_payload
    from build_ideology_thesis_page import payload as ideology_payload


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "site" / "ideology-performance.html"
HISTORICAL_WAR = (
    ROOT / "data" / "processed" / "war" / "alabama_historical_war_v1"
    / "candidate_cycle_war.csv"
)
EVIDENCE = ROOT / "data" / "processed" / "ideology" / "candidate_position_evidence_v3_all_sources.csv"
DISPLAY_NAME_ALIASES = ROOT / "data" / "manual" / "ideology" / "candidate_research_aliases.csv"
SOURCE_ID_PATTERN = re.compile(r"^[A-Z]{3}\d{3}[A-Z]{4,}$")

TRADITIONALIST = "Traditionalist-populist Democrats"
BRIDGE = "Bridge-coalition Democrats"
PROGRESSIVE = "Progressive-modern Democrats"
GROUPS = [TRADITIONALIST, BRIDGE, PROGRESSIVE]
PREFIX = "primitive_conservative_"
OUTCOMES = [
    "candidate_cycle_war",
    "candidate_federal_overperformance",
    "candidate_presidential_overperformance",
]


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


def person_clustered_contrasts(frame: pd.DataFrame, outcome: str) -> list[dict]:
    """Estimate bridge/progressive and traditionalist/progressive differences.

    Each estimate uses only cycle-by-chamber cells containing both the focal
    group and progressive-modern reference group. Fixed effects remove broad
    election-context differences. Candidate identity clusters uncertainty for
    repeat appearances.
    """
    base = frame[
        frame.party.eq("D") & frame.cluster_label.isin(GROUPS) & frame[outcome].notna()
    ].copy()
    rows = []
    base["stratum"] = base.cycle.astype(str) + "-" + base.chamber.astype(str)
    for focal in [TRADITIONALIST, BRIDGE]:
        data = base[base.cluster_label.isin([focal, PROGRESSIVE])].copy()
        supported = data.groupby("stratum").cluster_label.nunique()
        data = data[data.stratum.isin(supported[supported.eq(2)].index)].copy()
        if data.empty:
            continue
        data["focal_i"] = data.cluster_label.eq(focal).astype(float)
        fixed = pd.get_dummies(data.stratum, prefix="context", drop_first=True, dtype=float)
        design_frame = pd.concat([
            pd.DataFrame({"intercept": 1.0}, index=data.index),
            data[["focal_i"]], fixed,
        ], axis=1)
        design = design_frame.to_numpy(float)
        response = data[outcome].to_numpy(float)
        bread = np.linalg.pinv(design.T @ design)
        beta = bread @ design.T @ response
        residual = response - design @ beta
        identities = data.person_id.where(
            data.person_id.notna() & data.person_id.astype(str).str.strip().ne(""),
            data.canonical_candidate_id,
        ).astype(str)
        meat = np.zeros((design.shape[1], design.shape[1]))
        identity_array = identities.to_numpy()
        for identity in identities.unique():
            index = np.flatnonzero(identity_array == identity)
            score = design[index].T @ residual[index]
            meat += np.outer(score, score)
        people = int(identities.nunique())
        rank = int(np.linalg.matrix_rank(design))
        correction = (people / (people - 1)) * ((len(data) - 1) / (len(data) - rank))
        covariance = correction * bread @ meat @ bread
        position = design_frame.columns.get_loc("focal_i")
        estimate = float(beta[position])
        standard_error = float(np.sqrt(max(0.0, covariance[position, position])))
        rows.append({
            "outcome": outcome,
            "group": focal,
            "reference_group": PROGRESSIVE,
            "difference": estimate,
            "standard_error": standard_error,
            "ci_low": estimate - 1.96 * standard_error,
            "ci_high": estimate + 1.96 * standard_error,
            "n": int(len(data)),
            "people": people,
            "strata": int(data.stratum.nunique()),
            "method": "cycle_chamber_fixed_effects_person_clustered_se",
        })
    return rows


def group_summary(members: pd.DataFrame) -> pd.DataFrame:
    rows = []
    democrats = members[members.party.eq("D")]
    for group in GROUPS:
        sample = democrats[democrats.cluster_label.eq(group)]
        for outcome in OUTCOMES:
            values = pd.to_numeric(sample[outcome], errors="coerce").dropna()
            se = values.std(ddof=1) / np.sqrt(len(values)) if len(values) > 1 else np.nan
            rows.append({
                "group": group, "outcome": outcome, "n": int(len(values)),
                "people": int(sample.loc[values.index, "person_id"].nunique()),
                "mean": float(values.mean()), "median": float(values.median()),
                "standard_error": float(se),
                "ci_low": float(values.mean() - 1.96 * se),
                "ci_high": float(values.mean() + 1.96 * se),
            })
    return pd.DataFrame(rows)


def profile_rows(profiles: pd.DataFrame, issue_meta: dict[str, dict]) -> pd.DataFrame:
    democratic = profiles[profiles.party.eq("D")].set_index("cluster_label")
    rows = []
    for column in [column for column in democratic if column.startswith(PREFIX)]:
        values = {group: democratic.at[group, column] for group in GROUPS}
        if any(pd.isna(value) for value in values.values()):
            continue
        issue = column.removeprefix(PREFIX)
        rows.append({
            "issue": issue,
            "label": issue_meta.get(issue, {}).get("label", issue.replace("_", " ").title()),
            "traditionalist": float(values[TRADITIONALIST]),
            "bridge": float(values[BRIDGE]),
            "progressive": float(values[PROGRESSIVE]),
            "range": float(max(values.values()) - min(values.values())),
        })
    return pd.DataFrame(rows).sort_values("range", ascending=False)


def cycle_performance(members: pd.DataFrame) -> pd.DataFrame:
    rows = []
    democrats = members[members.party.eq("D")]
    for (cycle, group), sample in democrats.groupby(["cycle", "cluster_label"]):
        for outcome in OUTCOMES:
            values = pd.to_numeric(sample[outcome], errors="coerce").dropna()
            if values.empty:
                continue
            rows.append({
                "cycle": int(cycle), "group": group, "outcome": outcome,
                "n": int(len(values)), "mean": float(values.mean()),
                "standard_error": float(values.std(ddof=1) / np.sqrt(len(values)))
                if len(values) > 1 else None,
            })
    return pd.DataFrame(rows)


def representative_cases(members: pd.DataFrame) -> pd.DataFrame:
    rows = []
    democrats = members[members.party.eq("D")]
    for group in GROUPS:
        sample = democrats[
            democrats.cluster_label.eq(group)
            & democrats.candidate_cycle_war.notna()
            & democrats.candidate_federal_overperformance.notna()
        ].copy()
        if sample.empty:
            continue
        targets = [
            ("Near group median WAR", sample.candidate_cycle_war.median(), "candidate_cycle_war"),
            ("Upper-decile federal overperformance", sample.candidate_federal_overperformance.quantile(.90),
             "candidate_federal_overperformance"),
        ]
        for kind, target, field in targets:
            row = sample.loc[(sample[field] - target).abs().idxmin()]
            rows.append({
                "kind": kind, "group": group,
                "canonical_candidate_id": row.canonical_candidate_id,
                "name": row.canonical_name, "cycle": int(row.cycle),
                "chamber": row.chamber, "district": int(row.district),
                "candidate_cycle_war": float(row.candidate_cycle_war),
                "candidate_federal_overperformance": float(row.candidate_federal_overperformance),
                "candidate_presidential_overperformance": float(row.candidate_presidential_overperformance)
                if pd.notna(row.candidate_presidential_overperformance) else np.nan,
                "dimensions": int(row.cluster_dimensions_observed),
            })
    return pd.DataFrame(rows)


def source_coverage() -> pd.DataFrame:
    evidence = pd.read_csv(EVIDENCE, low_memory=False)
    categories = np.select([
        evidence.source_type.eq("legislative_vote"),
        evidence.source_type.eq("candidate_questionnaire"),
        evidence.source_type.isin(["interest_group_rating", "interest_group_endorsement"]),
        evidence.source_type.isin(["bill_sponsorship", "legislative_cosponsorship", "legislative_proposal"]),
    ], [
        "Recorded legislative votes", "Candidate questionnaires",
        "Interest-group evidence", "Sponsorship and proposals",
    ], default="Campaign and public-position evidence")
    evidence["source_category"] = categories
    return (evidence.groupby("source_category", as_index=False)
            .agg(evidence_rows=("evidence_id", "size"),
                 candidate_cycles=("canonical_candidate_id", "nunique"),
                 people=("person_id", "nunique"),
                 issue_axes=("primitive_axis", "nunique"))
            .sort_values("evidence_rows", ascending=False))


def absolute_era_war(members: pd.DataFrame, ideology: dict) -> pd.DataFrame:
    """Re-estimate the descriptive ideology slope with residual WAR as outcome.

    The earlier page inherited slopes fit to the superseded pooled candidate
    effect.  This fit uses candidate-cycle race-residual WAR, cycle and chamber
    fixed effects, and person-clustered uncertainty within each displayed era.
    """
    shor = pd.DataFrame(ideology["shorPoints"])[
        ["canonical_candidate_id", "absolute_conservatism_z"]
    ].drop_duplicates("canonical_candidate_id")
    frame = members.merge(
        shor, on="canonical_candidate_id", how="left", validate="one_to_one"
    )
    rows = []
    for era_name in ("pre_2008", "2008_2014", "post_2016"):
        sample = frame[
            frame.party.eq("D")
            & frame.era.eq(era_name)
            & frame.candidate_cycle_war.notna()
            & frame.absolute_conservatism_z.notna()
        ].copy()
        result = {
            "sample": f"D:{era_name}",
            "outcome": "candidate_cycle_war",
            "term": "absolute_conservatism_z",
            "n": int(len(sample)),
            "status": "not_estimated",
            "coefficient": np.nan,
            "standard_error": np.nan,
            "ci_low": np.nan,
            "ci_high": np.nan,
            "method": "cycle_chamber_fixed_effects_person_clustered_se",
        }
        if len(sample) < 3:
            rows.append(result)
            continue
        fixed = pd.get_dummies(
            sample.cycle.astype(str) + "-" + sample.chamber.astype(str),
            prefix="context", drop_first=True, dtype=float,
        )
        design_frame = pd.concat([
            pd.DataFrame({"intercept": 1.0}, index=sample.index),
            sample[["absolute_conservatism_z"]], fixed,
        ], axis=1)
        design = design_frame.to_numpy(float)
        response = sample.candidate_cycle_war.to_numpy(float)
        bread = np.linalg.pinv(design.T @ design)
        beta = bread @ design.T @ response
        residual = response - design @ beta
        identities = sample.person_id.where(
            sample.person_id.notna() & sample.person_id.astype(str).str.strip().ne(""),
            sample.canonical_candidate_id,
        ).astype(str)
        people = int(identities.nunique())
        rank = int(np.linalg.matrix_rank(design))
        if people <= 1 or len(sample) <= rank:
            rows.append(result)
            continue
        meat = np.zeros((design.shape[1], design.shape[1]))
        identity_array = identities.to_numpy()
        for identity in identities.unique():
            index = np.flatnonzero(identity_array == identity)
            score = design[index].T @ residual[index]
            meat += np.outer(score, score)
        correction = (people / (people - 1)) * ((len(sample) - 1) / (len(sample) - rank))
        covariance = correction * bread @ meat @ bread
        position = design_frame.columns.get_loc("absolute_conservatism_z")
        estimate = float(beta[position])
        standard_error = float(np.sqrt(max(0.0, covariance[position, position])))
        result.update({
            "status": "estimated",
            "coefficient": estimate,
            "standard_error": standard_error,
            "ci_low": estimate - 1.96 * standard_error,
            "ci_high": estimate + 1.96 * standard_error,
            "people": people,
        })
        rows.append(result)
    return pd.DataFrame(rows)


@lru_cache(maxsize=1)
def payload() -> dict:
    ideology = ideology_payload()
    clusters = cluster_payload()
    members = pd.DataFrame(clusters["members"])
    war = pd.read_csv(
        HISTORICAL_WAR,
        usecols=["canonical_candidate_id", "candidate_cycle_war", "scoring_scope"],
    ).rename(columns={"scoring_scope": "war_scoring_scope"})
    if war.canonical_candidate_id.duplicated().any():
        raise ValueError("Historical WAR output has duplicate candidate-cycle IDs")
    members = (members.drop(columns=["candidate_cmo", "candidate_quality_index",
                                     "candidate_quality_residual", "candidate_cycle_war",
                                     "war_scoring_scope"], errors="ignore")
               .merge(war, on="canonical_candidate_id", how="left", validate="one_to_one"))
    if members.candidate_cycle_war.isna().any():
        raise ValueError("Every clustered candidate-cycle must have historical residual WAR")
    aliases = pd.read_csv(DISPLAY_NAME_ALIASES, low_memory=False)
    aliases = aliases[aliases.identity_status.astype(str).str.startswith("verified_")][
        ["canonical_candidate_id", "research_name"]
    ].copy()
    if aliases.canonical_candidate_id.duplicated().any():
        raise ValueError("Verified public-name adjudications are not unique")
    members["source_candidate_name"] = members.canonical_name
    members = members.merge(
        aliases.rename(columns={"research_name": "verified_research_name"}),
        on="canonical_candidate_id", how="left", validate="one_to_one",
    )
    identifier_like = members.source_candidate_name.astype(str).str.fullmatch(
        SOURCE_ID_PATTERN, na=False
    )
    unresolved = identifier_like & members.verified_research_name.isna()
    if unresolved.any():
        names = members.loc[
            unresolved, ["canonical_candidate_id", "source_candidate_name"]
        ].to_dict("records")
        raise ValueError(f"Unresolved public candidate source IDs: {names[:5]}")
    members["canonical_name"] = members.source_candidate_name.where(
        ~identifier_like, members.verified_research_name
    )
    members["display_name_source"] = np.where(
        identifier_like,
        "verified_candidate_research_alias",
        "canonical_alabama_election_candidate",
    )
    members = members.drop(columns="verified_research_name")
    committee_like = members.canonical_name.astype(str).str.contains(
        r"\b(?:committee|campaign|friends of|elect|pac)\b", case=False, regex=True
    )
    if committee_like.any():
        names = members.loc[committee_like, "canonical_name"].tolist()
        raise ValueError(f"Committee-like public candidate names are prohibited: {names[:5]}")
    if members.canonical_name.astype(str).str.fullmatch(SOURCE_ID_PATTERN, na=False).any():
        raise ValueError("Identifier-shaped public candidate names are prohibited")
    members = members.drop(columns="source_candidate_name")
    if set(members.loc[members.party.eq("D"), "cluster_label"]) != set(GROUPS):
        raise ValueError("Current Democratic cluster labels do not match the three-group contract")
    if members.era.astype(str).str.lower().eq("undefined").any():
        raise ValueError("Undefined era in current cluster membership")

    profiles = pd.DataFrame(clusters["profiles"])
    issue_meta = {row["key"]: row for row in ideology["issueMeta"]}
    transition = (members[members.party.eq("D")]
                  .groupby(["cycle", "cluster_label"], as_index=False)
                  .agg(n=("canonical_candidate_id", "size")))
    transition["share"] = transition.n / transition.groupby("cycle").n.transform("sum")
    diagnostics = pd.DataFrame(clusters["diagnostics"])
    dem_diagnostics = diagnostics[diagnostics.party.eq("D")].iloc[0]
    era = absolute_era_war(members, ideology)

    result = {
        "schemaVersion": 3,
        "groups": GROUPS,
        "members": records(members),
        "issues": clusters["issues"],
        "issueMeta": ideology["issueMeta"],
        "constellation": clusters["constellation"],
        "groupSummary": records(group_summary(members)),
        "contrasts": records(pd.DataFrame([
            row for outcome in OUTCOMES for row in person_clustered_contrasts(members, outcome)
        ])),
        "transition": records(transition),
        "profiles": records(profile_rows(profiles, issue_meta)),
        "cyclePerformance": records(cycle_performance(members)),
        "cases": records(representative_cases(members)),
        "absoluteEra": records(era),
        "sourceCoverage": records(source_coverage()),
        "diagnostics": {
            "clusters": int(dem_diagnostics.clusters),
            "features": int(dem_diagnostics.features),
            "silhouette": float(dem_diagnostics.silhouette),
            "bootstrap_ari_mean": float(dem_diagnostics.bootstrap_ari_mean),
            "candidate_cycles": int(members.party.eq("D").sum()),
            "people": int(members.loc[members.party.eq("D"), "person_id"].nunique()),
        },
        "warMethodology": {
            "estimand": "race_residual_margin_points",
            "formula": "actual_legislative_minus_ticket_gap - fitted_structural_expected_gap",
            "historical_scope": "post2016_southern_model_backcast",
            "modern_scope": "published_alabama_same_cycle_residual",
            "pooled_candidate_effect": False,
            "fundraising_in_war": False,
            "candidate_name_source": "canonical_election_identity_with_verified_source_id_adjudication",
        },
    }
    return result


def build() -> str:
    data = json.dumps(payload(), separators=(",", ":"), allow_nan=False)
    template = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Alabama Democratic ideology, caucus groupings, and electoral performance"><link rel="icon" href="data:"><title>Ideology and caucuses · Jackson Hannan</title><style>
:root{--ink:#25191d;--muted:#695b60;--line:#b9aaaf;--paper:#fff;--blue:#b9d9ec;--blue-dark:#356f91;--ox:#651c2c;--ox-dark:#42101b;--gold:#a87418;--pale:#eef6fa;--wash:#f8f3f4}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--blue);color:var(--ink);font:15px/1.52 Arial,Helvetica,sans-serif}button,select,input{font:inherit}header,footer{background:var(--ox);color:#fff}.mast,.shell{width:min(1200px,calc(100% - 38px));margin:auto}.mast{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:17px 0}.brand{font:bold 23px Georgia,serif}.tag,.kicker{font:bold 10px Arial,sans-serif;letter-spacing:1px;text-transform:uppercase}.tag{color:#eadde1}.nav{display:flex;gap:16px;flex-wrap:wrap}.nav a,footer a{color:#fff;text-decoration:none;font-size:11px}.nav a[aria-current=page]{border-bottom:2px solid #fff;padding-bottom:3px}.shell{background:var(--paper);padding:48px clamp(18px,4vw,50px) 88px;border-left:1px solid #91b5c9;border-right:1px solid #91b5c9}.hero{max-width:900px}.kicker{color:var(--ox)}h1{font:bold clamp(39px,6vw,68px)/1.02 Georgia,serif;letter-spacing:-1.8px;margin:9px 0 18px}.dek{font:20px/1.5 Georgia,serif;margin:0}.finding{border:1px solid var(--ox);border-left:8px solid var(--ox);background:#fff9fa;padding:17px 19px;margin:25px 0 34px;font:16px/1.55 Georgia,serif}.contents{display:flex;gap:7px;flex-wrap:wrap;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px 0;margin:0 0 56px}.contents a{background:var(--wash);color:var(--ox);padding:5px 8px;text-decoration:none;font:bold 10px Arial}section{margin:70px 0;scroll-margin-top:18px}.section-head{max-width:850px;margin-bottom:24px}.section-head h2{font:bold 32px/1.12 Georgia,serif;margin:6px 0 9px}.section-head p{margin:0;color:#4e4246}.panel{border:1px solid var(--line);background:#fff}.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap;padding:12px 14px;border-bottom:1px solid var(--line);background:var(--wash)}.controls label{font:bold 9px Arial;text-transform:uppercase;letter-spacing:.65px;color:var(--muted)}select,input{display:block;margin-top:4px;border:1px solid #8f7e84;background:#fff;color:var(--ink);padding:8px 30px 8px 9px}.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--muted)}.legend i{display:inline-block;width:11px;height:11px;margin-right:5px;vertical-align:-1px}.trad{background:var(--ox)}.bridge{background:var(--gold)}.prog{background:var(--blue-dark)}.group-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}.group-card{background:#fff;padding:19px;border-top:6px solid var(--ox)}.group-card.bridge-card{border-top-color:var(--gold)}.group-card.prog-card{border-top-color:var(--blue-dark)}.group-card h3{font:bold 20px Georgia,serif;margin:0 0 5px}.group-card .count{color:var(--muted);font-size:11px}.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:15px}.metric-grid div{background:var(--wash);padding:9px}.metric-grid b{display:block;font:19px Georgia,serif}.metric-grid span{display:block;font-size:9px;color:var(--muted)}.contrast-list{padding:8px 17px 17px}.contrast-row{display:grid;grid-template-columns:220px minmax(260px,1fr) 180px;gap:15px;align-items:center;padding:14px 0;border-top:1px solid #e2d9dc}.contrast-row:first-child{border:0}.contrast-row h3{font:bold 13px Georgia,serif;margin:0}.contrast-track,.era-track{height:28px;position:relative;background:linear-gradient(90deg,#e8f3f9,#fff 50%,#f7e8eb)}.contrast-track:after,.era-track:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #76666b}.contrast-ci,.era-ci{position:absolute;top:13px;height:3px}.contrast-point,.era-point{position:absolute;top:8px;width:12px;height:12px;border-radius:50%;transform:translateX(-50%);border:2px solid #fff;box-shadow:0 0 0 1px #53454a}.contrast-value{font-size:10px;color:var(--muted)}.contrast-value b{display:block;font-size:12px;color:var(--ink)}.transition{padding:15px 18px}.transition-row{display:grid;grid-template-columns:56px 1fr 56px;gap:10px;align-items:center;padding:8px 0;border-top:1px solid #e2d9dc}.transition-row:first-child{border:0}.stack{height:26px;display:flex;border:1px solid #8f7d83}.stack span{height:100%;min-width:1px}.transition-row small{text-align:right;color:var(--muted)}.profile{padding:12px 17px}.profile-row{display:grid;grid-template-columns:185px 1fr 65px;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #e2d9dc}.profile-row:first-child{border:0}.profile-track{height:28px;position:relative;background:linear-gradient(90deg,#e4f1f8,#fff 49.5%,#f5e6e9)}.profile-track:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #7e6e73}.profile-dot{position:absolute;top:7px;width:13px;height:13px;border-radius:50%;transform:translateX(-50%);border:2px solid #fff;box-shadow:0 0 0 1px #55484c}.profile-row output{text-align:right;font:bold 11px Arial}.distribution{height:405px;position:relative;margin:20px 35px 47px 125px;border-left:1px solid var(--line);border-bottom:1px solid var(--line);background:repeating-linear-gradient(to right,transparent 0,transparent calc(20% - 1px),#eee 20%)}.zero{position:absolute;top:0;bottom:0;border-left:1px solid #76666b}.lane{position:absolute;left:-118px;width:110px;text-align:right;font-size:10px;transform:translateY(50%)}.performance-dot{position:absolute;width:9px;height:9px;border-radius:50%;border:1px solid #fff;box-shadow:0 0 0 1px #55484c;transform:translate(-50%,50%);opacity:.72;cursor:pointer}.mean-line{position:absolute;width:4px;height:28px;background:var(--ink);transform:translate(-50%,50%)}.axis-label{position:absolute;bottom:-31px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted)}.trend-wrap{padding:15px}.trend-chart,#constellation{display:block;width:100%;height:auto;background:#fbfdfe;border:1px solid var(--line)}.grid{stroke:#dce3e6;stroke-width:1}.axis-text{fill:var(--muted);font:10px Arial}.trend-line{fill:none;stroke-width:3}.trend-point{stroke:#fff;stroke-width:2;cursor:pointer}.issue-layout{display:grid;grid-template-columns:280px 1fr}.issue-copy{background:var(--wash);padding:18px;border-right:1px solid var(--line)}.issue-copy h3{font:bold 22px Georgia,serif;margin:0 0 8px}.issue-copy p{font-size:12px}.poles{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding-top:9px;font:bold 9px Arial;color:var(--muted);text-transform:uppercase}.issue-plot{height:405px;position:relative;margin:20px 28px 47px 70px;border-left:1px solid var(--line);border-bottom:1px solid var(--line);background:linear-gradient(90deg,#e4f1f8,#fff 49.5%,#f5e6e9)}.issue-plot:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #76666b}.coverage{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border-top:1px solid var(--line)}.coverage div{background:#fff;padding:11px}.coverage b{display:block;font:19px Georgia,serif}.coverage span{font-size:9px;color:var(--muted)}.cases{display:grid;grid-template-columns:repeat(3,1fr);gap:11px}.case{border:1px solid var(--line);border-top:5px solid var(--ox);padding:15px;background:#fff}.case.bridge-case{border-top-color:var(--gold)}.case.prog-case{border-top-color:var(--blue-dark)}.case h3{font:bold 19px Georgia,serif;margin:4px 0}.case p{font-size:11px;margin:0}.case .metric-grid{grid-template-columns:repeat(3,1fr)}.constellation-wrap{display:grid;grid-template-columns:minmax(0,1fr) 300px}.constellation-main{padding:15px;border-right:1px solid var(--line)}#constellation .member{stroke:#fff;stroke-width:1.4;cursor:pointer}#constellation .member.selected{stroke:var(--ink);stroke-width:3}.envelope{fill-opacity:.08;stroke-width:2;stroke-dasharray:5 4}.candidate-detail{padding:18px}.candidate-detail h3{font:bold 23px Georgia,serif;margin:0}.candidate-detail .score{font:bold 34px Georgia,serif;color:var(--ox);margin:16px 0}.candidate-detail .score span{display:block;font:9px Arial;color:var(--muted);text-transform:uppercase}.candidate-detail dl{font-size:11px}.candidate-detail dt{float:left;clear:left;color:var(--muted)}.candidate-detail dd{text-align:right;border-bottom:1px solid #e2d9dc;padding:4px 0}.table-wrap{max-height:390px;overflow:auto;border-top:1px solid var(--line)}table{width:100%;border-collapse:collapse;font-size:11px}th{position:sticky;top:0;background:var(--ox);color:#fff;text-align:left;padding:8px}td{padding:8px;border-top:1px solid #e2d9dc}tbody tr{cursor:pointer}tbody tr:hover{background:var(--pale)}.num{text-align:right}.era-list{padding:9px 17px}.era-row{display:grid;grid-template-columns:145px minmax(250px,1fr) 180px;gap:14px;align-items:center;padding:13px 0;border-top:1px solid #e2d9dc}.era-row:first-child{border:0}.era-value{font-size:10px;color:var(--muted)}.era-value b{display:block;color:var(--ink)}.source-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}.source-card{background:#fff;padding:13px}.source-card b{display:block;font:22px Georgia,serif}.source-card span{font-size:10px;color:var(--muted)}.method{border-left:6px solid var(--ox);background:var(--wash);padding:16px 18px;margin:11px 0}.method h3{font:bold 18px Georgia,serif;margin:0 0 6px}.method p{font-size:12px;margin:0}.tip{position:fixed;display:none;z-index:20;pointer-events:none;max-width:290px;background:var(--ox-dark);color:#fff;padding:9px 11px;font-size:11px;box-shadow:0 8px 22px #0004}footer{padding:24px max(20px,calc((100vw - 1160px)/2));font-size:11px}@media(max-width:820px){.mast{align-items:flex-start;flex-direction:column}.group-grid,.cases{grid-template-columns:1fr}.contrast-row,.era-row{grid-template-columns:1fr}.issue-layout,.constellation-wrap{grid-template-columns:1fr}.issue-copy,.constellation-main{border-right:0;border-bottom:1px solid var(--line)}.source-grid{grid-template-columns:1fr 1fr}.profile-row{grid-template-columns:130px 1fr 55px}}@media(max-width:540px){.mast,.shell{width:100%}.mast{padding:14px}.shell{padding:34px 13px 64px;border:0}h1{font-size:39px}.metric-grid{grid-template-columns:1fr}.distribution{margin-left:15px;margin-right:15px}.lane{left:5px;width:auto;background:#fffD;padding:2px 4px;z-index:3}.coverage,.source-grid{grid-template-columns:1fr}.profile-row{grid-template-columns:1fr 50px}.profile-track{grid-column:1/-1}.nav{gap:9px}}
</style></head><body><header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative elections</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="ideology-performance.html" aria-current="page">Ideology &amp; caucuses</a><a href="cmo-methodology.html">Methodology</a></nav></div></header><main class="shell"><div class="hero"><div class="kicker">Historical Democratic ideology and performance</div><h1>Alabama Democratic groupings, 1998–2022</h1><p class="dek">The current issue-position evidence identifies three Democratic regions: traditionalist-populist, bridge-coalition, and progressive-modern. The headline result is race-residual WAR, followed by raw performance against federal and presidential baselines.</p><div class="finding"><b>Headline result:</b> the comparisons below hold election cycle and chamber constant while applying the same residual WAR definition used by the historical race explorer. Raw ticket comparisons remain separate.</div></div><nav class="contents" aria-label="On this page"><a href="#performance">WAR</a><a href="#overview">Groups</a><a href="#transition">Transition</a><a href="#positions">Positions</a><a href="#distribution">Distribution</a><a href="#time">Cycles</a><a href="#issues">Issues</a><a href="#cases">Candidates</a><a href="#candidate-explorer">Similarity map</a><a href="#continuous">Continuous ideology</a><a href="#methods">Methods</a></nav>

<section id="performance"><div class="section-head"><div class="kicker">Headline result</div><h2>WAR relative to progressive-modern candidates</h2><p>WAR is the candidate-oriented race residual in two-party margin points: the actual legislative-minus-ticket gap minus the fitted structural expectation. Each comparison below holds cycle and chamber constant and uses only contexts containing both groups.</p></div><div id="warHeadline" class="war-headline"></div><div class="panel"><div id="contrastList" class="contrast-list"></div></div></section>

<section id="overview"><div class="section-head"><div class="kicker">Three-group summary</div><h2>Composition and supporting performance measures</h2><p>Group means are unadjusted. WAR is listed first. Raw margin overperformance versus federal candidates and versus the previous presidential result are separate ticket-comparison measures, not substitutes for WAR.</p></div><div id="groupGrid" class="group-grid"></div><div class="panel" style="margin-top:18px"><div class="supporting-head"><h3>Adjusted raw ticket comparisons</h3><p>These comparisons use the same pairwise common-context restriction as the headline WAR result, but retain the raw federal and presidential baselines.</p></div><div id="ticketContrastList" class="contrast-list"></div></div></section>

<section id="transition"><div class="section-head"><div class="kicker">Composition</div><h2>The observed Democratic field changed over time</h2><p>Shares include only candidate-cycles with enough issue evidence to enter the clustering analysis.</p></div><div class="panel"><div class="legend" style="padding:13px 18px 0"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="bridge"></i>Bridge coalition</span><span><i class="prog"></i>Progressive-modern</span></div><div id="transitionChart" class="transition"></div></div></section>

<section id="positions"><div class="section-head"><div class="kicker">Group issue profiles</div><h2>Where all three groups differ</h2><p>Dots are group means on conservative-oriented issue axes. The rows are ordered by the largest distance among the three group means.</p></div><div class="panel"><div class="legend" style="padding:13px 17px 0"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="bridge"></i>Bridge coalition</span><span><i class="prog"></i>Progressive-modern</span></div><div id="profileChart" class="profile"></div></div></section>

<section id="distribution"><div class="section-head"><div class="kicker">Candidate distribution</div><h2>Candidate-cycles behind the averages</h2><p>Points show individual observations. Black vertical marks show the selected group means. Residual WAR is the default view.</p></div><div class="panel"><div class="controls"><label>Measure<select id="distributionOutcome"><option value="candidate_cycle_war">Race-residual WAR</option><option value="candidate_federal_overperformance">Raw vs. federal baseline</option><option value="candidate_presidential_overperformance">Raw vs. previous president</option></select></label><label>Era<select id="distributionEra"><option value="all">All eras</option><option value="pre_2008">Before 2008</option><option value="2008_2014">2008–2014</option><option value="post_2016">2016 and later</option></select></label></div><div id="performanceDistribution" class="distribution"><span class="axis-label">Candidate-oriented margin points →</span></div></div></section>

<section id="time"><div class="section-head"><div class="kicker">Election-cycle averages</div><h2>Performance over time</h2><p>Lines connect observed group means by election cycle. Missing points mean that the group had no eligible observation in that year; they are not zeros.</p></div><div class="panel"><div class="controls"><label>Measure<select id="trendOutcome"><option value="candidate_cycle_war">Race-residual WAR</option><option value="candidate_federal_overperformance">Raw vs. federal baseline</option><option value="candidate_presidential_overperformance">Raw vs. previous president</option></select></label><div class="legend"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="bridge"></i>Bridge coalition</span><span><i class="prog"></i>Progressive-modern</span></div></div><div class="trend-wrap"><svg id="trendChart" class="trend-chart" viewBox="0 0 820 410" role="img" aria-label="Group performance by cycle"></svg></div></div></section>

<section id="issues"><div class="section-head"><div class="kicker">Issue-level evidence</div><h2>Position and performance by issue</h2><p>Select an issue, outcome, and era. Colors identify the three groups; horizontal position is the conservative-oriented issue score and vertical position is candidate performance.</p></div><div class="panel"><div class="controls"><label>Issue<select id="issueSelect"></select></label><label>Measure<select id="issueOutcome"><option value="candidate_cycle_war">Race-residual WAR</option><option value="candidate_federal_overperformance">Raw vs. federal baseline</option><option value="candidate_presidential_overperformance">Raw vs. previous president</option></select></label><label>Era<select id="issueEra"><option value="all">All eras</option><option value="pre_2008">Before 2008</option><option value="2008_2014">2008–2014</option><option value="post_2016">2016 and later</option></select></label></div><div class="issue-layout"><aside id="issueCopy" class="issue-copy"></aside><div id="issuePlot" class="issue-plot"></div></div><div id="issueCoverage" class="coverage"></div></div></section>

<section id="cases"><div class="section-head"><div class="kicker">Representative candidate-cycles</div><h2>Typical and high-performing observations from each group</h2><p>Each group contributes one candidate near its median WAR and one near its upper-decile federal overperformance. These are rule-selected examples, not editorial endorsements.</p></div><div id="caseStudies" class="cases"></div></section>

<section id="candidate-explorer"><div class="section-head"><div class="kicker">Similarity map</div><h2>Candidate proximity across all clustering dimensions</h2><p>Nearby points have similar observed issue records. Coordinates are a two-dimensional projection, not individual ideological axes. Envelopes are descriptive and do not imply formal membership boundaries.</p></div><div class="panel"><div class="constellation-wrap"><div class="constellation-main"><svg id="constellation" viewBox="0 0 760 500" role="img" aria-label="Candidate issue-position similarity map"></svg><div class="legend"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="bridge"></i>Bridge coalition</span><span><i class="prog"></i>Progressive-modern</span><span id="constellationCoverage"></span></div></div><aside id="candidateDetail" class="candidate-detail" aria-live="polite"><p>Select a point or table row.</p></aside></div><div class="controls"><label>Search candidates<input id="candidateSearch" type="search" placeholder="Name or district"></label><label>Group<select id="candidateGroup"><option value="all">All groups</option><option value="Traditionalist-populist Democrats">Traditionalist-populist</option><option value="Bridge-coalition Democrats">Bridge coalition</option><option value="Progressive-modern Democrats">Progressive-modern</option></select></label></div><div class="table-wrap"><table><thead><tr><th>Candidate</th><th>Race</th><th>Group</th><th class="num">WAR</th><th class="num">Vs. federal</th><th class="num">Vs. president</th></tr></thead><tbody id="candidateRows"></tbody></table></div></div></section>

<section id="continuous"><div class="section-head"><div class="kicker">Separate continuous measurement</div><h2>WAR and absolute Shor–McCarty ideology by era</h2><p>This is not a cluster comparison. Each row estimates the WAR change associated with a one-standard-deviation move toward the conservative end of the nationally comparable Shor–McCarty scale.</p></div><div class="panel"><div id="eraEvidence" class="era-list"></div></div></section>

<section id="methods"><div class="section-head"><div class="kicker">Coverage and interpretation</div><h2>Data and method</h2></div><div id="sourceGrid" class="source-grid"></div><div class="method"><h3>WAR definition</h3><p>The residual framing follows <a href="https://split-ticket.org/2025/08/15/deconstructing-war/">Split Ticket's WAR methodology</a>; this Alabama implementation and its estimates are independent. Race WAR = actual legislative-minus-ticket gap minus the fitted structural expected gap. Democratic WAR is the race residual and Republican WAR is its exact negative. The 1998–2014 observations shown here use a backward application of the model trained only on post-2016 Southern races; 2018 and 2022 retain the published same-cycle Alabama residuals. No pooled individual effect, fundraising term, or ideology term enters WAR.</p></div><div class="method"><h3>Group construction</h3><p id="clusterMethod"></p></div><div class="method"><h3>Performance attachment</h3><p>Election performance was not used to create the groups. WAR, incumbency, fundraising, demographics, district partisanship, and era are attached only after group assignment. Adjusted comparisons use cycle-and-chamber fixed effects and person-clustered uncertainty.</p></div><div class="method"><h3>Limits</h3><p>A race residual cannot uniquely distinguish candidate strength from opponent weakness or omitted local conditions. Historical backcasts extrapolate a modern relationship. Evidence is more available for officeholders and is not missing at random; the analysis is descriptive and does not prove that an issue caused electoral performance.</p></div></section></main><div id="tip" class="tip"></div><footer>Research and model by Jackson Hannan · <a href="cmo.html">Alabama WAR</a> · <a href="cmo-methodology.html">Methodology</a></footer>

<script>const DATA=__DATA__;
const TRAD='Traditionalist-populist Democrats',BRIDGE='Bridge-coalition Democrats',PROG='Progressive-modern Democrats',GROUPS=[TRAD,BRIDGE,PROG];
const COLORS={[TRAD]:'#651c2c',[BRIDGE]:'#a87418',[PROG]:'#356f91'};
const SHORT={[TRAD]:'Traditionalist-populist',[BRIDGE]:'Bridge coalition',[PROG]:'Progressive-modern'};
const OUTCOME_LABELS={candidate_cycle_war:'Race-residual WAR',candidate_federal_overperformance:'Raw vs. federal baseline',candidate_presidential_overperformance:'Raw vs. previous president'};
const $=s=>document.querySelector(s),fmt=v=>v==null||!Number.isFinite(+v)?'—':`${+v>=0?'+':''}${(+v).toFixed(1)}`,esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function colorClass(g){return g===TRAD?'trad':g===BRIDGE?'bridge':'prog'}
function cardClass(g){return g===BRIDGE?'bridge-card':g===PROG?'prog-card':''}
function hover(node,html){node.onpointerenter=e=>{const t=$('#tip');t.innerHTML=html;t.style.display='block';moveTip(e)};node.onpointermove=moveTip;node.onpointerleave=()=>$('#tip').style.display='none'}
function moveTip(e){const t=$('#tip'),pad=14;t.style.left=Math.min(innerWidth-t.offsetWidth-pad,e.clientX+14)+'px';t.style.top=Math.min(innerHeight-t.offsetHeight-pad,e.clientY+14)+'px'}
function eraLabel(e){return e==='pre_2008'?'Before 2008':e==='2008_2014'?'2008–2014':'2016 and later'}

function renderGroups(){const by=(g,o)=>DATA.groupSummary.find(x=>x.group===g&&x.outcome===o);$('#groupGrid').innerHTML=GROUPS.map(g=>{const war=by(g,'candidate_cycle_war'),fed=by(g,'candidate_federal_overperformance'),pres=by(g,'candidate_presidential_overperformance');return `<article class="group-card ${cardClass(g)}"><h3>${SHORT[g]}</h3><div class="count">${war.n} candidate-cycles · ${war.people} people</div><div class="metric-grid"><div><b>${fmt(war.mean)}</b><span>Mean residual WAR</span></div><div><b>${fmt(fed.mean)}</b><span>Mean vs. federal</span></div><div><b>${fmt(pres.mean)}</b><span>Mean vs. president</span></div></div></article>`}).join('')}

function contrastMarkup(rows){const bounds=rows.flatMap(x=>[x.ci_low,x.ci_high]).filter(Number.isFinite),limit=Math.max(10,Math.ceil(Math.max(...bounds.map(Math.abs),1)/5)*5),left=v=>5+90*(v+limit)/(2*limit);return rows.map(r=>`<div class="contrast-row"><h3>${esc(SHORT[r.group])}<br><small>${esc(OUTCOME_LABELS[r.outcome])}</small></h3><div class="contrast-track" role="img" aria-label="${esc(SHORT[r.group])} versus progressive-modern, ${fmt(r.difference)}, interval ${fmt(r.ci_low)} to ${fmt(r.ci_high)}"><i class="contrast-ci" style="left:${left(r.ci_low)}%;width:${left(r.ci_high)-left(r.ci_low)}%;background:${COLORS[r.group]}"></i><i class="contrast-point" style="left:${left(r.difference)}%;background:${COLORS[r.group]}"></i></div><div class="contrast-value"><b>${fmt(r.difference)} vs. progressive-modern</b><span>95% interval ${fmt(r.ci_low)} to ${fmt(r.ci_high)} · n=${r.n}; ${r.strata} contexts</span></div></div>`).join('')}
function renderWarHeadline(){const rows=DATA.contrasts.filter(r=>r.outcome==='candidate_cycle_war');$('#warHeadline').innerHTML=rows.map(r=>`<article class="war-card ${cardClass(r.group)}"><div class="war-number">${fmt(r.difference)}</div><h3>${esc(SHORT[r.group])} residual WAR</h3><p>Compared with progressive-modern Democrats in ${r.strata} common cycle/chamber contexts. 95% interval ${fmt(r.ci_low)} to ${fmt(r.ci_high)}; n=${r.n}.</p></article>`).join('')}
function renderContrasts(){const war=DATA.contrasts.filter(r=>r.outcome==='candidate_cycle_war'),tickets=DATA.contrasts.filter(r=>r.outcome!=='candidate_cycle_war');$('#contrastList').innerHTML=contrastMarkup(war);$('#ticketContrastList').innerHTML=contrastMarkup(tickets)}

function renderTransition(){const cycles=[...new Set(DATA.transition.map(x=>x.cycle))].sort((a,b)=>a-b);$('#transitionChart').innerHTML=cycles.map(c=>{const rows=DATA.transition.filter(x=>x.cycle===c),total=rows.reduce((s,x)=>s+x.n,0);return `<div class="transition-row"><strong>${c}</strong><div class="stack">${GROUPS.map(g=>{const r=rows.find(x=>x.cluster_label===g),n=r?.n||0;return `<span style="width:${total?100*n/total:0}%;background:${COLORS[g]}" title="${SHORT[g]}: ${n} of ${total}"></span>`}).join('')}</div><small>n=${total}</small></div>`}).join('')}

function renderProfiles(){const rows=DATA.profiles.slice(0,16),left=v=>5+90*(v+1)/2;$('#profileChart').innerHTML=rows.map(r=>`<div class="profile-row"><label>${esc(r.label)}</label><div class="profile-track">${[[TRAD,r.traditionalist],[BRIDGE,r.bridge],[PROG,r.progressive]].map(([g,v])=>`<i class="profile-dot" style="left:${left(v)}%;background:${COLORS[g]}" title="${SHORT[g]} ${fmt(v)}"></i>`).join('')}</div><output>range ${r.range.toFixed(2)}</output></div>`).join('')}

function renderDistribution(){const outcome=$('#distributionOutcome').value,era=$('#distributionEra').value,box=$('#performanceDistribution');box.querySelectorAll(':scope > :not(.axis-label)').forEach(x=>x.remove());const rows=DATA.members.filter(x=>x.party==='D'&&(era==='all'||x.era===era)&&x[outcome]!=null),values=rows.map(x=>+x[outcome]),limit=Math.max(20,Math.ceil(Math.max(...values.map(Math.abs),1)/10)*10),left=v=>5+90*(v+limit)/(2*limit);const zero=document.createElement('i');zero.className='zero';zero.style.left=left(0)+'%';box.appendChild(zero);GROUPS.forEach((g,i)=>{const lane=79-i*29,tag=document.createElement('span');tag.className='lane';tag.style.bottom=lane+'%';tag.textContent=SHORT[g];box.appendChild(tag);const group=rows.filter(x=>x.cluster_label===g);group.forEach((d,j)=>{const dot=document.createElement('button');dot.type='button';dot.className='performance-dot';dot.style.left=left(d[outcome])+'%';dot.style.bottom=`calc(${lane}% + ${(j%9-4)*3}px)`;dot.style.background=COLORS[g];dot.setAttribute('aria-label',`${d.canonical_name}, ${OUTCOME_LABELS[outcome]} ${fmt(d[outcome])}`);hover(dot,`<b>${esc(d.canonical_name)}</b><br>${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}<br>${esc(SHORT[g])}<br>${esc(OUTCOME_LABELS[outcome])}: ${fmt(d[outcome])}`);box.appendChild(dot)});if(group.length){const mean=group.reduce((s,x)=>s+(+x[outcome]),0)/group.length,mark=document.createElement('i');mark.className='mean-line';mark.style.left=left(mean)+'%';mark.style.bottom=lane+'%';mark.title=`${SHORT[g]} mean ${fmt(mean)}`;box.appendChild(mark)}})}

function renderTrend(){const outcome=$('#trendOutcome').value,rows=DATA.cyclePerformance.filter(x=>x.outcome===outcome),cycles=[...new Set(DATA.transition.map(x=>x.cycle))].sort((a,b)=>a-b),values=rows.map(x=>+x.mean),limit=Math.max(10,Math.ceil(Math.max(...values.map(Math.abs),1)/10)*10),x=c=>70+(c-cycles[0])/(cycles.at(-1)-cycles[0])*700,y=v=>350-(v+limit)/(2*limit)*300,svg=$('#trendChart');svg.innerHTML='';cycles.forEach(c=>svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="${x(c)}" y1="40" x2="${x(c)}" y2="350"/><text class="axis-text" x="${x(c)}" y="372" text-anchor="middle">${c}</text>`));[-limit,-limit/2,0,limit/2,limit].forEach(v=>svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="70" y1="${y(v)}" x2="770" y2="${y(v)}"/><text class="axis-text" x="61" y="${y(v)+3}" text-anchor="end">${fmt(v)}</text>`));GROUPS.forEach(g=>{const points=rows.filter(r=>r.group===g).sort((a,b)=>a.cycle-b.cycle);if(!points.length)return;svg.insertAdjacentHTML('beforeend',`<path class="trend-line" stroke="${COLORS[g]}" d="${points.map((p,i)=>`${i?'L':'M'}${x(p.cycle)},${y(p.mean)}`).join(' ')}"/>`);points.forEach(p=>{const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('class','trend-point');circle.setAttribute('cx',x(p.cycle));circle.setAttribute('cy',y(p.mean));circle.setAttribute('r',5+Math.min(5,p.n/5));circle.setAttribute('fill',COLORS[g]);hover(circle,`<b>${SHORT[g]}</b><br>${p.cycle}<br>${OUTCOME_LABELS[outcome]}: ${fmt(p.mean)}<br>n=${p.n}`);svg.appendChild(circle)})})}

function initIssues(){const preferred=['gun_access','civil_social_liberty','market_governance','criminal_punishment','abortion_access','racial_civil_rights'];const issues=DATA.issues.slice().sort((a,b)=>(preferred.indexOf(a.key)<0?99:preferred.indexOf(a.key))-(preferred.indexOf(b.key)<0?99:preferred.indexOf(b.key))||a.label.localeCompare(b.label));$('#issueSelect').innerHTML=issues.map(x=>`<option value="${x.key}">${esc(x.label)}</option>`).join('')}
function renderIssue(){const issue=$('#issueSelect').value,outcome=$('#issueOutcome').value,era=$('#issueEra').value,meta=DATA.issueMeta.find(x=>x.key===issue)||{label:issue,liberal:'Liberal-coded',conservative:'Conservative-coded',description:''},field='primitive_conservative_'+issue,box=$('#issuePlot');box.querySelectorAll('.performance-dot,.zero').forEach(x=>x.remove());const rows=DATA.members.filter(x=>x.party==='D'&&(era==='all'||x.era===era)&&x[field]!=null&&x[outcome]!=null),values=rows.map(x=>+x[outcome]),limit=Math.max(15,Math.ceil(Math.max(...values.map(Math.abs),1)/10)*10),left=v=>5+90*(v+1)/2,bottom=v=>5+90*(v+limit)/(2*limit);$('#issueCopy').innerHTML=`<h3>${esc(meta.label)}</h3><p>${esc(meta.description)}</p><div class="poles"><span>${esc(meta.liberal)}</span><span>${esc(meta.conservative)}</span></div>`;rows.forEach(d=>{const dot=document.createElement('button');dot.type='button';dot.className='performance-dot';dot.style.left=left(+d[field])+'%';dot.style.bottom=bottom(+d[outcome])+'%';dot.style.background=COLORS[d.cluster_label];dot.setAttribute('aria-label',`${d.canonical_name}, ${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}, ${SHORT[d.cluster_label]}, ${meta.label} position ${fmt(d[field])}, ${OUTCOME_LABELS[outcome]} ${fmt(d[outcome])}`);hover(dot,`<b>${esc(d.canonical_name)}</b><br>${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}<br>${esc(SHORT[d.cluster_label])}<br>${esc(meta.label)}: ${fmt(d[field])}<br>${OUTCOME_LABELS[outcome]}: ${fmt(d[outcome])}`);box.appendChild(dot)});const counts=GROUPS.map(g=>rows.filter(x=>x.cluster_label===g).length);$('#issueCoverage').innerHTML=GROUPS.map((g,i)=>`<div><b>${counts[i]}</b><span>${SHORT[g]} observations</span></div>`).join('')}

function renderCases(){const order=Object.fromEntries(GROUPS.map((g,i)=>[g,i]));$('#caseStudies').innerHTML=DATA.cases.sort((a,b)=>order[a.group]-order[b.group]||a.kind.localeCompare(b.kind)).map(d=>`<article class="case ${cardClass(d.group)}"><div class="kicker">${esc(d.kind)}</div><h3>${esc(d.name)}</h3><p>${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}<br>${esc(SHORT[d.group])} · ${d.dimensions} observed dimensions</p><div class="metric-grid"><div><b>${fmt(d.candidate_cycle_war)}</b><span>Residual WAR</span></div><div><b>${fmt(d.candidate_federal_overperformance)}</b><span>Vs. federal</span></div><div><b>${fmt(d.candidate_presidential_overperformance)}</b><span>Vs. president</span></div></div></article>`).join('')}

function ellipse(points){if(!points.length)return null;const mx=points.reduce((s,p)=>s+p.x,0)/points.length,my=points.reduce((s,p)=>s+p.y,0)/points.length;return{cx:mx,cy:my,rx:Math.max(40,Math.sqrt(points.reduce((s,p)=>s+(p.x-mx)**2,0)/points.length)*1.7),ry:Math.max(28,Math.sqrt(points.reduce((s,p)=>s+(p.y-my)**2,0)/points.length)*1.7)}}
let selected=null;function renderConstellation(){const svg=$('#constellation'),rows=DATA.members.filter(x=>x.party==='D'),point=d=>({x:380+d.constellation_x*310,y:250-d.constellation_y*205});svg.innerHTML='';[70,170,270,370,470,570,670].forEach(x=>svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="${x}" y1="30" x2="${x}" y2="470"/>`));[70,160,250,340,430].forEach(y=>svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="35" y1="${y}" x2="725" y2="${y}"/>`));GROUPS.forEach(g=>{const e=ellipse(rows.filter(x=>x.cluster_label===g).map(point));if(e)svg.insertAdjacentHTML('beforeend',`<ellipse class="envelope" cx="${e.cx}" cy="${e.cy}" rx="${e.rx}" ry="${e.ry}" fill="${COLORS[g]}" stroke="${COLORS[g]}"/>`)});rows.slice().sort((a,b)=>a.constellation_coverage-b.constellation_coverage).forEach(d=>{const p=point(d),circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('class','member'+(selected===d.canonical_candidate_id?' selected':''));circle.setAttribute('cx',p.x);circle.setAttribute('cy',p.y);circle.setAttribute('r',4+6*d.constellation_coverage);circle.setAttribute('fill',COLORS[d.cluster_label]);circle.setAttribute('opacity',.32+.65*d.constellation_coverage);circle.setAttribute('tabindex','0');circle.setAttribute('role','button');circle.setAttribute('aria-label',`${d.canonical_name}, ${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}, ${SHORT[d.cluster_label]}, ${Math.round(d.constellation_coverage*100)} percent issue-dimension coverage`);hover(circle,`<b>${esc(d.canonical_name)}</b><br>${esc(SHORT[d.cluster_label])}<br>${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}<br>${Math.round(d.constellation_coverage*100)}% dimension coverage`);circle.onclick=()=>selectCandidate(d);circle.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectCandidate(d)}};svg.appendChild(circle)});$('#constellationCoverage').textContent=`${rows.length} Democratic candidate-cycles · ${DATA.diagnostics.features} dimensions`}
function selectCandidate(d){selected=d.canonical_candidate_id;const positions=DATA.issues.map(x=>({label:x.label,value:d[PREFIX+x.key]})).filter(x=>x.value!=null).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value)).slice(0,7);$('#candidateDetail').innerHTML=`<h3>${esc(d.canonical_name)}</h3><p>${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}<br>${esc(SHORT[d.cluster_label])}</p><div class="score">${fmt(d.candidate_cycle_war)}<span>Residual WAR</span></div><dl>${positions.map(x=>`<dt>${esc(x.label)}</dt><dd>${fmt(x.value)}</dd>`).join('')}</dl>`;renderConstellation()}
const PREFIX='primitive_conservative_';function renderRows(){const q=$('#candidateSearch').value.toLowerCase(),group=$('#candidateGroup').value,rows=DATA.members.filter(x=>x.party==='D'&&(group==='all'||x.cluster_label===group)&&(!q||`${x.canonical_name} ${x.chamber} ${x.district}`.toLowerCase().includes(q))).sort((a,b)=>a.cycle-b.cycle||a.canonical_name.localeCompare(b.canonical_name));$('#candidateRows').innerHTML=rows.map(d=>`<tr data-id="${esc(d.canonical_candidate_id)}" tabindex="0"><td>${esc(d.canonical_name)}</td><td>${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}</td><td>${esc(SHORT[d.cluster_label])}</td><td class="num">${fmt(d.candidate_cycle_war)}</td><td class="num">${fmt(d.candidate_federal_overperformance)}</td><td class="num">${fmt(d.candidate_presidential_overperformance)}</td></tr>`).join('');document.querySelectorAll('#candidateRows tr').forEach(tr=>{tr.onclick=()=>selectCandidate(DATA.members.find(x=>x.canonical_candidate_id===tr.dataset.id));tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();tr.click()}}})}

function renderEra(){const rows=DATA.absoluteEra,estimated=rows.filter(x=>x.coefficient!=null),bounds=estimated.flatMap(x=>[x.ci_low,x.ci_high]),limit=Math.max(5,Math.ceil(Math.max(...bounds.map(Math.abs),1)/5)*5),left=v=>5+90*(v+limit)/(2*limit);$('#eraEvidence').innerHTML=['pre_2008','2008_2014','post_2016'].map(e=>{const r=rows.find(x=>x.sample===`D:${e}`),ok=r&&r.coefficient!=null;return `<div class="era-row"><b>${eraLabel(e)}</b><div class="era-track">${ok?`<i class="era-ci" style="left:${left(r.ci_low)}%;width:${left(r.ci_high)-left(r.ci_low)}%;background:#651c2c"></i><i class="era-point" style="left:${left(r.coefficient)}%;background:#651c2c"></i>`:''}</div><div class="era-value">${ok?`<b>${fmt(r.coefficient)} WAR per 1 SD more conservative</b><span>95% interval ${fmt(r.ci_low)} to ${fmt(r.ci_high)} · n=${r.n}</span>`:`<b>Not estimated</b><span>Insufficient coverage</span>`}</div></div>`}).join('')}
function renderSources(){$('#sourceGrid').innerHTML=DATA.sourceCoverage.map(r=>`<div class="source-card"><b>${r.evidence_rows.toLocaleString()}</b><span>${esc(r.source_category)}<br>${r.candidate_cycles} candidate-cycles · ${r.issue_axes} axes</span></div>`).join('');$('#clusterMethod').textContent=`The selected Democratic solution has ${DATA.diagnostics.clusters} groups across ${DATA.diagnostics.features} issue dimensions and ${DATA.diagnostics.candidate_cycles} candidate-cycles. Silhouette is ${DATA.diagnostics.silhouette.toFixed(3)} and mean bootstrap adjusted Rand index is ${DATA.diagnostics.bootstrap_ari_mean.toFixed(3)}. The modest silhouette indicates overlap; bootstrap stability indicates the broad partition recurs under resampling.`}

$('#distributionOutcome').onchange=renderDistribution;$('#distributionEra').onchange=renderDistribution;$('#trendOutcome').onchange=renderTrend;$('#issueSelect').onchange=renderIssue;$('#issueOutcome').onchange=renderIssue;$('#issueEra').onchange=renderIssue;$('#candidateSearch').oninput=renderRows;$('#candidateGroup').onchange=renderRows;
renderWarHeadline();renderGroups();renderContrasts();renderTransition();renderProfiles();renderDistribution();renderTrend();initIssues();renderIssue();renderCases();renderConstellation();renderRows();renderEra();renderSources();
</script></body></html>'''
    page = template.replace("__DATA__", data)
    headline_css = """<style>
.war-headline{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:14px}
.war-card{border:1px solid var(--line);border-top:7px solid var(--ox);background:#fff;padding:18px}
.war-card.bridge-card{border-top-color:var(--gold)}
.war-card .war-number{font:bold 46px/1 Georgia,serif;color:var(--ox)}
.war-card.bridge-card .war-number{color:#805610}
.war-card h3{font:bold 18px Georgia,serif;margin:8px 0 4px}
.war-card p{font-size:11px;color:var(--muted);margin:0}
.supporting-head{border-top:1px solid var(--line);padding:18px 17px 0}
.supporting-head h3{font:bold 19px Georgia,serif;margin:0 0 5px}
.supporting-head p{font-size:11px;color:var(--muted);margin:0}
.method a{color:var(--ox);font-weight:bold}
@media(max-width:820px){.war-headline{grid-template-columns:1fr}}
</style>"""
    return page.replace("</head>", headline_css + "</head>", 1)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
