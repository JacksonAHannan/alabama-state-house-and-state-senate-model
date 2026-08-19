"""Archive and ingest the newest Economist/YouGov generic-ballot topline."""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://yougov.com/en-us/content/the-economist"
RAW = ROOT / "data" / "raw" / "polling" / "silver_recent"
SUPPLEMENT = ROOT / "data" / "processed" / "polling" / "silver_recent_generic_ballot_cells.csv"
HEADERS = {"User-Agent": "Jackson-Hannan-Alabama-forecast/1.0 polling research"}


def latest_topline() -> tuple[str, bytes, str]:
    page = requests.get(PAGE, headers=HEADERS, timeout=45)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")
    links = []
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if "Economist Toplines" in label and "2026" in label:
            links.append((label, anchor["href"]))
    if not links:
        raise RuntimeError("No 2026 Economist/YouGov topline link discovered")
    label, url = links[0]
    pdf = requests.get(url, headers=HEADERS, timeout=60)
    pdf.raise_for_status()
    return label, pdf.content, pdf.url


def parse(content: bytes) -> dict:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    dates = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s*-\s*(\d{1,2}),\s*(2026)", text)
    sample = re.search(r"-\s*([\d,]+)\s+U\.S\.\s+Adult citizens", text)
    question_block = text[text.find("The Democratic candidate"):text.find("The Democratic candidate") + 900]
    question = re.search(
        r"The Democratic candidate[^%]*?(\d+)%.*?The Republican candidate[^%]*?(\d+)%",
        question_block, flags=re.I | re.S,
    )
    if not (dates and sample and question):
        raise RuntimeError("Could not parse date, sample, and generic-ballot topline")
    month, start, end, year = dates.groups()
    month_num = pd.Timestamp(f"{month} 1 {year}").month
    return {"start_date": f"{year}-{month_num:02d}-{int(start):02d}",
            "end_date": f"{year}-{month_num:02d}-{int(end):02d}",
            "sample_size": int(sample.group(1).replace(",", "")),
            "dem_pct": float(question.group(1)), "rep_pct": float(question.group(2))}


def main() -> None:
    label, content, url = latest_topline()
    values = parse(content)
    digest = sha256(content).hexdigest()
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / f"yougov_economist_{values['end_date']}_{digest[:12]}.pdf"
    target.write_bytes(content)
    row = {"poll_id": f"auto_yougov_{values['end_date'].replace('-', '')}", "pollster": "YouGov",
           "silver_grade": "B", "quality_eligible": True, **values, "population": "a",
           "dimension": "overall", "group": "all", "source_path": str(target.relative_to(ROOT)),
           "source_question": "Generic congressional ballot topline", "adapter": "yougov_topline_auto_v1",
           "reviewed": True, "dem_two_party_share": values["dem_pct"] / (values["dem_pct"] + values["rep_pct"]),
           "source_url": url, "source_sha256": digest, "retrieved_on": date.today().isoformat()}
    existing = pd.read_csv(SUPPLEMENT)
    for column in row:
        if column not in existing:
            existing[column] = pd.NA
    new = pd.DataFrame([row]).reindex(columns=existing.columns)
    out = pd.concat([existing[~existing.poll_id.eq(row["poll_id"])], new], ignore_index=True)
    out.to_csv(SUPPLEMENT, index=False)
    print(label, row["poll_id"], row["dem_pct"], row["rep_pct"], target)


if __name__ == "__main__":
    main()
