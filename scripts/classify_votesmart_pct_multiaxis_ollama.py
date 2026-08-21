"""Classify the 114 CMO-relevant Vote Smart items with a model cascade.

Two small local models make independent first passes. A larger model sees only
items where those passes disagree, report low confidence, or request review.
Outputs are proposals for human adjudication and never alter legacy scores.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

from serve_votesmart_adjudication import load_items
from votesmart_position_ontology import (
    AXES, CONFIDENCE_LEVELS, DOMAINS, EFFECT_STRENGTHS, ONTOLOGY_VERSION,
    canonical_effects, ontology_for_prompt, validate_effect,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "ideology"
CACHE = ROOT / "research" / "cmo_ideology" / "votesmart_pct_multiaxis_v2"
CLASS_OUT = OUT / "votesmart_pct_multiaxis_v2_classifications.csv"
CONSENSUS_OUT = OUT / "votesmart_pct_multiaxis_v2_consensus.csv"
DEFAULT_INITIAL_MODELS = ["gemma2:2b", "alibayram/smollm3:latest"]
DEFAULT_ESCALATION_MODEL = "ministral-3:8b"

SCHEMA = {
    "type": "object",
    "properties": {
        "primary_domain": {"type": "string", "enum": DOMAINS},
        "policy_key": {"type": "string"},
        "plain_english_policy": {"type": "string"},
        "substantive": {"type": "boolean"},
        "effects": {
            "type": "array", "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "axis": {"type": "string", "enum": list(AXES)},
                    "pole": {"type": "string"},
                    "strength": {"type": "string", "enum": EFFECT_STRENGTHS},
                    "rationale": {"type": "string"},
                },
                "required": ["axis", "pole", "strength", "rationale"],
            },
        },
        "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
        "evidence_quote": {"type": "string"},
        "needs_human_review": {"type": "boolean"},
        "review_reason": {"type": "string"},
    },
    "required": ["primary_domain", "policy_key", "plain_english_policy",
                 "substantive", "effects", "confidence", "evidence_quote",
                 "needs_human_review", "review_reason"],
}


def prompt(item: dict) -> str:
    return f"""Classify one historical Alabama candidate-questionnaire option descriptively.
Do not label it progressive, conservative, left, or right. Do not infer facts beyond the
source. Assign zero to four policy effects. Multiple effects are expected when warranted.
Every pole must be one of the listed poles for its axis. Use business_scale_alignment only
when the wording explicitly distinguishes small from large business. Distinguish actual
environmental protection, preservation, resource management/development, property rights,
and hunting or rural recreation. Treat childcare as its own domain. An evidence quote must
be a short verbatim substring of the source. Mark vague priorities and context-free labels
for human review.

Code the policy mechanism actually stated, not a speculative downstream effect. A tax credit
for employers that provide childcare is childcare_delivery=employer_incentive, not public
provision. Public provision means government directly operates or supplies the service.
Child-support collection is family_support_enforcement, not childcare delivery. Tax
distribution refers to who bears taxes, not whether any tax credit might reduce inequality.

ONTOLOGY VERSION: {ONTOLOGY_VERSION}
ALLOWED AXES AND POLES:
{ontology_for_prompt()}

