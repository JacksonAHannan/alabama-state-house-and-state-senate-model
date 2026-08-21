"""Extract candidate-level ratings from Ballotpedia-discovered scorecard PDFs."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader
from oe_normalize import normalize_name


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
MANIFEST = IDEOLOGY / "ballotpedia_linked_scorecard_manifest.csv"
CANONICAL = ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv"
VOTESMART = IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv"
OUT = IDEOLOGY / "ballotpedia_candidate_scorecard_ratings.csv"
AUDIT = IDEOLOGY / "ballotpedia_scorecard_rating_audit.csv"
OVERLAP_AUDIT = IDEOLOGY / "ballotpedia_scorecard_votesmart_overlap.csv"
VOTESMART_RATINGS = IDEOLOGY / "votesmart_all_1998_2022_ratings.csv"


def person_name_key(value: object) -> str:
    text = str(value or "")
    if "," in text:
        surname, given = text.split(",", 1)
        text = f"{given} {surname}"
    return normalize_name(text)


def scorecard_year(text: str, path: str) -> int | None:
    values = re.findall(r"\b20(?:1[4-9]|2[0-2])\b", f"{Path(path).name} {text[:1500]}")
    return int(values[0]) if values else None


def extract_club(texts: list[str], year: int) -> list[dict]:
    rows = []
    pattern = re.compile(r"^(.+?)\s+(HD|SD)-(\d{3})\s+([RD])\s+(\d+)%", re.M)
    for page in texts:
        for name, code, district, party, score in pattern.findall(page):
            rows.append({"legislator_name":name.strip(),"chamber":"house" if code == "HD" else "senate",
                         "district":int(district),"party":party,"rating":float(score),"rating_year":year})
    return rows


def extract_acu(texts: list[str], year: int) -> list[dict]:
    rows = []
    for page in texts:
        upper = page.upper()
        chamber = "senate" if "ALABAMA SENATE" in upper and "SCORE" in upper else "house" if "ALABAMA HOUSE" in upper and "SCORE" in upper else ""
        if not chamber:
            continue
        for line in page.splitlines():
            match = re.match(r"^(.+?)\s+([RD])\s+(\d{1,3})\s+(.+)$", line.strip())
            if not match:
                continue
            pct = re.search(r"\b(\d{1,3})%", match.group(4))
            if pct:
                rows.append({"legislator_name":match.group(1).strip(),"chamber":chamber,
                             "district":int(match.group(3)),"party":match.group(2),
                             "rating":float(pct.group(1)),"rating_year":year})
    return rows


def extract_nfib(texts: list[str], year: int) -> list[dict]:
    rows = []
    chamber = ""
    for page in texts:
        for line in page.splitlines():
            upper = line.upper()
            if "SENATE VOTING RECORD" in upper:
                chamber = "senate"; continue
            if "HOUSE OF REPRESENTATIVES VOTING RECORD" in upper:
                chamber = "house"; continue
            match = re.match(r"^(.+?)\s+(?:\^\s+)?[YN*].*?\s+(\d{1,3})%$", line.strip())
            if chamber and match:
                rows.append({"legislator_name":match.group(1).strip(),"chamber":chamber,
                             "district":None,"party":"","rating":float(match.group(2)),"rating_year":year})
    return rows


def main() -> None:
    manifest = pd.read_csv(MANIFEST, dtype=str).fillna("")
    files = manifest[(manifest.status.isin(["downloaded","cached"]))
                     & manifest.content_type.str.contains("pdf", case=False)]
    extracted, audits = [], []
    for source in files.itertuples(index=False):
        texts = [(page.extract_text() or "") for page in PdfReader(ROOT / source.local_path).pages]
        year = scorecard_year("\n".join(texts), source.local_path)
        if not year:
            audits.append({"source_url":source.source_url,"organization":source.organization,
                           "status":"year_unresolved","rows":0}); continue
        organization = source.organization
        if "Club for Growth" in organization:
            rows = extract_club(texts, year); canonical_org = "The Club for Growth"
        elif "Federation of Independent Business" in organization:
            rows = extract_nfib(texts, year); canonical_org = "National Federation of Independent Business - Alabama"
        elif "Conservative Union" in organization:
            rows = extract_acu(texts, year); canonical_org = "American Conservative Union (ACU)"
        else:
            rows = []; canonical_org = organization
        for row in rows:
            row.update({"organization":canonical_org,"source_url":source.source_url,
                        "local_path":source.local_path,"source_sha256":source.sha256})
        extracted.extend(rows)
        audits.append({"source_url":source.source_url,"organization":canonical_org,
                       "status":"parsed" if rows else "no_rating_rows_parsed","rows":len(rows)})
    ratings = pd.DataFrame(extracted).drop_duplicates()
    canonical = pd.read_csv(CANONICAL, dtype=str).fillna("")
    canonical["year_num"] = pd.to_numeric(canonical.year)
    canonical["district_num"] = pd.to_numeric(canonical.district)
    canonical["effective_name"] = canonical.canonical_name
    if VOTESMART.exists():
        votesmart = pd.read_csv(VOTESMART, dtype=str).fillna("")
        votesmart = votesmart[votesmart.accepted.str.lower().eq("true")][
            ["canonical_candidate_id", "votesmart_candidate"]]
        canonical = canonical.merge(votesmart, on="canonical_candidate_id", how="left", validate="one_to_one")
        encoded = canonical.canonical_name.str.match(r"^GS[LU]\d+[DR]", case=False)
        canonical.loc[encoded & canonical.votesmart_candidate.ne(""), "effective_name"] = canonical.votesmart_candidate
    canonical["name_key"] = canonical.effective_name.map(person_name_key)
    if len(ratings):
        ratings["election_cycle"] = ratings.rating_year.map(lambda year: 2018 if year <= 2018 else 2022)
        # District-bearing publications join deterministically. NFIB rows retain
        # names but no printed district and therefore stay unmatched pending a
        # conservative name/chamber identity pass.
        ratings["name_key"] = ratings.legislator_name.map(person_name_key)
        keyed = ratings[ratings.district.notna()].merge(
            canonical[["canonical_candidate_id","person_id","canonical_name","year_num","chamber","district_num","canonical_party","name_key"]],
            left_on=["election_cycle","chamber","district","party","name_key"],
            right_on=["year_num","chamber","district_num","canonical_party","name_key"],how="left",validate="many_to_one")
        unkeyed = ratings[ratings.district.isna()].copy()
        unkeyed["name_key"] = unkeyed.legislator_name.map(person_name_key)
        name_candidates = canonical.drop_duplicates(["year_num","chamber","name_key"], keep=False)
        unkeyed = unkeyed.merge(
            name_candidates[["canonical_candidate_id","person_id","canonical_name","year_num","chamber","name_key"]],
            left_on=["election_cycle","chamber","name_key"], right_on=["year_num","chamber","name_key"],
            how="left", validate="many_to_one")
        ratings = pd.concat([keyed, unkeyed], ignore_index=True, sort=False)
    ratings.to_csv(OUT, index=False)
    pd.DataFrame(audits).to_csv(AUDIT, index=False)
    overlap_rows = []
    votesmart = pd.read_csv(VOTESMART_RATINGS, dtype=str).fillna("") if VOTESMART_RATINGS.exists() else pd.DataFrame()
    if len(ratings):
        matched = ratings[ratings.canonical_candidate_id.notna() & ratings.canonical_candidate_id.ne("")].copy()
        if len(votesmart):
            votesmart["name_key"] = votesmart.candidate.map(person_name_key)
            votesmart["rating_year"] = pd.to_numeric(votesmart.rating_year_end, errors="coerce")
            votesmart_keys = set(zip(votesmart.name_key, votesmart.organization, votesmart.rating_year))
        else:
            votesmart_keys = set()
        for organization, group in ratings.groupby("organization"):
            exact_overlap = sum(
                (row.name_key, organization, row.rating_year) in votesmart_keys
                for row in group.itertuples(index=False)
            )
            overlap_rows.append({
                "organization": organization,
                "parsed_rating_rows": len(group),
                "canonical_matches": int(group.canonical_candidate_id.notna().mul(group.canonical_candidate_id.ne("")).sum()),
                "unique_canonical_candidates": matched.loc[matched.organization.eq(organization), "canonical_candidate_id"].nunique(),
                "exact_votesmart_name_org_year_overlap": exact_overlap,
                "integration_decision": (
                    "integrate_explicit_market_governance_mapping" if organization == "The Club for Growth"
                    else "exclude_duplicate_votesmart_source" if organization == "National Federation of Independent Business - Alabama"
                    else "exclude_broad_unmapped_scorecard"
                ),
            })
    pd.DataFrame(overlap_rows).to_csv(OVERLAP_AUDIT, index=False)
    print(pd.DataFrame(audits).groupby(["organization","status"]).rows.sum().to_string())
    matches = ratings.canonical_candidate_id.notna().mul(ratings.canonical_candidate_id.ne("")).sum() if len(ratings) else 0
    print(f"Extracted ratings: {len(ratings):,}; canonical candidate matches: {matches:,}")


if __name__ == "__main__":
    main()
