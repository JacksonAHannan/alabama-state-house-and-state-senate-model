"""Draft quote-grounded policy directions for the bounded sponsorship review queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"
MODELS = ["qwen3.5:9b", "ministral-3:8b"]
SCHEMA = {
    "type": "object",
    "properties": {
        "plain_english_policy": {"type": "string"},
        "policy_direction_if_enacted": {"type": "string"},
        "ideological_valence": {"type": "string", "enum": [
            "progressive", "conservative", "mixed", "nonideological", "indeterminate"
        ]},
        "local_or_ceremonial": {"type": "boolean"},
        "sponsorship_supports_position": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "evidence_quotes": {"type": "array", "items": {"type": "string"}},
        "needs_human_review": {"type": "boolean"},
        "review_reason": {"type": "string"},
    },
    "required": [
        "plain_english_policy", "policy_direction_if_enacted", "ideological_valence",
        "local_or_ceremonial", "sponsorship_supports_position", "confidence",
        "evidence_quotes", "needs_human_review", "review_reason",
    ],
}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def quote_supported(quote: str, text: str) -> bool:
    cleaned = str(quote).strip().strip('"“”')
    return bool(cleaned) and normalize(cleaned) in normalize(text)


def extract_text(path: Path) -> str:
    reader = PdfReader(path)
    return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()


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
                response_data = json.load(response)
            content = response_data.get("response") or response_data.get("thinking") or ""
            return json.loads(content)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Ollama failed after three attempts: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--models", nargs="+", default=MODELS)
    args = parser.parse_args()
    queue = pd.read_csv(RESEARCH / "candidate_sponsorship_direction_review_queue.csv")
    validation_path = DATA / "sponsorship_bill_text_link_validation.csv"
    if not validation_path.exists():
        raise FileNotFoundError(
            "Run validate_sponsorship_bill_text_links.py before classification"
        )
    validation = pd.read_csv(validation_path)
    valid_ids = set(validation.loc[
        validation.position_review_allowed.eq(True), "bill_id"
    ].astype(int))
    queue = queue.loc[queue.bill_id.astype(int).isin(valid_ids)].copy()
    effective_paths = validation[["bill_id", "bill_text_path"]].rename(
        columns={"bill_text_path": "validated_bill_text_path"}
    )
    queue = queue.merge(effective_paths, on="bill_id", how="left", validate="many_to_one")
    queue["bill_text_path"] = queue.validated_bill_text_path.fillna(queue.bill_text_path)
    bills = queue.drop_duplicates("bill_id").copy()
    if args.limit:
        bills = bills.head(args.limit)
    cache = RESEARCH / "sponsorship_bill_llm_classifications"
    cache.mkdir(exist_ok=True)
    text_cache = RESEARCH / "sponsorship_bill_text_extracts"
    text_cache.mkdir(exist_ok=True)
    prepared_bills = []
    for bill in bills.itertuples(index=False):
        text_path = text_cache / f"{int(bill.bill_id)}.txt"
        if text_path.exists():
            text = text_path.read_text(encoding="utf-8")
        else:
            text = extract_text(ROOT / bill.bill_text_path)
            text_path.write_text(text, encoding="utf-8")
        prepared_bills.append((bill, text_path, text, text[:30000]))

    # Keep each model resident while it works through the queue. Alternating models
    # bill-by-bill forces Ollama to repeatedly unload and reload several gigabytes.
    rows = []
    for model in args.models:
        for bill, text_path, text, excerpt in prepared_bills:
            safe_model = model.replace(":", "_").replace("/", "_")
            result_path = cache / f"{int(bill.bill_id)}_{safe_model}.json"
            if result_path.exists():
                result = json.loads(result_path.read_text(encoding="utf-8"))
            else:
                prompt = f"""Analyze an Alabama bill using only its official text and metadata. Explain
the policy direction that enactment would produce. Sponsorship indicates the sponsor affirmatively
advanced the bill, but do not infer positions beyond the bill. If the text is local, ceremonial,
appropriations-only without enough context, or otherwise ambiguous, say so. Evidence quotes must be
short verbatim passages found in BILL TEXT.

Bill: {bill.bill_number}; session year: {int(bill.session_year)}
Official title: {bill.title}
Official synopsis: {bill.description}
Retrieval issue: {bill.issue}

BILL TEXT:
{excerpt}
"""
                try:
                    result = call_model(model, prompt)
                    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                except Exception as exc:
                    result = {
                        "plain_english_policy": "Model classification failed.",
                        "policy_direction_if_enacted": "indeterminate",
                        "ideological_valence": "indeterminate", "local_or_ceremonial": False,
                        "sponsorship_supports_position": "indeterminate", "confidence": "low",
                        "evidence_quotes": [], "needs_human_review": True,
                        "review_reason": f"{type(exc).__name__}: {exc}",
                        "classification_error": True,
                    }
            quotes = result.get("evidence_quotes") or []
            rows.append({
                "bill_id": int(bill.bill_id), "bill_number": bill.bill_number,
                "model": model, **result,
                "all_quotes_verified": bool(quotes) and all(quote_supported(q, text) for q in quotes),
                "classification_cache": str(result_path.relative_to(ROOT)),
                "local_text": str(text_path.relative_to(ROOT)),
            })
            print(f"{bill.bill_number}/{int(bill.bill_id)} {model}: {result.get('ideological_valence')}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(RESEARCH / "sponsorship_bill_llm_classifications.csv", index=False)
    consensus = []
    fields = ["policy_direction_if_enacted", "ideological_valence", "local_or_ceremonial"]
    for bill_id, group in frame.groupby("bill_id"):
        base = group.iloc[0]
        agree = len(group) == len(args.models) and all(
            group[field].nunique(dropna=False) == 1 for field in fields
        )
        consensus.append({
            "bill_id": bill_id, "bill_number": base.bill_number,
            "models_run": len(group), "core_fields_agree": agree,
            "all_quotes_verified": bool(group.all_quotes_verified.all()),
            "eligible_for_automatic_stance": False,
            "review_priority": "agreement_review" if agree else "high_disagreement",
        })
    consensus = pd.DataFrame(consensus)
    candidate_review = queue.merge(consensus, on=["bill_id", "bill_number"], how="left")
    candidate_review.to_csv(
        RESEARCH / "candidate_sponsorship_direction_llm_review.csv", index=False
    )
    print(f"Wrote {len(frame)} classifications for {frame.bill_id.nunique()} bills")


if __name__ == "__main__":
    main()
