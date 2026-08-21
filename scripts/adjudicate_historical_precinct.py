"""Interactive CLI for durable historical precinct geography decisions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import pandas as pd

from warehouse import ROOT

QUEUE = ROOT / "data/processed/precinct_history/historical_precinct_adjudication_queue.csv"
DECISIONS = ROOT / "data/manual/precinct_history/historical_precinct_adjudications.csv"
COLUMNS = ["case_id", "cycle", "county_key", "precinct_key", "decision", "donor_vtd_id",
           "confidence", "reviewer_note", "reviewed_at_utc", "reviewer"]


def load_decisions() -> pd.DataFrame:
    if not DECISIONS.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(DECISIONS, dtype=str).fillna("").reindex(columns=COLUMNS)


def upsert(row: dict[str, object]) -> None:
    decisions = load_decisions()
    decisions = decisions[decisions.case_id.ne(str(row["case_id"]))]
    decisions = pd.concat([decisions, pd.DataFrame([row], columns=COLUMNS)], ignore_index=True)
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    decisions.sort_values(["cycle", "county_key", "precinct_key"]).to_csv(DECISIONS, index=False)


def show(row: pd.Series) -> None:
    print(f"\n[{int(row.priority_rank)}] {row.case_id}: {int(row.cycle)} {row.county_key} — {row.precinct_key}")
    print(f"Priority legislative activity: {int(row.priority_activity):,}; "
          f"all-office diagnostic: {int(row.turnout_proxy):,}")
    print(f"Race assignments: {row.known_race_assignments}; split ballot: {row.is_split_precinct}")
    print(f"Suggested donor: {row.suggested_donor_vtd_id} — {row.suggested_donor_name} "
          f"(name {row.name_match_score}, margin {row.name_match_margin})")
    print(f"Adjacent aliases: {row.alias_evidence or '[none]'}")
    print(f"Neighbor-cycle names: {row.adjacent_name_evidence or '[none]'}")
    print(f"Geocoder: {row.geocoder_evidence or '[none]'}")
    print(f"DOJ: {row.doj_evidence or '[none]'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id")
    parser.add_argument("--top", type=int, default=200)
    parser.add_argument("--reviewer", default="Jackson Hannan")
    args = parser.parse_args()
    queue = pd.read_csv(QUEUE).fillna("")
    decided = set(load_decisions().case_id)
    candidates = queue[queue.physical_adjudication_candidate.astype(str).str.lower().eq("true")
                       & queue.priority_rank.le(args.top) & ~queue.case_id.isin(decided)]
    if args.case_id:
        candidates = queue[queue.case_id.eq(args.case_id)]
    if candidates.empty:
        print("No undecided cases in scope."); return
    row = candidates.iloc[0]; show(row)
    print("\n1 accept suggested donor | 2 enter donor VTD | 3 non-geographic/admin | 4 defer | q quit")
    choice = input("Decision: ").strip().lower()
    if choice == "q": return
    if choice == "1":
        decision, donor = "accept_donor", str(row.suggested_donor_vtd_id)
        if not donor: raise ValueError("No suggested donor exists for this case")
    elif choice == "2":
        decision, donor = "accept_donor", input("Donor VTD ID: ").strip()
    elif choice == "3": decision, donor = "non_geographic", ""
    elif choice == "4": decision, donor = "defer", ""
    else: raise ValueError(f"Unknown decision {choice!r}")
    confidence = input("Confidence [low/medium/high]: ").strip().lower() or "medium"
    if confidence not in {"low", "medium", "high"}: raise ValueError("Invalid confidence")
    note = input("Reviewer note: ").strip()
    upsert({"case_id": row.case_id, "cycle": int(row.cycle), "county_key": row.county_key,
            "precinct_key": row.precinct_key, "decision": decision, "donor_vtd_id": donor,
            "confidence": confidence, "reviewer_note": note,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(), "reviewer": args.reviewer})
    print(f"Saved {decision} for {row.case_id}")


if __name__ == "__main__":
    main()
