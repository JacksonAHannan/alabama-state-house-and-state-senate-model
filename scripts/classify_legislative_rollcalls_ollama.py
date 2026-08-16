"""Classify pilot roll calls with two local models and expose disagreements."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import urllib.request

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
RESEARCH = ROOT / "research" / "cmo_ideology"
MODELS = ["qwen3.5:9b", "ministral-3:8b"]
ISSUES = [
    "public_education", "school_choice", "healthcare_medicaid", "labor_unions",
    "guns", "abortion", "taxes_revenue", "economic_development",
    "ethics_government", "culture_lgbtq", "gambling", "infrastructure",
    "social_services", "criminal_justice", "environment_energy", "immigration", "other",
]
SCHEMA = {
    "type": "object",
    "properties": {
        "primary_issue": {"type": "string", "enum": ISSUES},
        "secondary_issues": {"type": "array", "items": {"type": "string"}},
        "plain_english_change": {"type": "string"},
        "vote_stage": {"type": "string", "enum": ["final_passage", "amendment", "substitute", "concurrence", "procedural", "unknown"]},
        "substantive_vote": {"type": "boolean"},
        "yea_policy_effect": {"type": "string"},
        "ideological_valence": {"type": "string", "enum": ["progressive", "conservative", "mixed", "nonideological", "indeterminate"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "evidence_quotes": {"type": "array", "items": {"type": "string"}},
        "needs_human_review": {"type": "boolean"},
        "review_reason": {"type": "string"},
    },
    "required": ["primary_issue", "secondary_issues", "plain_english_change", "vote_stage", "substantive_vote", "yea_policy_effect", "ideological_valence", "confidence", "evidence_quotes", "needs_human_review", "review_reason"],
}


def relevant_excerpt(text: str, search_text: str, limit: int = 28000) -> str:
    if len(text) <= limit:
        return text
    terms = [term.lower() for term in re.findall(r"[A-Za-z]{6,}", search_text)[:30]]
    windows = [text[:10000]]
    lower = text.lower()
    for term in terms:
        position = lower.find(term)
        if position >= 0:
            windows.append(text[max(0, position - 1000):position + 3000])
        if sum(map(len, windows)) >= limit:
            break
    return "\n...[EXCERPT BREAK]...\n".join(windows)[:limit]


def call_model(model: str, prompt: str) -> dict:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "think": False, "format": SCHEMA,
                          "options": {"temperature": 0, "seed": 20260815}}).encode()
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.load(response)
    content = result.get("response") or result.get("thinking") or ""
    return json.loads(content)


def quote_supported(quote: str, text: str) -> bool:
    normalize = lambda value: re.sub(r"\s+", " ", value).strip().lower()
    cleaned = str(quote).strip().strip('"“”')
    return normalize(cleaned) in normalize(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--models", nargs="+", default=MODELS)
    args = parser.parse_args()
    pilot = pd.read_csv(DATA / "bill_text_pilot_manifest.csv")
    pilot = pilot[pilot.local_text.notna()].copy()
    if args.limit:
        pilot = pilot.head(args.limit)
    cache = RESEARCH / "rollcall_llm_classifications"
    cache.mkdir(exist_ok=True)
    records = []
    for _, row in pilot.iterrows():
        text = (ROOT / row.local_text).read_text(encoding="utf-8")
        excerpt = relevant_excerpt(text, f"{row.candidate_issues} {row.title} {row.description}")
        for model in args.models:
            cache_path = cache / f"v2_{int(row.roll_call_id)}_{model.replace(':', '_').replace('/', '_')}.json"
            if cache_path.exists():
                classification = json.loads(cache_path.read_text(encoding="utf-8"))
            else:
                prompt = f"""Classify an Alabama legislative roll call using only the supplied metadata and bill-text excerpt.
Do not infer the motion from the bill title alone. If vote description does not establish final passage or the
effect of Yea, use unknown/indeterminate and require human review. Keyword candidate issue is only a retrieval hint.
Evidence quotes must be short verbatim passages present in BILL TEXT. Do not discuss how legislators voted.

Bill: {row.bill_number}; date: {row.vote_date}; chamber: {row.chamber}
Vote description: {row.vote_description}
Title: {row.title}
Description: {row.description}
Keyword candidate issue: {row.candidate_issues}

BILL TEXT EXCERPT:
{excerpt}
"""
                classification = call_model(model, prompt)
                cache_path.write_text(json.dumps(classification, indent=2), encoding="utf-8")
            quotes = classification.get("evidence_quotes") or []
            supported = all(quote_supported(quote, text) for quote in quotes) and bool(quotes)
            records.append({**row.to_dict(), "model": model, **classification,
                            "all_quotes_verified": supported, "classification_cache": str(cache_path.relative_to(ROOT))})
            print(f"{row.bill_number}/{int(row.roll_call_id)} {model}: {classification.get('primary_issue')}")
    frame = pd.DataFrame(records)
    frame.to_csv(RESEARCH / "rollcall_llm_classifications.csv", index=False)
    compare_fields = ["primary_issue", "vote_stage", "substantive_vote", "ideological_valence"]
    consensus_rows = []
    for roll_id, group in frame.groupby("roll_call_id"):
        agreement = len(group) == len(args.models) and all(group[field].nunique(dropna=False) == 1 for field in compare_fields)
        quotes_ok = group.all_quotes_verified.all()
        base = group.iloc[0]
        consensus_rows.append({
            "roll_call_id": roll_id, "bill_number": base.bill_number, "candidate_issue": base.candidate_issues,
            "models_run": len(group), "core_fields_agree": agreement, "all_quotes_verified": quotes_ok,
            "ready_for_human_review": True, "eligible_for_automatic_stance": False,
            "review_priority": "high_disagreement" if not agreement else ("quote_failure" if not quotes_ok else "agreement_review"),
        })
    pd.DataFrame(consensus_rows).to_csv(RESEARCH / "rollcall_llm_consensus_review.csv", index=False)


if __name__ == "__main__":
    main()
