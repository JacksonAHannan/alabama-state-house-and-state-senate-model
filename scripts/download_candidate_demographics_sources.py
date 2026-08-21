"""Download archived public candidate-demographics research files."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "candidate_demographics"
MANIFEST = ROOT / "data" / "processed" / "elections" / "validation" / "candidate_demographics_source_manifest.csv"
SOURCES = [
    {
        "provider": "Reflective Democracy Campaign via Internet Archive",
        "coverage": "US candidates 2012-2018",
        "filename": "RD-Candidate-Analysis-2012-8.zip",
        "url": "https://web.archive.org/web/20210823105537id_/https://wholeads.us/wp-content/uploads/2021/01/RD-Candidate-Analysis-2012-8.zip",
        "source_page": "https://dss.princeton.edu/catalog/resource6303",
    },
    {
        "provider": "Reflective Democracy Campaign via Internet Archive",
        "coverage": "2018 candidates summary",
        "filename": "2018-Candidates-rev-Reflective-Democracy-Campaign-Summary.xlsx",
        "url": "https://web.archive.org/web/20200819145940id_/https://wholeads.us/wp-content/uploads/2019/06/2018-Candidates-rev-Reflective-Democracy-Campaign-Summary-.xlsx",
        "source_page": "https://dss.princeton.edu/catalog/resource6303",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for source in SOURCES:
        path = RAW / source["filename"]
        if not path.exists():
            response = requests.get(source["url"], timeout=120)
            response.raise_for_status()
            path.write_bytes(response.content)
        rows.append({**source, "local_path": str(path.relative_to(ROOT)),
                     "bytes": path.stat().st_size, "sha256": sha256(path)})
    pd.DataFrame(rows).to_csv(MANIFEST, index=False)
    print(pd.DataFrame(rows)[["filename", "bytes", "sha256"]].to_string(index=False))


if __name__ == "__main__":
    main()
