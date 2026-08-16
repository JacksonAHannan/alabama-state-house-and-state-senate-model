"""Use two local models to draft quote-grounded focal-amendment classifications.

Outputs are a human-review queue only. They never become candidate stances without
manual adjudication, and post-election amendments are explicitly identified.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
RESEARCH = ROOT / "research" / "cmo_ideology"
MODELS = ["qwen3.5:9b", "ministral-3:8b"]
ISSUES = [
    "public_education", "school_choice", "healthcare_medicaid", "labor_unions",
    "guns", "abortion", "taxes_budget", "business_economic_development",
    "ethics_government", "lgbtq_cultural", "gambling", "infrastructure_energy",
    "health_social_services", "criminal_justice", "environment", "immigration",
    "rural_hunting", "public_employee_benefits", "assisted_dying",
    "healthcare_conscience", "public_private_partnerships",
    "occupational_licensing", "anti_esg_governance", "other",
]
SCHEMA = {
    "type": "object",
    "properties": {
        "primary_issue": {"type": "string", "enum": ISSUES},
        "secondary_issues": {"type": "array", "items": {"type": "string", "enum": ISSUES}},
        "plain_english_revision": {"type": "string"},
        "revision_direction": {"type": "string", "enum": [
            "expands_policy", "restricts_policy", "increases_funding",
            "decreases_funding", "adds_safeguard", "removes_safeguard",
            "changes_administration", "technical", "local_or_narrow",
            "mixed", "indeterminate"
        ]},
        "ideological_valence": {"type": "string", "enum": [
            "progressive", "conservative", "mixed", "nonideological", "indeterminate"
        ]},
        "candidate_position_supported": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "evidence_quotes": {"type": "array", "items": {"type": "string"}},
        "needs_human_review": {"type": "boolean"},
        "review_reason": {"type": "string"},
    },
    "required": [
        "primary_issue", "secondary_issues", "plain_english_revision",
        "revision_direction", "ideological_valence", "candidate_position_supported",
        "confidence", "evidence_quotes", "needs_human_review", "review_reason"
    ],
}


def call_model(model: str, prompt: str) -> dict:
    payload = json.dumps({
        "model": model, "prompt": prompt, "stream": False, "think": False,
        "format": SCHEMA, "options": {"temperature": 0, "seed": 20260815},
    }).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                result = json.load(response)
            content = result.get("response") or result.get("thinking") or ""
            return json.loads(content)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Ollama failed after three attempts: {last_error}")


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def quote_supported(quote: str, text: str) -> bool:
    cleaned = str(quote).strip().strip('"“”')
    return bool(cleaned) and normalize(cleaned) in normalize(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--models", nargs="+", default=MODELS)
    args = parser.parse_args()
    manifest = pd.read_csv(DATA / "focal_amendment_text_manifest.csv")
    manifest = manifest.loc[manifest.text_status.eq("extracted")].copy()
    validation = pd.read_csv(DATA / "focal_amendment_bill_link_validation.csv")
    validation = validation.loc[validation.position_inference_allowed.eq(True), ["amendment_id"]]
    manifest = manifest.merge(validation, on="amendment_id", how="inner", validate="one_to_one")
    if args.limit:
        manifest = manifest.head(args.limit)
    cache = RESEARCH / "amendment_llm_classifications"
    cache.mkdir(exist_ok=True)
    rows = []
    for record in manifest.itertuples(index=False):
        text = (ROOT / record.local_text).read_text(encoding="utf-8")
        excerpt = text[:30000]
        for model in args.models:
            safe_model = model.replace(":", "_").replace("/", "_")
            cache_path = cache / f"{int(record.amendment_id)}_{safe_model}.json"
            if cache_path.exists():
                result = json.loads(cache_path.read_text(encoding="utf-8"))
            else:
                prompt = f"""Analyze an amendment to an Alabama legislative bill using only the supplied
metadata and amendment text. Explain what the amendment itself changes. Do not assume the underlying
bill's ideology from its title, and do not claim the sponsor supports the entire bill. The candidate
position field must describe only the policy effect affirmatively advanced by offering this amendment.
If the text is procedural, too fragmentary, or depends on unseen language, mark direction and valence
indeterminate. Evidence quotes must be short verbatim passages found in AMENDMENT TEXT.

Attributed legislator: {record.candidate}
Election cycle studied: {int(record.election_cycle)}
Amendment date: {record.date}; timing: {record.activity_timing}
Bill: {record.bill_number}
Bill title: {record.bill_title}
Bill synopsis: {record.bill_description}
Amendment title: {record.title}

AMENDMENT TEXT:
{excerpt}
"""
                try:
                    result = call_model(model, prompt)
                    cache_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                except Exception as exc:
                    result = {
                        "primary_issue": "other", "secondary_issues": [],
                        "plain_english_revision": "Model classification failed.",
                        "revision_direction": "indeterminate",
                        "ideological_valence": "indeterminate",
                        "candidate_position_supported": "indeterminate",
                        "confidence": "low", "evidence_quotes": [],
                        "needs_human_review": True,
                        "review_reason": f"{type(exc).__name__}: {exc}",
                        "classification_error": True,
                    }
            quotes = result.get("evidence_quotes") or []
            rows.append({
                **record._asdict(), "model": model, **result,
                "all_quotes_verified": bool(quotes) and all(quote_supported(q, text) for q in quotes),
                "classification_cache": str(cache_path.relative_to(ROOT)),
            })
            print(f"{int(record.amendment_id)} {model}: {result.get('primary_issue')}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(RESEARCH / "amendment_llm_classifications.csv", index=False)
    consensus = []
    fields = ["primary_issue", "revision_direction", "ideological_valence"]
    for amendment_id, group in frame.groupby("amendment_id"):
        base = group.iloc[0]
        core_agreement = len(group) == len(args.models) and all(
            group[field].nunique(dropna=False) == 1 for field in fields
        )
        quotes_ok = bool(group.all_quotes_verified.all())
        consensus.append({
            "amendment_id": amendment_id, "person_id": base.person_id,
            "candidate": base.candidate, "election_cycle": base.election_cycle,
            "date": base.date, "activity_timing": base.activity_timing,
            "bill_number": base.bill_number, "amendment_title": base.title,
            "models_run": len(group), "core_fields_agree": core_agreement,
            "all_quotes_verified": quotes_ok, "eligible_for_automatic_stance": False,
            "review_priority": (
                "high_disagreement" if not core_agreement else
                "quote_failure" if not quotes_ok else
                "pre_election_agreement" if base.activity_timing == "pre_or_during_election"
                else "post_election_agreement"
            ),
        })
    pd.DataFrame(consensus).to_csv(RESEARCH / "amendment_llm_consensus_review.csv", index=False)
    print(f"Wrote {len(frame)} model classifications for {frame.amendment_id.nunique()} amendments")


if __name__ == "__main__":
    main()
