"""Build context-aware Vote Smart evidence under ontology v3.

This does not blend sources or produce a final candidate ideology rating. It
creates questionnaire evidence rows compatible with future vote, statement,
and campaign-website evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ideology_ontology_v3 import ONTOLOGY_VERSION, family_loading, validate_primitive
from serve_votesmart_adjudication import review_id

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
ITEMS = IDEOLOGY / "votesmart_pct_item_crosswalk.csv"
CODED = IDEOLOGY / "votesmart_pct_coded_responses.csv"
AUDIT = IDEOLOGY / "votesmart_pct_full_corpus_ontology_audit.csv"
MANUAL = ROOT / "data" / "manual" / "ideology" / "votesmart_pct_multiaxis_v2_manual_adjudications.csv"
CROSSWALK = IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv"
ITEM_OUT = IDEOLOGY / "votesmart_pct_item_crosswalk_v3.csv"
EVIDENCE_OUT = IDEOLOGY / "candidate_position_evidence_v3_votesmart.csv"
FEATURE_OUT = IDEOLOGY / "votesmart_candidate_family_features_v3.csv"


def norm(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return re.sub(r"^(?:[a-z]|[0-9]+)\)\s*", "", text)


def stable_item_id(row: pd.Series) -> str:
    source = "|".join(str(row.get(field, "")) for field in
                      ["election_year", "section", "question", "option_text"])
    return hashlib.sha256(source.encode()).hexdigest()[:16].upper()


def one(axis: str, pole: str, strength: str = "primary", rationale: str = "legacy deterministic rule") -> list[dict]:
    validate_primitive(axis, pole)
    return [{"axis": axis, "pole": pole, "strength": strength, "rationale": rationale}]


def migrate_legacy_rule(row: pd.Series) -> tuple[list[dict], list[str]]:
    key, dimension = str(row.policy_key), str(row.dimension)
    direction = float(row.affirmative_direction)
    tags: list[str] = []
    if dimension == "abortion_position":
        return one("abortion_access", "restrict" if direction > 0 else "expand"), tags
    if dimension == "guns_position":
        if key in {"guns_background_checks", "guns_license"}:
            return one("gun_purchase_regulation", "strengthen"), tags
        return one("gun_access", "expand" if direction > 0 else "restrict"), tags
    if dimension == "criminal_justice_position":
        return one("criminal_punishment", "punitive" if direction > 0 else "rehabilitative"), tags
    if dimension == "immigration_position":
        return one("immigration_access", "restrict" if direction > 0 else "expand"), tags
    if dimension == "labor_position":
        return one("labor_capital_alignment", "capital_management" if direction > 0 else "labor"), tags
    if dimension == "social_ideology":
        if key == "social_same_sex_marriage":
            # The response sign records whether the candidate agreed with the
            # item.  The effect therefore describes the affirmative proposal,
            # rather than the old broad left/right direction.
            return one("christian_sexual_morality", "sexual_pluralism_autonomy"), tags
        if key == "social_marriage_restriction":
            return one("christian_sexual_morality", "traditional_morality"), tags
        if key == "restrict_marriage_to_opposite_sex":
            return one("christian_sexual_morality", "traditional_morality"), tags
        if key == "social_abstinence_education":
            return one("christian_sexual_morality", "traditional_morality"), tags
        if key == "social_comprehensive_sex_education":
            return one("christian_sexual_morality", "sexual_pluralism_autonomy"), tags
        if key == "social_stem_cell_research":
            return one("abortion_access", "expand"), tags
        if key == "social_confederate_monument_removal":
            return one("racial_civil_rights", "expand"), tags
        if key in {"social_low_income_childcare", "social_head_start"}:
            return one("childcare_support", "expansion"), tags
        if key in {"social_at_risk_youth_services", "social_at_risk_youth_programs"}:
            return one("welfare_generosity", "expand"), tags
        if key in {
            "social_voluntary_school_prayer",
            "social_moment_of_silence",
            "social_religious_display",
        }:
            return one("religion_state", "accommodation_establishment"), tags
        if key in {
            "social_sexual_orientation_protection",
            "social_sexual_orientation_inclusion",
            "social_gender_identity_inclusion",
        }:
            return one("christian_sexual_morality", "sexual_pluralism_autonomy"), tags
        if key == "social_affirmative_action":
            return one("racial_civil_rights", "expand"), tags
        return one("civil_social_liberty", "restrict" if direction > 0 else "expand"), tags
    if dimension == "government_reform_position":
        if "identification" in key or "photo_id" in key:
            return one("voting_access", "restrict"), tags
        if "balanced_budget" in key:
            return one("deficit_discipline", "fiscal_restraint"), tags
        return [], tags
    if dimension == "education_position":
        if key.startswith("spending_"):
            return one("education_public_funding", "expand"), tags
        if any(token in key for token in ["voucher", "choice", "charter"]):
            return one("education_market_choice", "expand"), tags
        if "testing" in key or "standards" in key:
            return one("education_accountability", "strengthen"), tags
        return [], tags
    if dimension == "healthcare_position":
        if "tort" in key or "damage" in key:
            return one("malpractice_liability", "limit_damages"), tags
        if "managed_care" in key:
            return one("medicaid_structure", "managed_care"), tags
        return one("healthcare_access", "restrict" if direction > 0 else "expand"), tags
    if dimension == "environment_position":
        if any(token in key for token in ["traditional_energy", "keystone"]):
            tags.append("extractive_industry")
            return one("resource_development", "expand"), tags
        if any(token in key for token in ["renewable", "alternative_energy", "alternative_fuel"]):
            return one("renewable_energy_support", "expand"), tags
        if "open_space" in key:
            return one("conservation_preservation", "preserve"), tags
        if any(token in key for token in ["takings", "compensate", "property"]):
            return one("land_use_property_rights", "property_rights"), tags
        return one("environmental_protection", "weaken" if direction > 0 else "strengthen"), tags
    if dimension == "economic_ideology":
        if key.startswith("tax_"):
            if any(token in key for token in ["lower", "low_family"]): tags.append("low_income")
            if any(token in key for token in ["middle", "mid"]): tags.append("middle_income")
            if any(token in key for token in ["upper", "high", "capital", "estate", "inheritance"]): tags.append("high_income")
            return one("tax_burden", "increase"), tags
        if key == "spending_welfare":
            return one("welfare_generosity", "expand"), tags
        if "welfare" in key or "tanf" in key:
            if any(token in key for token in ["work_requirement", "drug_test", "time_limit", "family_cap"]):
                return one("welfare_conditionality", "strengthen_conditions"), tags
            return one("welfare_generosity", "restrict" if direction > 0 else "expand"), tags
        if "privat" in key:
            return one("public_private_provision", "private_provision"), tags
        if "small_business" in key:
            tags.append("small_business")
        if any(token in key for token in ["regulation", "lower_taxes_growth", "flat_tax"]):
            return one("market_governance", "market_autonomy"), tags
        if any(token in key for token in ["government_spending", "business_incentive", "job_training", "homeowner_assistance"]):
            return one("market_governance", "intervention"), tags
    return [], tags


def build_item_map() -> pd.DataFrame:
    items = pd.read_csv(ITEMS).fillna("")
    audit = pd.read_csv(AUDIT).fillna("")
    keys = ["election_year", "section", "question", "option_text"]
    items = items.merge(audit[keys + ["policy_family", "normalized_option"]], on=keys,
                        how="left", validate="one_to_one")
    manual = pd.read_csv(MANUAL).fillna("")
    manual_map = {str(row.review_id): row for row in manual.itertuples(index=False)}
    rows = []
    for _, item in items.iterrows():
        year = item.election_year
        rid = review_id(year, norm(item.option_text)) if str(year) else ""
        effects: list[dict] = []
        tags: list[str] = []
        authority = "unreviewed"
        response_mode = str(item.response_mode or "binary")
        if rid in manual_map:
            decision = manual_map[rid]
            for position_effect in json.loads(decision.effects_json or "[]"):
                if position_effect["axis"] == "business_scale_alignment":
                    tags.append(position_effect["pole"])
                else:
                    effects.append(position_effect)
            response_mode = decision.response_mode or response_mode
            authority = "direct_text_review"
            policy_key = decision.policy_key
        elif item.coding_status == "rule_mapped":
            effects, tags = migrate_legacy_rule(item)
            authority = "legacy_deterministic_migrated" if effects else "legacy_rule_requires_v3_review"
            policy_key = item.policy_key
        else:
            policy_key = item.policy_key
            if item.coding_status in {"non_scorable", "position_only"}:
                authority = f"legacy_{item.coding_status}"
        for position_effect in effects:
            validate_primitive(position_effect["axis"], position_effect["pole"])
        row = item.to_dict()
        row.update({
            "ontology_version": ONTOLOGY_VERSION, "item_id_v3": stable_item_id(item),
            "review_id": rid, "policy_key_v3": policy_key,
            "effects_json_v3": json.dumps(effects, separators=(",", ":")),
            "constituency_tags_json": json.dumps(tags), "response_mode_v3": response_mode,
            "mapping_authority_v3": authority,
            "mapped_effects_v3": len(effects),
            "score_eligible_v3": bool(effects and authority in {"direct_text_review", "legacy_deterministic_migrated"}),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def build_evidence(item_map: pd.DataFrame) -> pd.DataFrame:
    coded = pd.read_csv(CODED, low_memory=False).fillna("")
    keys = ["election_year", "section", "question", "option_text"]
    fields = keys + ["item_id_v3", "policy_family", "policy_key_v3", "effects_json_v3",
                     "constituency_tags_json", "response_mode_v3", "mapping_authority_v3",
                     "score_eligible_v3"]
    joined = coded.drop(columns=[c for c in fields if c in coded and c not in keys], errors="ignore").merge(
        item_map[fields], on=keys, how="left", validate="many_to_one")
    joined["response_value"] = pd.to_numeric(joined.response_sign, errors="coerce")
    joined = joined[joined.response_value.notna() & joined.score_eligible_v3.eq(True)].copy()
    crosswalk = pd.read_csv(CROSSWALK).fillna("")
    crosswalk = crosswalk[crosswalk.accepted.eq(True)][
        ["votesmart_candidate_id", "election_year", "canonical_candidate_id", "person_id",
         "canonical_candidate", "chamber", "district", "party"]].copy()
    crosswalk.votesmart_candidate_id = pd.to_numeric(crosswalk.votesmart_candidate_id, errors="coerce")
    crosswalk.election_year = pd.to_numeric(crosswalk.election_year, errors="coerce")
    joined.votesmart_candidate_id = pd.to_numeric(joined.votesmart_candidate_id, errors="coerce")
    joined.election_year = pd.to_numeric(joined.election_year, errors="coerce")
    joined = joined.merge(crosswalk, on=["votesmart_candidate_id", "election_year"], how="left")
    rows = []
    for record in joined.itertuples(index=False):
        for position_effect in json.loads(record.effects_json_v3 or "[]"):
            axis, pole = position_effect["axis"], position_effect["pole"]
            family, loading = family_loading(axis, pole)
            stance = "support" if record.response_value > 0 else "oppose" if record.response_value < 0 else "maintain"
            evidence_id = hashlib.sha256(
                f"votesmart|{record.votesmart_candidate_id}|{record.item_id_v3}|{axis}|{pole}".encode()
            ).hexdigest()[:20].upper()
            rows.append({
                "ontology_version": ONTOLOGY_VERSION, "evidence_id": evidence_id,
                "canonical_candidate_id": record.canonical_candidate_id,
                "person_id": record.person_id, "candidate_name": record.candidate,
                "election_cycle": record.election_year, "evidence_date": "",
                "temporal_status": "same_cycle_candidate_statement",
                "source_type": "candidate_questionnaire", "source_provider": "Vote Smart",
                "source_record_id": record.votesmart_candidate_id, "source_url": record.source_url,
                "item_id": record.item_id_v3, "policy_family": record.policy_family,
                "policy_key": record.policy_key_v3, "primitive_axis": axis, "policy_pole": pole,
                "candidate_stance": stance, "position_value": record.response_value,
                "response_mode": record.response_mode_v3, "family": family or "",
                "family_direction": loading if loading is not None else np.nan,
                "family_contribution": loading * record.response_value if loading is not None else np.nan,
                "constituency_tags_json": record.constituency_tags_json,
                "confidence": "high" if record.mapping_authority_v3 == "direct_text_review" else "medium",
                "adjudication_authority": record.mapping_authority_v3,
                "evidence_weight": 1.0 if record.mapping_authority_v3 == "direct_text_review" else 0.9,
                "source_text": record.option_text, "raw_answer": record.raw_answer,
            })
    return pd.DataFrame(rows)


def candidate_features(evidence: pd.DataFrame) -> pd.DataFrame:
    eligible = evidence[evidence.canonical_candidate_id.astype(str).ne("") & evidence.family.astype(str).ne("")].copy()
    policy = eligible.groupby(
        ["canonical_candidate_id", "person_id", "election_cycle", "family", "policy_key"],
        as_index=False,
    ).agg(policy_score=("family_contribution", "mean"), evidence_rows=("evidence_id", "nunique"))
    family = policy.groupby(
        ["canonical_candidate_id", "person_id", "election_cycle", "family"], as_index=False
    ).agg(family_score=("policy_score", "mean"), policies_observed=("policy_key", "nunique"),
          evidence_rows=("evidence_rows", "sum"))
    wide = family.pivot_table(index=["canonical_candidate_id", "person_id", "election_cycle"],
                              columns="family", values="family_score").reset_index()
    counts = family.groupby(["canonical_candidate_id", "person_id", "election_cycle"], as_index=False).agg(
        families_observed=("family", "nunique"), policies_observed=("policies_observed", "sum"),
        evidence_rows=("evidence_rows", "sum"))
    return wide.merge(counts, on=["canonical_candidate_id", "person_id", "election_cycle"], validate="one_to_one")


def main() -> None:
    item_map = build_item_map()
    evidence = build_evidence(item_map)
    features = candidate_features(evidence)
    item_map.to_csv(ITEM_OUT, index=False)
    evidence.to_csv(EVIDENCE_OUT, index=False)
    features.to_csv(FEATURE_OUT, index=False)
    print(f"V3 item mappings: {item_map.score_eligible_v3.sum():,} / {len(item_map):,}")
    print(f"Questionnaire evidence effects: {len(evidence):,}")
    print(f"Canonical candidate-cycle profiles: {len(features):,}")
    print("These are questionnaire-only family features, not final multi-source ratings.")


if __name__ == "__main__":
    main()
