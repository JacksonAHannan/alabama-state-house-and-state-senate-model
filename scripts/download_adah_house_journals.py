"""Download Alabama House or Senate journals from ADAH Preservica."""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from html import unescape
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = {
    "house": "SO_27c37c3b-c276-4068-b37d-0118f5822e29",
    "senate": "SO_7a5c1db0-0c19-4ae7-9d07-b71d19a1c246",
}
RAW = ROOT / "data" / "raw" / "alabama_legislature" / "house_journals"
MANIFEST = RAW / "manifest.csv"
COLLECTION_ID = COLLECTIONS["house"]
BASE = "https://adah.access.preservica.com"
USER_AGENT = "Jackson-Hannan-Alabama-Legislative-Research/1.0"
ITEM_RE = re.compile(
    r"result-item[^>]+onclick=\"window\.location='([^']+)'\"[^>]+title=\"([^\"]+)\"",
    re.I,
)


def fetch(url: str, timeout: int, retries: int) -> tuple[bytes, str, dict[str, str]]:
    error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                headers = {key.lower(): value for key, value in response.headers.items()}
                return response.read(), response.geturl(), headers
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            error = exc
            if attempt < retries:
                time.sleep(0.75 * (attempt + 1))
    assert error is not None
    raise error


def safe_name(value: str) -> str:
    value = unescape(value).strip()
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).rstrip(". ")


def children(entity_id: str, timeout: int, retries: int) -> list[tuple[str, str, str]]:
    url = f"{BASE}/uncategorized/{entity_id}/"
    first = fetch(url, timeout, retries)[0].decode("utf-8", "replace")
    max_pages_match = re.search(r'data-max-pages="(\d+)"', first)
    max_pages = int(max_pages_match.group(1)) if max_pages_match else 1
    pages = [first]
    for page in range(2, max_pages + 1):
        page_url = f"{url}?pg={page}&ajax=1"
        pages.append(fetch(page_url, timeout, retries)[0].decode("utf-8", "replace"))
    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for html in pages:
        for link, title in ITEM_RE.findall(html):
            match = re.search(r"/(SO|IO)_[0-9a-f-]+", link, re.I)
            if not match:
                continue
            entity = match.group(0).lstrip("/")
            if entity not in seen:
                seen.add(entity)
                found.append((entity[:2].upper(), entity, safe_name(title)))
    return found


def inventory(timeout: int, retries: int, collection_id: str = COLLECTION_ID) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    sessions = [(entity_id, title) for kind, entity_id, title
                in children(collection_id, timeout, retries)
                if kind == "SO" and re.match(r"^(?:19|20)\d{2}_", title)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        session_futures = {pool.submit(children, entity_id, timeout, retries): (entity_id, title)
                           for entity_id, title in sessions}
        session_contents = []
        for future in as_completed(session_futures):
            entity_id, title = session_futures[future]
            session_contents.append((title, future.result()))
            print(f"Inventoried session folders {len(session_contents)}/{len(sessions)}", flush=True)

        volume_futures = {}
        for session, volumes in session_contents:
            for volume_kind, volume_id, volume in volumes:
                if volume_kind == "IO":
                    assets.append({"session": session, "volume": "", "asset": volume,
                                   "asset_id": volume_id})
                else:
                    volume_futures[pool.submit(children, volume_id, timeout, retries)] = (
                        session, volume
                    )
        completed = 0
        for future in as_completed(volume_futures):
            session, volume = volume_futures[future]
            completed += 1
            for asset_kind, asset_id, asset in future.result():
                if asset_kind == "IO":
                    assets.append({"session": session, "volume": volume, "asset": asset,
                                   "asset_id": asset_id})
            if completed % 20 == 0 or completed == len(volume_futures):
                print(f"Inventoried volume folders {completed}/{len(volume_futures)}: "
                      f"{len(assets):,} assets", flush=True)
    return assets


def download_asset(row: dict[str, str], timeout: int, retries: int,
                   raw_dir: Path = RAW) -> dict[str, str | int]:
    directory = raw_dir / row["session"]
    if row["volume"]:
        directory /= row["volume"]
    path = directory / f'{row["asset"]}.pdf'
    result: dict[str, str | int] = row | {"local_path": str(path.relative_to(ROOT))}
    if path.exists() and path.stat().st_size > 4 and path.read_bytes()[:5] == b"%PDF-":
        payload = path.read_bytes()
        return result | {"status": "existing", "bytes": len(payload),
                         "sha256": hashlib.sha256(payload).hexdigest(), "source_url": "", "error": ""}
    try:
        asset_url = f'{BASE}/uncategorized/{row["asset_id"]}/'
        html = fetch(asset_url, timeout, retries)[0].decode("utf-8", "replace")
        resource = re.search(r"https://us\.preservica\.com/Render/render/external\?[^\"<]+", html)
        if not resource:
            raise ValueError("asset page has no Preservica renderer URL")
        render_html = fetch(unescape(resource.group(0)), timeout, retries)[0].decode("utf-8", "replace")
        content = re.search(r"defaultUrl',\s*'([^']+)'", render_html)
        if not content:
            raise ValueError("renderer page has no content URL")
        payload, source_url, _ = fetch(unescape(content.group(1)), timeout, retries)
        if not payload.startswith(b"%PDF-"):
            raise ValueError("downloaded content is not a PDF")
        directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return result | {"status": "downloaded", "bytes": len(payload),
                         "sha256": hashlib.sha256(payload).hexdigest(),
                         "source_url": source_url, "error": ""}
    except Exception as exc:  # keep the complete crawl running and record failures
        return result | {"status": "failed", "bytes": 0, "sha256": "", "source_url": "",
                         "error": f"{type(exc).__name__}: {exc}"}


def write_manifest(rows: list[dict[str, str | int]], raw_dir: Path = RAW) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = raw_dir / "manifest.csv"
    fields = ["session", "volume", "asset", "asset_id", "local_path", "status", "bytes",
              "sha256", "source_url", "error"]
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (str(row["session"]), str(row["volume"]),
                                                       str(row["asset"]))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--chamber", choices=sorted(COLLECTIONS), default="house")
    args = parser.parse_args()
    raw_dir = ROOT / "data" / "raw" / "alabama_legislature" / f"{args.chamber}_journals"
    manifest = raw_dir / "manifest.csv"
    assets = inventory(args.timeout, args.retries, COLLECTIONS[args.chamber])
    print(f"Found {len(assets):,} {args.chamber} journal PDFs", flush=True)
    if args.inventory_only:
        return
    rows: list[dict[str, str | int]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download_asset, row, args.timeout, args.retries, raw_dir) for row in assets]
        for index, future in enumerate(as_completed(futures), 1):
            rows.append(future.result())
            if index % 50 == 0 or index == len(futures):
                counts = {status: sum(row["status"] == status for row in rows)
                          for status in ("downloaded", "existing", "failed")}
                print(f"Processed {index:,}/{len(futures):,}: {counts}", flush=True)
                write_manifest(rows, raw_dir)
    write_manifest(rows, raw_dir)
    failed = sum(row["status"] == "failed" for row in rows)
    print(f"Manifest: {manifest.relative_to(ROOT)}; failures: {failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
