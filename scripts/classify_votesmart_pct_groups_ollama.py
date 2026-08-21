"""Classify normalized groups of remaining Vote Smart PCT items with two 8B+ models."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import pandas as pd

from classify_votesmart_pct_items_ollama import (
    DIMENSIONS, ITEMS, MODELS, PCT, build_queue, call_model,
    MIN_PRODUCTION_MODEL_BILLIONS,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "ideology"
CACHE = ROOT / "research" / "cmo_ideology" / "votesmart_pct_group_classifications"
GROUPS_OUT = OUT / "votesmart_pct_group_review_queue.csv"
CLASS_OUT = OUT / "votesmart_pct_group_llm_classifications.csv"
CONSENSUS_OUT = OUT / "votesmart_pct_group_llm_consensus.csv"


def normalize_option(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return re.sub(r"^(?:[a-z]|[0-9]+)\)\s*", "", text)


def build_groups(queue: pd.DataFrame) -> pd.DataFrame:
    work = queue.copy()
    work["normalized_option"] = work.option_text.map(normalize_option)
    rows = []
    for option, group in work.groupby("normalized_option", sort=False):
        representative = group.sort_values(
            ["selected_response_count", "candidate_count"], ascending=False
        ).iloc[0]
        group_id = hashlib.sha256(option.encode()).hexdigest()[:16].upper()
        rows.append({
            "group_id": group_id, "normalized_option": option,
            "representative_section": representative.section,
            "representative_question": representative.question,
            "representative_option_text": representative.option_text,
            "item_count": len(group), "years": ";".join(map(str, sorted(group.election_year.unique()))),
            "selected_response_count": int(group.selected_response_count.sum()),
            "candidate_count_sum": int(group.candidate_count.sum()),
        })
    return pd.DataFrame(rows).sort_values(
        ["selected_response_count", "item_count"], ascending=False
    )


def group_prompt(row: object) -> str:
    return f"""Classify one historical Alabama candidate-questionnaire policy option.
Use +1 only when selecting/supporting the option is conventionally more conservative,
-1 only when conventionally more progressive, and 0 when mixed, procedural,
administrative, context-dependent, or lacking a stable left/right direction.
Set scorable=false for the 0 cases. Do not infer a candidate position. Return a short
verbatim evidence_quote copied from the option. Use a short snake_case policy_key.

Section: {row.representative_section}
Question: {row.representative_question}
Option: {row.representative_option_text}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--models", nargs="+", default=MODELS)
    parser.add_argument("--only-qwen-scorable", action="store_true",
                        help="review only groups Qwen previously marked scorable")
    parser.add_argument("--append-existing", action="store_true",
                        help="retain prior model rows when writing classifications")
    args = parser.parse_args()
    for model in args.models:
        size = re.search(r":([0-9]+(?:\.[0-9]+)?)b(?:$|-)", model.lower())
        if not size or float(size.group(1)) < MIN_PRODUCTION_MODEL_BILLIONS:
            parser.error(f"{model!r} is not explicitly labeled 8B+")
    queue = build_queue(pd.read_csv(ITEMS), pd.read_csv(PCT))
    groups = build_groups(queue)
    groups.to_csv(GROUPS_OUT, index=False)
    existing = pd.read_csv(CLASS_OUT) if args.append_existing and CLASS_OUT.exists() else pd.DataFrame()
    if args.only_qwen_scorable:
        if existing.empty:
            parser.error("--only-qwen-scorable requires an existing classification file")
        ids = set(existing[(existing.model.eq("qwen3.5:9b")) &
                           (existing.scorable.eq(True))].group_id)
        groups = groups[groups.group_id.isin(ids)]
    work = groups if args.limit is None else groups.head(args.limit)
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = []
    for model in args.models:
        safe_model = model.replace(":", "_").replace("/", "_")
        for row in work.itertuples(index=False):
            path = CACHE / f"{row.group_id}_{safe_model}.json"
            if path.exists():
                result = json.loads(path.read_text(encoding="utf-8"))
            else:
                result = call_model(model, group_prompt(row))
                path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            rows.append({**row._asdict(), "model": model, **result,
                         "classification_cache": str(path.relative_to(ROOT))})
            print(f"{model} {row.group_id} {result.get('dimension')} {result.get('affirmative_direction')}", flush=True)
    frame = pd.DataFrame(rows)
    if not existing.empty:
        replace = set(zip(frame.group_id, frame.model))
        existing = existing[[pair not in replace for pair in zip(existing.group_id, existing.model)]]
        frame = pd.concat([existing, frame], ignore_index=True, sort=False)
    frame.to_csv(CLASS_OUT, index=False)
    consensus = []
    for group_id, group in frame.groupby("group_id"):
        first = group.iloc[0]
        fields = ["dimension", "affirmative_direction", "scorable"]
        agree = group.model.nunique() >= 2 and all(group[x].nunique(dropna=False) == 1 for x in fields)
        consensus.append({
            "group_id": group_id, "normalized_option": first.normalized_option,
            "item_count": first.item_count, "selected_response_count": first.selected_response_count,
            "models_run": len(group), "core_fields_agree": agree,
            "consensus_dimension": first.dimension if agree else "",
            "consensus_direction": first.affirmative_direction if agree else None,
            "consensus_scorable": first.scorable if agree else None,
            "eligible_for_automatic_scoring": False,
        })
    pd.DataFrame(consensus).to_csv(CONSENSUS_OUT, index=False)
    print(f"Classified {len(work):,} normalized groups with {len(args.models)} models")


if __name__ == "__main__":
    main()
