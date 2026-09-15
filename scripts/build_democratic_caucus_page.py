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
GROUP_COLORS = ["#356f91", "#5f93b4", "#a87418", "#651c2c", "#42101b"]


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


def resolve_public_names(cycles: pd.DataFrame) -> pd.DataFrame:
    """One publishable name per person.

    Source identifiers are never published. Where neither the canonical record
    nor a verified research alias supplies a name, the person is described by
    the seat actually on record and flagged as an unresolved identity rather
    than given a guessed one.
    """
    aliases = pd.read_csv(ALIASES, low_memory=False)
    aliases = aliases[aliases.identity_status.astype(str).str.startswith("verified_")]
    verified = dict(zip(aliases.canonical_candidate_id, aliases.research_name))
    frame = cycles[["person_id", "canonical_candidate_id", "canonical_name",
                    "cycle", "chamber", "district"]].copy()
    identifier_like = frame.canonical_name.astype(str).str.fullmatch(SOURCE_ID_PATTERN, na=False)
    frame["public_name"] = np.where(identifier_like,
                                    frame.canonical_candidate_id.map(verified),
                                    frame.canonical_name)
    resolved = (frame.dropna(subset=["public_name"]).sort_values("cycle")
                .groupby("person_id").public_name.last())
    latest = frame.sort_values("cycle").groupby("person_id").last()
    seat = ("Unnamed " + latest.cycle.astype(str) + " "
            + latest.chamber.astype(str).str.upper().str[0] + "D-"
            + latest.district.astype(str) + " Democrat")
    names = pd.DataFrame({
        "name": resolved.reindex(latest.index).fillna(seat),
        "identityResolved": resolved.reindex(latest.index).notna(),
    })
    if names.name.astype(str).str.fullmatch(SOURCE_ID_PATTERN, na=False).any():
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
    template = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Ideological groupings of Alabama Democratic candidates, 1994-2022, and their overperformance against the fixed WAR reference model"><link rel="icon" href="data:"><title>Ideology and caucuses · Jackson Hannan</title><style>
