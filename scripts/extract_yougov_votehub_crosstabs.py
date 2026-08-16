"""Extract generic-ballot demographic cells from YouGov tabulation PDFs."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

import fitz
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data" / "processed" / "polling" / "votehub_crosstab_document_review_queue.csv"
CATALOG = ROOT / "data" / "raw" / "polling" / "votehub_generic_ballot_catalog.json"
OUT = ROOT / "data" / "processed" / "polling" / "votehub_yougov_extracted_candidates.csv"
REVIEWED = ROOT / "data" / "raw" / "polling" / "votehub_crosstabs_reviewed.csv"
PCT = re.compile(r"^(\d{1,3})%$")
BASE = re.compile(r"^\(([\d,]+)\)$")


def sequence_between(lines: list[str], start: str, end: str, pattern: re.Pattern, count: int = 12) -> list[int]:
    i, j = lines.index(start), lines.index(end)
    values = [int(pattern.match(x).group(1).replace(",", "")) for x in lines[i + 1:j] if pattern.match(x)]
    if len(values) < count:
        raise ValueError(f"Only {len(values)} values between {start!r} and {end!r}")
    return values[:count]


def extract_page(text: str, poll_id: str, source_url: str, page: int) -> pd.DataFrame:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if "Generic Congressional Vote" not in text:
        raise ValueError("Linked page is not a generic congressional-vote table")
    expected = ["Total", "Male", "Female", "White", "Black", "Hispanic", "18-29", "30-44",
                "45-64", "65+", "No degree", "College grad"]
    # The first table must expose YouGov's stable Sex/Race/Age/Education banner.
    header_start = lines.index("Total", lines.index("Education"))
    if lines[header_start:header_start + len(expected)] != expected:
        raise ValueError("Unexpected YouGov demographic banner")
    dem = sequence_between(lines, "The Democratic Party candidate", "The Republican Party candidate", PCT)
    rep = sequence_between(lines, "The Republican Party candidate", "Other", PCT)
    n_start = lines.index("Unweighted N")
    bases = [int(BASE.match(x).group(1).replace(",", "")) for x in lines[n_start + 1:] if BASE.match(x)][:12]
    if len(bases) != 12:
        raise ValueError("Could not identify 12 first-table unweighted bases")
    cells = [("overall", "all", 0), ("race", "white", 3), ("race", "black", 4),
             ("race", "hispanic", 5), ("education", "yougov_no_degree", 10),
             ("education", "yougov_college_grad", 11)]
    return pd.DataFrame([{"poll_id": poll_id, "dimension": dimension, "group": group,
                          "dem_pct": dem[index], "rep_pct": rep[index], "cell_base": bases[index],
                          "population_override": "a", "source_url": source_url,
                          "page_or_table": f"PDF page {page}: Generic Congressional Vote",
                          "extraction_method": "yougov_pdf_text_banner_adapter_v1", "reviewed": True}
                         for dimension, group, index in cells])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--promote-reviewed", action="store_true")
    args = parser.parse_args()
    queue, catalog = pd.read_csv(QUEUE), pd.read_json(CATALOG)
    yougov = queue[(queue.pollster == "YouGov") & queue.local_path.notna() & queue.asset_kind.eq("pdf")]
    candidates, failures = [], []
    for sha, part in yougov.groupby("sha256"):
        # Prefer the adult-citizen topline corresponding to the PDF's first table.
        part = part.merge(catalog[["id", "answers"]], on="id", how="left", suffixes=("", "_catalog"))
        chosen = part.sort_values("population", key=lambda x: x.ne("a")).iloc[0]
        try:
            doc = fitz.open(ROOT / str(chosen.local_path).replace("\\", "/"))
            match = re.search(r"#page=(\d+)", str(chosen.asset_url))
            hinted = [int(match.group(1))] if match else []
            discovered = [i + 1 for i, p in enumerate(doc)
                          if "Generic Congressional Vote" in p.get_text("text")]
            pages = list(dict.fromkeys(hinted + discovered))
            result, page_errors = None, []
            for page in pages:
                try:
                    result = extract_page(doc[page - 1].get_text("text"), str(chosen.id),
                                          str(chosen.asset_url), page)
                    break
                except Exception as exc:
                    page_errors.append(str(exc))
            if result is None:
                raise ValueError("; ".join(page_errors) if page_errors else "No generic-vote crosstab page found")
            # Check the extracted adult total against VoteHub when an adult row exists.
            answers = {str(x.get("choice", "")).lower(): float(x["pct"]) for x in (chosen.answers or [])}
            total = result[result.dimension.eq("overall")].iloc[0]
            dem_api = next((v for k, v in answers.items() if k in {"dem", "democrat", "democratic"}), None)
            rep_api = next((v for k, v in answers.items() if k in {"rep", "republican", "gop"}), None)
            if (str(chosen.population).lower() == "a" and dem_api is not None and
                    (abs(total.dem_pct - dem_api) > 1.1 or abs(total.rep_pct - rep_api) > 1.1)):
                raise ValueError("PDF total does not match the selected VoteHub topline")
            candidates.append(result)
        except Exception as exc:
            failures.append({"sha256": sha, "poll_ids": "|".join(part.id.astype(str)),
                             "local_path": chosen.local_path, "reason": str(exc)})
    result = pd.concat(candidates, ignore_index=True) if candidates else pd.DataFrame()
    result.to_csv(OUT, index=False)
    pd.DataFrame(failures).to_csv(OUT.with_name("votehub_yougov_extraction_failures.csv"), index=False)
    print(f"Extracted {len(result)} cells from {result.poll_id.nunique() if len(result) else 0} polls; "
          f"rejected {len(failures)} documents")
    if args.promote_reviewed and len(result):
        existing = pd.read_csv(REVIEWED) if REVIEWED.exists() else pd.DataFrame(columns=result.columns)
        if "extraction_method" in existing:
            existing = existing[~existing.extraction_method.eq("yougov_pdf_text_banner_adapter_v1")]
        combined = pd.concat([existing, result], ignore_index=True).drop_duplicates(
            ["poll_id", "dimension", "group"], keep="last")
        combined.to_csv(REVIEWED, index=False)
        print(f"Promoted {len(result)} adapter-validated cells")


if __name__ == "__main__":
    main()
