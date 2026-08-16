"""Download historical Alabama act volumes from the ADAH Internet Archive collection."""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

COLLECTION = "alabama-acts"
KEEP_FORMATS = {"Additional Text PDF", "Text PDF", "DjVuTXT", "Djvu XML", "Scandata"}


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.load(response)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def retrieve(urls: list[str], target: Path, attempts: int = 3) -> None:
    temporary = target.with_suffix(target.suffix + ".partial")
    last_error = None
    for url in urls:
        for attempt in range(1, attempts + 1):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "JacksonHannan-AlabamaElectionResearch/1.0"})
                with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as stream:
                    while block := response.read(1024 * 1024):
                        stream.write(block)
                temporary.replace(target)
                return
            except Exception as error:
                last_error = error
                if temporary.exists(): temporary.unlink()
                if attempt < attempts: time.sleep(2 ** attempt)
    raise last_error


def collection_items(years: list[int]) -> list[dict]:
    year_query = " OR ".join(f"year:{year}" for year in years)
    query = urllib.parse.quote(f"collection:{COLLECTION} AND ({year_query})")
    url = ("https://archive.org/advancedsearch.php?"
           f"q={query}&fl[]=identifier,title,date,year,description&rows=200&page=1&output=json")
    return get_json(url)["response"]["docs"]


def download(root: Path, years: list[int]) -> pd.DataFrame:
    destination = root / "data" / "raw" / "alabama_legislature" / "acts" / "internet_archive"
    destination.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).isoformat()
    rows = []
    for item in collection_items(years):
        identifier = item["identifier"]
        metadata = get_json(f"https://archive.org/metadata/{identifier}")
        item_dir = destination / identifier
        item_dir.mkdir(parents=True, exist_ok=True)
        selected = [f for f in metadata["files"] if f.get("format") in KEEP_FORMATS]
        selected += [f for f in metadata["files"] if f.get("name") == f"{identifier}_meta.xml"]
        for file in selected:
            name = file["name"]
            target = item_dir / name
            quoted = urllib.parse.quote(name)
            url = f"https://archive.org/download/{identifier}/{quoted}"
            direct_urls = [f"https://{metadata[host]}{metadata['dir']}/{quoted}"
                           for host in ("d1", "d2") if metadata.get(host) and metadata.get("dir")]
            expected = int(file.get("size") or 0)
            if not target.exists() or (expected and target.stat().st_size != expected):
                print(f"Downloading {identifier}/{name}", flush=True)
                retrieve(direct_urls + [url], target)
            rows.append({
                "year": int(item["year"]), "identifier": identifier,
                "title": item.get("title", ""), "description": item.get("description", ""),
                "file_name": name, "format": file.get("format", ""),
                "bytes": target.stat().st_size, "sha256": sha256(target),
                "source_url": url, "retrieved_at_utc": retrieved,
                "local_path": str(target.relative_to(root)).replace("\\", "/"),
            })
    result = pd.DataFrame(rows).sort_values(["year", "identifier", "file_name"])
    result.to_csv(destination / "source_manifest.csv", index=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, nargs="+", default=[1994, 1998])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = download(root, args.years)
    print(result.groupby(["year", "identifier"]).agg(files=("file_name", "size"),
          megabytes=("bytes", lambda x: round(x.sum() / 1024**2, 1))).to_string())


if __name__ == "__main__":
    main()