:root{--ink:#25191d;--muted:#695b60;--line:#b9aaaf;--paper:#fff;--blue:#b9d9ec;--blue-dark:#356f91;--ox:#651c2c;--ox-dark:#42101b;--gold:#a87418;--pale:#eef6fa;--wash:#f8f3f4}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--blue);color:var(--ink);font:15px/1.52 Arial,Helvetica,sans-serif}button,select,input{font:inherit}header,footer{background:var(--ox);color:#fff}.mast,.shell{width:min(1200px,calc(100% - 38px));margin:auto}.mast{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:17px 0}.brand{font:bold 23px Georgia,serif}.tag,.kicker{font:bold 10px Arial,sans-serif;letter-spacing:1px;text-transform:uppercase}.tag{color:#eadde1}.nav{display:flex;gap:16px;flex-wrap:wrap}.nav a,footer a{color:#fff;text-decoration:none;font-size:11px}.nav a[aria-current=page]{border-bottom:2px solid #fff;padding-bottom:3px}.shell{background:var(--paper);padding:48px clamp(18px,4vw,50px) 88px;border-left:1px solid #91b5c9;border-right:1px solid #91b5c9}.hero{max-width:900px}.kicker{color:var(--ox)}h1{font:bold clamp(37px,6vw,64px)/1.03 Georgia,serif;letter-spacing:-1.7px;margin:9px 0 18px}.dek{font:20px/1.5 Georgia,serif;margin:0}.finding{border:1px solid var(--ox);border-left:8px solid var(--ox);background:#fff9fa;padding:17px 19px;margin:25px 0 34px;font:16px/1.55 Georgia,serif}.contents{display:flex;gap:7px;flex-wrap:wrap;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px 0;margin:0 0 56px}.contents a{background:var(--wash);color:var(--ox);padding:5px 8px;text-decoration:none;font:bold 10px Arial}section{margin:70px 0;scroll-margin-top:18px}.section-head{max-width:860px;margin-bottom:24px}.section-head h2{font:bold 31px/1.12 Georgia,serif;margin:6px 0 9px}.section-head p{margin:0;color:#4e4246}.panel{border:1px solid var(--line);background:#fff}.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap;padding:12px 14px;border-bottom:1px solid var(--line);background:var(--wash)}.controls label{font:bold 9px Arial;text-transform:uppercase;letter-spacing:.65px;color:var(--muted)}select,input{display:block;margin-top:4px;border:1px solid #8f7e84;background:#fff;color:var(--ink);padding:8px 14px 8px 9px;max-width:100%}.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--muted);padding:12px 16px}.legend i{display:inline-block;width:11px;height:11px;margin-right:5px;vertical-align:-1px}.group-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}.group-card{background:#fff;padding:18px;border-top:6px solid var(--ox)}.group-card h3{font:bold 19px Georgia,serif;margin:0 0 5px}.group-card .count{color:var(--muted);font-size:11px}.group-card p{font-size:12px;color:#4e4246}.metric-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px;margin-top:14px}.metric-grid div{background:var(--wash);padding:9px}.metric-grid b{display:block;font:18px Georgia,serif}.metric-grid span{display:block;font-size:9px;color:var(--muted)}.profile{padding:12px 17px}.profile-row{display:grid;grid-template-columns:200px 1fr 92px;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #e2d9dc}.profile-row:first-child{border:0}.profile-row label{font-size:12px}.profile-row label small{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.4px}.profile-track{height:30px;position:relative;background:linear-gradient(90deg,#e4f1f8,#fff 49.5%,#f5e6e9)}.profile-track:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #7e6e73}.profile-dot{position:absolute;top:8px;width:13px;height:13px;border-radius:50%;transform:translateX(-50%);border:2px solid #fff;box-shadow:0 0 0 1px #55484c}.profile-row output{text-align:right;font:11px Arial;color:var(--muted)}.distribution{height:420px;position:relative;margin:20px 32px 47px 150px;border-left:1px solid var(--line);border-bottom:1px solid var(--line)}.zero{position:absolute;top:0;bottom:0;border-left:1px solid #76666b}.lane{position:absolute;left:-143px;width:135px;text-align:right;font-size:10px;transform:translateY(50%)}.performance-dot{position:absolute;width:9px;height:9px;border-radius:50%;border:1px solid #fff;box-shadow:0 0 0 1px #55484c;transform:translate(-50%,50%);opacity:.74;cursor:pointer;padding:0}.mean-line{position:absolute;width:4px;height:26px;background:var(--ink);transform:translate(-50%,50%)}.axis-label{position:absolute;bottom:-32px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted)}.stack-row{display:grid;grid-template-columns:56px 1fr 62px;gap:10px;align-items:center;padding:8px 0;border-top:1px solid #e2d9dc}.stack-row:first-child{border:0}.stack{height:26px;display:flex;border:1px solid #8f7d83}.stack span{height:100%;min-width:1px}.stack-row small{text-align:right;color:var(--muted)}.table-wrap{max-height:430px;overflow:auto;border-top:1px solid var(--line)}table{width:100%;border-collapse:collapse;font-size:11px}th{position:sticky;top:0;background:var(--ox);color:#fff;text-align:left;padding:8px}td{padding:8px;border-top:1px solid #e2d9dc}tbody tr{cursor:pointer}tbody tr:hover{background:var(--pale)}.num{text-align:right}.detail{padding:18px;border-left:1px solid var(--line)}.detail h3{font:bold 21px Georgia,serif;margin:0}.detail .score{font:bold 32px Georgia,serif;color:var(--ox);margin:14px 0}.detail .score span{display:block;font:9px Arial;color:var(--muted);text-transform:uppercase}.detail dl{font-size:11px;margin:0}.detail dt{float:left;clear:left;color:var(--muted)}.detail dd{text-align:right;border-bottom:1px solid #e2d9dc;padding:4px 0;margin:0}.explorer{display:grid;grid-template-columns:minmax(0,1fr) 290px}.coverage{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}.coverage div{background:#fff;padding:12px}.coverage b{display:block;font:20px Georgia,serif}.coverage span{font-size:9px;color:var(--muted)}.funnel{padding:14px 17px}.funnel-row{display:grid;grid-template-columns:230px 1fr 74px;gap:12px;align-items:center;padding:9px 0;border-top:1px solid #e2d9dc;font-size:12px}.funnel-row:first-child{border:0}.funnel-bar{height:22px;background:var(--blue-dark)}.sens-row{display:grid;grid-template-columns:270px 1fr 62px;gap:12px;align-items:center;padding:11px 0;border-top:1px solid #e2d9dc;font-size:12px}.sens-row:first-child{border:0}.sens-track{height:20px;background:var(--wash);position:relative}.sens-fill{position:absolute;left:0;top:0;bottom:0;background:var(--gold)}.sens-row output{text-align:right;font:bold 12px Arial}.sens-row p{margin:2px 0 0;font-size:10px;color:var(--muted)}.method{border-left:6px solid var(--ox);background:var(--wash);padding:16px 18px;margin:11px 0}.method h3{font:bold 18px Georgia,serif;margin:0 0 6px}.method p{font-size:12px;margin:0}.method a{color:var(--ox);font-weight:bold}.tip{position:fixed;display:none;z-index:20;pointer-events:none;max-width:290px;background:var(--ox-dark);color:#fff;padding:9px 11px;font-size:11px;box-shadow:0 8px 22px #0004}footer{padding:24px max(20px,calc((100vw - 1160px)/2));font-size:11px}@media(max-width:820px){.mast{align-items:flex-start;flex-direction:column}.explorer{grid-template-columns:1fr}.detail{border-left:0;border-top:1px solid var(--line)}.profile-row,.sens-row,.funnel-row{grid-template-columns:140px 1fr 60px}}@media(max-width:540px){.mast,.shell{width:100%}.mast{padding:14px}.shell{padding:34px 13px 64px;border:0}h1{font-size:37px}.metric-grid{grid-template-columns:1fr}.distribution{margin-left:15px;margin-right:15px}.lane{left:5px;width:auto;background:#fffd;padding:2px 4px;z-index:3;text-align:left}.profile-row,.sens-row,.funnel-row{grid-template-columns:1fr 58px}.profile-track,.sens-track,.funnel-bar{grid-column:1/-1}.nav{gap:9px}}
</style></head><body><header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative elections</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="ideology-performance.html" aria-current="page">Ideology &amp; caucuses</a><a href="cmo-methodology.html">Methodology</a></nav></div></header><main class="shell"><div class="hero"><div class="kicker">Alabama Democratic ideology and performance</div><h1>Five Democratic groupings, 1994&ndash;2022</h1><p class="dek">Every Democratic general-election candidate of the last eight cycles, grouped by the issue positions their roll calls, sponsorships, questionnaires and endorsements actually record &mdash; then measured against the fixed WAR reference model.</p><div class="finding" id="headlineFinding"></div></div><nav class="contents" aria-label="On this page"><a href="#groups">Groups</a><a href="#positions">Positions</a><a href="#performance">Performance</a><a href="#composition">Composition</a><a href="#members">Members</a><a href="#coverage">Coverage</a><a href="#limits">Limits</a><a href="#methods">Method</a></nav>

<section id="groups"><div class="section-head"><div class="kicker">The groupings</div><h2>Five position profiles, formed without looking at any election result</h2><p>Clustering uses the eight ontology issue families only. Residual WAR, wins and incumbency are attached afterwards, so no electoral outcome can place a member in a group. Unscored candidate-cycles are seats with no contested general election; they are not zeros.</p></div><div id="groupGrid" class="group-grid"></div></section>

<section id="positions"><div class="section-head"><div class="kicker">Issue profiles</div><h2>Where the groups actually differ</h2><p>Dots are group means on each issue family, plotted between that family&rsquo;s two poles. The count beside each row is how many people in the whole sample have evidence on that family, so thin rows can be read as thin.</p></div><div class="panel"><div id="profileLegend" class="legend"></div><div id="profileChart" class="profile"></div></div></section>

<section id="performance"><div class="section-head"><div class="kicker">Headline result</div><h2>Overperformance against the reference model</h2><p>WAR is the candidate-oriented race residual in two-party margin points: the actual legislative-minus-ticket gap minus the fitted structural expectation of the fixed 2018&ndash;24 reference model. Pre-2016 cycles are scored against modern partisan expectations, so early-era Democrats show large positive WAR partly by construction.</p></div><div class="panel"><div class="controls"><label>Measure<select id="measure"><option value="cycle">Cycle WAR (each contested race)</option><option value="career">Career cumulative WAR (per person)</option></select></label></div><div id="distribution" class="distribution"><span class="axis-label">Candidate-oriented margin points &rarr;</span></div></div></section>

<section id="composition"><div class="section-head"><div class="kicker">Composition</div><h2>Which groups the Democratic field contained, by cycle</h2><p>Counts are candidate-cycles whose person was grouped. A cycle&rsquo;s bar excludes candidates without enough issue evidence, so bars are not chamber totals.</p></div><div class="panel"><div id="compositionLegend" class="legend"></div><div id="compositionChart" class="funnel"></div></div></section>

<section id="members"><div class="section-head"><div class="kicker">Members</div><h2>Every grouped person, with the evidence behind them</h2><p>Select a row for that person&rsquo;s issue profile. &ldquo;Families observed&rdquo; is how many of the eight issue families their record covers; three is the minimum to be grouped.</p></div><div class="panel"><div class="controls"><label>Search<input id="search" type="search" placeholder="Name or chamber"></label><label>Group<select id="groupFilter"></select></label></div><div class="explorer"><div class="table-wrap"><table><thead><tr><th>Person</th><th>Cycles</th><th>Group</th><th class="num">Families</th><th class="num">Career WAR</th><th class="num">Scored</th></tr></thead><tbody id="memberRows"></tbody></table></div><aside id="detail" class="detail" aria-live="polite"><p>Select a person to see their issue profile.</p></aside></div></div></section>

<section id="coverage"><div class="section-head"><div class="kicker">Coverage</div><h2>Who is in the analysis, and who is not</h2><p>Nobody is dropped silently. People without enough issue evidence are counted and reported with the reason.</p></div><div class="panel"><div id="funnel" class="funnel"></div></div><div id="coverageGrid" class="coverage" style="margin-top:18px"></div></section>

<section id="limits"><div class="section-head"><div class="kicker">How much to trust this</div><h2>Cluster sensitivity, stated plainly</h2><p>Each bar is an adjusted Rand index between the published grouping and the grouping produced by an alternative reasonable choice: 1.0 is identical, 0 is no better than chance. These are descriptive tendencies, not formal caucus membership.</p></div><div class="panel"><div id="sensitivity" class="funnel"></div></div><div class="method"><h3>What these groups are not</h3><p>They are not the Alabama Legislative Black Caucus or any other organised caucus, which have real membership rolls this analysis does not use. They are not a pre-election snapshot: a member&rsquo;s later roll calls help define the group used to read their earlier race. They are not causal &mdash; a group&rsquo;s mean WAR describes the races its members happened to run, including opponent quality and local conditions this measure cannot separate.</p></div></section>

<section id="methods"><div class="section-head"><div class="kicker">Method and provenance</div><h2>How this page was produced</h2></div><div class="method"><h3>Grouping</h3><p id="methodCluster"></p></div><div class="method"><h3>WAR definition</h3><p>The residual framing follows <a href="https://split-ticket.org/2025/08/15/deconstructing-war/">Split Ticket&rsquo;s WAR methodology</a>; this Alabama implementation and its estimates are independent. Race WAR = actual legislative-minus-ticket gap minus the fitted structural expected gap. Democratic WAR is the race residual and Republican WAR is its exact negative. One fixed reference model, fitted on 2018&ndash;24 Southern races, scores every cycle; no era-specific refit is applied. Career cumulative WAR is the sum of a person&rsquo;s scored cycle WAR. No pooled individual effect, fundraising term, or ideology term enters WAR.</p></div><div class="method"><h3>Evidence</h3><p id="methodEvidence"></p></div><div class="method"><h3>Source credit</h3><p>Roll-call and bill records from <a href="https://legiscan.com/" target="_blank" rel="noopener">LegiScan</a> (CC BY 4.0) and the Alabama Legislature; candidate questionnaires and interest-group ratings summarised from <a href="https://justfacts.votesmart.org/" target="_blank" rel="noopener">Vote Smart</a>; election identities and totals from the Alabama Secretary of State. Only derived summaries are published here.</p></div><div class="method"><h3>Run</h3><p id="methodRun"></p></div></section></main><div id="tip" class="tip"></div><footer>Research and model by Jackson Hannan · <a href="cmo.html">Alabama WAR</a> · <a href="cmo-methodology.html">Methodology</a></footer>

<script>const DATA=__DATA__;
const $=s=>document.querySelector(s),COLORS=DATA.colors,GROUPS=DATA.groups;
const fmt=v=>v==null||!Number.isFinite(+v)?'—':`${+v>=0?'+':''}${(+v).toFixed(1)}`,pct=v=>`${Math.round(v*100)}%`;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const groupOf=r=>GROUPS.find(g=>g.rank===r),color=r=>COLORS[(r-1)%COLORS.length];
function hover(node,html){node.onpointerenter=e=>{const t=$('#tip');t.innerHTML=html;t.style.display='block';moveTip(e)};node.onpointermove=moveTip;node.onpointerleave=()=>$('#tip').style.display='none'}
function moveTip(e){const t=$('#tip'),pad=14;t.style.left=Math.min(innerWidth-t.offsetWidth-pad,e.clientX+14)+'px';t.style.top=Math.min(innerHeight-t.offsetHeight-pad,e.clientY+14)+'px'}

function renderHeadline(){const sorted=GROUPS.slice().sort((a,b)=>a.cycleWarMean-b.cycleWarMean),low=sorted[0],high=sorted.at(-1);$('#headlineFinding').innerHTML=`<b>Headline result:</b> ${esc(low.label)} average <b>${fmt(low.cycleWarMean)}</b> margin points of WAR per contested race, against <b>${fmt(high.cycleWarMean)}</b> for ${esc(high.label)}. Pre-2016 races are scored against modern partisan expectations, which lifts early-era groups by construction; the ordering survives era-normalised regrouping, the levels do not.`}
function renderGroups(){$('#groupGrid').innerHTML=GROUPS.map(g=>`<article class="group-card" style="border-top-color:${color(g.rank)}"><h3>${esc(g.label)}</h3><div class="count">${g.people} people · ${g.candidateCycles} candidate-cycles</div><p>${esc(g.description)}</p><div class="metric-grid"><div><b>${fmt(g.cycleWarMean)}</b><span>Mean cycle WAR (SE ${g.cycleWarSe==null?'—':g.cycleWarSe.toFixed(2)})</span></div><div><b>${fmt(g.careerWarMedian)}</b><span>Median career WAR</span></div><div><b>${g.cyclesScored}</b><span>Scored cycles</span></div><div><b>${pct(g.unscoredShare)}</b><span>Cycles with no contested race</span></div></div></article>`).join('')}
function legend(node){$(node).innerHTML=GROUPS.map(g=>`<span><i style="background:${color(g.rank)}"></i>${esc(g.label)}</span>`).join('')}

function renderProfiles(){const left=v=>5+90*(v+1)/2;$('#profileChart').innerHTML=DATA.families.map(f=>{const dots=GROUPS.map(g=>{const cell=g.profile.find(p=>p.family===f.key);return cell&&cell.value!=null?`<i class="profile-dot" style="left:${left(cell.value)}%;background:${color(g.rank)}" title="${esc(g.label)}: ${cell.value.toFixed(2)} (${cell.people} people)"></i>`:''}).join('');const observed=GROUPS.reduce((s,g)=>s+(g.profile.find(p=>p.family===f.key)?.people||0),0);return `<div class="profile-row"><label>${esc(f.label)}<small>${esc(f.negativePole)} to ${esc(f.positivePole)}</small></label><div class="profile-track" role="img" aria-label="${esc(f.label)} group means from ${esc(f.negativePole)} to ${esc(f.positivePole)}">${dots}</div><output>${observed} people</output></div>`}).join('')}

function renderDistribution(){const mode=$('#measure').value,box=$('#distribution');box.querySelectorAll(':scope > :not(.axis-label)').forEach(x=>x.remove());const series=mode==='cycle'?DATA.warCycles.map(r=>({rank:r.cluster_rank,value:r.candidate_cycle_war,label:`${r.cycle} ${String(r.chamber).toUpperCase()}-${r.district}`,name:DATA.members.find(m=>m.person_id===r.person_id)?.name||''})):DATA.members.filter(m=>m.career_war!=null).map(m=>({rank:m.cluster_rank,value:m.career_war,label:`${m.cycles_scored} scored cycles`,name:m.name}));const values=series.map(s=>+s.value),limit=Math.max(20,Math.ceil(Math.max(...values.map(Math.abs),1)/10)*10),left=v=>5+90*(v+limit)/(2*limit);const zero=document.createElement('i');zero.className='zero';zero.style.left=left(0)+'%';box.appendChild(zero);GROUPS.forEach((g,i)=>{const lane=86-i*17,tag=document.createElement('span');tag.className='lane';tag.style.bottom=lane+'%';tag.textContent=g.label;box.appendChild(tag);const rows=series.filter(s=>s.rank===g.rank);rows.forEach((d,j)=>{const dot=document.createElement('button');dot.type='button';dot.className='performance-dot';dot.style.left=left(d.value)+'%';dot.style.bottom=`calc(${lane}% + ${(j%7-3)*3}px)`;dot.style.background=color(g.rank);dot.setAttribute('aria-label',`${d.name}, ${d.label}, ${fmt(d.value)} margin points`);hover(dot,`<b>${esc(d.name)}</b><br>${esc(d.label)}<br>${esc(g.label)}<br>${fmt(d.value)} margin points`);box.appendChild(dot)});if(rows.length){const mean=rows.reduce((s,x)=>s+(+x.value),0)/rows.length,mark=document.createElement('i');mark.className='mean-line';mark.style.left=left(mean)+'%';mark.style.bottom=lane+'%';mark.title=`${g.label} mean ${fmt(mean)}`;box.appendChild(mark)}})}

function renderComposition(){const cycles=[...new Set(DATA.composition.map(x=>x.cycle))].sort((a,b)=>a-b);$('#compositionChart').innerHTML=cycles.map(c=>{const rows=DATA.composition.filter(x=>x.cycle===c),total=rows.reduce((s,x)=>s+x.n,0);return `<div class="stack-row"><strong>${c}</strong><div class="stack">${GROUPS.map(g=>{const n=rows.find(x=>x.cluster_rank===g.rank)?.n||0;return `<span style="width:${total?100*n/total:0}%;background:${color(g.rank)}" title="${esc(g.label)}: ${n} of ${total}"></span>`}).join('')}</div><small>n=${total}</small></div>`}).join('')}

function renderFunnel(){const c=DATA.coverage,rows=[['Democratic candidates, 1994–2022',c.people],['With any issue evidence',c.peopleWithEvidence],['Grouped (≥3 of 8 families)',c.peopleClustered]];$('#funnel').innerHTML=rows.map(([label,n])=>`<div class="funnel-row"><span>${esc(label)}</span><div class="funnel-bar" style="width:${100*n/c.people}%"></div><output>${n}</output></div>`).join('')+c.unclustered.map(u=>`<div class="funnel-row"><span>Not grouped — ${u.reason==='no_ontology_evidence'?'no issue evidence at all':'evidence on fewer than three families'}</span><div class="funnel-bar" style="width:${100*u.people/c.people}%;background:var(--muted)"></div><output>${u.people}</output></div>`).join('');$('#coverageGrid').innerHTML=[[c.candidateCycles,'Democratic candidate-cycles'],[c.cyclesScored,'Scored by the WAR model'],[c.cyclesUnscored,'No contested general election'],[c.peopleWithUnresolvedIdentity,'Grouped people whose canonical 2022 record carries no name; listed by seat, identity unresolved']].map(([n,l])=>`<div><b>${n.toLocaleString()}</b><span>${l}</span></div>`).join('')+c.channels.slice(0,4).map(ch=>`<div><b>${ch.evidence_rows.toLocaleString()}</b><span>${esc(ch.channel)} records · ${ch.people} people</span></div>`).join('')}

function renderSensitivity(){$('#sensitivity').innerHTML=DATA.sensitivity.map(s=>`<div class="sens-row"><span>${esc(s.test)}<p>${esc(s.reading)}</p></span><div class="sens-track" role="img" aria-label="${esc(s.test)} agreement ${s.statistic.toFixed(2)} of 1"><i class="sens-fill" style="width:${Math.max(0,Math.min(1,s.statistic))*100}%"></i></div><output>${s.statistic.toFixed(2)}</output></div>`).join('')}

let selected=null;
function renderMembers(){const q=$('#search').value.toLowerCase(),filter=$('#groupFilter').value,rows=DATA.members.filter(m=>(filter==='all'||m.cluster_rank===+filter)&&(!q||`${m.name} ${m.chambers}`.toLowerCase().includes(q))).sort((a,b)=>(b.career_war??-1e9)-(a.career_war??-1e9));$('#memberRows').innerHTML=rows.map(m=>`<tr data-id="${esc(m.person_id)}" tabindex="0"><td>${esc(m.name)}</td><td>${m.first_cycle}–${m.last_cycle}</td><td><i style="display:inline-block;width:9px;height:9px;background:${color(m.cluster_rank)}"></i> ${esc(m.cluster_label)}</td><td class="num">${m.features_observed}</td><td class="num">${fmt(m.career_war)}</td><td class="num">${m.cycles_scored}/${m.cycles_total}</td></tr>`).join('');document.querySelectorAll('#memberRows tr').forEach(tr=>{tr.onclick=()=>select(tr.dataset.id);tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();tr.click()}}})}
function select(id){const m=DATA.members.find(x=>x.person_id===id);if(!m)return;selected=id;const positions=DATA.families.map(f=>({label:f.label,value:m[f.key]})).filter(x=>x.value!=null);$('#detail').innerHTML=`<h3>${esc(m.name)}</h3><p>${esc(m.chambers)} · ${m.first_cycle}–${m.last_cycle} · ${esc(m.cluster_label)}</p><div class="score">${fmt(m.career_war)}<span>Career cumulative WAR · ${m.cycles_scored} of ${m.cycles_total} cycles scored</span></div><dl>${positions.map(x=>`<dt>${esc(x.label)}</dt><dd>${x.value.toFixed(2)}</dd>`).join('')}</dl><p style="font-size:10px;color:var(--muted)">Era-normalised grouping places this person in group ${m.eraGroup}.</p>`}