SOURCE:
Year: {item['election_year']}
Section: {item['section']}
Question: {item['question']}
Option: {item['option_text']}
"""


def call_model(model: str, text: str) -> dict:
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({"model": model, "prompt": text, "stream": False,
                         "think": False, "format": SCHEMA,
                         "options": {"temperature": 0, "seed": 20260816}}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                envelope = json.load(response)
            return json.loads(envelope.get("response") or envelope.get("thinking") or "")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError, ValueError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"{model} failed after three attempts: {error}")


def sanitize_result(result: dict) -> tuple[dict, list[str]]:
    """Keep valid model content while surfacing invalid ontology effects."""
    valid, errors = [], []
    for effect in result.get("effects", []):
        try:
            validate_effect(effect)
            valid.append(effect)
        except ValueError as exc:
            errors.append(str(exc))
    result["effects"] = valid
    if errors:
        result["needs_human_review"] = True
        result["confidence"] = "low"
        prior = str(result.get("review_reason", "")).strip()
        result["review_reason"] = "; ".join(filter(None, [prior, *errors]))
    return result, errors


def safe_model_name(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def classify(items: list[dict], model: str, stage: str) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = []
    for number, item in enumerate(items, 1):
        path = CACHE / f"{ONTOLOGY_VERSION}_{item['review_id']}_{safe_model_name(model)}.json"
        try:
            result = json.loads(path.read_text(encoding="utf-8")) if path.exists() else call_model(model, prompt(item))
            result, ontology_errors = sanitize_result(result)
            if not path.exists():
                path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            error = "; ".join(ontology_errors)
        except Exception as exc:
            result = {"primary_domain": "other", "policy_key": "", "plain_english_policy": "",
                      "substantive": False, "effects": [], "confidence": "low",
                      "evidence_quote": "", "needs_human_review": True,
                      "review_reason": str(exc)}
            error = f"{type(exc).__name__}: {exc}"
        source = " ".join([item["section"], item["question"], item["option_text"]]).lower()
        quote = str(result.get("evidence_quote", "")).strip().strip('"').lower()
        rows.append({
            "ontology_version": ONTOLOGY_VERSION, "review_id": item["review_id"],
            "election_year": item["election_year"], "section": item["section"],
            "question": item["question"], "option_text": item["option_text"],
            "candidate_count": item["candidate_count"], "stage": stage, "model": model,
            **{key: value for key, value in result.items() if key != "effects"},
            "effects_json": json.dumps(result.get("effects", []), separators=(",", ":")),
            "effect_signature": json.dumps(canonical_effects(result)),
            "evidence_quote_verified": bool(quote and quote in source),
            "classification_error": error,
            "classification_cache": str(path.relative_to(ROOT)),
        })
        print(f"{stage} {model} {number}/{len(items)} {item['review_id']}", flush=True)
    return rows


def initial_agreement(group: pd.DataFrame) -> bool:
    if len(group) != 2 or group.classification_error.fillna("").ne("").any():
        return False
    fields = ["primary_domain", "substantive", "effect_signature"]
    return all(group[field].nunique(dropna=False) == 1 for field in fields)


def needs_escalation(group: pd.DataFrame) -> bool:
    return (not initial_agreement(group) or group.confidence.eq("low").any()
            or group.needs_human_review.eq(True).any()
            or ~group.evidence_quote_verified.eq(True).all())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--initial-models", nargs=2, default=DEFAULT_INITIAL_MODELS)
    parser.add_argument("--escalation-model", default=DEFAULT_ESCALATION_MODEL)
    parser.add_argument("--no-escalation", action="store_true")
    args = parser.parse_args()
    items = load_items()
    if args.limit is not None:
        items = items[:args.limit]
    initial_rows = []
    for model in args.initial_models:
        initial_rows.extend(classify(items, model, "initial"))
    initial = pd.DataFrame(initial_rows)
    escalation_ids = {
        identifier for identifier, group in initial.groupby("review_id")
        if needs_escalation(group)
    }
    escalation_rows = []
    if not args.no_escalation and escalation_ids:
        escalation_items = [item for item in items if item["review_id"] in escalation_ids]
        escalation_rows = classify(escalation_items, args.escalation_model, "escalation")
    frame = pd.concat([initial, pd.DataFrame(escalation_rows)], ignore_index=True, sort=False)
    frame.to_csv(CLASS_OUT, index=False)
    consensus = []
    for identifier, group in initial.groupby("review_id"):
        first = group.iloc[0]
        agree = initial_agreement(group)
        consensus.append({
            "ontology_version": ONTOLOGY_VERSION, "review_id": identifier,
            "election_year": first.election_year, "section": first.section,
            "question": first.question, "option_text": first.option_text,
            "candidate_count": first.candidate_count, "initial_models_agree": agree,
            "escalated": identifier in escalation_ids and not args.no_escalation,
            "initial_effect_signature": first.effect_signature if agree else "",
            "human_review_required": True,
        })
    pd.DataFrame(consensus).to_csv(CONSENSUS_OUT, index=False)
    print(f"Initial passes: {len(items):,} items x {len(args.initial_models)} small models")
    print(f"Escalation queue: {len(escalation_ids):,} items")
    print("No classifications were imported into candidate scores.")


if __name__ == "__main__":
    main()
