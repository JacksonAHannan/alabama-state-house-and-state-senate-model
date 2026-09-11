"""Adjudicate every Alabama LegiScan bill at the bill level with the Luna model.

This produces the bill-level frontier adjudication file consumed by
`build_frontier_rollcall_ontology.py` (`data/manual/ideology/
frontier_legislative_bill_adjudications.csv`). Per the accountable owner's
decision on 2026-09-08, the human `frontier_manual_review` layer is superseded by
a full automated pass: every bill in the scoring universe is adjudicated by Luna
(`gpt-5.6-luna`) from its official synopsis, using the same decision taxonomy and
the same primitive axis/pole ontology the human layer used, so the output is a
drop-in replacement in the identical schema.

Design:
  * Universe = the union of every distinct non-null bill_id in
    `comprehensive_rollcall_classifications.csv` (the file the ontology joins
    against, whose coverage the ontology strictly requires) and the existing
    manual file, so no roll-call bill is left without an adjudication.
  * One row per bill_id (the ontology validates a many-to-one merge).
  * bill_id written as a plain integer string, matching the existing manual file.
  * Decisions use the human taxonomy: map, multi_axis, local_non_generalizable,
    procedural, symbolic, mixed_no_scalar_direction, insufficient_text.
  * map/multi_axis carry one-or-more allowed (axis, pole) pairs from the v3
    ontology; every pair is schema-validated. A mapping that fails validation is
    diverted to a review queue and fails closed to a non-scoring disposition
    rather than inventing an out-of-ontology pole.
  * Per-bill JSON cache makes the run resumable and re-runs a no-op.

The model layer (key loading, chat with retry/parameter-fallback, token-usage
accounting) is reused from `adjudicate_legislative_ontology_v3_all`; only the
bill-level prompt, taxonomy and validation are new here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path

import pandas as pd

import adjudicate_legislative_ontology_v3_all as rollcall
from ideology_ontology_v3 import PRIMITIVES

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
MANUAL = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications.csv"
COMPREHENSIVE = LEG / "comprehensive_rollcall_classifications.csv"
AUDIT = LEG / "legislative_rollcall_ontology_v3_audit.csv"
# Full digitized bill corpus (all classified bills, 2010-2026), including the
# ~19.7k bills that never received a floor roll call but carry sponsorship and
# so still inform ideology through the sponsorship evidence channel.
BILL_DB = LEG / "alabama_legislative_rollcalls_1998_2026.sqlite"
CACHE = ROOT / "research" / "cmo_ideology" / "frontier_bill_adjudications_luna"
OUT = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications_luna.csv"
REVIEW_QUEUE = LEG / "frontier_legislative_bill_adjudications_luna_review_queue.csv"
RUN_MANIFEST = LEG / "frontier_legislative_bill_adjudications_luna_run_manifest.json"

MODEL = "gpt-5.6-luna"
REVIEWER = "gpt-5.6-luna"
SUPERSEDES = "frontier_manual_review"
DOC_TYPE = "official_synopsis"

SCORING_DECISIONS = {"map", "multi_axis"}
NONSCORING_DECISIONS = {
    "local_non_generalizable", "procedural", "symbolic",
    "mixed_no_scalar_direction", "insufficient_text",
}
ALL_DECISIONS = SCORING_DECISIONS | NONSCORING_DECISIONS
CONFIDENCES = {"high", "medium", "low"}

# Admitted mappings (map/multi_axis) whose model confidence is only "low" are
# still scored, but per the 2026-09-08 owner contract they must be diverted to
# the review queue rather than silently surviving into the scores. The scoring
# decision is deliberately not changed: the contract queues them, it does not
# exclude them.
LOW_CONFIDENCE_REASON = "low_confidence_admitted_mapping"

OUTPUT_COLUMNS = [
    "bill_id", "session_year", "bill_number", "reviewed_document_type", "decision",
    "primitive_axes", "policy_poles", "confidence", "rationale", "reviewer",
    "review_date", "supersedes_authority",
]


def norm_bill_id(value: object) -> str:
    text = str(value).strip()
    if text in ("", "nan", "None", "NaN"):
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def _ontology_block() -> str:
    lines = [f"  {axis}: {list(poles)}" for axis, poles in PRIMITIVES.items()]
    return "\n".join(lines)


ONTOLOGY_BLOCK = _ontology_block()


def build_universe() -> "pd.DataFrame":
    """Return one row per bill to adjudicate, with the richest available text.

    The universe is the full digitized bill corpus (`bill_issue_classification`,
    every classified 2010-2026 bill) unioned with the roll-call sources, so every
    bill is adjudicated whether or not it ever received a floor vote.
    """
    frames = []
    with sqlite3.connect(f"file:{BILL_DB}?mode=ro", uri=True) as con:
        bills = pd.read_sql(
            "SELECT bill_id, session_year, bill_number, title, description "
            "FROM bill_issue_classification", con)
    bills["bill_id"] = bills["bill_id"].map(norm_bill_id)
    bills = bills[bills["bill_id"] != ""]
    frames.append(bills)
    comp = pd.read_csv(COMPREHENSIVE, low_memory=False,
                       usecols=["bill_id", "session_year", "bill_number", "title", "description"])
    comp["bill_id"] = comp["bill_id"].map(norm_bill_id)
    comp = comp[comp["bill_id"] != ""]
    frames.append(comp)
    if AUDIT.exists():
        aud = pd.read_csv(AUDIT, low_memory=False,
                          usecols=["bill_id", "session_year", "bill_number", "title", "description"])
        aud["bill_id"] = aud["bill_id"].map(norm_bill_id)
        aud = aud[aud["bill_id"] != ""]
        frames.append(aud)
    if MANUAL.exists():
        man = pd.read_csv(MANUAL, low_memory=False)
        man["bill_id"] = man["bill_id"].map(norm_bill_id)
        man = man[man["bill_id"] != ""]
        # Manual file has no bill text; keep only its identity to guarantee coverage.
        man = man.reindex(columns=["bill_id", "session_year", "bill_number", "title", "description"])
        frames.append(man)
    universe = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    for column in ("title", "description"):
        universe[column] = universe[column].astype(str)
    # Pick, per bill, the row with the most descriptive text.
    universe["_score"] = universe["title"].str.len() + universe["description"].str.len()
    universe = (universe.sort_values("_score", ascending=False)
                .drop_duplicates(subset="bill_id", keep="first")
                .drop(columns="_score")
                .sort_values("bill_id")
                .reset_index(drop=True))
    return universe


def build_prompt(items: list[dict[str, str]]) -> str:
    compact = [
        {"id": it["bill_id"], "bill_number": it["bill_number"],
         "session_year": it["session_year"],
         "synopsis": (it["title"] if len(it["title"]) >= len(it["description"]) else it["description"])[:1200]}
        for it in items
    ]
    return f"""You are classifying Alabama state legislative bills by their statewide ideological policy content, using each bill's official synopsis.

