"""Download and validate Alabama legislative bill texts from official state hosts.

LegiScan's bulk JSON supplies the version manifest, but document bytes are fetched
from the Alabama Legislature links. Downloads are resumable and stored by
session/bill/document identifiers so repeated bill numbers cannot collide.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from io import BytesIO
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
RAW = ROOT / "data" / "raw" / "alabama_legislature" / "bill_text"
STATUS = DATA / "alabama_bill_text_download_status.csv"
USER_AGENT = "Jackson-Hannan-Alabama-Legislative-Research/1.0"


def official_candidates(state_link: str) -> list[str]:
    """Return official-host URL candidates, modernizing legacy ALISON paths."""
    parsed = urlparse(state_link)
    path = parsed.path
    candidates: list[str] = []
    marker = "SearchableInstruments/"
    if marker in path:
        suffix = path.split(marker, 1)[1]
        suffixes = [suffix]
        canonical = re.sub(
            r"-(int|eng|enr)\.pdf$",
            lambda match: f"-{match.group(1).title()}.pdf",
            suffix,
            flags=re.IGNORECASE,
        )
        suffixes.append(canonical)
        for versioned_suffix in dict.fromkeys(suffixes):
            candidates.append(
                "https://alison.legislature.state.al.us/files/pdf/"
                f"SearchableInstruments/{versioned_suffix}"
            )
            candidates.append(
                "https://www.legislature.state.al.us/pdf/"
                f"SearchableInstruments/{versioned_suffix.replace('/PrintFiles/', '/')}"
            )
    if parsed.hostname in {
        "alison.legislature.state.al.us",
        "www.legislature.state.al.us",
        "legislature.state.al.us",
        "alisondb.legislature.state.al.us",
    }:
        candidates.append(state_link.replace("http://", "https://", 1))
    return list(dict.fromkeys(candidates))


def destination(row: pd.Series) -> Path:
    year = str(row.session_year)
    session = str(int(row.session_id))
    bill = str(int(row.bill_id))
    doc = str(int(row.doc_id))
    kind = str(row.document_type).lower().replace(" ", "_")
    return RAW / year / session / bill / f"{doc}_{kind}.pdf"


def validate_pdf(payload: bytes) -> tuple[int, str]:
    if not payload.startswith(b"%PDF-"):
        raise ValueError("response is not a PDF")
    reader = PdfReader(BytesIO(payload))
    if not reader.pages:
        raise ValueError("PDF contains no pages")
    return len(reader.pages), hashlib.sha256(payload).hexdigest()


def fetch(row: pd.Series, timeout: int, retries: int) -> dict[str, object]:
    path = destination(row)
    base = {
        "doc_id": int(row.doc_id), "bill_id": int(row.bill_id),
        "bill_number": row.bill_number, "session_id": int(row.session_id),
        "session_year": int(row.session_year), "document_type": row.document_type,
        "local_path": str(path.relative_to(ROOT)),
    }
    if path.exists():
        try:
            payload = path.read_bytes()
            pages, digest = validate_pdf(payload)
            return base | {"status": "existing", "source_url": "", "bytes": len(payload),
                           "pages": pages, "sha256": digest, "error": ""}
        except Exception:
            path.unlink()

    errors = []
    for url in official_candidates(str(row.state_link)):
        for attempt in range(retries + 1):
            try:
                request = Request(url, headers={"User-Agent": USER_AGENT})
                with urlopen(request, timeout=timeout) as response:
                    payload = response.read()
                pages, digest = validate_pdf(payload)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                return base | {"status": "downloaded", "source_url": url,
                               "bytes": len(payload), "pages": pages,
                               "sha256": digest, "error": ""}
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                errors.append(f"{url}: {type(exc).__name__}: {exc}")
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
    return base | {"status": "failed", "source_url": "", "bytes": 0, "pages": 0,
                   "sha256": "", "error": " | ".join(errors)[-4000:]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--year", type=int, action="append")
    parser.add_argument(
        "--all-versions", action="store_true",
        help="Download every document version instead of one canonical text per bill.",
    )
    args = parser.parse_args()

    documents = pd.read_csv(DATA / "legiscan_bill_text_manifest.csv")
    bills = pd.read_csv(DATA / "legiscan_alabama_bills.csv")
    documents = documents.merge(
        bills[["bill_id", "session_year"]].drop_duplicates("bill_id"),
        on="bill_id", how="left", validate="many_to_one",
    )
    documents = documents[documents.session_year.ge(2010)].copy()
    if args.year:
        documents = documents[documents.session_year.isin(args.year)]
    if not args.all_versions:
        priority = {"Enrolled": 3, "Engrossed": 2, "Introduced": 1}
        documents["version_priority"] = documents.document_type.map(priority).fillna(0)
        documents = (documents.sort_values(
            ["bill_id", "version_priority", "document_date", "doc_id"]
        ).drop_duplicates("bill_id", keep="last"))
    documents = documents.sort_values(["session_year", "session_id", "bill_id", "doc_id"])
    if args.limit:
        documents = documents.head(args.limit)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(fetch, row, args.timeout, args.retries): int(row.doc_id)
            for _, row in documents.iterrows()
        }
        for index, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if index % 500 == 0:
                print(f"Processed {index:,}/{len(futures):,} documents")

    current = pd.DataFrame(results)
    if STATUS.exists():
        previous = pd.read_csv(STATUS)
        current = pd.concat([previous, current], ignore_index=True)
        current = current.drop_duplicates("doc_id", keep="last")
    current.sort_values(["session_year", "session_id", "bill_id", "doc_id"]).to_csv(
        STATUS, index=False
    )
    counts = current[current.doc_id.isin(documents.doc_id)].status.value_counts().to_dict()
    print(f"Processed {len(documents):,} documents: {counts}")
    print(f"Status manifest: {STATUS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
