"""Validate narrow county-code decoders against inventory and ballot evidence."""
from __future__ import annotations

import pandas as pd

from audit_historical_precinct_geography import (
    canonical_vtd_code, decoded_county_vtd_code, donor_vtds,
)
from warehouse import ROOT

QUEUE = ROOT / "data/processed/precinct_history/historical_precinct_adjudication_queue.csv"
OUT = ROOT / "data/processed/precinct_history/county_code_decoder_validation.csv"


def assignments(value: object) -> set[tuple[str, int]]:
    result = set()
    for token in str(value).split("|"):
        if "-" not in token:
            continue
        chamber, number = token.split("-", 1)
        if number.isdigit():
            result.add((chamber, int(number)))
    return result


def main() -> None:
    queue = pd.read_csv(QUEUE).fillna("")
    donors = donor_vtds()
    donors["canonical_code"] = donors.vtd_code.map(canonical_vtd_code)
    rows = []
    for row in queue.itertuples(index=False):
        code, method = decoded_county_vtd_code(
            row.county_key, row.precinct_key, assignments(row.known_race_assignments))
        if not code:
            continue
        vintage = 2010 if int(row.cycle) >= 2006 else 2000
        candidates = donors[(donors.donor_vintage.eq(vintage))
                            & donors.county_key.str.replace(" ", "").eq(
                                str(row.county_key).replace(" ", ""))
                            & donors.canonical_code.eq(code)]
        rows.append({
            "cycle": row.cycle, "county_key": row.county_key,
            "precinct_key": row.precinct_key, "decoder_method": method,
            "decoded_code": code, "candidate_count": len(candidates),
            "unique_donor": len(candidates) == 1,
            "donor_vtd_id": candidates.donor_vtd_id.iloc[0] if len(candidates) == 1 else "",
            "donor_name": candidates.donor_name.iloc[0] if len(candidates) == 1 else "",
        })
    result = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result.groupby("decoder_method").agg(
        cases=("precinct_key", "size"), unique_donors=("unique_donor", "sum")).to_string())
    failures = result[~result.unique_donor]
    if not failures.empty:
        print("\nDecoder inventory failures:")
        print(failures.to_string(index=False))


if __name__ == "__main__":
    main()