For each bill choose exactly one decision:
- "map": the bill takes one clear position on exactly ONE policy axis below.
- "multi_axis": the bill takes clear positions on TWO OR MORE distinct axes below.
- "local_non_generalizable": the bill applies only to a specific named county, city, district, or local entity, or is a purely local/constituency matter with no statewide ideological pole (this is common in Alabama; classify here whenever the synopsis names a specific local jurisdiction and the substance is local administration, local taxation, local referenda, or similar).
- "procedural": appropriations with no directional fiscal pole, administrative, technical, definitional, reauthorization, study/commission, or code-cleanup measures with no substantive policy direction.
- "symbolic": resolutions, commendations, memorials, congratulations, namings, and other non-binding or purely symbolic measures.
- "mixed_no_scalar_direction": substantive but combines opposing directions on the same axis, or has no scalar policy pole.
- "insufficient_text": the synopsis is too sparse or vague to determine content.

Rules for map/multi_axis:
- Use ONLY an axis name and one of its EXACT allowed poles from the ontology below. Never invent an axis or pole. Never use party labels or a generic liberal/conservative direction.
- Judge the direction of the bill's substantive final policy (what the bill would do if enacted), not any single procedural vote.
- Prefer a non-scoring decision over forcing a weak or speculative pole.

Allowed axes and their exact poles (axis: [allowed poles]):
{ONTOLOGY_BLOCK}

