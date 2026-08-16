"""Build all-universe sponsorship evidence and an amendment review inventory."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
WINDOWS = {1998:(1998,1998), 2002:(1999,2002), 2006:(2003,2006), 2010:(2007,2010),
           2014:(2011,2014), 2018:(2015,2018), 2022:(2019,2022)}


def amendment_author(title: object) -> str:
    text = str(title or "")
    match = re.search(r"(?:House|Senate)\s+(.+?)\s+(?:first |second |third )?(?:Amendment|Substitute)\b", text, re.I)
    if not match or match.group(1).lower() in {"committee", "floor"}:
        return ""
    return match.group(1).strip()


def main() -> None:
    bills = pd.read_csv(LEG / "comprehensive_bill_classifications.csv", low_memory=False)
    sponsors = pd.read_csv(LEG / "legiscan_bill_sponsors.csv", low_memory=False).merge(
        bills[["bill_id","session_year","issue_code","issue_codes","yea_direction",
               "classification_status","classification_reason"]], on="bill_id", how="left", validate="many_to_one")
    sponsors["action_type"] = np.where(sponsors.sponsor_order.eq(0), "primary_sponsor", "cosponsor")
    sponsors["action_weight"] = np.where(sponsors.sponsor_order.eq(0), 1.0, 0.5)
    sponsors["sponsor_position"] = sponsors.yea_direction
    sponsors.to_csv(LEG / "comprehensive_bill_sponsor_positions.csv", index=False)

    candidates = pd.read_csv(IDEOLOGY / "candidate_ideology_full_universe.csv", low_memory=False)
    candidates["people_id"] = candidates.member_source_id.astype(str).str.extract(r"LEGISCAN-(\d+)", expand=False)
    candidates["people_id"] = pd.to_numeric(candidates.people_id, errors="coerce")
    rows = []
    directional = sponsors[sponsors.sponsor_position.notna()].copy()
    for c in candidates.itertuples():
        if pd.isna(c.people_id) or c.year not in WINDOWS:
            continue
        start, end = WINDOWS[c.year]
        hit = directional[(directional.people_id.eq(c.people_id)) & directional.session_year.between(start,end)].copy()
        for issue, part in hit.groupby("issue_code"):
            rows.append({"canonical_candidate_id": c.canonical_candidate_id, "year": c.year,
                         "issue_code": issue, "sponsorship_issue_score": np.average(part.sponsor_position, weights=part.action_weight),
                         "directional_sponsored_bills": len(part), "primary_sponsored_bills": int(part.action_type.eq("primary_sponsor").sum())})
    summary = pd.DataFrame(rows, columns=["canonical_candidate_id","year","issue_code","sponsorship_issue_score",
                                         "directional_sponsored_bills","primary_sponsored_bills"])
    summary.to_csv(IDEOLOGY / "candidate_sponsorship_issue_full_universe.csv", index=False)

    amendments = pd.read_csv(LEG / "legiscan_bill_amendments.csv", low_memory=False).merge(
        bills[["bill_id","session_year","issue_code","issue_codes","yea_direction"]], on="bill_id", how="left", validate="many_to_one")
    amendments["attributed_author_text"] = amendments.title.map(amendment_author)
    amendments["amendment_direction"] = np.nan
    amendments["classification_status"] = np.where(
        amendments.attributed_author_text.ne(""), "needs_amendment_text_direction_review", "needs_author_and_text_review")
    amendments["classification_note"] = "Parent-bill direction is context only and is not inherited by the amendment."
    amendments.to_csv(LEG / "comprehensive_amendment_classification_queue.csv", index=False)
    print(f"Processed {len(sponsors):,} sponsor actions; {len(directional):,} concern directionally classified bills")
    print(f"Produced {len(summary):,} candidate-issue sponsorship profiles")
    print(f"Processed {len(amendments):,} amendments; {amendments.attributed_author_text.ne('').sum():,} have an author string")


if __name__ == "__main__":
    main()
