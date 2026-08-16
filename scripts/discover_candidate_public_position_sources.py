"""Discover candidate-specific Alabama Political Reporter archive pages."""

from pathlib import Path
import time

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
SEARCH_API = "https://www.alreporter.com/wp-json/wp/v2/search"
USER_AGENT = "Jackson-Hannan-Alabama-Legislative-Research/1.0"


def main() -> None:
    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")
    rows = []
    for candidate in cohort.itertuples(index=False):
        response = requests.get(
            SEARCH_API,
            params={"search": candidate.candidate, "per_page": 100},
            headers={"User-Agent": USER_AGENT}, timeout=30,
        )
        response.raise_for_status()
        for result in response.json():
            rows.append({
                "person_id": candidate.person_id, "candidate": candidate.candidate,
                "election_cycle": int(candidate.cycle), "source_site": "Alabama Political Reporter",
                "result_id": result.get("id"), "title": result.get("title"),
                "url": result.get("url"), "result_type": result.get("type"),
                "review_status": "discovered_needs_content_review",
            })
        time.sleep(0.1)
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(["person_id", "url"]).sort_values(
            ["election_cycle", "candidate", "title"]
        )
    frame.to_csv(RESEARCH / "candidate_public_source_discovery.csv", index=False)
    print(f"Discovered {len(frame)} candidate-specific archive results for {frame.person_id.nunique()} candidates")


if __name__ == "__main__":
    main()
