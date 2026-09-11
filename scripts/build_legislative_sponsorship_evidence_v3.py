"""Translate bulk bill sponsorship into ontology-v3 candidate ideology evidence.

A legislator who sponsors a bill is credited with supporting that bill's mapped
policy pole, weighted above a recorded vote because authoring or co-signing a
measure is a more direct signal of priority than voting on it. Every sponsored
bill counts, whether or not it ever reached a recorded floor vote, so bills that
died in committee still inform ideology through who chose to sponsor them. Bill
direction reuses the same conservative canonical translation as the roll-call vote
channel (`build_frontier_rollcall_ontology.canonical_mapping`), so votes and
sponsorship live on one ontology. Temporal eligibility mirrors the vote builder.

Output columns match `candidate_legislative_position_evidence_v3.csv` exactly so
this ledger slots into `build_candidate_position_evidence_v3.py` and
`build_candidate_issue_valence_v3.py` unchanged.
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ideology_ontology_v3 import ONTOLOGY_VERSION, family_loading, validate_primitive
from build_frontier_rollcall_ontology import canonical_mapping, split_pairs
from build_legislative_position_evidence_v3 import WINDOWS, general_election_date

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
MANUAL = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications.csv"
SPONSORS = LEG / "legiscan_bill_sponsors.csv"
CROSSWALK = IDEOLOGY / "candidate_legislator_identity_crosswalk.csv"
OUT = IDEOLOGY / "candidate_legislative_sponsorship_evidence_v3.csv"

# Sponsorship is weighted above a recorded vote (1.0): sponsoring a measure is a
# more direct signal of a legislator's priorities than a floor vote on it.
SPONSORSHIP_WEIGHT = 1.2


def norm_id(value: object) -> str:
    text = str(value).strip()
    if text in ("", "nan", "None", "NaN"):
        return ""
    return text[:-2] if text.endswith(".0") else text


def digest(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:20].upper()


def bill_admitted_pairs() -> dict[str, tuple[list[tuple[str, str, str, str, str, str]], int, str]]:
    """Map bill_id -> (admitted (axis, pole, src_axis, src_pole, rule, confidence) list,
    session_year, bill_number), for bills the frontier layer maps to a policy pole.

    Uses the same conservative translation as the roll-call ontology; only pairs
    admitted there contribute, so sponsorship and votes score on identical axes.
    """
    manual = pd.read_csv(MANUAL, low_memory=False).fillna("")
    manual = manual[manual.decision.isin(["map", "multi_axis"])]
    out: dict[str, tuple[list, int, str]] = {}
    for row in manual.itertuples(index=False):
        pairs = split_pairs(pd.Series(row._asdict()))
        admitted: list[tuple[str, str, str, str, str, str]] = []
        seen: set[tuple[str, str]] = set()
        for src_axis, src_pole in pairs:
            mapping = canonical_mapping(src_axis, src_pole)
            if not mapping:
                continue
            axis, pole, rule = mapping
            if (axis, pole) in seen:
                continue
            validate_primitive(axis, pole)
            seen.add((axis, pole))
            admitted.append((axis, pole, src_axis, src_pole, rule, str(row.confidence)))
        if not admitted:
            continue
        try:
            session_year = int(float(str(row.session_year)))
        except (TypeError, ValueError):
            continue
        out[norm_id(row.bill_id)] = (admitted, session_year, str(row.bill_number))
    return out


def main() -> None:
    bills = bill_admitted_pairs()

    sponsors = pd.read_csv(SPONSORS, low_memory=False)
    sponsors["bill_id"] = sponsors.bill_id.map(norm_id)
    sponsors["people_id"] = sponsors.people_id.map(norm_id)
    sponsors = sponsors[sponsors.bill_id.isin(bills) & sponsors.people_id.ne("")]

    # people_id -> set of sponsored bill_ids (every sponsor role counts equally).
    from collections import defaultdict
    pid_bills: dict[str, set[str]] = defaultdict(set)
    for row in sponsors.itertuples(index=False):
        pid_bills[row.people_id].add(row.bill_id)

    crosswalk = pd.read_csv(CROSSWALK, dtype=str).fillna("")
    crosswalk["people_id"] = crosswalk.people_id.map(norm_id)
    crosswalk = crosswalk[crosswalk.people_id.ne("")]
    crosswalk["year_num"] = pd.to_numeric(crosswalk.year, errors="coerce")
    crosswalk = crosswalk[crosswalk.year_num.isin(WINDOWS)]

    attributable_pids = set(pid_bills) & set(crosswalk.people_id)

    rows: list[dict] = []
    for cand in crosswalk.itertuples(index=False):
        pid = cand.people_id
        if pid not in pid_bills:
            continue
        year = int(cand.year_num)
        start, end = WINDOWS[year]
        cutoff = general_election_date(year)
        for bill_id in pid_bills[pid]:
            admitted, session_year, bill_number = bills[bill_id]
            if not (start <= session_year <= end):
                continue
            # Sponsorship carries no exact date; a regular-session action precedes
            # the November election. Use a transparent mid-session placeholder for
            # the temporal cutoff, as the vote builder does for undated records.
            if date(session_year, 6, 1) > cutoff:
                continue
            for axis, pole, src_axis, src_pole, rule, confidence in admitted:
                family, direction = family_loading(axis, pole)
                rows.append({
                    "ontology_version": ONTOLOGY_VERSION,
                    "evidence_id": digest("sponsorship", cand.canonical_candidate_id, bill_id, axis),
                    "canonical_candidate_id": cand.canonical_candidate_id,
                    "person_id": cand.person_id,
                    "candidate_name": cand.canonical_name,
                    "election_cycle": year,
                    "evidence_date": f"{session_year}-session-sponsorship",
                    "temporal_status": "pre_or_same_cycle_legislative_action",
                    "source_type": "bill_sponsorship",
                    "source_provider": "Alabama Legislature via LegiScan",
                    "source_record_id": f"sponsorship:{bill_id}",
                    "source_url": "",
                    "item_id": digest(bill_id, axis),
                    "policy_family": src_axis,
                    "policy_key": f"{axis}_{bill_number}",
                    "primitive_axis": axis,
                    "policy_pole": pole,
                    "candidate_stance": "support",
                    "position_value": 1.0,
                    "response_mode": "sponsorship",
                    "family": family or "",
                    "family_direction": direction if direction is not None else np.nan,
                    "family_contribution": 1.0 * direction if direction is not None else np.nan,
                    "constituency_tags_json": "[]",
                    "confidence": confidence or "medium",
                    "adjudication_authority": f"frontier_luna_sponsorship:{rule}",
                    "evidence_weight": SPONSORSHIP_WEIGHT,
                    "source_text": f"Sponsored {bill_number}",
                    "raw_answer": "sponsor",
                })

    evidence = pd.DataFrame(rows)
    if not evidence.empty:
        assert evidence.evidence_id.is_unique, "duplicate sponsorship evidence_id"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    evidence.to_csv(OUT, index=False)
    n_cand = evidence.canonical_candidate_id.nunique() if not evidence.empty else 0
    n_axes = evidence.primitive_axis.nunique() if not evidence.empty else 0
    print(f"Wrote {len(evidence):,} candidate sponsorship evidence records "
          f"from {len(bills):,} mapped bills; {n_cand} candidate-cycles; {n_axes} axes; "
          f"{len(attributable_pids)} attributable sponsors "
          f"({len(set(pid_bills))} distinct sponsors of mapped bills)")


if __name__ == "__main__":
    main()
