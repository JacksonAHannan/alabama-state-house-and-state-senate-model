"""Extract text for amendments confidently attributed to focal legislators."""

from pathlib import Path

import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
RESEARCH = ROOT / "research" / "cmo_ideology"
TEXT = DATA / "focal_amendment_text"


def main() -> None:
    amendments = pd.read_csv(RESEARCH / "candidate_attributed_amendments.csv")
    downloads = pd.read_csv(DATA / "alabama_amendment_download_status.csv")
    downloads = downloads.loc[downloads.status.isin(["downloaded", "existing"]), [
        "amendment_id", "local_path", "pages", "sha256"
    ]].drop_duplicates("amendment_id")
    amendments = amendments.drop_duplicates("amendment_id").merge(
        downloads, on="amendment_id", how="left", validate="one_to_one"
    )
    TEXT.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in amendments.itertuples(index=False):
        record = row._asdict()
        if pd.isna(row.local_path):
            record |= {"text_status": "missing_pdf", "local_text": "", "text_characters": 0}
            rows.append(record)
            continue
        pdf_path = ROOT / str(row.local_path)
        text_path = TEXT / f"{int(row.amendment_id)}.txt"
        try:
            reader = PdfReader(pdf_path)
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
            if text:
                text_path.write_text(text, encoding="utf-8")
                status = "extracted"
            else:
                status = "no_extractable_text"
            record |= {
                "text_status": status,
                "local_text": str(text_path.relative_to(ROOT)) if text else "",
                "text_characters": len(text),
            }
        except Exception as exc:
            record |= {
                "text_status": "extraction_error", "local_text": "",
                "text_characters": 0, "text_error": f"{type(exc).__name__}: {exc}",
            }
        rows.append(record)
    result = pd.DataFrame(rows)
    result.to_csv(DATA / "focal_amendment_text_manifest.csv", index=False)
    print(f"Focal amendments: {len(result)}; {result.text_status.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
