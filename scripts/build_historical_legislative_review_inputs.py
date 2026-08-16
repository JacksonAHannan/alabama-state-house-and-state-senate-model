"""Build review queues for historical roll-call repair and issue coding."""
from __future__ import annotations

from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"


def main() -> None:
    senate = pd.read_csv(DATA / "historical_senate_journal_rollcalls.csv")
    audit = pd.read_csv(DATA / "historical_senate_section63_audit.csv")
    invalid = senate[~senate.count_valid].copy()
    invalid["review_reason"] = "printed_member_count_mismatch"
    invalid["passage_event_id"] = None
    mismatch = audit[~audit.audit_status.eq("matched_same_measure_count_valid")].copy()
    mismatch["review_reason"] = mismatch.audit_status
    review = pd.concat([
        invalid[["review_reason", "rollcall_id", "session", "asset", "local_path", "page", "bill_type", "bill_number", "context"]],
        mismatch.rename(columns={"matched_rollcall_id": "rollcall_id"})[
            ["review_reason", "rollcall_id", "session", "asset", "local_path", "page", "bill_type", "bill_number", "context"]
        ],
    ], ignore_index=True).drop_duplicates()
    review.to_csv(DATA / "historical_senate_rollcall_manual_review_queue.csv", index=False)

    frames = []
    for chamber in ("house", "senate"):
        rollcalls = pd.read_csv(DATA / f"historical_{chamber}_journal_rollcalls.csv")
        eligible = rollcalls[rollcalls.count_valid & rollcalls.bill_number.notna()].copy()
        eligible["priority"] = eligible.motion_type.map({"final_passage": 1, "conference_report": 2}).fillna(3)
        eligible = (eligible.sort_values(["session_year", "bill_type", "bill_number", "priority", "page"])
                    .drop_duplicates(["session_year", "bill_type", "bill_number"], keep="first"))
        eligible["chamber"] = chamber
        frames.append(eligible)
    queue = pd.concat(frames, ignore_index=True)
    act_links = []
    for chamber in ("house", "senate"):
        links = pd.read_csv(DATA / f"historical_{chamber}_rollcall_act_links.csv")
        links = links[links.act_link_status.eq("unique_act_match")][["rollcall_id", "act_citation", "title"]]
        act_links.append(links)
    links = pd.concat(act_links, ignore_index=True).drop_duplicates("rollcall_id")
    queue = queue.merge(links, on="rollcall_id", how="left", validate="one_to_one")
    queue["issue_code"] = None
    queue["policy_direction"] = None
    queue["coding_status"] = "queued"
    queue[[
        "rollcall_id", "session_year", "chamber", "bill_type", "bill_number", "motion_type",
        "act_citation", "title", "context", "local_path", "page", "issue_code",
        "policy_direction", "coding_status",
    ]].to_csv(DATA / "historical_rollcall_issue_classification_queue.csv", index=False)
    print(f"Manual repair rows: {len(review):,}")
    print(f"Distinct historical measures queued for issue coding: {len(queue):,}")


if __name__ == "__main__":
    main()
