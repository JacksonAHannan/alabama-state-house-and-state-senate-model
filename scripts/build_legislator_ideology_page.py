"""Build the public evidence atlas for the CMO research cohort.

The page deliberately separates directional balance from evidence coverage.  It
uses only human-reviewed directional codes for color; uncoded public positions
remain visible in candidate records but do not silently become ideology scores.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
ASSETS = ROOT / "dashboard"
OUTPUT = ROOT / "docs" / "legislators.html"
VOTESMART = ROOT / "data" / "processed" / "ideology" / "votesmart_pct_candidate_cycle_features.csv"
LEGISLATIVE_IDEOLOGY = ROOT / "data" / "processed" / "ideology" / "candidate_ideology_full_universe.csv"

ISSUE_GROUPS = {
    "abortion": "Abortion",
    "guns": "Guns",
    "labor_unions": "Labor & wages",
    "minimum_wage_worker_pay": "Labor & wages",
    "public_employee_benefits": "Labor & wages",
    "public_education": "Public education",
    "school_choice": "School choice",
    "taxes_budget": "Taxes & spending",
    "business_economic_development": "Economic development",
    "occupational_licensing": "Economic development",
    "public_private_partnerships": "Economic development",
    "healthcare_medicaid": "Health care",
    "health_social_services": "Health care",
    "healthcare_conscience": "Health care",
    "criminal_justice": "Criminal justice",
    "assisted_dying": "Criminal justice",
    "immigration": "Immigration",
    "racial_civil_rights": "Civil & cultural rights",
    "lgbtq_cultural": "Civil & cultural rights",
    "ethics_government": "Government & ethics",
    "anti_esg_governance": "Government & ethics",
    "environment": "Environment & infrastructure",
    "infrastructure_energy": "Environment & infrastructure",
    "rural_hunting": "Rural & local interests",
    "gambling": "Rural & local interests",
}

GROUP_ORDER = [
    "Abortion", "Guns", "Labor & wages", "Public education", "School choice",
    "Taxes & spending", "Economic development", "Health care", "Criminal justice",
    "Immigration", "Civil & cultural rights", "Government & ethics",
    "Environment & infrastructure", "Rural & local interests",
]

VALENCE = {"progressive": -1.0, "conservative": 1.0}
CONFIDENCE = {"high": 1.0, "medium": 0.75, "low": 0.5}
PCT_GROUPS = {
    "abortion_position": "Abortion", "guns_position": "Guns",
    "labor_position": "Labor & wages", "education_position": "Public education",
    "economic_ideology": "Taxes & spending", "healthcare_position": "Health care",
    "criminal_justice_position": "Criminal justice", "social_ideology": "Civil & cultural rights",
    "government_reform_position": "Government & ethics",
    "environment_position": "Environment & infrastructure",
}


def clean(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value


def add_record(records, **values):
    records.append({key: clean(value) for key, value in values.items()})


def build_payload() -> dict:
    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")
    bios = pd.read_csv(RESEARCH / "candidate_biographies.csv").set_index("person_id")
    shor = pd.read_csv(RESEARCH / "shor_mccarty_matches.csv").set_index("person_id")
    legislative = pd.read_csv(LEGISLATIVE_IDEOLOGY) if LEGISLATIVE_IDEOLOGY.exists() else pd.DataFrame()
    records: list[dict] = []

    pct_profiles = {}
    if VOTESMART.exists():
        pct = pd.read_csv(VOTESMART)
        pct = pct[pct.pct_dimensions_scored.notna()].copy()
        for cohort_row in cohort.itertuples(index=False):
            eligible = pct[pct.person_id.eq(cohort_row.person_id) &
                           pct.election_year.le(cohort_row.cycle)]
            if eligible.empty:
                continue
            profile = eligible.sort_values("election_year").iloc[-1]
            pct_profiles[cohort_row.person_id] = profile
            for dimension, group in PCT_GROUPS.items():
                score = pd.to_numeric(profile.get(dimension), errors="coerce")
                if pd.isna(score):
                    continue
                add_record(
                    records, person_id=cohort_row.person_id, issue=dimension,
                    group=group, source_type="Vote Smart PCT", direction=float(score),
                    weight=.7, confidence="medium", timing="pre_election_candidate_supplied",
                    date=str(int(profile.election_year)), bill=None,
                    summary=(f"Candidate-supplied {int(profile.election_year)} Vote Smart questionnaire: "
                             f"dimension score {score:+.2f} (-1 progressive to +1 conservative)."),
                    url=f"https://justfacts.votesmart.org/candidate/political-courage-test/{int(profile.votesmart_candidate_id)}",
                )

    codes = pd.read_csv(RESEARCH / "anchor_vote_human_codes.csv")
    codes = codes.drop_duplicates("roll_call_id").set_index("roll_call_id")
    votes = pd.read_csv(RESEARCH / "candidate_rollcall_position_evidence.csv")
    for _, row in votes.iterrows():
        code = codes.loc[row.roll_call_id] if row.roll_call_id in codes.index else None
        valence = None if code is None else VALENCE.get(str(code.ideological_valence).lower())
        if valence is not None and str(row.vote).lower() == "nay":
            valence *= -1
        add_record(
            records, person_id=row.person_id, issue=row.human_issue_code,
            group=ISSUE_GROUPS.get(row.human_issue_code, row.human_issue_code),
            source_type="Roll call", direction=valence, weight=.85,
            confidence=None if code is None else code.human_confidence,
            timing=row.evidence_timing, date=row.vote_date, bill=row.bill_number,
            summary=row.candidate_position, url=row.source_url,
        )

    sponsors = pd.read_csv(RESEARCH / "candidate_sponsorship_position_evidence.csv")
    for _, row in sponsors.iterrows():
        role = str(row.sponsorship_role).lower()
        weight = 1.0 if "primary" in role else .35
        add_record(
            records, person_id=row.person_id, issue=row.human_issue_code,
            group=ISSUE_GROUPS.get(row.human_issue_code, row.human_issue_code),
            source_type="Sponsorship", direction=VALENCE.get(str(row.ideological_valence).lower()),
            weight=weight, confidence=row.confidence, timing=row.temporal_status,
            date=row.evidence_date, bill=row.bill_number, summary=row.position_summary,
            url=row.source_url,
        )

    amendments = pd.read_csv(RESEARCH / "candidate_amendment_position_evidence.csv")
    for _, row in amendments.iterrows():
        add_record(
            records, person_id=row.person_id, issue=row.issue,
            group=ISSUE_GROUPS.get(row.issue, row.issue), source_type="Amendment",
            direction=VALENCE.get(str(row.ideological_valence).lower()), weight=1.0,
            confidence=row.confidence, timing=row.temporal_status, date=row.evidence_date,
            bill=row.bill_number, summary=row.position_summary, url=row.source_url,
        )

    public = pd.read_csv(RESEARCH / "state_issue_position_ledger.csv")
    for _, row in public.iterrows():
        add_record(
            records, person_id=row.person_id, issue=row.issue,
            group=ISSUE_GROUPS.get(row.issue, row.issue), source_type="Public position",
            direction=None, weight=.7, confidence=row.confidence, timing=row.temporal_status,
            date=row.evidence_date, bill=None, summary=row.position_summary, url=row.source_url,
        )

    by_person = {pid: [] for pid in cohort.person_id}
    for record in records:
        by_person.setdefault(record["person_id"], []).append(record)

    candidates = []
    for _, row in cohort.iterrows():
        pid = row.person_id
        candidate_records = by_person.get(pid, [])
        bio = bios.loc[pid] if pid in bios.index else None
        sm = shor.loc[pid] if pid in shor.index else None
        li_pool = (legislative[legislative.person_id.eq(pid) & legislative.year.eq(row.cycle)]
                   if not legislative.empty else legislative)
        li = li_pool.iloc[0] if len(li_pool)==1 else None
        cells = []
        for group in GROUP_ORDER:
            group_records = [r for r in candidate_records if r["group"] == group]
            directional = [r for r in group_records if r["direction"] is not None]
            weighted = [r["direction"] * r["weight"] * CONFIDENCE.get(str(r["confidence"]).lower(), .75) for r in directional]
            weights = [r["weight"] * CONFIDENCE.get(str(r["confidence"]).lower(), .75) for r in directional]
            score = sum(weighted) / sum(weights) if weights else None
            progressive = sum(w for w, r in zip(weights, directional) if r["direction"] < 0)
            conservative = sum(w for w, r in zip(weights, directional) if r["direction"] > 0)
            disagreement = min(progressive, conservative) / max(progressive + conservative, .001)
            cells.append({
                "group": group, "score": score, "records": len(group_records),
                "directional": len(directional), "disagreement": disagreement,
                "sourceTypes": sorted({r["source_type"] for r in group_records}),
            })
        source_counts = {source: sum(r["source_type"] == source for r in candidate_records)
                         for source in ["Roll call", "Sponsorship", "Amendment", "Public position", "Vote Smart PCT"]}
        pct_profile = pct_profiles.get(pid)
        candidates.append({
            "personId": pid,
            "name": clean(bio.display_candidate) if bio is not None else row.candidate,
            "cycle": int(row.cycle),
            "chamber": str(row.chamber).title(), "district": int(row.district),
            "cmo": clean(row.robust_cmo_median), "bestCmo": clean(row.best_cmo),
            "incumbent": bool(row.incumbent), "winner": bool(row.winner),
            "bio": None if bio is None else {
                "summary": clean(bio.summary), "service": clean(bio.offices_and_public_service),
                "profession": clean(bio.profession_and_employment), "education": clean(bio.education),
                "community": clean(bio.community_and_local_ties), "profile": clean(bio.political_profile),
                "caveats": clean(bio.important_caveats), "status": clean(bio.review_status),
            },
            "shor": None if sm is None else {
                "status": clean(sm.match_status), "score": clean(sm.np_score),
                "percentile": clean(sm.al_dem_caucus_conservative_percentile),
                "temporalUse": clean(sm.temporal_use), "note": clean(sm.review_note),
            },
            "legislativeIdeology": None if li is None or not bool(li.legislative_ideology_available) else {
                "score": clean(li.behavioral_ideology),
                "percentile": clean(li.chamber_percentile),
                "votes": clean(li.votes_used),
                "window": f"{int(li.window_start)}–{int(li.window_end)}",
                "matchMethod": clean(li.identity_match_method),
            },
            "voteSmart": None if pct_profile is None else {
                "questionnaireYear": int(pct_profile.election_year),
                "exactCycle": int(pct_profile.election_year) == int(row.cycle),
                "dimensions": int(pct_profile.pct_dimensions_scored),
                "policies": int(pct_profile.pct_policies_scored),
                "candidateId": int(pct_profile.votesmart_candidate_id),
            },
            "counts": source_counts, "cells": cells, "records": candidate_records,
        })

    return {
        "generated": "August 15, 2026", "groups": GROUP_ORDER,
        "candidates": candidates,
        "method": {
            "directionalRecords": sum(r["direction"] is not None for r in records),
            "allRecords": len(records),
            "voteSmartProfiles": len(pct_profiles),
            "voteSmartMissing": len(cohort) - len(pct_profiles),
            "note": "Color uses reviewed legislative evidence plus separately labeled candidate-supplied Vote Smart PCT dimensions. Missing questionnaires remain missing.",
        },
    }


def build_page() -> str:
    payload = json.dumps(build_payload(), ensure_ascii=False, separators=(",", ":"))
    css = (ASSETS / "legislator_ideology.css").read_text(encoding="utf-8")
    js = (ASSETS / "legislator_ideology.js").read_text(encoding="utf-8")
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Alabama Legislator Issue Atlas</title><style>{css}</style></head><body>
<header><div class=\"mast\"><div><div class=\"brand\">Jackson Hannan</div><div class=\"tag\">Alabama legislative models</div></div><nav class=\"nav\" aria-label=\"Site navigation\"><a href=\"index.html\">Forecast</a><a href=\"cmo.html\">CMO</a><a href=\"legislators.html\" aria-current=\"page\">Issue atlas</a><a href=\"cmo-methodology.html\">Methodology</a><a href=\"https://github.com/JacksonAHannan\" target=\"_blank\" rel=\"me noopener\">GitHub</a></nav></div></header>
<main><section class=\"story-head\"><div class=\"kicker\">The politics behind overperformance</div><h1>What did Alabama's standout Democrats stand for?</h1><div class=\"dek\">An evidence atlas of the votes, bills, amendments, and public positions of 30 Democratic legislative candidates who substantially outran expectations from 2010 through 2022.</div><div class=\"byline\">Research and analysis by <b>Jackson Hannan</b> &nbsp;•&nbsp; August 2026</div></section>
<section class=\"status\"><div class=\"status-lead\"><span>How to read this project</span><b>Direction is not certainty</b><p>Color describes reviewed actions and candidate-supplied questionnaire positions. Opacity describes how much evidence exists; gray means we do not know.</p></div><div><b>30</b><span>Target candidates</span></div><div><b>5</b><span>Evidence types</span></div><div><b>14</b><span>Issue families</span></div></section>
<section class=\"intro\"><p>Alabama Democrats have not overperformed in only one way. Some paired support for public investment with culturally conservative votes. Others assembled records centered on labor, civil rights, local economic development, or constituent service. This page shows those combinations without forcing every career onto a single national left–right line.</p></section>
<section class=\"atlas\"><div class=\"section-head\"><div><div class=\"eyebrow\">Comparative view</div><h2>The issue mosaic</h2></div><p>Choose a cell to inspect the candidate and the evidence behind that issue.</p></div><div class=\"toolbar\"><label>Find a candidate<input id=\"search\" type=\"search\" placeholder=\"Name, chamber, or district\"></label><label>Order by<select id=\"sort\"><option value=\"cmo\">CMO, highest first</option><option value=\"coverage\">Evidence coverage</option><option value=\"name\">Candidate name</option><option value=\"cycle\">Election year</option></select></label><label>Evidence timing<select id=\"timing\"><option value=\"all\">All observed years</option><option value=\"pre\">Before/during election</option><option value=\"post\">After election</option></select></label></div><div class=\"legend\"><span>More progressive</span><i class=\"swatch p2\"></i><i class=\"swatch p1\"></i><i class=\"swatch neutral\"></i><i class=\"swatch c1\"></i><i class=\"swatch c2\"></i><span>More conservative</span><em>Pattern = mixed record</em><em>Gray = no directional evidence</em></div><div class=\"heat-scroll\"><div id=\"heatmap\" class=\"heatmap\"></div></div></section>
<section class=\"profile-shell\" id=\"profile\"><div class=\"profile-empty\"><b>Select a candidate or heatmap cell</b><span>The profile will show their biography, issue record, evidence mix, and underlying sources.</span></div></section>
<section class=\"method\"><div class=\"eyebrow\">Research notes</div><h2>What this page measures—and what it does not</h2><div class=\"method-grid\"><p><b>Directional balance, not an ideology test.</b> Color combines reviewed legislative evidence with separately labeled candidate-supplied Vote Smart questionnaire dimensions.</p><p><b>Vote Smart is sparse.</b> Only four of the 30 focal candidates have a scored questionnaire available at or before the focal election. The 1994 archive has no scored questionnaire profiles. Missing responses are never coded as moderate or replaced with group ratings.</p><p><b>Public positions remain legible.</b> Campaign statements appear even when their wording has not been normalized into a directional score.</p><p><b>Timing matters.</b> The latest questionnaire no later than the focal election may be shown, with its year preserved. Later answers never leak backward.</p></div><p class=\"source-note\">This project uses LegiScan, ALISON, Vote Smart candidate-supplied Political Courage Tests, campaign materials, contemporary reporting, reviewed bill text, and the Candidate Margin Overperformance model. Read the <a href=\"cmo-methodology.html\">CMO methodology</a>.</p></section></main><div id=\"tip\" class=\"tip\"></div>
<script>const ATLAS={payload};{js}</script></body></html>"""


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_page(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
