"""Reconcile 2026 roster candidates to the official state finance summaries.

The live FCPA financial-summary endpoint sometimes returned an empty annual
payload for committees that have positive activity in the state's downloaded
2026-cycle summary export.  This build uses the August 14 state exports as the
cutoff-specific authority, with PCC legal names as identity aliases and an
explicit manual alias table for the rare nickname/legal-name case.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz.fuzz import WRatio


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/finance/alabama"
WAR = ROOT / "data/processed/war"
OUT = ROOT / "data/processed/finance"
MANUAL = ROOT / "data/manual/finance/2026_candidate_finance_aliases.csv"

KEYS = ["cycle", "chamber", "district", "party", "candidate"]
MONEY_COLUMNS = {
    "Beginning Funds on Hand": "beginning_cash",
    "Monetary Contributions": "cash_contributions",
    "Monetary Expenditures": "expenditures",
    "Non-Monetary Contributions": "in_kind_contributions",
    "Other Receipts": "other_receipts",
    "Ending Funds on Hand": "ending_cash",
}
FIRST_EQUIVALENTS = {
    "BILL": "WILLIAM",
    "BILLY": "WILLIAM",
    "BOB": "ROBERT",
    "CHRIS": "CHRISTOPHER",
    "CINDY": "CYNTHIA",
    "ED": "EDWARD",
    "JIM": "JAMES",
    "MIKE": "MICHAEL",
    "PAM": "PAMELA",
    "RON": "RONALD",
    "SAM": "SAMUEL",
    "TOM": "THOMAS",
    "WES": "WESLEY",
    "WILL": "WILLIAM",
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text)
    text = re.sub(r"[^A-Z ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def ordered_name(value: object) -> str:
    """Put `LAST, FIRST MIDDLE` source names into natural token order."""
    raw = str(value).strip()
    if "," in raw:
        last, rest = raw.split(",", 1)
        raw = f"{rest} {last}"
    return normalize(raw)


def name_parts(value: object) -> tuple[str, str, tuple[str, ...]]:
    tokens = ordered_name(value).split()
    if not tokens:
        return "", "", ()
    first = FIRST_EQUIVALENTS.get(tokens[0], tokens[0])
    last = tokens[-1]
    middle = tuple(tokens[1:-1])
    return first, last, middle


def middle_compatible(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if not left or not right:
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    return all(shorter[index][0] == longer[index][0] for index in range(len(shorter)))


def score_names(expected: object, observed: object) -> tuple[float, str]:
    left = ordered_name(expected)
    right = ordered_name(observed)
    if not left or not right:
        return 0.0, "empty"
    if left == right:
        return 100.0, "exact_ordered_name"
    if sorted(left.split()) == sorted(right.split()):
        return 99.0, "exact_tokens"
    left_first, left_last, left_middle = name_parts(expected)
    right_first, right_last, right_middle = name_parts(observed)
    if left_first == right_first and left_last == right_last:
        if middle_compatible(left_middle, right_middle):
            return 97.0 if left_middle and right_middle else 95.0, "first_last_middle_compatible"
        return 92.0, "first_last_middle_conflict"
    return min(91.0, float(WRatio(left, right))), "fuzzy_unaccepted"


def read_state_source() -> pd.DataFrame:
    frames = []
    for chamber, filename in (
        ("house", "State House Fundraising 2026 Cycle.csv"),
        ("senate", "State Senate Fundraising 2026 Cycle.csv"),
    ):
        frame = pd.read_csv(RAW / filename)
        frame["chamber"] = chamber
        frame["source_file"] = filename
        frame["source_row"] = np.arange(2, len(frame) + 2)
        frames.append(frame)
    source = pd.concat(frames, ignore_index=True)
    source = source.rename(columns={"Candidate": "state_candidate", "Candidate Status": "committee_status",
                                    "Year": "summary_year", **MONEY_COLUMNS})
    for column in MONEY_COLUMNS.values():
        source[column] = pd.to_numeric(source[column], errors="coerce")
    source["state_identity_key"] = source.state_candidate.map(ordered_name)
    source["active_priority"] = source.committee_status.astype(str).str.upper().eq("ACTIVE").astype(int)
    source["summary_year"] = pd.to_numeric(source.summary_year, errors="coerce")
    source["activity_total"] = source[["cash_contributions", "other_receipts", "expenditures"]].fillna(0).sum(axis=1)
    source["source_identity_rows"] = source.groupby(["chamber", "state_identity_key"])["state_candidate"].transform("size")
    # The requested product rule is one main committee per candidate.  Active
    # takes precedence over dissolved, followed by the newest/largest summary.
    return (source.sort_values(
        ["active_priority", "summary_year", "activity_total"], ascending=[False, False, False]
    ).drop_duplicates(["chamber", "state_identity_key"]).reset_index(drop=True))


def roster_aliases(roster: pd.DataFrame) -> dict[tuple, list[tuple[str, str]]]:
    aliases: dict[tuple, list[tuple[str, str]]] = {
        tuple(getattr(row, column) for column in KEYS): [(row.candidate, "roster_name")]
        for row in roster.itertuples(index=False)
    }
    inventory_path = WAR / "fcpa_candidate_committee_inventory.csv"
    if inventory_path.exists():
        inventory = pd.read_csv(inventory_path)
        inventory = inventory[inventory.cycle.eq(2026) & inventory.fcpa_candidate_name.notna()]
        for row in inventory.itertuples(index=False):
            key = (int(row.cycle), row.chamber, int(row.district), row.party, row.candidate)
            if key in aliases:
                aliases[key].append((str(row.fcpa_candidate_name), "fcpa_legal_name"))
    if MANUAL.exists():
        manual = pd.read_csv(MANUAL)
        approved = manual[manual.decision.eq("approved")]
        for row in approved.itertuples(index=False):
            key = (int(row.cycle), row.chamber, int(row.district), row.party, row.candidate)
            if key in aliases:
                aliases[key].append((str(row.state_candidate), "manual_approved_alias"))
    return aliases


def match_roster(roster: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
    aliases = roster_aliases(roster)
    proposals = []
    for candidate in roster.itertuples(index=False):
        key = tuple(getattr(candidate, column) for column in KEYS)
        pool = source[source.chamber.eq(candidate.chamber)]
        scored = []
        for index, observed in pool.iterrows():
            options = []
            for alias, alias_source in aliases[key]:
                score, method = score_names(alias, observed.state_candidate)
                options.append((score, method, alias_source, alias))
            score, method, alias_source, alias = max(options, key=lambda item: item[0])
            scored.append((score, index, method, alias_source, alias))
        scored.sort(reverse=True, key=lambda item: item[0])
        best = scored[0] if scored else (0.0, None, "no_source", "none", "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        accepted = best[0] >= 95.0 and best[0] - second >= 2.0
        proposals.append({**dict(zip(KEYS, key)), "source_index": best[1] if accepted else np.nan,
                          "match_score": best[0], "match_margin": best[0] - second,
                          "match_method": best[2] if accepted else "unresolved",
                          "matched_alias_source": best[3] if accepted else best[3],
                          "matched_alias": best[4] if accepted else best[4]})
    matches = pd.DataFrame(proposals)
    accepted = matches[matches.source_index.notna()].copy()
    duplicate_assignments = accepted.source_index.value_counts()
    duplicated = set(duplicate_assignments[duplicate_assignments.gt(1)].index)
    if duplicated:
        matches.loc[matches.source_index.isin(duplicated), ["source_index", "match_method"]] = [np.nan, "duplicate_source_review"]
    matches["source_index"] = matches.source_index.astype("Int64")
    joined = matches.merge(source.reset_index(names="source_index"), on="source_index", how="left", suffixes=("", "_source"))
    return joined


def prior_finance(roster: pd.DataFrame) -> pd.DataFrame:
    prior = pd.read_csv(WAR / "fcpa_candidate_cycle_finance.csv")
    prior = prior[prior.cycle.eq(2026)].copy()
    keep = KEYS + ["pcc_records", "pcc_records_with_activity", "fundraising_total", "cash_contributions",
                   "other_receipts", "in_kind_contributions", "expenditures", "years_with_summary",
                   "aggregation_status"]
    prior = prior[keep].rename(columns={column: f"prior_{column}" for column in keep if column not in KEYS})
    return roster.merge(prior, on=KEYS, how="left", validate="one_to_one")


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    roster = pd.read_csv(WAR / "2026_final_candidate_roster.csv")
    roster = roster[roster.party.isin(["D", "R"])][KEYS].drop_duplicates().copy()
    roster["district"] = roster.district.astype(int)
    source = read_state_source()
    matched = match_roster(roster, source)
    prior = prior_finance(roster)
    result = matched.merge(prior, on=KEYS, how="left", validate="one_to_one")
    observed = result.state_candidate.notna()
    prior_observed = result.prior_years_with_summary.fillna(0).gt(0)
    # The FCPA annual-summary snapshot contains 2025 but not 2026 for every
    # retrieved committee (zero or one available year).  The downloaded state
    # export contains 2026 year-to-date activity.  These are non-overlapping
    # calendar-year components and must be added, never substituted.
    if result.prior_years_with_summary.fillna(0).gt(1).any():
        raise ValueError("Expected the frozen FCPA snapshot to contain at most the 2025 annual summary")
    for column in ("cash_contributions", "other_receipts", "in_kind_contributions", "expenditures"):
        result[f"state_2026_{column}"] = result[column]
        result[f"fcpa_2025_{column}"] = result[f"prior_{column}"].where(prior_observed)
        result[column] = np.where(
            observed,
            result[f"state_2026_{column}"].fillna(0) + result[f"fcpa_2025_{column}"].fillna(0),
            np.nan,
        )
    result["state_2026_fundraising_total"] = (
        result.state_2026_cash_contributions + result.state_2026_other_receipts
    )
    result["fcpa_2025_fundraising_total"] = result.prior_fundraising_total.where(prior_observed)
    result["fundraising_total"] = np.where(
        observed,
        result.state_2026_fundraising_total.fillna(0) + result.fcpa_2025_fundraising_total.fillna(0),
        np.nan,
    )
    result["finance_source"] = np.select(
        [observed & prior_observed, observed, prior_observed],
        ["fcpa_2025_plus_state_2026_08_14", "state_2026_08_14_only", "fcpa_2025_only_incomplete"],
        default="not_observed",
    )
    result["finance_observation_status"] = np.select(
        [observed & result.fundraising_total.gt(0),
         observed & result.fundraising_total.eq(0) & result.in_kind_contributions.gt(0),
         observed,
         result.prior_aggregation_status.eq("single_active_pcc_record"),
         result.prior_aggregation_status.eq("committee_found_no_cycle_activity")],
        ["observed_positive", "observed_noncash_only", "observed_zero",
         "prior_live_summary_positive", "unverified_live_summary_zero"],
        default="not_observed_unknown_not_zero",
    )
    result["aggregation_status"] = np.select(
        [observed & (result.fundraising_total.gt(0) | result.expenditures.gt(0) | result.in_kind_contributions.gt(0)),
         observed,
         ~observed & result.prior_aggregation_status.eq("committee_found_no_cycle_activity"),
         result.prior_aggregation_status.notna()],
        ["single_official_state_record_with_activity", "official_state_record_no_activity",
         "unverified_live_summary_zero",
         result.prior_aggregation_status.fillna("")],
        default="not_observed_unknown_not_zero",
    )
    prior_zero = result.prior_aggregation_status.eq("committee_found_no_cycle_activity")
    prior_missing = result.prior_aggregation_status.isna()
    result["prior_zero_or_missing"] = prior_zero | prior_missing
    result["reconciliation_resolution"] = np.select(
        [prior_zero & observed & result.fundraising_total.gt(0),
         prior_zero & observed & result.fundraising_total.eq(0) &
             (result.expenditures.gt(0) | result.in_kind_contributions.gt(0)),
         prior_zero & observed,
         prior_missing & observed & result.fundraising_total.gt(0),
         prior_missing & observed,
         (prior_zero | prior_missing) & ~observed],
        ["recovered_positive_from_official_summary", "recovered_nonfundraising_activity_from_official_summary",
         "confirmed_observed_zero_from_official_summary", "recovered_missing_positive_from_official_summary",
         "recovered_missing_observed_record", "unresolved_no_official_state_summary"],
        default="prior_positive_or_not_in_audit",
    )
    output_columns = KEYS + [
        "state_candidate", "committee_status", "summary_year", "source_file", "source_row",
        "source_identity_rows", "match_score", "match_margin", "match_method", "matched_alias_source",
        "matched_alias", "beginning_cash", "cash_contributions", "other_receipts", "fundraising_total",
        "in_kind_contributions", "expenditures", "ending_cash", "finance_source", "finance_observation_status",
        "state_2026_cash_contributions", "state_2026_other_receipts", "state_2026_fundraising_total",
        "state_2026_in_kind_contributions", "state_2026_expenditures",
        "fcpa_2025_cash_contributions", "fcpa_2025_other_receipts", "fcpa_2025_fundraising_total",
        "fcpa_2025_in_kind_contributions", "fcpa_2025_expenditures",
        "aggregation_status", "prior_aggregation_status", "prior_fundraising_total", "prior_expenditures",
        "prior_zero_or_missing", "reconciliation_resolution",
    ]
    result = result[output_columns].sort_values(["chamber", "district", "party", "candidate"])
    audit = result[result.prior_zero_or_missing].copy()
    return result, audit


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result, audit = build()
    result.to_csv(OUT / "2026_candidate_finance_reconciled.csv", index=False)
    audit.to_csv(OUT / "2026_candidate_finance_match_audit.csv", index=False)
    print(f"Roster candidates: {len(result)}")
    print(f"Previously zero or missing: {len(audit)}")
    print(audit.reconciliation_resolution.value_counts(dropna=False).to_string())
    unresolved = audit[audit.reconciliation_resolution.eq("unresolved_no_official_state_summary")]
    if len(unresolved):
        print("\nUnresolved candidates:")
        print(unresolved[["chamber", "district", "party", "candidate", "prior_aggregation_status"]].to_string(index=False))


if __name__ == "__main__":
    main()
