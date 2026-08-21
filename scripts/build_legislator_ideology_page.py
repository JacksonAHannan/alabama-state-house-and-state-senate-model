"""Build the public evidence atlas for the CMO research cohort.

The page deliberately separates directional balance from evidence coverage.  It
uses only human-reviewed directional codes for color; uncoded public positions
remain visible in candidate records but do not silently become ideology scores.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ideology_ontology_v3 import primitive_axis_direction


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

FRONTIER_GROUPS = {
    "abortion_access": "Abortion", "abortion_public_funding": "Abortion",
    "gun_access": "Guns", "gun_purchase_regulation": "Guns",
    "labor_rights": "Labor & wages", "labor_capital_alignment": "Labor & wages",
    "public_employee_compensation": "Labor & wages",
    "education_public_funding": "Public education", "education_access": "Public education",
    "education_accountability": "Public education", "education_market_choice": "School choice",
    "tax_burden": "Taxes & spending", "tax_distribution": "Taxes & spending",
    "public_spending": "Taxes & spending", "deficit_discipline": "Taxes & spending",
    "market_governance": "Economic development", "business_subsidy": "Economic development",
    "public_private_provision": "Economic development",
    "healthcare_access": "Health care", "healthcare_public_responsibility": "Health care",
    "healthcare_delivery": "Health care", "medicaid_structure": "Health care",
    "criminal_punishment": "Criminal justice", "incarceration": "Criminal justice",
    "due_process": "Criminal justice", "police_authority": "Criminal justice",
    "drug_criminalization": "Criminal justice", "drug_treatment": "Criminal justice",
    "immigration_access": "Immigration", "immigration_enforcement": "Immigration",
    "immigrant_public_benefits": "Immigration", "national_language_identity": "Immigration",
    "christian_sexual_morality": "Civil & cultural rights",
    "civil_social_liberty": "Civil & cultural rights", "racial_civil_rights": "Civil & cultural rights",
    "anti_discrimination": "Civil & cultural rights", "affirmative_action": "Civil & cultural rights",
    "religion_state": "Civil & cultural rights", "confederate_commemoration": "Civil & cultural rights",
    "voting_access": "Government & ethics", "election_integrity_controls": "Government & ethics",
    "campaign_finance_disclosure": "Government & ethics",
    "government_ethics_transparency": "Government & ethics",
    "environmental_protection": "Environment & infrastructure",
    "conservation_preservation": "Environment & infrastructure",
    "resource_development": "Environment & infrastructure", "climate_energy": "Environment & infrastructure",
    "renewable_energy_support": "Environment & infrastructure",
    "hunting_rural_recreation": "Rural & local interests", "gambling_policy": "Rural & local interests",
}

# Convert the ontology's issue-specific first-pole coordinate into the page's
# display scale (-1 progressive, +1 conservative). None means the issue has no
# honest general left/right display direction and remains visible but uncolored.
CONSERVATIVE_SIGN = {
    "abortion_access": -1, "abortion_public_funding": -1,
    "gun_access": 1, "gun_purchase_regulation": -1,
    "labor_rights": -1, "labor_capital_alignment": -1, "public_employee_compensation": -1,
    "education_public_funding": -1, "education_access": -1,
    "education_accountability": 1, "education_market_choice": 1,
    "tax_burden": -1, "tax_distribution": -1, "public_spending": -1,
    "deficit_discipline": 1, "market_governance": -1, "public_private_provision": -1,
    "healthcare_access": -1, "healthcare_public_responsibility": -1,
    "criminal_punishment": 1, "incarceration": 1, "due_process": -1,
    "police_authority": 1, "drug_criminalization": 1, "drug_treatment": -1,
    "immigration_access": -1, "immigration_enforcement": 1,
    "immigrant_public_benefits": -1, "national_language_identity": 1,
    "christian_sexual_morality": 1, "civil_social_liberty": -1,
    "racial_civil_rights": -1, "anti_discrimination": -1, "affirmative_action": -1,
    "religion_state": 1, "voting_access": -1, "election_integrity_controls": 1,
    "campaign_finance_disclosure": -1, "government_ethics_transparency": -1,
    "environmental_protection": -1, "conservation_preservation": -1,
    "resource_development": 1, "climate_energy": -1, "renewable_energy_support": -1,
    "hunting_rural_recreation": 1,
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

    frontier_path = ROOT / "data" / "processed" / "ideology" / "candidate_legislative_position_evidence_v3.csv"
    frontier_votes = pd.read_csv(frontier_path, low_memory=False).fillna("")
    for _, row in frontier_votes.iterrows():
        axis_direction = primitive_axis_direction(row.primitive_axis, row.policy_pole)
        sign = CONSERVATIVE_SIGN.get(row.primitive_axis)
        valence = None if axis_direction is None or sign is None else float(row.position_value) * axis_direction * sign
        add_record(
            records, person_id=row.person_id, issue=row.primitive_axis,
            group=FRONTIER_GROUPS.get(row.primitive_axis, row.primitive_axis.replace("_", " ").title()),
            source_type="Frontier-reviewed roll call", direction=valence, weight=1.0,
            confidence=row.confidence, timing=row.temporal_status, date=row.evidence_date,
            evidence_cycle=pd.to_numeric(row.election_cycle, errors="coerce"),
            bill=row.policy_key, summary=row.source_text, url=row.source_url,
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
        candidate_records = [record for record in by_person.get(pid, [])
                             if record.get("evidence_cycle") is None
                             or pd.isna(record.get("evidence_cycle"))
                             or record["evidence_cycle"] <= row.cycle]
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
<header><div class=\"mast\"><div><div class=\"brand\">Jackson Hannan</div><div class=\"tag\">Alabama legislative models</div></div><nav class=\"nav\" aria-label=\"Site navigation\"><a href=\"index.html\">Forecast</a><a href=\"cmo.html\">CMO</a><a href=\"ideology-performance.html\">Issues & caucuses</a><a href=\"legislators.html\" aria-current=\"page\">Issue atlas</a><a href=\"cmo-methodology.html\">Methodology</a><a href=\"https://github.com/JacksonAHannan\" target=\"_blank\" rel=\"me noopener\">GitHub</a></nav></div></header>
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
