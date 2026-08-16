"""Draft two-model classifications for unmapped Vote Smart PCT items.

Outputs are a review queue only. They do not enter candidate scores until an
adjudicated item crosswalk explicitly accepts them.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
PCT = IDEOLOGY / "votesmart_all_1998_2022_pct_options.csv"
ITEMS = IDEOLOGY / "votesmart_pct_item_crosswalk.csv"
QUEUE_OUT = IDEOLOGY / "votesmart_pct_llm_review_queue.csv"
CLASS_OUT = IDEOLOGY / "votesmart_pct_llm_classifications.csv"
CONSENSUS_OUT = IDEOLOGY / "votesmart_pct_llm_consensus.csv"
CACHE = ROOT / "research" / "cmo_ideology" / "votesmart_pct_item_classifications"
MODELS = ["qwen3.5:9b", "ministral-3:8b"]
MIN_PRODUCTION_MODEL_BILLIONS = 8.0
DIMENSIONS = [
    "abortion_position", "guns_position", "economic_ideology", "labor_position",
    "social_ideology", "education_position", "environment_position",
    "healthcare_position", "criminal_justice_position", "government_reform_position",
    "immigration_position", "other", "nonideological", "indeterminate",
]
SCHEMA = {
    "type": "object",
    "properties": {
        "policy_key": {"type": "string"},
        "dimension": {"type": "string", "enum": DIMENSIONS},
        "affirmative_direction": {"type": "integer", "enum": [-1, 0, 1]},
        "scorable": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "plain_english_policy": {"type": "string"},
        "evidence_quote": {"type": "string"},
        "needs_human_review": {"type": "boolean"},
        "review_reason": {"type": "string"},
    },
    "required": [
        "policy_key", "dimension", "affirmative_direction", "scorable", "confidence",
        "plain_english_policy", "evidence_quote", "needs_human_review", "review_reason",
    ],
}


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def item_id(row: object) -> str:
    import hashlib
    text = "|".join(normalize(getattr(row, field)) for field in (
        "election_year", "section", "question", "option_text"
    ))
    return hashlib.sha256(text.encode()).hexdigest()[:16].upper()


def quote_supported(quote: object, source: str) -> bool:
    value = normalize(quote).strip('"')
    return bool(value) and value in normalize(source)


def call_model(model: str, prompt: str) -> dict:
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({
            "model": model, "prompt": prompt, "stream": False, "think": False,
            "format": SCHEMA, "options": {"temperature": 0, "seed": 20260816},
        }).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                payload = json.load(response)
            return json.loads(payload.get("response") or payload.get("thinking") or "")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Ollama failed after three attempts: {error}")


def build_queue(items: pd.DataFrame, pct: pd.DataFrame) -> pd.DataFrame:
    keys = ["election_year", "section", "question", "option_text"]
    stats = pct.groupby(keys, dropna=False, as_index=False).agg(
        candidate_count=("votesmart_candidate_id", "nunique"),
        selected_response_count=("selected", "sum"),
    )
    queue = items[items.coding_status.eq("unmapped")].merge(
        stats, on=keys, how="left", validate="one_to_one"
    )
    queue = queue[
        ~queue.option_text.fillna("").str.match(
            r"^\s*(?:[a-z]\)\s*)?(?:other|other or expanded principles)\s*$", case=False
        )
    ].copy()
    queue["priority"] = queue.selected_response_count.fillna(0) * 1000 + queue.candidate_count.fillna(0)
    queue = queue.sort_values(["priority", "election_year"], ascending=[False, True])
    queue.insert(0, "item_id", [item_id(row) for row in queue.itertuples(index=False)])
    return queue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="classify only the highest-priority N items")
    parser.add_argument("--all", action="store_true", help="classify the complete unmapped queue")
    parser.add_argument("--models", nargs="+", default=MODELS)
    args = parser.parse_args()
    for model in args.models:
        size = re.search(r":([0-9]+(?:\.[0-9]+)?)b(?:$|-)", model.lower())
        if not size or float(size.group(1)) < MIN_PRODUCTION_MODEL_BILLIONS:
            parser.error(
                f"model {model!r} is not an explicitly labeled 8B+ local model; "
                "small models are excluded from production PCT review"
            )
    if args.limit is None and not args.all:
        parser.error("specify --limit N for a review tranche or --all")
    pct = pd.read_csv(PCT)
    items = pd.read_csv(ITEMS)
    queue = build_queue(items, pct)
    queue.to_csv(QUEUE_OUT, index=False)
    work = queue if args.all else queue.head(args.limit)
    CACHE.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    # Keep each model resident for its complete tranche.
    for model in args.models:
        for record in work.itertuples(index=False):
            safe_model = model.replace(":", "_").replace("/", "_")
            cache_path = CACHE / f"{record.item_id}_{safe_model}.json"
            source = f"Section: {record.section}\nPrompt: {record.question}\nOption: {record.option_text}"
            if cache_path.exists():
                result = json.loads(cache_path.read_text(encoding="utf-8"))
            else:
                prompt = f"""Classify one historical candidate questionnaire item using only SOURCE TEXT.
The requested direction is the direction of answering YES or selecting the option: +1 for the
conventionally more conservative policy, -1 for the conventionally more progressive policy, and 0
only when nonideological, mixed, or indeterminate. Do not infer a candidate's position. Mark scorable
false for priorities, administrative details, vague items, context-dependent spending levels, or
anything without a defensible stable direction. Use a short snake_case policy key. The evidence quote
must be a short verbatim substring of SOURCE TEXT.

SOURCE TEXT:
{source}
"""
                try:
                    result = call_model(model, prompt)
                    cache_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                except Exception as exc:
                    result = {
                        "policy_key": "", "dimension": "indeterminate", "affirmative_direction": 0,
                        "scorable": False, "confidence": "low", "plain_english_policy": "",
                        "evidence_quote": "", "needs_human_review": True,
                        "review_reason": f"{type(exc).__name__}: {exc}", "classification_error": True,
                    }
            rows.append({
                **record._asdict(), "model": model, **result,
                "evidence_quote_verified": quote_supported(result.get("evidence_quote"), source),
                "classification_cache": str(cache_path.relative_to(ROOT)),
            })
            print(f"{record.item_id} {model}: {result.get('dimension')}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(CLASS_OUT, index=False)
    consensus = []
    # Generated policy-key wording is not a substantive agreement field; models
    # may describe the same policy with different valid snake_case labels.
    fields = ["dimension", "affirmative_direction", "scorable"]
    for identifier, group in frame.groupby("item_id"):
        base = group.iloc[0]
        agree = len(group) == len(args.models) and all(
            group[field].nunique(dropna=False) == 1 for field in fields
        )
        quotes_ok = bool(group.evidence_quote_verified.all())
        consensus.append({
            "item_id": identifier, "election_year": base.election_year,
            "section": base.section, "question": base.question, "option_text": base.option_text,
            "models_run": len(group), "core_fields_agree": agree,
            "all_quotes_verified": quotes_ok, "eligible_for_automatic_scoring": False,
            "review_priority": "high_disagreement" if not agree else "quote_failure" if not quotes_ok else "agreement_review",
        })
    pd.DataFrame(consensus).to_csv(CONSENSUS_OUT, index=False)
    print(f"Wrote {len(frame):,} classifications for {frame.item_id.nunique():,} items")


if __name__ == "__main__":
    main()
