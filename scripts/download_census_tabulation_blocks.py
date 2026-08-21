"""Download official Census 2000/2010 Alabama tabulation-block shapefiles."""
from __future__ import annotations

import hashlib
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from warehouse import ROOT

SOURCES = {
    2000: "https://www2.census.gov/geo/tiger/TIGER2010/TABBLOCK/2000/tl_2010_01_tabblock00.zip",
    2010: "https://www2.census.gov/geo/tiger/TIGER2010/TABBLOCK/2010/tl_2010_01_tabblock10.zip",
}
DESTINATION = ROOT / "data/raw/census/tabulation_blocks"
MANIFEST = DESTINATION / "source_manifest.csv"


def digest(path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    rows = []
    for vintage, url in SOURCES.items():
        target = DESTINATION / url.rsplit("/", 1)[-1]
        if not target.exists():
            temporary = target.with_suffix(".zip.part")
            print(f"Downloading {vintage} blocks from {url}")
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(target)
        rows.append({"vintage": vintage, "provider": "US Census Bureau",
                     "url": url, "local_path": target.relative_to(ROOT).as_posix(),
                     "bytes": target.stat().st_size, "sha256": digest(target),
                     "verified_at_utc": datetime.now(timezone.utc).isoformat()})
    pd.DataFrame(rows).to_csv(MANIFEST, index=False)
    print(pd.DataFrame(rows)[["vintage", "bytes", "sha256"]].to_string(index=False))


if __name__ == "__main__":
    main()
