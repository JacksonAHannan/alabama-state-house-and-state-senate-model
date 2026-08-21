"""Normalize staged Ballotpedia sections into research-ready source tables."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
SECTIONS = IDEOLOGY / "ballotpedia_candidate_sections.csv"
LINKS = IDEOLOGY / "ballotpedia_candidate_source_links.csv"
QUESTIONNAIRES = IDEOLOGY / "ballotpedia_questionnaire_items.csv"
ARTICLES = IDEOLOGY / "ballotpedia_article_and_source_urls.csv"
ENDORSEMENTS = IDEOLOGY / "ballotpedia_group_endorsements.csv"
COALITION_SIGNALS = IDEOLOGY / "ballotpedia_candidate_coalition_signals.csv"
SCORECARDS = IDEOLOGY / "ballotpedia_scorecard_source_registry.csv"

NEWS_DOMAINS = {
    "www.al.com", "blog.al.com", "aldailynews.com", "1819news.com",
    "www.decaturdaily.com", "www.gadsdentimes.com", "web.waaytv.com",
    "www.waaytv.com", "www.shelbycountyreporter.com", "www.bamapolitics.com",
    "news.yahoo.com", "www.therepublic.com",
}
OFFICIAL_DOMAINS = {"www.alabamavotes.gov", "www.sos.alabama.gov", "www.legislature.state.al.us",
                    "governor.alabama.gov", "www.justice.gov", "docs.google.com"}


def clean_url(value: object) -> str:
    url = str(value or "").replace("\\_", "_").strip()
    if not url.startswith(("http://", "https://")):
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, parts.query, parts.fragment))


def source_category(row: pd.Series) -> str:
    url = clean_url(row.link_url); domain = urlsplit(url).netloc
    text = f"{row.link_text} {url}".lower()
    if domain.endswith("ballotpedia.org") or "ballotpedia" in domain:
        return "ballotpedia_internal"
    if row.section == "Scorecards" or any(token in text for token in ("scorecard", "rating", "legislative ratings")):
        return "scorecard_publication"
    if any(token in text for token in ("questionnaire", "candidate connection", "survey", "voter guide")):
        return "questionnaire_or_voter_guide"
    if domain in NEWS_DOMAINS:
        return "news_article_or_profile"
    if domain == "web.archive.org":
        return "archived_source"
    if domain in OFFICIAL_DOMAINS:
        return "official_or_election_source"
    if any(token in text for token in ("campaign website", "campaign site", "official campaign", "vote")):
        return "candidate_or_campaign_site"
    if any(token in text for token in ("endorse", "tea party", "afl-cio", "nfib", "club for growth")):
        return "interest_group_or_endorsement_source"
    return "other_external_source"


def questionnaire_rows(sections: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    selected = sections[(sections.section.eq("Campaign themes"))
                        & sections.subsection_year.eq(sections.election_year)
                        & ~sections.section_text.str.contains("did not complete", case=False, na=False)]
    question = re.compile(r"\*\*(.+?\?)\*\*\s*(.*?)(?=\*\*.+?\?\*\*|$)", re.S)
    for record in selected.itertuples(index=False):
        matches = question.findall(record.section_text)
        if not matches and len(record.section_text.strip()) > 100:
            matches = [("Campaign themes or unstructured survey response", record.section_text)]
        for ordinal, (prompt, answer) in enumerate(matches, 1):
            answer = re.sub(r"\s+", " ", answer).strip()
            if not answer:
                continue
            item_id = hashlib.sha256(
                f"{record.canonical_candidate_id}|{record.election_year}|{ordinal}|{prompt}|{answer}".encode()
            ).hexdigest()[:20].upper()
            rows.append({"questionnaire_item_id":item_id,
                "canonical_candidate_id":record.canonical_candidate_id,
                "election_year":record.election_year,"candidate_name":record.candidate_name,
                "questionnaire_url":record.ballotpedia_url,"questionnaire_provider":"Ballotpedia Candidate Connection or campaign themes",
                "question":re.sub(r"\s+", " ", prompt).strip(),"answer":answer,
                "item_ordinal":ordinal,"temporal_status":"same_cycle_candidate_statement",
                "page_sha256":record.page_sha256,"retrieved_date":record.retrieved_date})
    return rows


def endorsement_rows(sections: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for record in sections[sections.section.eq("Endorsements")].itertuples(index=False):
        text = re.sub(r"\[\[[^]]+\]\]\([^)]+\)", "", record.section_text)
        years = re.findall(r"\b(?:19|20)\d{2}\b", text)
        evidence_year = record.subsection_year or (years[0] if years else "")
        bullets = re.findall(r"(?:^|\n)\s*\*\s+(?:\*\*)?([^\n*][^\n]*?)(?:\*\*)?\s*(?=\n|$)", text)
        for group in bullets:
            group = re.sub(r"\[[^]]+\]\([^)]+\)", "", group)
            group = re.sub(r"\s+", " ", group).strip(" .;:")
            if not group or group.lower().startswith(("see also", "image")):
                continue
            cycle = str(record.election_year)
            temporal = ("pre_or_same_cycle_group_signal" if evidence_year == cycle else
                        "undated_group_signal" if not evidence_year else
                        "post_election" if int(evidence_year) > int(cycle) else "historical_pre_election")
            rows.append({"canonical_candidate_id":record.canonical_candidate_id,
                "election_year":record.election_year,"candidate_name":record.candidate_name,
                "endorsing_group":group,"endorsement_year":evidence_year,
                "temporal_status":temporal,"source_url":record.ballotpedia_url,
                "source_text":re.sub(r"\s+", " ", record.section_text).strip(),
                "page_sha256":record.page_sha256})
    return rows


def main() -> None:
    sections = pd.read_csv(SECTIONS, dtype=str).fillna("")
    links = pd.read_csv(LINKS, dtype=str).fillna("")
    links["link_url"] = links.link_url.map(clean_url)
    links["source_category"] = links.apply(source_category, axis=1)
    external = links[~links.source_category.eq("ballotpedia_internal")].drop_duplicates(
        ["canonical_candidate_id", "election_year", "link_url", "section"])
    external.to_csv(ARTICLES, index=False)
    questionnaires = pd.DataFrame(questionnaire_rows(sections))
    questionnaires.to_csv(QUESTIONNAIRES, index=False)
    endorsements = pd.DataFrame(endorsement_rows(sections)).drop_duplicates()
    endorsements.to_csv(ENDORSEMENTS, index=False)
    coalition = endorsements.copy()
    if len(coalition):
        coalition.insert(0, "coalition_signal_id", [
            hashlib.sha256(f"{row.canonical_candidate_id}|{row.endorsing_group}|{row.endorsement_year}|{row.page_sha256}".encode()).hexdigest()[:20].upper()
            for row in coalition.itertuples(index=False)
        ])
        coalition["model_eligible_same_cycle"] = coalition.temporal_status.eq("pre_or_same_cycle_group_signal")
        coalition["ideological_position_assigned"] = False
        coalition["treatment_note"] = "Coalition evidence only; no issue direction without an explicit group ontology mapping."
    coalition.to_csv(COALITION_SIGNALS, index=False)
    scorecards = external[external.source_category.eq("scorecard_publication")].copy()
    scorecards["scorecard_year"] = scorecards.subsection_year
    scorecards = scorecards.drop_duplicates(["link_url", "scorecard_year", "link_text"])
    scorecards.to_csv(SCORECARDS, index=False)
    print("External source categories:")
    print(external.groupby("source_category").agg(rows=("link_url","size"), unique_urls=("link_url","nunique")).to_string())
    print(f"Questionnaire items: {len(questionnaires):,} across {questionnaires.canonical_candidate_id.nunique() if len(questionnaires) else 0:,} candidates")
    same = endorsements[endorsements.temporal_status.eq("pre_or_same_cycle_group_signal")] if len(endorsements) else endorsements
    print(f"Endorsements: {len(endorsements):,}; contemporaneous: {len(same):,}")
    print(f"External scorecard sources: {len(scorecards):,}")


if __name__ == "__main__":
    main()
