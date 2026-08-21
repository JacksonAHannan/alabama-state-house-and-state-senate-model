"""Extract auditable sections and outbound citations from cached Ballotpedia pages.

This is staging, not ideological adjudication.  Candidate-authored survey text,
editorial biography text, and scorecard directory links have different authority
and must not be collapsed into one evidence type.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
MANIFEST = IDEOLOGY / "ballotpedia_page_manifest.csv"
CROSSWALK = IDEOLOGY / "ballotpedia_candidate_crosswalk.csv"
SECTIONS = IDEOLOGY / "ballotpedia_candidate_sections.csv"
LINKS = IDEOLOGY / "ballotpedia_candidate_source_links.csv"
HEADING = re.compile(r"^(#{2,5})\s+(.+?)\s*$")
MARKDOWN_LINK = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^\s)]+)(?:\s+\"[^\"]*\")?\)")
KEEP = {"Biography", "Campaign themes", "Scorecards", "Footnotes", "Endorsements", "Campaign website"}


def extract_sections(text: str) -> list[dict[str, str]]:
    rows, current, buffer, subsection_year = [], "", [], ""
    def flush():
        if current and buffer:
            body = "\n".join(buffer).strip()
            if body:
                rows.append({"section":current, "subsection_year":subsection_year, "section_text":body})
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            level, title = len(match.group(1)), re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", match.group(2)).strip()
            if level == 2:
                flush(); buffer=[]; subsection_year=""
                current = title if title in KEEP else ""
            elif current and level >= 3:
                flush(); buffer=[]
                year = re.search(r"\b(19|20)\d{2}\b", title)
                subsection_year = year.group(0) if year else subsection_year
                buffer.append(line)
            continue
        if current:
            buffer.append(line)
    flush()
    return rows


def main() -> None:
    manifest = pd.read_csv(MANIFEST, dtype=str).fillna("")
    crosswalk = pd.read_csv(CROSSWALK, dtype=str).fillna("")
    page_manifest = manifest[(manifest.record_type.eq("candidate_page")) & ~manifest.status.str.startswith("error")]
    page_manifest = page_manifest.drop_duplicates("source_url")
    sections, links = [], []
    for page in page_manifest.itertuples(index=False):
        text = (ROOT / page.local_path).read_text(encoding="utf-8")
        candidates = crosswalk[crosswalk.ballotpedia_url.eq(page.source_url)]
        for section in extract_sections(text):
            section_links = MARKDOWN_LINK.findall(section["section_text"])
            for candidate in candidates.itertuples(index=False):
                base = {"canonical_candidate_id":candidate.canonical_candidate_id,
                        "election_year":candidate.election_year, "candidate_name":candidate.matched_name,
                        "ballotpedia_url":page.source_url, "retrieved_date":page.retrieved_date,
                        "page_sha256":page.sha256, **section}
                sections.append(base)
                for label, url in section_links:
                    links.append({k:base[k] for k in ["canonical_candidate_id","election_year","candidate_name","ballotpedia_url","section","subsection_year"]}
                                 | {"link_text":label, "link_url":url})
    pd.DataFrame(sections).to_csv(SECTIONS, index=False)
    pd.DataFrame(links).drop_duplicates().to_csv(LINKS, index=False)
    if sections:
        frame = pd.DataFrame(sections)
        print(frame.groupby("section").agg(records=("canonical_candidate_id","size"), candidates=("canonical_candidate_id","nunique")).to_string())
    print(f"Source links: {len(pd.DataFrame(links).drop_duplicates()):,}")


if __name__ == "__main__":
    main()
