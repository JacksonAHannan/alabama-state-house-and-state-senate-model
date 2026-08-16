"""Extract schema-stable Focaldata generic-ballot banner tables.

Only workbooks containing an explicit ``House generic ballot by BANNER`` table
are accepted. Earlier Focaldata workbooks expose component questions rather
than the final derived ballot and are intentionally rejected.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data" / "processed" / "polling" / "votehub_crosstab_document_review_queue.csv"
OUT = ROOT / "data" / "processed" / "polling" / "votehub_focaldata_extracted_candidates.csv"
REVIEWED = ROOT / "data" / "raw" / "polling" / "votehub_crosstabs_reviewed.csv"

RACE = {
    "White": "white", "Black or African American": "black",
    "Hispanic": "hispanic", "Asian": "asian", "Other / multiple races": "other",
}
EDUCATION = {
    "focaldata_hs_or_less": ["Did not graduate high school", "High school graduate"],
    "focaldata_some_college_or_associate": ["Some college, no degree", "Associate's degree (2-year)"],
    "focaldata_bachelors": ["Bachelor's degree (4-year)"],
    "focaldata_postgrad": ["Graduate or professional degree"],
}


def extract_table(frame: pd.DataFrame, poll_id: str, source_url: str) -> pd.DataFrame:
    hits = [i for i, value in frame.iloc[:, 0].items()
            if isinstance(value, str) and value.strip().lower() == "house generic ballot by banner"]
    if len(hits) != 1:
        raise ValueError(f"Expected one final House generic-ballot banner; found {len(hits)}")
    start = hits[0]
    labels = frame.iloc[start + 2]
    response = frame.iloc[start + 3:start + 14, 0].astype(str)
    dem_row = response[response.eq("The Democratic Party candidate")].index
    rep_row = response[response.eq("The Republican Party candidate")].index
    n_row = response[response.eq("Column n")].index
    pop_row = response[response.eq("Column Population")].index
    if not all(len(x) == 1 for x in (dem_row, rep_row, n_row, pop_row)):
        raise ValueError("Unexpected Focaldata response-row structure")
    label_to_col = {str(value).strip(): col for col, value in labels.items() if pd.notna(value)}

    def combine(dimension: str, group: str, source_labels: list[str]) -> dict:
        missing = set(source_labels) - set(label_to_col)
        if missing:
            raise ValueError(f"Missing Focaldata banner columns: {sorted(missing)}")
        cols = [label_to_col[x] for x in source_labels]
        populations = pd.to_numeric(frame.loc[pop_row[0], cols], errors="raise")
        dem_counts = pd.to_numeric(frame.loc[dem_row[0] + 1, cols], errors="raise")
        rep_counts = pd.to_numeric(frame.loc[rep_row[0] + 1, cols], errors="raise")
        bases = pd.to_numeric(frame.loc[n_row[0], cols], errors="raise")
        return {"poll_id": poll_id, "dimension": dimension, "group": group,
                "dem_pct": 100 * dem_counts.sum() / populations.sum(),
                "rep_pct": 100 * rep_counts.sum() / populations.sum(),
                "cell_base": int(bases.sum()), "population_override": "a",
                "source_url": source_url, "page_or_table": "House generic ballot by BANNER",
                "extraction_method": "focaldata_xlsx_weighted_count_adapter_v1", "reviewed": True}

    rows = [combine("race", group, [label]) for label, group in RACE.items()]
    rows.extend(combine("education", group, labels) for group, labels in EDUCATION.items())
    total = combine("overall", "all", ["Total"])
    # Exact reconstruction of the displayed total is a schema/checksum guard.
    total_col = label_to_col["Total"]
    displayed_dem = 100 * float(frame.loc[dem_row[0], total_col])
    displayed_rep = 100 * float(frame.loc[rep_row[0], total_col])
    if abs(total["dem_pct"] - displayed_dem) > 0.02 or abs(total["rep_pct"] - displayed_rep) > 0.02:
        raise ValueError("Weighted-count reconstruction does not match displayed Focaldata topline")
    rows.append(total)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--promote-reviewed", action="store_true",
                        help="Merge schema-validated adapter output into the reviewed-cell input")
    args = parser.parse_args()
    queue = pd.read_csv(QUEUE)
    candidates = []
    failures = []
    focal = queue[(queue.pollster == "Focaldata") & queue.local_path.notna() & queue.asset_kind.eq("xlsx")]
    # Identical documents can be linked to several VoteHub universes. The final
    # banner's adult universe is attached once, preferring an adult catalog row.
    for sha, part in focal.groupby("sha256"):
        chosen = part.sort_values("population", key=lambda x: x.ne("a")).iloc[0]
        path = ROOT / str(chosen.local_path).replace("\\", "/")
        try:
            workbook = pd.ExcelFile(path)
            table_sheets = [s for s in workbook.sheet_names if s not in {"Info", "Headline results"}]
            extracted = None
            for sheet in table_sheets:
                frame = pd.read_excel(path, sheet_name=sheet, header=None)
                try:
                    extracted = extract_table(frame, str(chosen.id), str(chosen.asset_url))
                    break
                except ValueError as exc:
                    if "found 0" not in str(exc):
                        raise
            if extracted is None:
                raise ValueError("No final House generic-ballot banner (component questions only)")
            candidates.append(extracted)
        except Exception as exc:  # failure report is an intentional pipeline output
            failures.append({"sha256": sha, "poll_ids": "|".join(part.id.astype(str)),
                             "local_path": chosen.local_path, "reason": str(exc)})
    result = pd.concat(candidates, ignore_index=True) if candidates else pd.DataFrame()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    pd.DataFrame(failures).to_csv(OUT.with_name("votehub_focaldata_extraction_failures.csv"), index=False)
    print(f"Extracted {len(result)} cells from {result.poll_id.nunique() if len(result) else 0} polls; "
          f"rejected {len(failures)} incompatible workbooks")
    if args.promote_reviewed and len(result):
        existing = pd.read_csv(REVIEWED) if REVIEWED.exists() else pd.DataFrame(columns=result.columns)
        if "extraction_method" in existing:
            existing = existing[~existing.extraction_method.eq("focaldata_xlsx_weighted_count_adapter_v1")]
        combined = pd.concat([existing, result], ignore_index=True)
        combined = combined.drop_duplicates(["poll_id", "dimension", "group"], keep="last")
        combined.to_csv(REVIEWED, index=False)
        print(f"Promoted {len(result)} adapter-validated cells to {REVIEWED}")


if __name__ == "__main__":
    main()
