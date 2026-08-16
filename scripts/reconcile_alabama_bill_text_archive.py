"""Reconcile the local bill-text archive against every LegiScan document record."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
RAW = ROOT / "data" / "raw" / "alabama_legislature" / "bill_text"


def expected_path(row: pd.Series) -> Path:
    kind = str(row.document_type).lower().replace(" ", "_")
    return (RAW / str(int(row.session_year)) / str(int(row.session_id)) /
            str(int(row.bill_id)) / f"{int(row.doc_id)}_{kind}.pdf")


def main() -> None:
    documents = pd.read_csv(DATA / "legiscan_bill_text_manifest.csv")
    bills = pd.read_csv(DATA / "legiscan_alabama_bills.csv")
    documents = documents.merge(
        bills[["bill_id", "session_year"]].drop_duplicates("bill_id"),
        on="bill_id", how="left", validate="many_to_one",
    )
    documents = documents.loc[documents.session_year.ge(2010)].copy()
    actual = {
        path.resolve() for path in RAW.rglob("*.pdf")
    }
    documents["local_path"] = [
        str(expected_path(row).relative_to(ROOT)) for _, row in documents.iterrows()
    ]
    documents["archive_status"] = [
        "present" if (ROOT / path).resolve() in actual else "missing"
        for path in documents.local_path
    ]
    documents.to_csv(DATA / "alabama_bill_text_archive_reconciliation.csv", index=False)

    bill_ids = set(bills.loc[bills.session_year.ge(2010), "bill_id"].astype(int))
    with_text = set(documents.bill_id.astype(int))
    missing_metadata = bills.loc[
        bills.bill_id.astype(int).isin(bill_ids - with_text)
    ].copy()
    missing_metadata.to_csv(DATA / "alabama_bills_without_text_metadata.csv", index=False)
    print(f"Document versions: {len(documents):,}")
    print(documents.archive_status.value_counts().to_dict())
    print(f"Bills without text metadata: {len(missing_metadata):,}")


if __name__ == "__main__":
    main()
