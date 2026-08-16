"""Select and download a stratified pilot of issue-relevant Alabama bill texts."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import urllib.request

import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"
RAW_TEXT = ROOT / "data" / "raw" / "legiscan" / "bill_text_pilot"
EXTRACTED = ROOT / "data" / "processed" / "legislative" / "bill_text_pilot"


def choose_document(row: pd.Series, documents: pd.DataFrame) -> pd.Series | None:
    pool = documents[documents.bill_id.eq(row.bill_id)].copy()
    if pool.empty:
        return None
    pool["document_date_parsed"] = pd.to_datetime(pool.document_date, errors="coerce")
    vote_date = pd.to_datetime(row.vote_date, errors="coerce")
    prior = pool[pool.document_date_parsed.le(vote_date)] if pd.notna(vote_date) else pool
    if not prior.empty:
        pool = prior
    type_rank = {"Enrolled": 4, "Engrossed": 3, "Substituted": 2, "Introduced": 1}
    pool["type_rank"] = pool.document_type.map(type_rank).fillna(0)
    return pool.sort_values(["document_date_parsed", "type_rank"], ascending=False).iloc[0]


def download(urls: list[str], destination: Path) -> str:
    if destination.exists() and destination.stat().st_size:
        return "cached"
    error = ""
    for url in urls:
        if not url or url == "nan":
            continue
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Jackson-Hannan-Alabama-legislative-research/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response:
                destination.write_bytes(response.read())
            return "downloaded"
        except Exception as exc:  # Preserve failure in manifest and try fallback.
            error = f"{type(exc).__name__}: {exc}"
    return error or "no_url"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-issue", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--min-year", type=int)
    parser.add_argument("--roll-id", type=int)
    args = parser.parse_args()
    queue = pd.read_csv(RESEARCH / "legislative_issue_bill_review_queue.csv")
    if args.min_year:
        queue = queue[queue.session_year.ge(args.min_year)]
    if args.roll_id:
        queue = queue[queue.roll_call_id.eq(args.roll_id)]
    documents = pd.read_csv(DATA / "legiscan_bill_text_manifest.csv")
    selected = (queue.sort_values("party_gap", ascending=False)
                .drop_duplicates(["candidate_issues", "bill_id"])
                .groupby("candidate_issues", group_keys=False).head(args.per_issue))
    selected = selected.drop_duplicates("roll_call_id")
    if args.limit:
        selected = selected.head(args.limit)
    RAW_TEXT.mkdir(parents=True, exist_ok=True)
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    records = []
    for _, row in selected.iterrows():
        document = choose_document(row, documents)
        result = row.to_dict()
        if document is None:
            result["download_status"] = "no_document_metadata"
            records.append(result)
            continue
        doc_id = int(document.doc_id)
        pdf_path = RAW_TEXT / f"{doc_id}.pdf"
        status = download([str(document.state_link), str(document.url)], pdf_path)
        result.update(document.to_dict())
        result["download_status"] = status
        result["local_pdf"] = str(pdf_path.relative_to(ROOT)) if pdf_path.exists() else ""
        if pdf_path.exists():
            result["download_sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            try:
                reader = PdfReader(pdf_path)
                pages = [page.extract_text() or "" for page in reader.pages]
                text_path = EXTRACTED / f"{doc_id}.txt"
                text_path.write_text("\n\n".join(f"[PAGE {i + 1}]\n{text}" for i, text in enumerate(pages)), encoding="utf-8")
                result["local_text"] = str(text_path.relative_to(ROOT))
                result["page_count"] = len(pages)
                result["extracted_characters"] = sum(map(len, pages))
            except Exception as exc:
                result["download_status"] = f"pdf_parse_error: {type(exc).__name__}: {exc}"
        records.append(result)
        print(f"{row.bill_number} / {row.roll_call_id}: {result['download_status']}")
    output_path = DATA / "bill_text_pilot_manifest.csv"
    output = pd.DataFrame(records)
    if args.roll_id and output_path.exists():
        prior = pd.read_csv(output_path)
        output = pd.concat([prior, output], ignore_index=True).drop_duplicates("roll_call_id", keep="last")
    output.to_csv(output_path, index=False)
    print(f"Pilot records: {len(records)}")


if __name__ == "__main__":
    main()
