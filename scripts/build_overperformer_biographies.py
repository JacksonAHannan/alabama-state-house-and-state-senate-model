"""Create sourced draft biographies for the focal CMO overperformers.

The local model may summarize only the candidate memo supplied to it. Outputs
remain draft syntheses; URLs and underlying memo text are the evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import urllib.request

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
MEMOS = RESEARCH / "candidate_memos"
MODEL = "qwen3.5:9b"
ALIASES = {
    "Andrew \"Andy\" Betterton": "andy_betterton.md",
    "Barbara Bigsby Boyd": "barbara_boyd.md",
    "Barbara A. Drummond": "barbara_drummond.md",
    "David \"Coach\" Burkette": "david_burkette.md",
    "James C. Fields Jr.": "james_fields.md",
    "Henry A. White": "henry_white.md",
    "Johnny Mack Morrow": "johnny_mack_morrow.md",
    "Napoleon Bracy Jr.": "napoleon_bracy.md",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "identity_assessment": {"type": "string", "enum": ["confirmed_alabama", "ambiguous", "insufficient"]},
        "summary": {"type": "string"},
        "offices_and_public_service": {"type": "array", "items": {"type": "string"}},
        "profession_and_employment": {"type": "array", "items": {"type": "string"}},
        "education": {"type": "array", "items": {"type": "string"}},
        "community_and_local_ties": {"type": "array", "items": {"type": "string"}},
        "political_profile": {"type": "array", "items": {"type": "string"}},
        "important_caveats": {"type": "array", "items": {"type": "string"}},
        "source_urls_used": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "identity_assessment", "summary", "offices_and_public_service",
        "profession_and_employment", "education", "community_and_local_ties",
        "political_profile", "important_caveats", "source_urls_used",
    ],
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def call_ollama(prompt: str, model: str) -> dict:
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False, "format": SCHEMA,
        "options": {"temperature": 0, "seed": 20260815},
    }).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.load(response)
    # Current Qwen 3.5 Ollama builds may place schema-constrained output in the
    # `thinking` field while leaving `response` empty.
    content = result.get("response") or result.get("thinking") or ""
    return json.loads(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    matrix = pd.read_csv(RESEARCH / "candidate_state_issue_matrix.csv")
    candidates = matrix[["person_id", "election_cycle", "display_candidate", "chamber", "district"]].drop_duplicates()
    if args.limit:
        candidates = candidates.head(args.limit)
    cache = RESEARCH / "candidate_biography_drafts"
    cache.mkdir(exist_ok=True)
    records = []
    for _, row in candidates.iterrows():
        memo_name = ALIASES.get(row.display_candidate, f"{slug(row.display_candidate)}.md")
        memo_path = MEMOS / memo_name
        if not memo_path.exists():
            records.append({**row.to_dict(), "review_status": "missing_memo", "summary": ""})
            continue
        memo = memo_path.read_text(encoding="utf-8")
        allowed_urls = sorted(set(re.findall(r"https?://[^\s)>]+", memo)))
        cache_path = cache / f"{row.person_id}_{row.election_cycle}_{args.model.replace(':', '_')}.json"
        if cache_path.exists():
            result = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            prompt = f"""You are building a factual research biography of an Alabama legislative candidate.
Candidate: {row.display_candidate}
Election identity: Alabama {row.chamber} district {row.district}, {row.election_cycle} election.

Use ONLY the research memo below. Do not add facts from memory. The same-name-person risk is important:
return identity_assessment=confirmed_alabama only when the memo evidence fits this Alabama identity.
Use empty arrays when facts are unavailable. Clearly distinguish evidence published later from facts that
the memo says predated the election. The summary must be neutral and concise. source_urls_used must contain
only URLs present in the memo and actually supporting biography facts.

MEMO:
{memo}
"""
            result = call_ollama(prompt, args.model)
            result["model"] = args.model
            result["allowed_source_urls"] = allowed_urls
            cache_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        used = result.get("source_urls_used", [])
        invalid_urls = [url for url in used if url not in allowed_urls]
        records.append({
            **row.to_dict(), **{key: result.get(key) for key in SCHEMA["properties"]},
            "memo_path": str(memo_path.relative_to(ROOT)), "model": args.model,
            "invalid_source_urls": invalid_urls,
            "review_status": "needs_human_review" if invalid_urls or result.get("identity_assessment") != "confirmed_alabama" else "draft_sourced",
        })
        print(f"{row.display_candidate}: {records[-1]['review_status']}")
    frame = pd.DataFrame(records)
    for column in SCHEMA["properties"]:
        if column != "summary" and column in frame:
            frame[column] = frame[column].map(lambda value: json.dumps(value) if isinstance(value, list) else value)
    frame.to_csv(RESEARCH / "candidate_biographies.csv", index=False)

    lines = ["# Draft biographies of focal Alabama legislative overperformers", "",
             "These are source-constrained research drafts. Consult each linked memo and public source before publication.", ""]
    for record in records:
        lines += [f"## {record['display_candidate']}", "", record.get("summary") or "Biography evidence remains unavailable.", ""]
        for label, key in [
            ("Public service", "offices_and_public_service"), ("Profession", "profession_and_employment"),
            ("Education", "education"), ("Community and local ties", "community_and_local_ties"),
            ("Political profile", "political_profile"), ("Caveats", "important_caveats")]:
            values = record.get(key) or []
            if values:
                lines += [f"### {label}", ""] + [f"- {value}" for value in values] + [""]
        sources = record.get("source_urls_used") or []
        if sources:
            lines += ["### Sources", ""] + [f"- {url}" for url in sources] + [""]
        lines += [f"Review status: `{record.get('review_status')}`. Memo: `{record.get('memo_path', '')}`.", ""]
    (RESEARCH / "CANDIDATE_BIOGRAPHIES.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
