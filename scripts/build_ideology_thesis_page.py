"""Build the absolute-ideology and candidate-overperformance release candidate."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
OUTPUT = ROOT / "artifacts" / "site" / "ideology-performance.html"

ISSUES = {
    "market_governance": ("Market autonomy", "Government intervention", "Market autonomy", "Whether economic activity should be directed by government or left more to private markets."),
    "gun_access": ("Gun access", "Restricted access", "Expanded access", "Support for carrying, owning, and accessing firearms. This is separate from purchase-screening regulation."),
    "gun_purchase_regulation": ("Gun purchase rules", "Stronger regulation", "Weaker regulation", "Background checks, purchase restrictions, and other rules governing firearm acquisition."),
    "abortion_access": ("Abortion access", "Expanded access", "Restricted access", "Legal availability of abortion, including restrictions incorporated from related bioethics evidence."),
    "marriage_equality": ("Marriage equality", "Expanded equality", "Traditional restriction", "Recognition of same-sex marriage and related legal equality."),
    "civil_social_liberty": ("Christian sexual morality", "Broader private liberty", "Traditional regulation", "Traditional marriage, sexual-conduct rules, abstinence policy, and LGBTQ+ autonomy. Racial civil rights are excluded."),
    "racial_civil_rights": ("Racial civil rights", "Expanded protections", "Restricted protections", "Racial equality, affirmative remedies, and civil-rights protections. Guns and sexual morality are excluded."),
    "anti_discrimination": ("Anti-discrimination", "Expanded protections", "Restricted protections", "Statutory protections against discrimination across covered groups."),
    "religion_state": ("Religion and state", "Separation", "Accommodation", "Government accommodation or establishment of religious practice versus stricter institutional separation."),
    "criminal_punishment": ("Criminal punishment", "Rehabilitation", "Punitive enforcement", "Sentencing severity and punishment-oriented responses, distinct from gun policy."),
    "due_process": ("Due process", "Stronger safeguards", "Weaker safeguards", "Procedural protections for defendants and people subject to state enforcement."),
    "drug_criminalization": ("Drug criminalization", "Decriminalization", "Criminalization", "Whether drug conduct should receive criminal penalties rather than treatment or civil handling."),
    "tax_burden": ("Tax burden", "Higher burden", "Lower burden", "Whether the measured proposal raises or lowers taxes. This does not identify which taxpayers bear the change."),
    "tax_distribution": ("Who bears taxes", "Progressive distribution", "Regressive distribution", "Whether tax burdens shift toward higher-income or lower-income taxpayers; kept separate from total burden."),
    "public_spending": ("Public spending", "Expanded spending", "Reduced spending", "Overall public expenditure direction rather than the beneficiary of a particular program."),
    "deficit_discipline": ("Deficit discipline", "Fiscal flexibility", "Fiscal restraint", "Preference for tight budget balance and restraint rather than flexibility during fiscal pressure."),
    "welfare_generosity": ("Material support", "Expanded support", "Restricted support", "Generosity of direct public assistance and social benefits."),
    "welfare_conditionality": ("Benefit conditions", "Relaxed conditions", "Stronger conditions", "Work, eligibility, and behavioral conditions attached to public benefits."),
    "labor_capital_alignment": ("Labor or management", "Labor alignment", "Management alignment", "Whose bargaining and institutional interests receive priority."),
    "labor_rights": ("Labor rights", "Expanded rights", "Restricted rights", "Collective bargaining, organizing, and workplace rights."),
    "public_employee_compensation": ("Public employee benefits", "Protected compensation", "Reduced compensation", "Pay and benefit protections for public employees."),
    "education_public_funding": ("Public-school funding", "Expanded funding", "Reduced funding", "Support for public-school appropriations and resources."),
    "education_market_choice": ("School choice", "Restricted choice", "Expanded choice", "Charters, vouchers, and other market-oriented alternatives to assigned public schools."),
    "healthcare_access": ("Health-care access", "Expanded access", "Restricted access", "Public responsibility for affordable health coverage and access."),
    "environmental_protection": ("Environmental protection", "Stronger protection", "Weaker protection", "Regulatory and preservation measures protecting environmental resources."),
    "resource_development": ("Resource development", "Restricted development", "Expanded development", "Extraction and development of land, energy, and natural resources."),
    "conservation_preservation": ("Conservation", "Preservation", "Development priority", "Conservation and preservation versus development or property-use priority."),
    "immigration_access": ("Immigration access", "Expanded access", "Restricted access", "Access and inclusion for immigrants rather than enforcement severity."),
    "immigration_enforcement": ("Immigration enforcement", "Relaxed enforcement", "Stronger enforcement", "State support for enforcement and restriction of unauthorized immigration."),
    "government_ethics_transparency": ("Ethics and transparency", "Stronger safeguards", "Weaker safeguards", "Disclosure, ethics enforcement, and transparency requirements."),
    "voting_access": ("Voting access", "Expanded access", "Restricted access", "Rules affecting access to registration and voting."),
}


def clean_records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


def payload() -> dict:
    panel = pd.read_csv(RESEARCH / "absolute_rebuild_panel.csv", low_memory=False)
    estimates = pd.read_csv(RESEARCH / "absolute_rebuild_estimates.csv")
    issue = pd.read_csv(RESEARCH / "absolute_rebuild_issue_estimates.csv")
    coverage = pd.read_csv(RESEARCH / "absolute_rebuild_coverage.csv")
    overlap = pd.read_csv(RESEARCH / "absolute_rebuild_overlap.csv")
    selection = pd.read_csv(RESEARCH / "absolute_rebuild_selection.csv")
    durability = pd.read_csv(RESEARCH / "absolute_rebuild_durability.csv")

    absolute = estimates[
        estimates.specification.eq("party_total_context")
        & estimates.term.eq("absolute_conservatism_z")
        & estimates.outcome.isin(["candidate_cmo", "candidate_statewide_overperformance",
                                  "candidate_federal_overperformance", "candidate_presidential_overperformance"])]
    mediator = estimates[
        estimates.specification.isin(["party_total_context", "party_mediator_adjusted"])
        & estimates.term.eq("absolute_conservatism_z")
        & estimates.outcome.isin(["candidate_cmo", "candidate_federal_overperformance",
                                  "candidate_presidential_overperformance"])]
    incumbency = estimates[
        estimates.specification.isin(["common_incumbency", "party_specific_incumbency"])
        & estimates.term.isin(["incumbent_i", "democratic_x_incumbency"])]
    era = estimates[
        estimates.specification.eq("party_era_context")
        & estimates.term.eq("absolute_conservatism_z")
        & estimates.outcome.isin(["candidate_cmo", "candidate_quality_index",
                                  "candidate_federal_overperformance"])]
    robustness = estimates[
        estimates.specification.isin(["party_winners_only", "party_prior_service_only", "party_leave_cycle_out"])
        & estimates.term.eq("absolute_conservatism_z")
        & estimates.outcome.isin(["candidate_cmo", "candidate_federal_overperformance"])]

    primitive = issue[
        issue.specification.str.startswith("issue_total:primitive:")
        & issue.term.str.startswith("primitive_conservative_")
        & issue.outcome.isin(["candidate_federal_overperformance", "candidate_presidential_overperformance"])] .copy()
    primitive["issue"] = primitive.specification.str.replace("issue_total:primitive:", "", regex=False)
    primitive = primitive[primitive.issue.isin(ISSUES)]
    direct_issue = issue[
        issue.specification.str.startswith("issue_mediator_adjusted:primitive:")
        & issue.term.str.startswith("primitive_conservative_")
        & issue.outcome.isin(["candidate_federal_overperformance", "candidate_presidential_overperformance"])] .copy()
    direct_issue["issue"] = direct_issue.specification.str.replace("issue_mediator_adjusted:primitive:", "", regex=False)
    direct_issue = direct_issue[direct_issue.issue.isin(ISSUES)]
    congruence = issue[
        issue.specification.str.startswith("issue_district_congruence:primitive:")
        & issue.term.str.startswith("primitive_congruence_")
        & issue.outcome.isin(["candidate_federal_overperformance", "candidate_presidential_overperformance"])] .copy()
    congruence["issue"] = congruence.specification.str.replace("issue_district_congruence:primitive:", "", regex=False)
    congruence = congruence[congruence.issue.isin(ISSUES)]

    shor_points = panel[panel.absolute_conservatism_z.notna()][[
        "canonical_candidate_id", "canonical_name", "party", "cycle", "chamber", "district",
        "absolute_conservatism_z", "candidate_cmo", "candidate_federal_overperformance",
        "candidate_presidential_overperformance", "winner", "incumbent_i", "served_by_election"]]
    issue_rows = []
    for key in ISSUES:
        column = f"primitive_conservative_{key}"
        if column not in panel:
            continue
        for row in panel[panel[column].notna()].itertuples(index=False):
            issue_rows.append({"issue": key, "id": row.canonical_candidate_id, "name": row.canonical_name,
                               "party": row.party, "cycle": int(row.cycle), "chamber": row.chamber,
                               "district": int(row.district), "position": getattr(row, column),
                               "federal": row.candidate_federal_overperformance,
                               "presidential": row.candidate_presidential_overperformance,
                               "cmo": row.candidate_cmo, "winner": bool(row.winner)})

    dem_cmo = absolute[(absolute["sample"].eq("D")) & absolute.outcome.eq("candidate_cmo")].iloc[0]
    dem_federal = absolute[(absolute["sample"].eq("D")) & absolute.outcome.eq("candidate_federal_overperformance")].iloc[0]
    rep_cmo = absolute[(absolute["sample"].eq("R")) & absolute.outcome.eq("candidate_cmo")].iloc[0]
    selected_d = selection[selection.party.eq("D") & selection.shor_observed.eq(True)].iloc[0]
    issue_meta = [{"key": key, "label": value[0], "liberal": value[1],
                   "conservative": value[2], "description": value[3]} for key, value in ISSUES.items()]
    return {"stats": {"demCmo": dem_cmo.coefficient, "demFederal": dem_federal.coefficient,
                       "repCmo": rep_cmo.coefficient, "shorN": int(len(shor_points)),
                       "demWinnerShare": selected_d.winner_share,
                       "commonSupport": int(overlap.inside_common_support.sum())},
            "absolute": clean_records(absolute), "mediator": clean_records(mediator),
            "incumbency": clean_records(incumbency), "era": clean_records(era),
            "robustness": clean_records(robustness), "issues": clean_records(primitive),
            "issueDirect": clean_records(direct_issue), "congruence": clean_records(congruence),
            "coverage": clean_records(coverage), "overlap": clean_records(overlap),
            "selection": clean_records(selection), "durability": clean_records(durability),
            "shorPoints": clean_records(shor_points), "issueRows": clean_records(pd.DataFrame(issue_rows)),
            "issueMeta": issue_meta, "built": "August 21, 2026"}



def build() -> str:
    """Compatibility entry point for the merged ideology and caucus page."""
    try:
        from scripts.build_democratic_transition_page import build as build_merged
    except ModuleNotFoundError:
        from build_democratic_transition_page import build as build_merged
    return build_merged()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