Return ONLY a single JSON object: {{"items": [ ... ]}}. Each element must be:
{{"id": <bill id echoed exactly>, "decision": <one decision above>, "axes": [{{"axis": <axis>, "pole": <pole>}}, ...], "confidence": "high"|"medium"|"low", "rationale": <one concise sentence>}}
For map give exactly one entry in "axes"; for multi_axis give two or more; for every non-scoring decision give "axes": [].

Bills:
{json.dumps(compact, ensure_ascii=False)}"""


def validate_item(result: dict, item: dict) -> tuple[dict, str | None]:
    """Return (row, review_reason). review_reason is None when clean.

    On any schema problem, fail closed to a non-scoring disposition and record a
    reason so the item is diverted to the review queue rather than silently
    fabricating a pole.
    """
    bill_id = item["bill_id"]
    decision = str(result.get("decision", "")).strip()
    confidence = str(result.get("confidence", "")).strip().lower() or "low"
    if confidence not in CONFIDENCES:
        confidence = "low"
    rationale = str(result.get("rationale", "")).strip().replace("\n", " ")[:500]
    base = {
        "bill_id": bill_id, "session_year": item["session_year"],
        "bill_number": item["bill_number"], "reviewed_document_type": DOC_TYPE,
        "confidence": confidence, "rationale": rationale, "reviewer": REVIEWER,
        "review_date": dt.date.today().isoformat(), "supersedes_authority": SUPERSEDES,
    }
    if decision not in ALL_DECISIONS:
        return ({**base, "decision": "insufficient_text", "primitive_axes": "", "policy_poles": "",
                 "rationale": rationale or "unrecognized decision from model"},
                f"unrecognized_decision:{decision!r}")
    if decision in NONSCORING_DECISIONS:
        return ({**base, "decision": decision, "primitive_axes": "", "policy_poles": ""}, None)
    # Scoring decision: validate axes/poles.
    raw_axes = result.get("axes") or []
    pairs: list[tuple[str, str]] = []
    for entry in raw_axes:
        if not isinstance(entry, dict):
            return ({**base, "decision": "mixed_no_scalar_direction", "primitive_axes": "",
                     "policy_poles": ""}, "axes_not_objects")
        axis = str(entry.get("axis", "")).strip()
        pole = str(entry.get("pole", "")).strip()
        try:
            rollcall.validate_primitive(axis, pole)
        except ValueError as exc:
            return ({**base, "decision": "mixed_no_scalar_direction", "primitive_axes": "",
                     "policy_poles": ""}, f"invalid_axis_pole:{exc}")
        pairs.append((axis, pole))
    if not pairs:
        return ({**base, "decision": "mixed_no_scalar_direction", "primitive_axes": "",
                 "policy_poles": ""}, "map_without_axes")
    # Deduplicate while preserving order.
    seen = set()
    dedup = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            dedup.append(pair)
    pairs = dedup
    final_decision = "map" if len(pairs) == 1 else "multi_axis"
    return ({**base, "decision": final_decision,
             "primitive_axes": ";".join(a for a, _ in pairs),
             "policy_poles": ";".join(p for _, p in pairs)}, None)


def review_reason_for(row: dict, reason: str | None) -> str | None:
    """Return the review-queue reason for a produced row, or None when unqueued.

    Schema failures keep their original reason. A clean ``map``/``multi_axis``
    row is queued only when its model confidence is low: the 2026-09-08 contract
    admits it to scoring but requires a review record.
    """
    if reason:
        return reason
    if row["decision"] in SCORING_DECISIONS and row["confidence"] == "low":
        return LOW_CONFIDENCE_REASON
    return None


def cached_path(bill_id: str) -> Path:
    return CACHE / f"{bill_id}.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--limit", type=int, default=0, help="cap bills for a smoke run (0 = all)")
    parser.add_argument("--smoke", action="store_true", help="write to a .smoke.csv, do not touch OUT")
    parser.add_argument("--no-cache", action="store_true", help="ignore existing per-bill cache")
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    key = rollcall.load_openai_key()
    universe = build_universe()
    if args.limit:
        universe = universe.head(args.limit).reset_index(drop=True)
    items = universe.to_dict("records")
    total = len(items)
    print(f"bills to adjudicate: {total:,}")

    results: dict[str, dict] = {}
    review_rows: list[dict] = []

    # Resume from cache.
    pending = []
    for it in items:
        bid = it["bill_id"]
        cp = cached_path(bid)
        if not args.no_cache and cp.exists():
            try:
                results[bid] = json.loads(cp.read_text(encoding="utf-8"))
                continue
            except (json.JSONDecodeError, OSError):
                pass
        pending.append(it)
    print(f"cached: {total - len(pending):,}; pending: {len(pending):,}")

    for start in range(0, len(pending), args.batch_size):
        batch = pending[start:start + args.batch_size]
        by_id = {it["bill_id"]: it for it in batch}
        try:
            content = rollcall.openai_chat(key, MODEL, build_prompt(batch))
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                parsed = parsed.get("items") or parsed.get("results") or []
        except Exception as exc:  # network/JSON: fail the batch closed, keep going
            parsed = []
            print(f"  batch {start//args.batch_size} error: {type(exc).__name__}: {exc}")
        returned = {str(r.get("id", "")).strip(): r for r in parsed if isinstance(r, dict)}
        for bid, it in by_id.items():
            raw = returned.get(bid)
            if raw is None:
                # Also accept a normalized id echo.
                raw = returned.get(norm_bill_id(bid))
            if raw is None:
                row, reason = ({
                    "bill_id": bid, "session_year": it["session_year"],
                    "bill_number": it["bill_number"], "reviewed_document_type": DOC_TYPE,
                    "decision": "insufficient_text", "primitive_axes": "", "policy_poles": "",
                    "confidence": "low", "rationale": "model returned no item for this bill",
                    "reviewer": REVIEWER, "review_date": dt.date.today().isoformat(),
                    "supersedes_authority": SUPERSEDES,
                }, "missing_from_model_response")
            else:
                row, reason = validate_item(raw, it)
            results[bid] = row
            # Do not persist a transient batch omission: caching it would freeze a
            # fail-closed insufficient_text verdict that a plain resume never retries.
            # A genuine model response (including a schema near-miss) is cached.
            if reason != "missing_from_model_response":
                cached_path(bid).write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
            queued_reason = review_reason_for(row, reason)
            if queued_reason:
                review_rows.append({**row, "review_reason": queued_reason})
        done = min(start + args.batch_size, len(pending))
        if done % (args.batch_size * 20) == 0 or done == len(pending):
            print(f"  processed {done:,}/{len(pending):,} pending "
                  f"(api_requests={rollcall.USAGE['api_requests']}, "
                  f"tokens={rollcall.USAGE['total_tokens']:,})")

    # Assemble output in the exact manual schema, one row per bill.
    out_rows = [results[it["bill_id"]] for it in items]
    out = pd.DataFrame(out_rows, columns=OUTPUT_COLUMNS)
    assert out["bill_id"].is_unique, "duplicate bill_id in Luna output"
    target = OUT.with_suffix(".smoke.csv") if args.smoke else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False)

    if review_rows:
        pd.DataFrame(review_rows).to_csv(REVIEW_QUEUE, index=False)

    dist = out["decision"].value_counts().to_dict()
    scoring = int(out["decision"].isin(SCORING_DECISIONS).sum())
    manifest = {
        "model": MODEL, "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "bills": total, "scoring_bills": scoring, "review_queue": len(review_rows),
        "decision_distribution": dist,
        "usage": dict(rollcall.USAGE), "output": str(target.relative_to(ROOT)),
        "smoke": args.smoke,
    }
    if not args.smoke:
        RUN_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
