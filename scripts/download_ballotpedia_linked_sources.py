"""Download external scorecards discovered through Ballotpedia footnotes."""
from __future__ import annotations

import argparse
import hashlib
import mimetypes
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ballotpedia" / "linked_scorecards"
REGISTRY = ROOT / "data" / "processed" / "ideology" / "ballotpedia_scorecard_source_registry.csv"
MANIFEST = ROOT / "data" / "processed" / "ideology" / "ballotpedia_linked_scorecard_manifest.csv"


def target_path(url: str, content_type: str = "") -> Path:
    path = urlsplit(url).path
    suffix = Path(path).suffix.lower()
    if suffix not in {".pdf", ".html", ".htm", ".csv", ".xlsx", ".xls"}:
        suffix = mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) or ".html"
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(path).stem)[-80:] or "scorecard"
    return RAW / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}_{name}{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-sources", type=int)
    parser.add_argument("--delay", type=float, default=.5)
    args = parser.parse_args()
    sources = pd.read_csv(REGISTRY, dtype=str).fillna("").drop_duplicates("link_url")
    if args.max_sources is not None:
        sources = sources.head(args.max_sources)
    prior = pd.read_csv(MANIFEST, dtype=str).fillna("") if MANIFEST.exists() else pd.DataFrame()
    prior_by_url = prior.drop_duplicates("source_url", keep="last").set_index("source_url") if len(prior) else None
    session = requests.Session()
    session.headers["User-Agent"] = "AlabamaLegislativeCMOResearch/1.0 (public-source archival research)"
    rows = []
    for number, source in enumerate(sources.itertuples(index=False), 1):
        if prior_by_url is not None and source.link_url in prior_by_url.index:
            old = prior_by_url.loc[source.link_url].to_dict(); old["status"] = "cached"; rows.append(old)
            continue
        try:
            response = session.get(source.link_url, timeout=60, allow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            target = target_path(source.link_url, content_type)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(response.content)
            rows.append({"organization":source.link_text,"source_url":source.link_url,
                "final_url":response.url,"retrieved_date":str(date.today()),
                "local_path":str(target.relative_to(ROOT)),"content_type":content_type,
                "bytes":len(response.content),"sha256":hashlib.sha256(response.content).hexdigest(),
                "status":"downloaded"})
        except Exception as exc:
            rows.append({"organization":source.link_text,"source_url":source.link_url,
                "final_url":"","retrieved_date":str(date.today()),"local_path":"",
                "content_type":"","bytes":0,"sha256":"","status":f"error:{type(exc).__name__}"})
        print(f"Linked scorecards {number:,}/{len(sources):,}", flush=True)
        time.sleep(args.delay)
    output = pd.DataFrame(rows)
    if len(prior):
        output = pd.concat([prior, output], ignore_index=True).drop_duplicates("source_url", keep="last")
    output.to_csv(MANIFEST, index=False)
    print(output.status.value_counts().to_string())


if __name__ == "__main__":
    main()
