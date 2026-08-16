"""Download and checksum recent public assets from A-range Silver pollsters."""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "polling" / "silver_recent"
MANIFEST = OUT / "manifest.csv"

ASSETS = [
    ("fox_beacon_shaw_2026_07_crosstabs.pdf", "Beacon Research/Shaw & Co. Research", "A-", "2026-07-17", "2026-07-20", "crosstabs", "https://static.foxnews.com/foxnews.com/content/uploads/2026/07/fox_july-17-20-2026_national_cross-tabs_july-27-release.pdf"),
    ("fox_beacon_shaw_2026_07_topline.pdf", "Beacon Research/Shaw & Co. Research", "A-", "2026-07-17", "2026-07-20", "topline", "https://static.foxnews.com/foxnews.com/content/uploads/2026/07/fox_july-17-20-2026_national_topline_july-27-release.pdf"),
    ("echelon_2026_07_crosstabs.xlsx", "Echelon Insights", "A-", "2026-07-09", "2026-07-13", "crosstabs", "https://docs.google.com/spreadsheets/d/1tupLF7a50dTC-mx8k8mzT1WdbExscW3I/export?format=xlsx"),
    ("echelon_2026_07_topline.pdf", "Echelon Insights", "A-", "2026-07-09", "2026-07-13", "topline", "https://echeloninsights.com/hubfs/_Media%20for%20Insights%20Blog/July%202026%20Voter%20Omnibus%20Topline%20-%20Updated%20External.pdf"),
    ("cygnal_2026_07_deck.pdf", "Cygnal", "A", "2026-06-30", "2026-07-01", "presentation_deck", "https://www.cygn.al/wp-content/uploads/2026/07/24136-Cygnal-National-Jul-26-NVT-Deck-Public-2.pdf"),
    ("cygnal_2026_08_deck.pdf", "Cygnal", "A", "2026-08-06", "2026-08-07", "presentation_deck", "https://www.cygn.al/wp-content/uploads/2026/08/24265-Cygnal-National-Aug26-NVT-Deck-Public-1.pdf"),
    ("quinnipiac_2026_06_release.pdf", "Quinnipiac University", "B+", "2026-06-18", "2026-06-22", "release_tables", "https://poll.qu.edu/images/polling/us/us06242026_ujrk36.pdf"),
    ("cnbc_hart_pos_2026_q2_topline.pdf", "Hart Research Associates/Public Opinion Strategies", "A-", "2026-07-08", "2026-07-12", "topline", "https://fm.cnbc.com/applications/cnbc.com/resources/editorialfiles/2026/07/17/CNBC_Q2_2026_Topline.pdf"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = []
    for filename, pollster, grade, start, end, kind, url in ASSETS:
        # A normal browser user agent is required by CNBC's public CDN.
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
        response.raise_for_status()
        content = response.content
        magic = content[:4]
        if filename.endswith(".pdf") and magic != b"%PDF":
            raise ValueError(f"{filename}: response is not a PDF")
        if filename.endswith(".xlsx") and magic[:2] != b"PK":
            raise ValueError(f"{filename}: response is not an XLSX archive")
        path = OUT / filename
        path.write_bytes(content)
        rows.append({
            "filename": filename, "pollster": pollster, "silver_grade": grade,
            "field_start": start, "field_end": end, "asset_kind": kind,
            "source_url": url, "retrieved_utc": retrieved, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
        print(f"Downloaded {filename} ({len(content):,} bytes)")
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
