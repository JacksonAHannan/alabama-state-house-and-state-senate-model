"""Prioritize documentary requests for unresolved precinct changes."""
from __future__ import annotations

import pandas as pd

from warehouse import ROOT

BASE = ROOT / "data/processed/precinct_history"
OUT = BASE / "precinct_document_request_manifest.csv"
SUMMARY = ROOT / "project_docs/audits/PRECINCT_DOCUMENT_REQUEST_PRIORITIES.md"


def main() -> None:
    queue = pd.read_csv(BASE / "historical_precinct_adjudication_queue.csv").fillna("")
    doj = pd.read_csv(BASE / "doj_precinct_candidate_submissions.csv", dtype={"submission_number": str}).fillna("")
    rows = []
    for row in queue.itertuples(index=False):
        for number in str(row.intervening_submission_numbers).split("|"):
            if number:
                rows.append({"submission_number": number, "cycle": int(row.cycle),
                             "county_key": row.county_key, "case_id": row.case_id,
                             "precinct_key": row.precinct_key,
                             "priority_activity": float(row.priority_activity)})
    cases = pd.DataFrame(rows)
    if cases.empty:
        manifest = pd.DataFrame()
    else:
        grouped = cases.groupby("submission_number").agg(
            affected_cases=("case_id", "nunique"),
            affected_activity=("priority_activity", "sum"),
            affected_cycles=("cycle", lambda values: "|".join(map(str, sorted(set(values))))),
            affected_counties=("county_key", lambda values: "|".join(sorted(set(values))))).reset_index()
        manifest = grouped.merge(doj, on="submission_number", how="left")
        manifest["priority_score"] = manifest.affected_activity + 250 * manifest.affected_cases
        manifest["requested_materials"] = (
            "submission packet; county resolution; precinct list; map; legal boundary description; determination correspondence")
        manifest["retrieval_status"] = "underlying_packet_not_in_local_archive"
        manifest = manifest.sort_values("priority_score", ascending=False)
    manifest.to_csv(OUT, index=False)
    top = manifest.head(15)
    lines = ["# Precinct documentary request priorities", "",
             "The local DOJ weekly notices identify a change but generally do not contain the underlying map or resolution.", "",
             "| Rank | Submission | County | Cases | Activity | Description |",
             "|---:|---|---|---:|---:|---|"]
    for rank, row in enumerate(top.itertuples(index=False), 1):
        description = str(row.descriptions).replace("|", "/")
        lines.append(f"| {rank} | {row.submission_number} | {row.affected_counties} | "
                     f"{row.affected_cases} | {row.affected_activity:.0f} | {description} |")
    lines += ["", "Request these packets from the DOJ Voting Section and the Alabama Legislative Reapportionment Office. "
              "Each request should cite the exact submission number and ask for the original maps, resolutions, boundary descriptions, and correspondence."]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest)} prioritized DOJ packet requests to {OUT}")


if __name__ == "__main__":
    main()
