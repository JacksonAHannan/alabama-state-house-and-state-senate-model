"""Combine small-model Vote Smart labels and focus Ministral on pole conflicts."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

from votesmart_position_ontology import AXES, ONTOLOGY_VERSION

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "processed" / "ideology" / "votesmart_pct_multiaxis_v2_classifications.csv"
OUT = ROOT / "data" / "processed" / "ideology" / "votesmart_pct_multiaxis_v2_auto_adjudications.csv"
QUEUE = ROOT / "data" / "processed" / "ideology" / "votesmart_pct_multiaxis_v2_manual_queue.csv"
CACHE = ROOT / "research" / "cmo_ideology" / "votesmart_pct_multiaxis_v2_direction_adjudication"
MODEL = "ministral-3:8b"


def effects(row: pd.Series) -> list[dict]:
    return json.loads(row.effects_json or "[]")


def triage(group: pd.DataFrame) -> tuple[str, dict[str, set[str]], list[dict], list[str]]:
    rows = list(group.itertuples(index=False))
    domains = sorted({str(row.primary_domain) for row in rows if str(row.primary_domain)})
    by_axis: dict[str, set[str]] = {}
    all_effects: dict[tuple[str, str], dict] = {}
    model_axes = []
    for row in rows:
        current = effects(pd.Series(row._asdict()))
        model_axes.append({effect["axis"] for effect in current})
        for effect in current:
            by_axis.setdefault(effect["axis"], set()).add(effect["pole"])
            all_effects.setdefault((effect["axis"], effect["pole"]), effect)
    conflicts = {axis: poles for axis, poles in by_axis.items() if len(poles) > 1}
    domain_agreement = len(domains) == 1
    axes_overlap = bool(model_axes[0] & model_axes[1]) if len(model_axes) == 2 else False
    if conflicts:
        status = "direction_conflict"
    elif not domain_agreement and not axes_overlap:
        status = "complete_disagreement"
    else:
        status = "compatible_additive"
    compatible = [effect for key, effect in all_effects.items() if key[0] not in conflicts]
    return status, conflicts, compatible, domains


def adjudicate_direction(row: pd.Series, conflicts: dict[str, set[str]]) -> dict[str, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{ONTOLOGY_VERSION}_{row.review_id}_ministral.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    allowed = {axis: [*sorted(poles), "not_applicable"] for axis, poles in conflicts.items()}
    schema = {
        "type": "object", "properties": {
            axis: {"type": "string", "enum": poles} for axis, poles in allowed.items()
        }, "required": list(allowed),
    }
    prompt = f"""Resolve only the disputed direction of the policy option below.
For each axis choose one of the two proposed poles, or not_applicable when the axis itself
does not describe the source. Do not add domains or axes. Judge the stated policy mechanism,
not a speculative downstream consequence.

DISPUTED AXES: {json.dumps(allowed)}
Section: {row.section}
Question: {row.question}
Option: {row.option_text}
"""
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                         "think": False, "format": schema,
                         "options": {"temperature": 0, "seed": 20260816}}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                envelope = json.load(response)
            result = json.loads(envelope.get("response") or "")
            path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result
        except Exception as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"focused Ministral adjudication failed: {error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-model", action="store_true", help="build queues without focused calls")
    args = parser.parse_args()
    frame = pd.read_csv(SOURCE).fillna("")
    initial = frame[frame.stage.eq("initial")]
    auto, manual = [], []
    for identifier, group in initial.groupby("review_id"):
        first = group.iloc[0]
        status, conflicts, accepted, domains = triage(group)
        resolutions = {}
        if status == "direction_conflict" and not args.no_model:
            resolutions = adjudicate_direction(first, conflicts)
            for axis, pole in resolutions.items():
                if pole != "not_applicable":
                    accepted.append({"axis": axis, "pole": pole, "strength": "primary",
                                     "rationale": "Focused Ministral pole adjudication"})
        record = {
            "ontology_version": ONTOLOGY_VERSION, "review_id": identifier,
            "election_year": first.election_year,
            "normalized_option": re.sub(r"^(?:[a-z]|[0-9]+)\)\s*", "", str(first.option_text).strip().lower()),
            "question": first.question, "option_text": first.option_text,
            "decision": "adjudicated", "primary_domain": domains[0] if domains else "other",
            "policy_domains_json": json.dumps(domains, separators=(",", ":")),
            "policy_key": "", "effects_json": json.dumps(accepted, separators=(",", ":")),
            "confidence": "medium", "reviewer_notes": "",
            "consensus_status": status, "direction_resolutions_json": json.dumps(resolutions),
            "review_source": "small_model_additive_consensus" if status == "compatible_additive"
                             else "focused_ministral_direction_adjudication",
        }
        if status == "complete_disagreement" or (status == "direction_conflict" and not resolutions):
            record["decision"] = "skip"
            manual.append(record)
        else:
            auto.append(record)
    pd.DataFrame(auto).to_csv(OUT, index=False)
    pd.DataFrame(manual).to_csv(QUEUE, index=False)
    print(f"Automatic adjudications: {len(auto)}")
    print(f"Manual queue: {len(manual)}")
    print(f"Focused Ministral direction calls: {sum(x['consensus_status'] == 'direction_conflict' for x in auto)}")


if __name__ == "__main__":
    main()
