"""Download and validate Alabama amendment PDFs from official state hosts."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from io import BytesIO
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
from pypdf import PdfReader

from download_alabama_bill_text_archive import official_candidates


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
RAW = ROOT / "data" / "raw" / "alabama_legislature" / "amendments"
STATUS = DATA / "alabama_amendment_download_status.csv"
USER_AGENT = "Jackson-Hannan-Alabama-Legislative-Research/1.0"


def destination(row: pd.Series) -> Path:
    return (RAW / str(int(row.session_year)) / str(int(row.session_id)) /
            str(int(row.bill_id)) / f"{int(row.amendment_id)}.pdf")


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
        "amendment_id": int(row.amendment_id), "bill_id": int(row.bill_id),
        "bill_number": row.bill_number, "session_id": int(row.session_id),
        "session_year": int(row.session_year), "date": row.date,
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
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    amendments = pd.read_csv(DATA / "legiscan_bill_amendments.csv")
    bills = pd.read_csv(DATA / "legiscan_alabama_bills.csv")
    amendments = amendments.merge(
        bills[["bill_id", "session_year"]].drop_duplicates("bill_id"),
        on="bill_id", how="left", validate="many_to_one",
    ).sort_values(["session_year", "session_id", "bill_id", "amendment_id"])
    if args.limit:
        amendments = amendments.head(args.limit)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch, row, args.timeout, args.retries)
                   for _, row in amendments.iterrows()]
        for index, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if index % 500 == 0:
                print(f"Processed {index:,}/{len(futures):,} amendments", flush=True)
    current = pd.DataFrame(results).sort_values(
        ["session_year", "session_id", "bill_id", "amendment_id"]
    )
    current.to_csv(STATUS, index=False)
    print(f"Processed {len(amendments):,}: {current.status.value_counts().to_dict()}")
    print(f"Status manifest: {STATUS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
