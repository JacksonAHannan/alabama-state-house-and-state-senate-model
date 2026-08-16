"""Extract versioned bill-document metadata from LegiScan API JSON archives."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "legiscan" / "alabama"
OUT = ROOT / "data" / "processed" / "legislative" / "legiscan_bill_text_manifest.csv"


def main() -> None:
    rows = []
    for archive_path in sorted(RAW.glob("*.zip")):
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.namelist():
                if "/bill/" not in member or not member.endswith(".json"):
                    continue
                record = json.loads(archive.read(member).decode("utf-8-sig"))
                bill = record.get("bill", record)
                session = bill.get("session", {})
                for document in bill.get("texts") or []:
                    rows.append({
                        "bill_id": bill.get("bill_id"), "bill_number": bill.get("bill_number"),
                        "session_id": bill.get("session_id") or session.get("session_id"),
                        "session_name": session.get("session_name"), "doc_id": document.get("doc_id"),
                        "document_date": document.get("date"), "document_type": document.get("type"),
                        "mime": document.get("mime"), "url": document.get("url"),
                        "state_link": document.get("state_link"), "text_size": document.get("text_size"),
                        "text_hash": document.get("text_hash"), "source_archive": archive_path.name,
                    })
    frame = pd.DataFrame(rows).drop_duplicates("doc_id", keep="last")
    frame.to_csv(OUT, index=False)
    print(f"Wrote {len(frame):,} versioned bill-document records for {frame.bill_id.nunique():,} bills")


if __name__ == "__main__":
    main()
