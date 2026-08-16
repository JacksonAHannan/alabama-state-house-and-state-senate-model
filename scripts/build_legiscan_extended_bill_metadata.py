"""Normalize subjects, sponsors, history, and amendments from LegiScan archives."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "legiscan" / "alabama"
OUT = ROOT / "data" / "processed" / "legislative"


def main() -> None:
    subjects, sponsors, history, amendments = [], [], [], []
    for archive_path in sorted(RAW.glob("*.zip")):
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.namelist():
                if "/bill/" not in member or not member.endswith(".json"):
                    continue
                record = json.loads(archive.read(member).decode("utf-8-sig"))
                bill = record.get("bill", record)
                bill_id, bill_number = bill.get("bill_id"), bill.get("bill_number")
                session = bill.get("session") or {}
                base = {
                    "bill_id": bill_id, "bill_number": bill_number,
                    "session_id": bill.get("session_id") or session.get("session_id"),
                    "session_name": session.get("session_name"),
                }
                for item in bill.get("subjects") or []:
                    subjects.append({**base, "subject_id": item.get("subject_id"), "subject_name": item.get("subject_name")})
                for item in bill.get("sponsors") or []:
                    sponsors.append({
                        **base, "people_id": item.get("people_id"), "name": item.get("name"),
                        "party": item.get("party"), "role": item.get("role"), "district": item.get("district"),
                        "sponsor_type_id": item.get("sponsor_type_id"), "sponsor_order": item.get("sponsor_order"),
                        "committee_sponsor": item.get("committee_sponsor"),
                    })
                for order, item in enumerate(bill.get("history") or [], start=1):
                    history.append({
                        **base, "history_order": order, "action_date": item.get("date"),
                        "action": item.get("action"), "chamber": item.get("chamber"),
                        "importance": item.get("importance"),
                    })
                for item in bill.get("amendments") or []:
                    amendments.append({
                        **base, "amendment_id": item.get("amendment_id"), "date": item.get("date"),
                        "chamber": item.get("chamber"), "title": item.get("title"),
                        "description": item.get("description"), "adopted": item.get("adopted"),
                        "url": item.get("url"), "state_link": item.get("state_link"),
                        "amendment_hash": item.get("amendment_hash"),
                    })
    tables = {
        "legiscan_bill_subjects.csv": subjects,
        "legiscan_bill_sponsors.csv": sponsors,
        "legiscan_bill_history.csv": history,
        "legiscan_bill_amendments.csv": amendments,
    }
    for filename, rows in tables.items():
        frame = pd.DataFrame(rows).drop_duplicates()
        frame.to_csv(OUT / filename, index=False)
        print(f"{filename}: {len(frame):,}")


if __name__ == "__main__":
    main()
