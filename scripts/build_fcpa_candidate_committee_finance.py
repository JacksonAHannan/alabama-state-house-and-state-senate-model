"""Build a committee-ID-centered FCPA inventory for every modeled cycle."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz.fuzz import WRatio

from oe_normalize import normalize_name
from pilot_fcpa_surname_search import all_financial_summaries, expected_office, search, surname

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data/processed/war"


def party_compatible(expected: str, observed: object) -> bool:
    value = str(observed).strip().upper()
    if expected not in {"D", "R"}:
        return True
    return not value or value.startswith(expected)


def candidate_surname(value: object) -> str:
    # Some certified-roster names arrived without a space between first and
    # last name (for example, ChadRobertson). Repair only a lowercase-to-uppercase
    # boundary before applying the shared suffix-aware surname normalizer.
    repaired = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(value))
    return surname(repaired)


def district_compatible(chamber: str, district: int, item: dict) -> bool:
    office_ok = expected_office(chamber) in str(item.get("office", "")).upper()
    digits = "".join(character for character in str(item.get("jurisdiction", "")) if character.isdigit())
    return office_ok and bool(digits) and int(digits) == int(district)


def candidate_records(delay: float) -> pd.DataFrame:
    source = pd.read_csv(WAR / "candidate_finance_matches.csv")
    candidates = (source[source.cycle.isin([2014, 2018, 2022, 2026])]
                  [["cycle", "chamber", "district", "party", "candidate"]]
                  .drop_duplicates().copy())
    candidates["surname"] = candidates.candidate.map(candidate_surname)
    retrieved = datetime.now(timezone.utc).isoformat()
    surnames = sorted(set(candidates.surname) - {""})
    with ThreadPoolExecutor(max_workers=6) as executor:
        cache = dict(zip(surnames, executor.map(search, surnames)))
    rows = []
    for candidate in candidates.itertuples(index=False):
        results, url = cache[candidate.surname]
        compatible = [item for item in results
                      if district_compatible(candidate.chamber, candidate.district, item)
                      and party_compatible(candidate.party, item.get("party"))]
        scored = []
        for item in compatible:
            found = " ".join(filter(None, [item.get("candidateFirstName"), item.get("candidateMiddleName"),
                                            item.get("candidateLastName")]))
            candidate_name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(candidate.candidate))
            scored.append((float(WRatio(normalize_name(candidate_name), normalize_name(found))), found, item))
        scored.sort(key=lambda value: value[0], reverse=True)
        best_score = scored[0][0] if scored else 0.0
        # Retain every PCC record tied to the same best-scoring legal candidate
        # name; a candidate may have renewed or duplicate committee records.
        best_name = normalize_name(scored[0][1]) if scored else ""
        selected = [entry for entry in scored if normalize_name(entry[1]) == best_name]
        second_names = [entry[0] for entry in scored if normalize_name(entry[1]) != best_name]
        margin = best_score - max(second_names, default=0.0)
        acceptance = ("automatic_name_office_district_party" if best_score >= 88 and margin >= 5 else
                      "unique_office_district_party_review" if len({normalize_name(x[1]) for x in scored}) == 1
                      and best_score >= 65 else "unresolved")
        if acceptance == "unresolved":
            selected = []
        if not selected:
            rows.append({"cycle": candidate.cycle, "chamber": candidate.chamber, "district": candidate.district,
                         "party": candidate.party, "candidate": candidate.candidate,
                         "committee_match_status": acceptance, "surname_results": len(results),
                         "compatible_results": len(compatible), "name_score": best_score,
                         "name_margin": margin, "search_url": url, "retrieved_at_utc": retrieved})
        for score, found, item in selected:
            rows.append({"cycle": candidate.cycle, "chamber": candidate.chamber, "district": candidate.district,
                         "party": candidate.party, "candidate": candidate.candidate,
                         "committee_match_status": acceptance, "surname_results": len(results),
                         "compatible_results": len(compatible), "name_score": score, "name_margin": margin,
                         "fcpa_record_id": item.get("id"), "committee_id": item.get("committeeId"),
                         "fcpa_candidate_name": found, "committee_status": item.get("committeeStatus"),
                         "registered_date": item.get("registeredDate"), "search_url": url,
                         "retrieved_at_utc": retrieved})
    return pd.DataFrame(rows)


def financial_summaries(records: pd.DataFrame, delay: float) -> pd.DataFrame:
    rows = []
    matched = records[records.fcpa_record_id.notna()].drop_duplicates(
        ["cycle", "candidate", "fcpa_record_id"])
    record_ids = sorted(matched.fcpa_record_id.astype(int).unique())
    with ThreadPoolExecutor(max_workers=6) as executor:
        fetched = dict(zip(record_ids, executor.map(all_financial_summaries, record_ids)))
    for item in matched.itertuples(index=False):
        payload, url = fetched[int(item.fcpa_record_id)]
        years = (int(item.cycle)-1, int(item.cycle))
        annuals = [(year, payload.get(str(year), {})) for year in years]
        values = {key: sum(float(annual.get(key) or 0) for _, annual in annuals)
                  for key in ("cashContributions", "otherReceipts", "inKindContributions", "expenditures")}
        rows.append({"cycle": item.cycle, "chamber": item.chamber, "district": item.district,
                     "party": item.party, "candidate": item.candidate,
                     "fcpa_candidate_name": item.fcpa_candidate_name, "fcpa_record_id": item.fcpa_record_id,
                     "committee_id": item.committee_id, "committee_status": item.committee_status,
                     "registered_date": item.registered_date,
                     "years_with_summary": sum(bool(annual) for _, annual in annuals),
                     "cycle_cash_contributions": values["cashContributions"],
                     "cycle_other_receipts": values["otherReceipts"],
                     "cycle_in_kind_contributions": values["inKindContributions"],
                     "cycle_expenditures": values["expenditures"],
                     "financial_summary_url": url})
    return pd.DataFrame(rows)


def main(delay: float = .1) -> None:
    records = candidate_records(delay)
    records.to_csv(WAR / "fcpa_candidate_committee_inventory.csv", index=False)
    summaries = financial_summaries(records, delay)
    summaries.to_csv(WAR / "fcpa_candidate_committee_financial_summaries.csv", index=False)
    keys = ["cycle", "chamber", "district", "party", "candidate"]
    summaries["committee_activity"] = (summaries.cycle_cash_contributions
                                       + summaries.cycle_other_receipts
                                       + summaries.cycle_expenditures)
    candidate_finance = summaries.groupby(keys, as_index=False).agg(
        pcc_records=("committee_id", "nunique"),
        pcc_records_with_activity=("committee_activity", lambda values: int(values.gt(0).sum())),
        cash_contributions=("cycle_cash_contributions", "sum"),
        other_receipts=("cycle_other_receipts", "sum"),
        in_kind_contributions=("cycle_in_kind_contributions", "sum"),
        expenditures=("cycle_expenditures", "sum"),
        years_with_summary=("years_with_summary", "max"))
    candidate_finance["fundraising_total"] = (candidate_finance.cash_contributions
                                               + candidate_finance.other_receipts)
    candidate_finance["aggregation_status"] = np.select(
        [candidate_finance.pcc_records_with_activity.gt(1),
         candidate_finance.pcc_records_with_activity.eq(1)],
        ["multiple_active_pcc_records_review", "single_active_pcc_record"],
        default="committee_found_no_cycle_activity")
    candidate_finance.to_csv(WAR / "fcpa_candidate_cycle_finance.csv", index=False)
    review = records[~records.committee_match_status.eq("automatic_name_office_district_party")].copy()
    review = review.merge(candidate_finance[keys + ["pcc_records_with_activity", "aggregation_status"]],
                          on=keys, how="left")
    review.to_csv(WAR / "fcpa_candidate_committee_review.csv", index=False)
    recovered = records[records.fcpa_record_id.notna()][["cycle", "candidate", "chamber", "district", "party"]].drop_duplicates()
    positive = summaries[summaries.committee_activity.gt(0)]
    print(f"Candidate-cycles audited: {records[['cycle','candidate','chamber','district','party']].drop_duplicates().shape[0]}")
    print(f"Candidates with matched PCC records: {len(recovered)}")
    print(f"Matched committee records: {len(summaries)}")
    print(f"Committee-cycle records with positive two-calendar-year financial activity: {len(positive)}")
    if len(positive):
        print(positive.nlargest(20, "cycle_cash_contributions")[["candidate", "committee_id",
              "cycle_cash_contributions", "cycle_expenditures"]].to_string(index=False))


if __name__ == "__main__":
    main()
