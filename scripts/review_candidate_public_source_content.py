"""Fetch and triage candidate-specific Alabama Political Reporter search results."""

from __future__ import annotations

from html import unescape
from pathlib import Path
import re
import time

from bs4 import BeautifulSoup
import pandas as pd
import requests

from build_candidate_legislative_activity import ELECTION_DATES, ISSUE_PATTERNS


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
POSTS_API = "https://www.alreporter.com/wp-json/wp/v2/posts"
USER_AGENT = "Jackson-Hannan-Alabama-Legislative-Research/1.0"


def plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(unescape(str(html)), "html.parser").get_text(" ")).strip()


def name_tokens(name: str) -> list[str]:
    cleaned = re.sub(r"[^A-Za-z ]", " ", str(name))
    tokens = [token.lower() for token in cleaned.split() if len(token) > 2]
    # Suffixes and nicknames are not required to establish the same person.
    return [token for token in tokens if token not in {"coach", "mack", "jr"}]


def candidate_name_pattern(name: str) -> re.Pattern[str] | None:
    """Require the candidate's first and last names in one local phrase.

    Requiring name tokens anywhere in an article caused surnames such as White and
    Means to match unrelated prose. Middle names and nicknames remain optional.
    """
    tokens = name_tokens(name)
    if len(tokens) < 2:
        return None
    return re.compile(
        rf"\b{re.escape(tokens[0])}\b.{{0,60}}?\b{re.escape(tokens[-1])}\b",
        re.I | re.S,
    )


def candidate_excerpt(text: str, pattern: re.Pattern[str], radius: int = 650) -> str:
    windows = []
    for match in pattern.finditer(text):
        windows.append(text[max(0, match.start() - radius):match.end() + radius])
    return " … ".join(dict.fromkeys(windows))


def main() -> None:
    discovery = pd.read_csv(RESEARCH / "candidate_public_source_discovery.csv")
    ids = sorted(discovery.result_id.dropna().astype(int).unique())
    posts = {}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        response = session.get(
            POSTS_API,
            params={
                "include": ",".join(map(str, batch)), "per_page": 100,
                "_fields": "id,date,link,title,content,excerpt",
            }, timeout=60,
        )
        response.raise_for_status()
        for post in response.json():
            posts[int(post["id"])] = post
        time.sleep(0.1)

    rows = []
    for source in discovery.itertuples(index=False):
        post = posts.get(int(source.result_id))
        if not post:
            continue
        content = plain_text(post.get("content", {}).get("rendered", ""))
        title = plain_text(post.get("title", {}).get("rendered", source.title))
        pattern = candidate_name_pattern(source.candidate)
        combined = f"{title} {content}"
        exact_candidate_mentioned = pattern is not None and bool(pattern.search(combined))
        if not exact_candidate_mentioned:
            continue
        excerpt = candidate_excerpt(content, pattern)
        issues = [
            issue for issue, pattern in ISSUE_PATTERNS.items()
            if re.search(pattern, excerpt, re.I)
        ] or ["unclassified"]
        date = pd.to_datetime(post.get("date"), errors="coerce")
        election_date = ELECTION_DATES[int(source.election_cycle)]
        timing = "pre_election" if pd.notna(date) and date <= election_date else "post_election"
        for issue in issues:
            rows.append({
                **source._asdict(), "publication_date": date.date() if pd.notna(date) else "",
                "exact_candidate_mentioned": True, "issue_retrieval_tag": issue,
                "temporal_status": timing, "candidate_context_excerpt": excerpt,
                "content_review_status": "needs_human_position_review",
                "automatic_stance_allowed": False,
            })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates([
            "person_id", "url", "issue_retrieval_tag"
        ]).sort_values(["election_cycle", "candidate", "publication_date", "url"])
    frame.to_csv(RESEARCH / "candidate_public_source_content_review.csv", index=False)
    pre = frame.loc[frame.temporal_status.eq("pre_election")]
    print(
        f"Triage rows: {len(frame)}; exact-name sources: {frame.url.nunique()}; "
        f"pre-election sources: {pre.url.nunique()}"
    )


if __name__ == "__main__":
    main()