function renderMethods(){const d=DATA.diagnostics,c=DATA.coverage,r=DATA.run;$('#methodCluster').textContent=`One career profile per person, from all ontology-v3 evidence. Features are the ${d.features} issue families; k-means with k chosen in 2–5 by bootstrap stability selected ${d.clusters} groups (silhouette ${d.silhouette.toFixed(3)}, mean bootstrap ARI ${d.bootstrapAri.toFixed(3)}, tenth percentile ${d.bootstrapAriP10.toFixed(3)}). ${pct(DATA.repeatedPeopleShare)} of grouped people ran in more than one cycle, which the person-level unit absorbs. Group labels were proposed from the profiles and approved by the author.`;$('#methodEvidence').textContent=`${c.channels.reduce((s,x)=>s+x.evidence_rows,0).toLocaleString()} evidence records across ${c.channels.length} channels cover ${c.peopleWithEvidence} of ${c.people} Democratic candidates; ${c.peopleClustered} meet the three-family minimum. Roll calls and sponsorships carry the most weight, questionnaires and endorsements less.`;$('#methodRun').textContent=`Caucus run ${r.caucusRunId}, generated ${r.generatedAt.slice(0,10)}, joined to historical WAR run ${r.historicalWarRunId}. Labels from ${r.labelsSource}.`}

$('#groupFilter').innerHTML='<option value="all">All groups</option>'+GROUPS.map(g=>`<option value="${g.rank}">${esc(g.label)}</option>`).join('');
$('#measure').onchange=renderDistribution;$('#search').oninput=renderMembers;$('#groupFilter').onchange=renderMembers;
renderHeadline();renderGroups();legend('#profileLegend');legend('#compositionLegend');renderProfiles();renderDistribution();renderComposition();renderFunnel();renderSensitivity();renderMembers();renderMethods();
</script></body></html>'''
    return template.replace("__DATA__", data)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
