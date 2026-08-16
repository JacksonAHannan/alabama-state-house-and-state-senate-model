"""Recover clipped historical bill synopses from original journal PDF pages."""
from __future__ import annotations

from pathlib import Path

import fitz
import pandas as pd

try:
    from build_comprehensive_rollcall_classifications import extract_historical_synopsis, infer_historical_measure
except ModuleNotFoundError:  # imported as scripts.* by pytest
    from scripts.build_comprehensive_rollcall_classifications import extract_historical_synopsis, infer_historical_measure

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
QUEUE = LEG / "historical_rollcall_issue_classification_queue.csv"
OUTPUT = LEG / "historical_rollcall_synopsis_recovery.csv"


def page_window(document: fitz.Document, page: object, before: int = 4, after: int = 2) -> str:
    try:
        center = int(float(page)) - 1
    except (TypeError, ValueError):
        return ""
    start, stop = max(0, center - before), min(len(document), center + after + 1)
    return "\n".join(document[i].get_text("text") for i in range(start, stop))


def main() -> None:
    queue = pd.read_csv(QUEUE, low_memory=False)
    resolved = [infer_historical_measure(r.context, r.bill_type, r.bill_number) for r in queue.itertuples()]
    queue["original_bill_type"] = queue.bill_type
    queue["original_bill_number"] = queue.bill_number
    queue["bill_type"] = [x[0] for x in resolved]
    queue["bill_number"] = [x[1] for x in resolved]
    queue["measure_identity_status"] = [x[2] for x in resolved]
    queue["context_synopsis"] = [extract_historical_synopsis(r.context, r.bill_type, r.bill_number)
                                  for r in queue.itertuples()]
    need = queue[queue.context_synopsis.eq("") & queue.local_path.notna() & queue.page.notna()].copy()
    recovered: list[dict[str, object]] = []
    for local_path, rows in need.groupby("local_path", sort=False):
        path = ROOT / str(local_path)
        if not path.exists():
            for r in rows.itertuples():
                recovered.append({"rollcall_id": r.rollcall_id, "recovered_synopsis": "",
                                  "recovery_status": "source_pdf_missing", "source_page_window": ""})
            continue
        try:
            with fitz.open(path) as document:
                windows: dict[int, str] = {}
                full_document_text: str | None = None
                for r in rows.itertuples():
                    page = int(float(r.page))
                    windows.setdefault(page, page_window(document, page))
                    synopsis = extract_historical_synopsis(windows[page], r.bill_type, r.bill_number)
                    # Very long constitutional, bond, and code-revision bills
                    # can begin many pages before the named vote.
                    if not synopsis:
                        synopsis = extract_historical_synopsis(
                            page_window(document, page, before=15, after=3), r.bill_type, r.bill_number)
                    if not synopsis and str(r.motion_type) == "final_passage":
                        if full_document_text is None:
                            full_document_text = "\n".join(p.get_text("text") for p in document)
                        synopsis = extract_historical_synopsis(
                            full_document_text, r.bill_type, r.bill_number)
                    recovered.append({"rollcall_id": r.rollcall_id, "recovered_synopsis": synopsis,
                                      "recovery_status": "recovered_exact_pdf_window" if synopsis else "exact_target_synopsis_not_found",
                                      "source_page_window": ("whole_document" if synopsis and full_document_text is not None
                                                             else f"{max(1,page-15)}-{min(len(document),page+3)}")})
        except (RuntimeError, ValueError) as exc:
            for r in rows.itertuples():
                recovered.append({"rollcall_id": r.rollcall_id, "recovered_synopsis": "",
                                  "recovery_status": f"pdf_read_error:{type(exc).__name__}", "source_page_window": ""})
    result = queue[["rollcall_id", "original_bill_type", "original_bill_number", "bill_type", "bill_number",
                    "measure_identity_status", "context_synopsis"]].merge(pd.DataFrame(recovered), on="rollcall_id", how="left")
    result["best_synopsis"] = result.context_synopsis.where(result.context_synopsis.ne(""), result.recovered_synopsis.fillna(""))
    result["synopsis_source"] = "context_window"
    result.loc[result.context_synopsis.eq("") & result.recovered_synopsis.fillna("").ne(""), "synopsis_source"] = "exact_pdf_page_window"
    result.loc[result.best_synopsis.eq(""), "synopsis_source"] = "unavailable"
    result.to_csv(OUTPUT, index=False)
    print(result.synopsis_source.value_counts().to_string())


if __name__ == "__main__":
    main()
