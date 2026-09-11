#!/usr/bin/env python3
"""Build canonical Southern candidate-cycle fundraising from report summaries.

The target measure is money raised during the election calendar year and the
preceding calendar year.  Cash contributions and other monetary receipts are
combined only when the source exposes those categories.  Loans, in-kind
receipts, expenditures, and cash balances remain separate.  Missing values are
never coerced to zero without an explicit no-activity filing.
"""

from __future__ import annotations

import hashlib
import csv
import json
import logging
import re
import zipfile
from collections import defaultdict
from datetime import date
from itertools import combinations, permutations
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

try:
    import fitz
    from rapidocr_onnxruntime import RapidOCR
except ImportError:  # OCR remains an explicit unknown when optional dependencies are absent.
    fitz = None
    RapidOCR = None


logging.getLogger("pypdf").setLevel(logging.ERROR)

from acquire_southern_candidate_finance_summaries import (
    ar_party,
    ar_provider_identity,
    candidate_identity_score,
    candidate_score,
    candidate_universe,
    match_ga_legacy_registrations,
    match_ga_recordsearch_registrations,
    parse_ga_legacy_candidate_detail,
    parse_ga_recordsearch_candidate_response,
    IDENTITY_CONTEXT_STOPWORDS,
    normalized_tokens,
    person_parts,
    parse_fl_candidate_summary,
    parse_ky_candidate_index,
    parse_va_committee_reports,
    VA_BASE,
)
from acquire_southern_campaign_finance import florida_query_coverage


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data/processed/war"
FINANCE = ROOT / "data/processed/finance"
SUMMARY_RAW = ROOT / "data/raw/finance/southern_summaries"
TRANSACTION_RAW = ROOT / "data/raw/finance/southern"
TRANSACTION_MANIFEST = (
    ROOT / "data/processed/source_audits/southern_campaign_finance_manifest.csv"
)
TX_ROOT = ROOT.parent / "texas-state-house-and-state-senate-model"
TX_FALLBACK = FINANCE / "texas_report_contribution_detail_fallback.csv"
FINANCE_IDENTITY_ADJUDICATIONS = (
    ROOT / "data/manual/finance/southern_finance_identity_adjudications.csv"
)
OUTPUT = FINANCE / "southern_candidate_cycle_finance.csv"
PERIOD_OUTPUT = FINANCE / "southern_candidate_finance_report_periods.csv"
COVERAGE_OUTPUT = FINANCE / "southern_candidate_cycle_finance_coverage.csv"
REVIEW_OUTPUT = FINANCE / "southern_candidate_cycle_finance_review.csv"
KEY = ["state", "cycle", "chamber", "district", "party"]

FL_MONETARY_CONTRIBUTION_TYPES = {"CAS", "CHE", "INT", "MO", "RCT", "REF"}
FL_CASH_CONTRIBUTION_TYPES = {"CAS", "CHE", "MO", "REF"}
FL_NON_FUNDRAISING_TYPES = {"COF", "INK", "LOA", "X", ""}


def build_code_sha256() -> str:
    """Hash this builder and the shared identity/acquisition dependency."""
    digest = hashlib.sha256()
    for path in (
        Path(__file__).resolve(),
        Path(__file__).resolve().parent / "acquire_southern_candidate_finance_summaries.py",
        FINANCE_IDENTITY_ADJUDICATIONS,
    ):
        if not path.exists():
            continue
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def approved_finance_identity_adjudications(state: str) -> pd.DataFrame:
    """Load approved, evidence-bearing identity decisions for one provider."""
    columns = [
        "adjudication_id", "state_code", "cycle_start", "cycle_end",
        "chamber", "district", "party", "candidate_name",
        "provider_identity", "provider_candidate_name", "evidence_source_path",
        "evidence_source_url", "evidence_quote", "rationale",
        "review_status", "reviewer",
    ]
    if not FINANCE_IDENTITY_ADJUDICATIONS.exists():
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(FINANCE_IDENTITY_ADJUDICATIONS, dtype=str)
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(
            "Finance identity adjudications are missing columns: "
            + ", ".join(missing)
        )
    frame = frame[
        frame.state_code.eq(state) & frame.review_status.eq("approved")
    ].copy()
    if frame.empty:
        return frame
    if frame.adjudication_id.duplicated().any():
        raise ValueError("Finance identity adjudication IDs must be unique")
    for column in ("cycle_start", "cycle_end", "district"):
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(int)
    if frame[["evidence_source_path", "evidence_source_url", "evidence_quote",
              "rationale", "reviewer"]].replace("", np.nan).isna().any().any():
        raise ValueError("Approved finance identity adjudications require complete evidence")
    return frame


def apply_texas_identity_adjudications(crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Apply approved TEC filer decisions at exact election scope."""
    out = crosswalk.copy()
    adjudications = approved_finance_identity_adjudications("TX")
    universe = candidate_universe("TX", prefer_final_names=True)
    claimed: set[tuple[int, str, int, str]] = set()
    for decision in adjudications.itertuples(index=False):
        for cycle in range(decision.cycle_start, decision.cycle_end + 1, 2):
            key = (cycle, decision.chamber, decision.district, decision.party)
            if key in claimed:
                raise ValueError(f"Overlapping approved Texas identity decision: {key}")
            claimed.add(key)
            mask = (
                out.cycle.eq(cycle) & out.chamber.eq(decision.chamber)
                & out.district.eq(str(decision.district))
                & out.party.eq(decision.party)
            )
            if int(mask.sum()) == 0:
                # The companion TEC crosswalk is based on its own election
                # panel and can omit a contest that exists in the central
                # final-election universe.  An approved exact-scope decision
                # may add that one missing crosswalk row; the universe check
                # prevents an adjudication from manufacturing a contest.
                universe_mask = (
                    universe.cycle.eq(cycle)
                    & universe.chamber.eq(decision.chamber)
                    & universe.district.eq(decision.district)
                    & universe.party.eq(decision.party)
                )
                if int(universe_mask.sum()) != 1:
                    raise ValueError(
                        "Approved Texas identity decision is absent from the "
                        f"central candidate universe: {key}"
                    )
                universe_name = str(universe.loc[universe_mask, "candidate"].iloc[0])
                if candidate_score(universe_name, decision.candidate_name) < 75.0:
                    raise ValueError(
                        "Approved Texas identity candidate drift from central universe "
                        f"for {decision.adjudication_id}"
                    )
                added = {column: "" for column in out.columns}
                added.update({
                    "cycle": cycle, "chamber": decision.chamber,
                    "district": str(decision.district), "party": decision.party,
                    "candidate_name": decision.candidate_name,
                    "candidate_key": " ".join(normalized_tokens(decision.candidate_name)),
                    "person_key": " ".join(normalized_tokens(decision.candidate_name)),
                    "filer_id": "", "filer_match_method": "",
                    "filer_candidates_considered": "0",
                })
                out = pd.concat([out, pd.DataFrame([added])], ignore_index=True)
                mask = (
                    out.cycle.eq(cycle) & out.chamber.eq(decision.chamber)
                    & out.district.eq(str(decision.district))
                    & out.party.eq(decision.party)
                )
            if int(mask.sum()) != 1:
                raise ValueError(
                    f"Approved Texas identity decision does not resolve one crosswalk row: {key}"
                )
            row = out.loc[mask].iloc[0]
            if candidate_score(row.candidate_name, decision.candidate_name) < 75.0:
                raise ValueError(
                    f"Approved Texas identity candidate drift for {decision.adjudication_id}"
                )
            existing = str(row.filer_id).strip() if pd.notna(row.filer_id) else ""
            if existing and existing != decision.provider_identity:
                raise ValueError(
                    f"Approved Texas identity conflicts with existing filer for {key}"
                )
            out.loc[mask, "filer_id"] = decision.provider_identity
            out.loc[mask, "filer_match_method"] = (
                "approved_identity_adjudication:" + decision.adjudication_id
            )
            out.loc[mask, "filer_candidates_considered"] = "1"
    return out


def committee_identity_name(value: object) -> str:
    """Remove organization/office boilerplate while retaining person tokens."""
    return " ".join(
        token for token in normalized_tokens(value)
        if token not in IDENTITY_CONTEXT_STOPWORDS and not token.isdigit()
    )


def reciprocal_identity_assignments(
    targets: pd.DataFrame,
    identities: pd.DataFrame,
    *,
    identity_column: str,
    name_column: str,
    committee_names: bool = False,
) -> tuple[dict[int, list[str]], dict[int, dict[str, object]]]:
    """Assign provider identities to their unique best modeled candidate.

    Provider aliases are grouped before ambiguity is evaluated, preventing one
    person's spelling variants or replacement committee IDs from acting as
    competing candidates.  A surname-only committee is accepted only when the
    surname is unique within the exact cycle/chamber target scope.
    """
    grouped = {
        str(provider_id): sorted(set(group[name_column].dropna().astype(str)))
        for provider_id, group in identities.dropna(subset=[identity_column]).groupby(
            identity_column
        )
    }
    surname_index: dict[str, set[str]] = {}
    comparable_aliases: dict[str, list[tuple[str, str]]] = {}
    for provider_id, aliases in grouped.items():
        comparable_aliases[provider_id] = []
        for alias in aliases:
            comparable = committee_identity_name(alias) if committee_names else alias
            comparable_aliases[provider_id].append((alias, comparable))
            tokens = normalized_tokens(comparable)
            for width in range(1, min(3, len(tokens)) + 1):
                for selected_tokens in combinations(tokens, width):
                    for ordered_tokens in permutations(selected_tokens):
                        surname_index.setdefault(
                            "".join(ordered_tokens), set()
                        ).add(provider_id)
    target_records = list(targets.reset_index(drop=True).itertuples(index=True))
    surname_frequency: dict[str, int] = {}
    for target in target_records:
        surname = person_parts(target.candidate)[1]
        surname_frequency[surname] = surname_frequency.get(surname, 0) + 1

    assigned: dict[int, list[str]] = {target.Index: [] for target in target_records}
    evidence: dict[int, dict[str, object]] = {
        target.Index: {"score": 0.0, "margin": 0.0, "provider_names": []}
        for target in target_records
    }
    provider_proposals: dict[str, list[tuple[float, int, str]]] = {}
    for target in target_records:
        surname = person_parts(target.candidate)[1]
        for provider_id in surname_index.get(surname, set()):
            scored_aliases = [
                (
                    max(
                        candidate_score(target.candidate, comparable),
                        candidate_identity_score(target.candidate, comparable, alias),
                    ),
                    alias,
                )
                for alias, comparable in comparable_aliases[provider_id]
            ]
            best_alias_score, best_alias = max(scored_aliases, default=(0.0, ""))
            provider_proposals.setdefault(provider_id, []).append(
                (best_alias_score, target.Index, best_alias)
            )

    for provider_id, proposals in provider_proposals.items():
        proposals.sort(reverse=True)
        top_score, target_index, best_alias = proposals[0]
        second_score = proposals[1][0] if len(proposals) > 1 else 0.0
        target = target_records[target_index]
        surname = person_parts(target.candidate)[1]
        strong = top_score >= 94.0 and top_score - second_score >= 4.0
        surname_only_alias = (
            committee_names
            and "".join(normalized_tokens(committee_identity_name(best_alias))) == surname
        )
        surname_only = (
            top_score >= 90.0
            and top_score - second_score >= 4.0
            and surname_frequency.get(surname, 0) == 1
            and surname_only_alias
        )
        target_first = person_parts(target.candidate)[0]
        provider_tokens = normalized_tokens(committee_identity_name(best_alias))
        independent_given_prefix = any(
            min(len(target_first), len(token)) >= 3
            and (target_first.startswith(token) or token.startswith(target_first))
            for token in provider_tokens
        )
        competing_given_prefix = any(
            any(
                min(len(person_parts(target_records[other_index].candidate)[0]), len(token)) >= 3
                and (
                    person_parts(target_records[other_index].candidate)[0].startswith(token)
                    or token.startswith(person_parts(target_records[other_index].candidate)[0])
                )
                for token in normalized_tokens(committee_identity_name(other_alias))
            )
            for _, other_index, other_alias in proposals[1:]
        )
        unique_given_supported = (
            committee_names
            and top_score >= 90.0
            and independent_given_prefix
            and not competing_given_prefix
        )
        if not (strong or surname_only or unique_given_supported):
            continue
        assigned[target_index].append(provider_id)
        current = evidence[target_index]
        current["score"] = max(float(current["score"]), float(top_score))
        current["margin"] = max(float(current["margin"]), float(top_score - second_score))
        current["provider_names"].append(best_alias)
    for provider_ids in assigned.values():
        provider_ids.sort()
    return assigned, evidence


def apply_north_carolina_identity_adjudications(
    targets: pd.DataFrame,
    identities: pd.DataFrame,
    assignments: dict[int, list[str]],
    evidence: dict[int, dict[str, object]],
    cycle: int,
) -> dict[int, str]:
    """Apply approved NC committee decisions without weakening auto-matching."""
    available_ids = set(identities["Committee SBoE ID"].dropna().astype(str))
    applied: dict[int, str] = {}
    claimed: set[tuple[str, int, str]] = set()
    for decision in approved_finance_identity_adjudications("NC").itertuples(index=False):
        if not decision.cycle_start <= cycle <= decision.cycle_end:
            continue
        key = (decision.chamber, decision.district, decision.party)
        if key in claimed:
            raise ValueError(f"Overlapping approved North Carolina identity decision: {key}")
        claimed.add(key)
        mask = (
            targets.chamber.eq(decision.chamber)
            & targets.district.astype(int).eq(decision.district)
            & targets.party.eq(decision.party)
        )
        if int(mask.sum()) != 1:
            raise ValueError(
                "Approved North Carolina identity decision does not resolve one "
                f"candidate in {cycle}: {decision.adjudication_id}"
            )
        target_index = int(targets.index[mask][0])
        target_name = str(targets.loc[target_index, "candidate"])
        if candidate_score(target_name, decision.candidate_name) < 75.0:
            raise ValueError(
                f"Approved North Carolina identity candidate drift for {decision.adjudication_id}"
            )
        if decision.provider_identity not in available_ids:
            raise ValueError(
                "Approved North Carolina committee is absent from the exact cycle "
                f"exports for {decision.adjudication_id}: {decision.provider_identity}"
            )
        existing = assignments[target_index]
        if existing and existing != [decision.provider_identity]:
            raise ValueError(
                f"Approved North Carolina identity conflicts with automatic match: {key}"
            )
        assignments[target_index] = [decision.provider_identity]
        evidence[target_index] = {
            "score": 100.0,
            "margin": 100.0,
            "provider_names": [decision.provider_candidate_name],
        }
        applied[target_index] = decision.adjudication_id
    return applied


def amount(items: list[dict], item_type: str, field: str = "filingPeriod") -> float:
    matches = [item.get(field) for item in items if item.get("type") == item_type]
    if len(matches) != 1 or matches[0] is None:
        return np.nan
    return float(matches[0])


def parse_sc_period(value: object) -> tuple[pd.Timestamp, pd.Timestamp]:
    parts = str(value or "").split(" - ")
    if len(parts) != 2:
        return pd.NaT, pd.NaT
    return pd.to_datetime(parts[0], errors="coerce"), pd.to_datetime(
        parts[1], errors="coerce"
    )


def sc_period_rows() -> pd.DataFrame:
    rows = []
    sc_root = SUMMARY_RAW / "SC"
    versioned = sorted(sc_root.glob("*_matched_report_details_v4.jsonl"))
    if not versioned:
        versioned = sorted(sc_root.glob("*_matched_report_details_v3.jsonl"))
    if not versioned:
        versioned = sorted(sc_root.glob("*_matched_report_details_v2.jsonl"))
    paths = versioned or sorted(sc_root.glob("*_matched_report_details.jsonl"))
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                envelope = json.loads(line)
                index = envelope["index"]
                detail = envelope["detail"]
                overview = detail.get("overview") or {}
                income = overview.get("income") or []
                expenditures = overview.get("expenditures") or []
                start, end = parse_sc_period(detail.get("filingPeriod"))
                cash = amount(income, "Cash Contributions")
                personal = amount(income, "Personal Contributions")
                debt_setoff = amount(income, "Debt Setoff Funds")
                credits = amount(income, "Account Credits")
                other = np.nan if any(pd.isna(x) for x in (debt_setoff, credits)) else debt_setoff + credits
                monetary = (
                    np.nan if any(pd.isna(x) for x in (cash, personal, other))
                    else cash + personal + other
                )
                cycle_cash = amount(
                    income, "Cash Contributions", "electionCycleTotal"
                )
                cycle_personal = amount(
                    income, "Personal Contributions", "electionCycleTotal"
                )
                cycle_debt_setoff = amount(
                    income, "Debt Setoff Funds", "electionCycleTotal"
                )
                cycle_credits = amount(
                    income, "Account Credits", "electionCycleTotal"
                )
                cycle_other = (
                    np.nan if any(pd.isna(x) for x in (
                        cycle_debt_setoff, cycle_credits
                    )) else cycle_debt_setoff + cycle_credits
                )
                cycle_monetary = (
                    np.nan if any(pd.isna(x) for x in (
                        cycle_cash, cycle_personal, cycle_other
                    )) else cycle_cash + cycle_personal + cycle_other
                )
                campaign_totals = {
                    item.get("totalType"): item for item in overview.get("totals") or []
                }
                rows.append({
                    "state": "SC", "cycle": int(index["cycle"]),
                    "chamber": index["chamber"], "district": int(index["district"]),
                    "party": index["party"], "candidate": index["candidate"],
                    "provider_candidate": index["candidateName"].strip(),
                    "committee_id": str(index["candidateFilerId"]),
                    "campaign_id": str(index["campaignId"]),
                    "report_id": str(index["reportId"]),
                    "report_type": detail.get("reportType"),
                    "report_name": index.get("reportName"),
                    "period_start": start, "period_end": end,
                    "filed_or_updated_at": index.get("lastUpdated"),
                    "is_amendment": bool(detail.get("isAmendment")),
                    "cash_contributions": cash,
                    "personal_contributions": personal,
                    "other_receipts": other,
                    "monetary_receipts": monetary,
                    "cycle_cash_contributions": cycle_cash,
                    "cycle_personal_contributions": cycle_personal,
                    "cycle_other_receipts": cycle_other,
                    "cycle_monetary_receipts": cycle_monetary,
                    "in_kind_contributions": amount(income, "In-kind Contributions"),
                    "loans_received": amount(income, "Loans"),
                    "expenditures": amount(expenditures, "Expenditures"),
                    "cycle_in_kind_contributions": amount(
                        income, "In-kind Contributions", "electionCycleTotal"
                    ),
                    "cycle_loans_received": amount(
                        income, "Loans", "electionCycleTotal"
                    ),
                    "cycle_expenditures": amount(
                        expenditures, "Expenditures", "electionCycleTotal"
                    ),
                    "returned_contributions": amount(expenditures, "Returned Contributions"),
                    "ending_cash": (
                        campaign_totals.get("Campaign Funds", {}).get("endingBalance", np.nan)
                    ),
                    "source_path": path.relative_to(ROOT).as_posix(),
                    "source_url": envelope["source_url"],
                })
    return pd.DataFrame(rows)


def intervals_overlap(frame: pd.DataFrame) -> bool:
    ordered = frame.sort_values(["period_start", "period_end"])
    prior_end = None
    for row in ordered.itertuples(index=False):
        if pd.isna(row.period_start) or pd.isna(row.period_end):
            return True
        if prior_end is not None and row.period_start <= prior_end:
            return True
        prior_end = row.period_end
    return False


def drop_zero_overlapping_periods(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove only overlap records proven to contribute exactly zero.

    Several state portals publish zero-dollar initial or pre-election reports
    whose covered dates overlap the normal quarterly schedule.  Removing such
    a row cannot change the fundraising total and avoids turning a complete
    candidate-cycle into a false review case.
    """
    if frame.empty:
        return frame
    keep = []
    for index, row in frame.iterrows():
        others = frame.drop(index=index)
        overlaps = bool((
            others.period_start.le(row.period_end)
            & others.period_end.ge(row.period_start)
        ).any())
        if not (overlaps and row.monetary_receipts == 0):
            keep.append(index)
    if not keep and frame.monetary_receipts.eq(0).all():
        keep = [frame.sort_values(["period_end", "period_start"]).index[-1]]
    return frame.loc[keep].copy()


def drop_strictly_contained_report_periods(frame: pd.DataFrame) -> pd.DataFrame:
    """Prefer an official full-period report over a contained interim report.

    South Carolina publishes initial and pre-election reports alongside a
    later quarterly report whose declared coverage fully contains the shorter
    interval.  The portal's ``filingPeriod`` amounts are totals for each
    declared interval, so adding both double-counts the contained dates.  This
    rule applies only to strict containment; partial overlaps remain review
    items.
    """
    if frame.empty:
        return frame
    keep = []
    for index, row in frame.iterrows():
        others = frame.drop(index=index)
        contained = bool((
            others.period_start.le(row.period_start)
            & others.period_end.ge(row.period_end)
            & (
                others.period_start.lt(row.period_start)
                | others.period_end.gt(row.period_end)
            )
        ).any())
        if not contained:
            keep.append(index)
    return frame.loc[keep].copy()


def drop_superseded_near_duplicate_periods(frame: pd.DataFrame) -> pd.DataFrame:
    """Resolve amendment periods whose boundary shifted by at most one day.

    Virginia sometimes retains an older scheduled report after an amendment
    changes 06/30 to 07/01 (or an equivalent one-day endpoint).  Within the
    same committee, equal opposite endpoints plus a one-day shifted endpoint
    describe the same reporting slot; the highest amendment/latest filing is
    authoritative.  Larger or cross-committee overlaps remain review items.
    """
    if frame.empty:
        return frame
    kept = []
    ordered = frame.sort_values(
        ["amendment_num", "filed_sort", "report_id"], ascending=False
    )
    for index, row in ordered.iterrows():
        duplicate = False
        for kept_index in kept:
            prior = frame.loc[kept_index]
            same_start = row.period_start == prior.period_start
            same_end = row.period_end == prior.period_end
            start_shift = abs((row.period_start - prior.period_start).days)
            end_shift = abs((row.period_end - prior.period_end).days)
            if (same_start and end_shift <= 1) or (same_end and start_shift <= 1):
                duplicate = True
                break
        if not duplicate:
            kept.append(index)
    return frame.loc[kept].copy()


def aggregate_sc() -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = sc_period_rows()
    if periods.empty:
        return pd.DataFrame(), periods
    periods["filed_sort"] = pd.to_datetime(periods.filed_or_updated_at, errors="coerce")
    periods["report_id_sort"] = pd.to_numeric(periods.report_id, errors="coerce")
    # Exact-period duplicates are retained only at their latest official state.
    periods = periods.sort_values(["filed_sort", "report_id_sort"]).drop_duplicates(
        KEY + ["campaign_id", "period_start", "period_end"], keep="last"
    )
    rows = []
    for key, group in periods.groupby(KEY, dropna=False):
        state, cycle, chamber, district, party = key
        selected_parts = []
        for _, campaign in group.groupby("campaign_id", dropna=False):
            complete = campaign[campaign.cycle_monetary_receipts.notna()].copy()
            if complete.empty:
                continue
            # Monetary election-cycle totals are cumulative and nonnegative.
            # The greatest complete official snapshot is therefore the most
            # complete fundraising observation for this campaign even when a
            # later amendment corrects an older filing-period boundary.
            selected_parts.append(complete.sort_values([
                "cycle_monetary_receipts", "filed_sort", "report_id_sort"
            ]).tail(1))
        selected = (
            pd.concat(selected_parts, ignore_index=False)
            if selected_parts else group.iloc[0:0].copy()
        )
        campaign_count = group.campaign_id.nunique(dropna=False)
        monetary_complete = bool(
            not selected.empty and len(selected) == campaign_count
            and selected.cycle_monetary_receipts.notna().all()
        )
        status = (
            "unknown_no_report_summary" if group.empty
            else "unknown_missing_election_cycle_total" if not monetary_complete
            else "observed_zero" if selected.cycle_monetary_receipts.sum() == 0
            else "observed_positive"
        )
        usable = status in {"observed_zero", "observed_positive"}
        last = selected.sort_values("period_end").tail(1)
        first = selected.head(1)
        rows.append({
            "state": state, "cycle": int(cycle), "chamber": chamber,
            "district": int(district), "party": party,
            "candidate": first.candidate.iloc[0] if not first.empty else group.candidate.iloc[0],
            "provider_candidate": (
                first.provider_candidate.iloc[0] if not first.empty
                else group.provider_candidate.iloc[0]
            ),
            "committee_id": group.committee_id.iloc[0],
            "total_fundraising": (
                selected.cycle_monetary_receipts.sum() if usable else np.nan
            ),
            "cash_contributions": (
                selected.cycle_cash_contributions.sum()
                + selected.cycle_personal_contributions.sum()
                if usable else np.nan
            ),
            "other_receipts": (
                selected.cycle_other_receipts.sum() if usable else np.nan
            ),
            "in_kind_contributions": (
                selected.cycle_in_kind_contributions.sum(min_count=1)
                if not selected.empty else np.nan
            ),
            "loans_received": (
                selected.cycle_loans_received.sum(min_count=1)
                if not selected.empty else np.nan
            ),
            "expenditures": (
                selected.cycle_expenditures.sum(min_count=1)
                if not selected.empty else np.nan
            ),
            "ending_cash": last.ending_cash.iloc[0] if not last.empty else np.nan,
            "report_count": len(selected),
            "period_start": selected.period_start.min() if not selected.empty else pd.NaT,
            "period_end": selected.period_end.max() if not selected.empty else pd.NaT,
            "finance_observation_status": status,
            "aggregation_status": (
                "maximum_complete_official_election_cycle_total_per_campaign_"
                "then_sum_distinct_campaign_registrations"
            ),
            "source_name": "South Carolina State Ethics Commission report summaries",
            "source_measure": (
                "election_cycle_total_cash_plus_personal_contributions_plus_"
                "account_credits_and_debt_setoff"
            ),
            "source_path": ";".join(sorted(selected.source_path.unique())) if not selected.empty else "",
        })
    return pd.DataFrame(rows), periods.drop(columns=["filed_sort", "report_id_sort"])


def alabama_rows() -> pd.DataFrame:
    path = WAR / "fcpa_candidate_cycle_finance.csv"
    data = pd.read_csv(path)
    data = data[data.cycle.between(2016, 2024)].copy()
    data["state"] = "AL"
    data["provider_candidate"] = data.candidate
    data["committee_id"] = ""
    data["total_fundraising"] = data.fundraising_total
    data["loans_received"] = np.nan
    data["ending_cash"] = np.nan
    data["report_count"] = data.pcc_records_with_activity
    data["period_start"] = pd.to_datetime((data.cycle - 1).astype(str) + "-01-01")
    data["period_end"] = pd.to_datetime(data.cycle.astype(str) + "-12-31")
    data["finance_observation_status"] = np.where(
        data.aggregation_status.eq("committee_found_no_cycle_activity"),
        "observed_zero", "observed_positive",
    )
    data["source_name"] = "Alabama Secretary of State FCPA PCC summaries"
    data["source_measure"] = "cash_contributions_plus_other_receipts"
    data["source_path"] = path.relative_to(ROOT).as_posix()
    columns = [
        *KEY, "candidate", "provider_candidate", "committee_id", "total_fundraising",
        "cash_contributions", "other_receipts", "in_kind_contributions",
        "loans_received", "expenditures", "ending_cash", "report_count",
        "period_start", "period_end", "finance_observation_status",
        "aggregation_status", "source_name", "source_measure", "source_path",
    ]
    data = data[columns]

    index_path = next(
        (
            path for path in (
                SUMMARY_RAW / "AL" / "adjudicated_candidate_financial_summary_index_v3.jsonl",
                SUMMARY_RAW / "AL" / "adjudicated_candidate_financial_summary_index_v2.jsonl",
                SUMMARY_RAW / "AL" / "adjudicated_candidate_financial_summary_index_v1.jsonl",
            ) if path.exists()
        ),
        SUMMARY_RAW / "AL" / "adjudicated_candidate_financial_summary_index_v3.jsonl",
    )
    if not index_path.exists():
        return data
    supplemental = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cycle = int(item["cycle"])
        cash = other = in_kind = expenditures = 0.0
        report_count = activity_count = 0
        for path_text in item["summary_paths"]:
            envelope = json.loads((ROOT / path_text).read_text(encoding="utf-8"))
            payload = envelope.get("financial_summary") or {}
            record_activity = 0.0
            for year in (cycle - 1, cycle):
                annual = payload.get(str(year)) or {}
                if annual:
                    report_count += 1
                annual_cash = float(annual.get("cashContributions") or 0.0)
                annual_other = float(annual.get("otherReceipts") or 0.0)
                annual_in_kind = float(annual.get("inKindContributions") or 0.0)
                annual_expenditures = float(annual.get("expenditures") or 0.0)
                cash += annual_cash
                other += annual_other
                in_kind += annual_in_kind
                expenditures += annual_expenditures
                record_activity += (
                    annual_cash + annual_other + annual_in_kind + annual_expenditures
                )
            activity_count += int(record_activity > 0)
        total = cash + other
        supplemental.append({
            "state": "AL", "cycle": cycle, "chamber": item["chamber"],
            "district": int(item["district"]), "party": item["party"],
            "candidate": item["candidate"],
            "provider_candidate": item["provider_candidate"],
            "committee_id": "|".join(
                f"fcpa_record:{value}"
                for value in str(item["provider_identity"]).split("|")
            ),
            "total_fundraising": total, "cash_contributions": cash,
            "other_receipts": other, "in_kind_contributions": in_kind,
            "loans_received": np.nan, "expenditures": expenditures,
            "ending_cash": np.nan, "report_count": report_count,
            "period_start": pd.Timestamp(cycle - 1, 1, 1),
            "period_end": pd.Timestamp(cycle, 12, 31),
            "finance_observation_status": (
                "observed_zero" if total == 0 else "observed_positive"
            ),
            "aggregation_status": (
                "sum_official_fcpa_calendar_year_summaries_across_candidate_records;"
                f"active_records={activity_count};identity=approved_identity_adjudication:"
                + item["adjudication_id"]
            ),
            "source_name": "Alabama Secretary of State FCPA PCC summaries",
            "source_measure": "cash_contributions_plus_other_receipts",
            "source_path": ";".join(
                [item["search_path"], *item["summary_paths"]]
            ),
        })
    supplemental_frame = pd.DataFrame(supplemental, columns=columns)
    overlap = data.merge(supplemental_frame, on=KEY, how="inner")
    if not overlap.empty:
        raise ValueError("Approved Alabama completion overlaps an existing finance row")
    return pd.concat([data, supplemental_frame], ignore_index=True)


def parse_ar_legacy_report_text(text: str) -> dict[str, float]:
    """Extract the cumulative column from an Arkansas candidate report."""
    normalized = text.replace("\u00a0", " ")

    def cumulative_between(start: str, end: str) -> float:
        match = re.search(start + r"(?P<body>.*?)" + end, normalized, re.I | re.S)
        if match is None:
            return np.nan
        amounts = re.findall(r"\$\s*([\d,]+\.\d{2})", match.group("body"))
        return float(amounts[1].replace(",", "")) if len(amounts) >= 2 else np.nan

    monetary = cumulative_between(
        r"Total\s+Monetary\s+Contributions", r"Total\s+Expenditures"
    )
    expenditures = cumulative_between(
        r"Total\s+Expenditures", r"(?:Carryover Funds|Balance of campaign funds)"
    )
    loans = cumulative_between(
        r"Total\s+Loans", r"Total\s+Monetary\s+Contributions"
    )
    balance_match = re.search(
        r"(?:Carryover Funds or Debt at close of election|"
        r"Balance of campaign funds at close of reporting period)"
        r".*?\(?\$\s*([\d,]+\.\d{2})\)?",
        normalized, re.I | re.S,
    )

    def amounts_on_label_line(label: str) -> list[float]:
        line = next(
            (line for line in normalized.splitlines()
             if re.search(label, line, re.I)),
            "",
        )
        return [
            float(value.replace(",", ""))
            for value in re.findall(r"(?<!\d)([\d,]+\.\d{2})(?!\d)", line)
        ]

    if pd.isna(monetary):
        amounts = amounts_on_label_line(r"Total\s+Monetary\s+Contributions")
        monetary = amounts[-1] if len(amounts) >= 2 else np.nan
    if pd.isna(expenditures):
        amounts = amounts_on_label_line(r"Total\s+Expenditures")
        expenditures = amounts[-1] if len(amounts) >= 2 else np.nan
    if pd.isna(loans):
        amounts = amounts_on_label_line(r"Total\s+Loans")
        loans = amounts[-1] if len(amounts) >= 2 else np.nan
    ending_cash = (
        float(balance_match.group(1).replace(",", ""))
        if balance_match else np.nan
    )
    if pd.isna(ending_cash):
        amounts = amounts_on_label_line(
            r"(?:Carryover Funds or Debt|Balance of campaign funds)"
        )
        ending_cash = amounts[-1] if amounts else np.nan
    return {
        "monetary_contributions": monetary,
        "expenditures": expenditures,
        "loans": loans,
        "ending_cash": ending_cash,
    }


def arkansas_legacy_rows() -> pd.DataFrame:
    index_paths = [
        SUMMARY_RAW / "AR" / "matched_legacy_candidate_reports_v2.jsonl",
        SUMMARY_RAW / "AR" / "matched_legacy_candidate_reports_v1.jsonl",
    ]
    index_path = next((path for path in index_paths if path.exists()), None)
    if index_path is None:
        return pd.DataFrame()
    items = [
        json.loads(line) for line in index_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    rows = []
    for item in items:
        local_path = ROOT / str(item.get("local_path", ""))
        status = str(item.get("download_status", ""))
        values = {
            "monetary_contributions": np.nan, "expenditures": np.nan,
            "loans": np.nan, "ending_cash": np.nan,
        }
        parse_status = status or "unknown_download_status"
        if status == "downloaded_pdf" and local_path.exists():
            try:
                reader = PdfReader(local_path)
                page = reader.pages[0]
                text = page.extract_text(extraction_mode="layout") or page.extract_text() or ""
                values = parse_ar_legacy_report_text(text)
                parse_status = (
                    "parsed_cumulative_summary"
                    if pd.notna(values["monetary_contributions"])
                    else "unknown_unparseable_cumulative_summary"
                )
            except Exception:
                parse_status = "unknown_unreadable_report_pdf"
        raised = values["monetary_contributions"]
        observation = (
            "observed_zero" if raised == 0
            else "observed_positive" if pd.notna(raised)
            else parse_status
        )
        rows.append({
            "state": "AR", "cycle": int(item["cycle"]),
            "chamber": item["chamber"], "district": int(item["district"]),
            "party": item["party"], "candidate": item["candidate"],
            "provider_candidate": item["provider_candidate"],
            "committee_id": item.get("candidate_filer_id") or item["report_id"],
            "total_fundraising": float(raised) if pd.notna(raised) else np.nan,
            "source_reported_total": float(raised) if pd.notna(raised) else np.nan,
            "cash_contributions": float(raised) if pd.notna(raised) else np.nan,
            "other_receipts": np.nan, "in_kind_contributions": np.nan,
            "loans_received": values["loans"],
            "expenditures": values["expenditures"],
            "ending_cash": values["ending_cash"], "report_count": 1,
            "period_start": pd.Timestamp(f"{int(item['cycle']) - 1}-01-01"),
            "period_end": pd.to_datetime(item.get("report_end"), errors="coerce"),
            "finance_observation_status": observation,
            "aggregation_status": (
                "official_candidate_report_cumulative_total;" + parse_status
            ),
            "source_name": "Arkansas Secretary of State candidate finance report",
            "source_measure": "cumulative_total_monetary_contributions",
            "source_path": str(item.get("local_path", "")),
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    if frame.duplicated(KEY).any():
        raise ValueError("Arkansas legacy report selection must be unique by candidate key")
    return frame


def arkansas_followthemoney_rows() -> pd.DataFrame:
    path = SUMMARY_RAW / "AR" / "followthemoney_candidate_matches_v1.jsonl"
    if not path.exists():
        return pd.DataFrame()
    items = [
        json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    rows = []
    for item in items:
        if item.get("match_status") != "accepted_secondary_fallback":
            continue
        raised = pd.to_numeric(item.get("total_contributions"), errors="coerce")
        if pd.isna(raised):
            continue
        rows.append({
            "state": "AR", "cycle": int(item["cycle"]),
            "chamber": item["chamber"], "district": int(item["district"]),
            "party": item["party"], "candidate": item["candidate"],
            "provider_candidate": item["provider_candidate"],
            "committee_id": item.get("candidate_filer_id", ""),
            "total_fundraising": float(raised),
            "source_reported_total": float(raised),
            "cash_contributions": float(raised), "other_receipts": np.nan,
            "in_kind_contributions": np.nan, "loans_received": np.nan,
            "expenditures": np.nan, "ending_cash": np.nan,
            "report_count": int(item.get("record_count") or 0),
            "period_start": pd.Timestamp(f"{int(item['cycle']) - 1}-01-01"),
            "period_end": pd.Timestamp(f"{int(item['cycle'])}-12-31"),
            "finance_observation_status": (
                "observed_zero" if raised == 0 else "observed_positive"
            ),
            "aggregation_status": (
                "secondary_fallback_after_unusable_or_unavailable_official_report;"
                "exact_cycle_chamber_district_party_and_person_match"
            ),
            "source_name": "FollowTheMoney.org candidate cycle totals",
            "source_measure": "candidate_cycle_total_contributions",
            "source_path": path.relative_to(ROOT).as_posix(),
        })
    frame = pd.DataFrame(rows)
    if not frame.empty and frame.duplicated(KEY).any():
        raise ValueError("Arkansas FollowTheMoney fallback must be unique by candidate key")
    return frame


def arkansas_rows() -> pd.DataFrame:
    path = SUMMARY_RAW / "AR" / "2024_candidate_financial_summary_index.json"
    match_path = ROOT / "data/processed/source_audits/southern_finance_summary_candidate_matches.csv"
    if not path.exists() or not match_path.exists():
        official = arkansas_legacy_rows()
        fallback = arkansas_followthemoney_rows()
        if official.empty:
            return fallback
        usable = official.finance_observation_status.isin(
            ["observed_zero", "observed_positive"]
        )
        unresolved = official.loc[~usable, KEY]
        fallback = fallback.merge(
            unresolved.assign(_fallback_allowed=1), on=KEY, how="inner",
            validate="one_to_one",
        ).drop(columns="_fallback_allowed")
        return pd.concat([official.loc[usable], fallback], ignore_index=True, sort=False)
    envelope = json.loads(path.read_text(encoding="utf-8-sig"))
    source = pd.DataFrame(envelope["response"]["data"]["items"])
    source = source[source.office.isin(["State Representative", "State Senate"])].copy()
    source["chamber"] = source.office.map(
        {"State Representative": "house", "State Senate": "senate"}
    )
    source["district"] = pd.to_numeric(source.officeDistrictName, errors="coerce")
    source["party"] = source.politicalParty.map(ar_party)
    source["provider_identity"] = source.apply(ar_provider_identity, axis=1)
    matches = pd.read_csv(match_path, dtype=str)
    matches["cycle"] = pd.to_numeric(matches.cycle, errors="coerce")
    matches["district"] = pd.to_numeric(matches.district, errors="coerce")
    matches = matches[
        matches.state.eq("AR") & matches.cycle.eq(2024)
        & matches.match_status.eq("accepted_automatic")
    ].copy()
    rows = []
    for match in matches.to_dict("records"):
        group = source[source.provider_identity.eq(match["provider_identity"])].copy()
        distinct = group[[
            "totalRaised", "totalSpent", "balanceofFunds", "isPaperFiler"
        ]].drop_duplicates()
        conflicting = len(distinct) > 1
        selected = group.iloc[0] if not group.empty else None
        raised = pd.to_numeric(selected.totalRaised, errors="coerce") if selected is not None else np.nan
        paper = bool(selected.isPaperFiler) if selected is not None and pd.notna(selected.isPaperFiler) else False
        status = (
            "unknown_provider_identity_missing" if selected is None
            else "review_conflicting_provider_registrations" if conflicting
            else "unknown_paper_filer_summary_not_authoritative" if paper
            else "unknown_missing_report_amount" if pd.isna(raised)
            else "observed_zero" if raised == 0
            else "observed_positive"
        )
        usable = status in {"observed_zero", "observed_positive"}
        rows.append({
            "state": "AR", "cycle": 2024, "chamber": match["chamber"],
            "district": int(float(match["district"])), "party": match["party"],
            "candidate": match["candidate"],
            "provider_candidate": match["provider_candidate"],
            "committee_id": match["candidate_filer_id"],
            "total_fundraising": float(raised) if usable else np.nan,
            "source_reported_total": float(raised) if pd.notna(raised) else np.nan,
            "cash_contributions": float(raised) if usable else np.nan,
            "other_receipts": np.nan, "in_kind_contributions": np.nan,
            "loans_received": np.nan,
            "expenditures": (
                pd.to_numeric(selected.totalSpent, errors="coerce")
                if selected is not None else np.nan
            ),
            "ending_cash": (
                pd.to_numeric(selected.balanceofFunds, errors="coerce")
                if selected is not None else np.nan
            ),
            "report_count": np.nan,
            "period_start": pd.Timestamp("2023-01-01"),
            "period_end": pd.Timestamp("2024-12-31"),
            "finance_observation_status": status,
            "aggregation_status": "provider_candidate_election_summary_as_of_retrieval",
            "source_name": "Arkansas Secretary of State candidate financial summaries",
            "source_measure": "portal_total_raised_for_selected_election_year",
            "source_path": path.relative_to(ROOT).as_posix(),
        })
    current = pd.DataFrame(rows)
    legacy = arkansas_legacy_rows()
    official = pd.concat([legacy, current], ignore_index=True, sort=False)
    if official.duplicated(KEY).any():
        raise ValueError("Arkansas current and legacy finance rows overlap")
    fallback = arkansas_followthemoney_rows()
    usable = official.finance_observation_status.isin(
        ["observed_zero", "observed_positive"]
    )
    unresolved = official.loc[~usable, KEY]
    missing = candidate_universe("AR")[KEY].merge(
        official[KEY], on=KEY, how="left", indicator=True, validate="one_to_one"
    )
    missing = missing.loc[missing._merge.eq("left_only"), KEY]
    allowed = pd.concat([unresolved, missing], ignore_index=True).drop_duplicates()
    fallback = fallback.merge(
        allowed.assign(_fallback_allowed=1), on=KEY, how="inner",
        validate="one_to_one",
    ).drop(columns="_fallback_allowed")
    combined = pd.concat(
        [official.loc[usable], fallback], ignore_index=True, sort=False
    )
    if combined.duplicated(KEY).any():
        raise ValueError("Arkansas fallback created duplicate candidate keys")
    return combined


def fl_name_signature(value: object) -> str:
    """Return an order-insensitive person-name key for Florida exports."""
    return " ".join(sorted(normalized_tokens(value)))


def parse_fl_transaction_candidate(value: object) -> tuple[str, str, str] | None:
    match = re.match(
        r"^(.*?)\s*\(([^)]+)\)\((STS|STR)\)$", str(value or "").strip()
    )
    if match is None:
        return None
    candidate, party, office = match.groups()
    return candidate.strip(), party.strip(), office


def florida_transaction_rows() -> pd.DataFrame:
    """Read complete, non-overlapping leaves of the partitioned FL export.

    The acquisition manifest labels capped parent queries ``acquired_truncated``.
    Those parents must not be combined with their recursively partitioned child
    queries.  Every retained row remains tied to its immutable raw leaf file.
    """
    if not TRANSACTION_MANIFEST.exists():
        return pd.DataFrame()
    manifest = pd.read_csv(TRANSACTION_MANIFEST, dtype=str).fillna("")
    complete_dimensions, expected_dimensions = florida_query_coverage(
        manifest.to_dict("records")
    )
    if complete_dimensions != expected_dimensions:
        raise RuntimeError(
            "Florida transaction partitions are incomplete: "
            f"{complete_dimensions}/{expected_dimensions} dimensions"
        )
    manifest = manifest[
        manifest.state_code.eq("FL")
        & manifest.data_kind.eq("contributions")
        & ~manifest.ingest_status.eq("acquired_truncated")
    ].copy()
    aggregates: dict[tuple[int, str, str, str, str, str], dict[str, object]] = {}
    csv.field_size_limit(10_000_000)
    for item in manifest.to_dict("records"):
        path = ROOT / item["local_path"]
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
            for source in csv.DictReader(handle, delimiter="\t"):
                identity = parse_fl_transaction_candidate(
                    source.get("Candidate/Committee")
                )
                if identity is None:
                    continue
                candidate, party, office = identity
                cycle = int(item["cycle"])
                date_match = re.fullmatch(
                    r"(\d{2})/(\d{2})/(\d{4})", str(source.get("Date") or "").strip()
                )
                parsed_amount = pd.to_numeric(source.get("Amount"), errors="coerce")
                if pd.isna(parsed_amount):
                    continue
                contribution_type = str(source.get("Typ") or "").strip().upper()
                scopes = ["all_candidacy"]
                if date_match is not None and int(date_match.group(3)) in {
                    cycle - 1, cycle
                }:
                    scopes.append("cycle_window")
                for scope in scopes:
                    key = (
                        cycle, office, party, fl_name_signature(candidate),
                        contribution_type, scope,
                    )
                    aggregate = aggregates.setdefault(key, {
                        "provider_candidate": candidate,
                        "amount": 0.0,
                        "transaction_count": 0,
                        "source_paths": set(),
                    })
                    aggregate["amount"] = (
                        float(aggregate["amount"]) + float(parsed_amount)
                    )
                    aggregate["transaction_count"] = int(
                        aggregate["transaction_count"]
                    ) + 1
                    aggregate["source_paths"].add(item["local_path"])
    rows = []
    for key, aggregate in aggregates.items():
        cycle, office, party, name_signature, contribution_type, scope = key
        rows.append({
            "cycle": cycle, "office": office, "party_provider": party,
            "provider_candidate": aggregate["provider_candidate"],
            "name_signature": name_signature,
            "contribution_type": contribution_type,
            "aggregation_scope": scope,
            "amount": aggregate["amount"],
            "transaction_count": aggregate["transaction_count"],
            "source_path": ";".join(sorted(aggregate["source_paths"])),
        })
    return pd.DataFrame(rows)


def florida_rows() -> pd.DataFrame:
    root = SUMMARY_RAW / "FL"
    match_path = ROOT / "data/processed/source_audits/southern_finance_summary_candidate_matches.csv"
    if not root.exists() or not match_path.exists():
        return pd.DataFrame()
    source_rows = []
    for path in sorted(root.glob("*_candidate_contribution_summary*.html")):
        cycle_match = re.match(r"(20\d{2})_", path.name)
        if not cycle_match:
            continue
        for row in parse_fl_candidate_summary(path.read_bytes()):
            chamber = "house" if row["office"] == "STR" else "senate"
            party = {"DEM": "D", "REP": "R"}.get(row["party"])
            identity = (
                f"{chamber}|{int(row['district'])}|"
                f"{' '.join(normalized_tokens(row['candidate']))}|{party or ''}"
            )
            source_rows.append({
                **row, "cycle": int(cycle_match.group(1)), "chamber": chamber,
                "party_normalized": party, "provider_identity": identity,
                "name_signature": fl_name_signature(row["candidate"]),
                "source_path": path.relative_to(ROOT).as_posix(),
            })
    source = pd.DataFrame(source_rows)
    transactions = florida_transaction_rows()
    matches = pd.read_csv(match_path, dtype=str)
    matches["cycle"] = pd.to_numeric(matches.cycle, errors="coerce")
    matches = matches[
        matches.state.eq("FL") & matches.match_status.eq("accepted_automatic")
    ].copy()
    rows = []
    for match in matches.to_dict("records"):
        contextual = source[
            source.cycle.eq(int(match["cycle"]))
            & source.chamber.eq(match["chamber"])
            & source.district.astype(int).eq(int(float(match["district"])))
            & source.party_normalized.eq(match["party"])
        ]
        # Recompute the provider key with the current normalizer instead of
        # joining to a serialized audit key.  This preserves accepted identity
        # evidence across fixes such as MC CLAIN -> MCCLAIN.
        group = contextual[
            contextual.name_signature.eq(
                fl_name_signature(match["provider_candidate"])
            )
        ].drop_duplicates(["total_amount", "source_path"])
        totals = group.total_amount.dropna().drop_duplicates()
        conflicting = len(totals) > 1
        reported = totals.iloc[0] if len(totals) == 1 else np.nan
        office = "STR" if match["chamber"] == "house" else "STS"
        provider_party = {"D": "DEM", "R": "REP"}.get(match["party"], "")
        detail = transactions[
            transactions.cycle.eq(int(match["cycle"]))
            & transactions.office.eq(office)
            & transactions.party_provider.eq(provider_party)
            & transactions.name_signature.eq(
                fl_name_signature(match["provider_candidate"])
            )
        ].copy()
        start = pd.Timestamp(date(int(match["cycle"]) - 1, 1, 1))
        end = pd.Timestamp(date(int(match["cycle"]), 12, 31))
        all_detail = detail[detail.aggregation_scope.eq("all_candidacy")]
        cycle_detail = detail[detail.aggregation_scope.eq("cycle_window")]
        type_totals = cycle_detail.set_index("contribution_type").amount.to_dict()
        all_detail_total = all_detail.amount.sum(min_count=1)
        unknown_types = {
            value for value in type_totals
            if value not in FL_MONETARY_CONTRIBUTION_TYPES
            | FL_NON_FUNDRAISING_TYPES
        }
        unexplained_x = abs(float(type_totals.get("X", 0.0))) > 0.005
        reconciled = bool(
            pd.notna(reported)
            and (
                (pd.isna(all_detail_total) and abs(float(reported)) <= 0.005)
                or (
                    pd.notna(all_detail_total)
                    and abs(float(all_detail_total) - float(reported)) <= 0.02
                )
            )
        )
        cash = sum(
            float(type_totals.get(value, 0.0))
            for value in FL_CASH_CONTRIBUTION_TYPES
        )
        other = sum(float(type_totals.get(value, 0.0)) for value in ("INT", "RCT"))
        in_kind = float(type_totals.get("INK", 0.0))
        loans = float(type_totals.get("LOA", 0.0))
        detail_available = not cycle_detail.empty
        reported_zero_without_detail = bool(
            not detail_available and not conflicting
            and pd.notna(reported) and abs(float(reported)) <= 0.005
        )
        usable = bool(
            (detail_available or reported_zero_without_detail)
            and not unknown_types and not unexplained_x
        )
        fundraising = cash + other if usable else np.nan
        model_usable = bool(usable and fundraising >= -0.005)
        status = (
            "unknown_provider_identity_missing" if group.empty and not detail_available
            else "unknown_missing_transaction_detail" if not usable and not detail_available
            else "review_unrecognized_contribution_type" if unknown_types or unexplained_x
            else "review_net_negative_cycle_receipts" if fundraising < -0.005
            else "observed_zero" if abs(fundraising) <= 0.005
            else "observed_positive"
        )
        rows.append({
            "state": "FL", "cycle": int(match["cycle"]),
            "chamber": match["chamber"], "district": int(float(match["district"])),
            "party": match["party"], "candidate": match["candidate"],
            "provider_candidate": match["provider_candidate"], "committee_id": "",
            "total_fundraising": fundraising if model_usable else np.nan,
            "source_reported_total": reported,
            "cash_contributions": cash if model_usable else np.nan,
            "other_receipts": other if model_usable else np.nan,
            "in_kind_contributions": in_kind if usable else np.nan,
            "loans_received": loans if usable else np.nan,
            "expenditures": np.nan, "ending_cash": np.nan,
            "report_count": (
                cycle_detail.transaction_count.sum() if not cycle_detail.empty else 0
            ),
            "period_start": start,
            "period_end": end,
            "finance_observation_status": status,
            "aggregation_status": (
                "official_complete_partitioned_transaction_types;summary_reconciliation="
                + (
                    "conflicting" if conflicting else
                    "missing" if pd.isna(reported) else
                    "matched" if reconciled else "mismatch"
                )
                if model_usable else
                "official_transaction_detail_retained_for_type_or_amount_review"
            ),
            "source_name": (
                "Florida Division of Elections contribution detail and candidate summaries"
            ),
            "source_measure": (
                "cash_check_money_order_interest_and_refunds_excluding_carryover_in_kind_and_loans"
            ),
            "source_path": ";".join(sorted(set(group.source_path.unique()) | set(
                path for value in cycle_detail.source_path if value
                for path in str(value).split(";")
            ))),
        })
    return pd.DataFrame(rows)


def kentucky_rows() -> pd.DataFrame:
    root = SUMMARY_RAW / "KY"
    match_path = ROOT / "data/processed/source_audits/southern_finance_summary_candidate_matches.csv"
    if not root.exists() or not match_path.exists():
        return pd.DataFrame()
    source_rows = []
    for path in sorted(root.glob("*_candidate_finance_index.html")):
        found = re.match(r"(20\d{2})_(house|senate)_", path.name)
        if not found:
            continue
        cycle, chamber = int(found.group(1)), found.group(2)
        for row in parse_ky_candidate_index(path.read_bytes(), chamber):
            source_rows.append({
                **row, "cycle": cycle,
                "source_path": path.relative_to(ROOT).as_posix(),
            })
    for path in sorted(root.glob("*_unresolved_candidate_name_searches_v1.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            chamber = item["target"]["chamber"]
            for row in parse_ky_candidate_index(
                __import__("base64").b64decode(item["content_base64"]), chamber
            ):
                election_date = pd.to_datetime(row["election_date"], errors="coerce")
                if pd.isna(election_date):
                    continue
                source_rows.append({
                    **row, "cycle": int(election_date.year),
                    "source_path": path.relative_to(ROOT).as_posix(),
                })
    source = pd.DataFrame(source_rows).drop_duplicates(
        ["cycle", "chamber", "district", "candidate_id"], keep="first"
    )
    matches = pd.read_csv(match_path, dtype=str)
    matches["cycle"] = pd.to_numeric(matches.cycle, errors="coerce")
    matches = matches[
        matches.state.eq("KY") & matches.match_status.str.startswith("accepted_")
    ]
    rows = []
    for match in matches.to_dict("records"):
        group = source[
            source.cycle.eq(int(match["cycle"]))
            & source.candidate_id.astype(str).eq(str(match["provider_identity"]))
        ]
        selected = group.iloc[0] if len(group) == 1 else None
        receipts = selected.total_receipts if selected is not None else np.nan
        status = (
            "unknown_provider_identity_missing" if group.empty
            else "review_duplicate_provider_identity" if len(group) > 1
            else "unknown_missing_report_amount" if pd.isna(receipts)
            else "observed_zero" if receipts == 0
            else "observed_positive"
        )
        usable = status in {"observed_zero", "observed_positive"}
        rows.append({
            "state": "KY", "cycle": int(match["cycle"]),
            "chamber": match["chamber"], "district": int(float(match["district"])),
            "party": match["party"], "candidate": match["candidate"],
            "provider_candidate": match["provider_candidate"],
            "committee_id": match["provider_identity"],
            "total_fundraising": receipts if usable else np.nan,
            "source_reported_total": receipts,
            "cash_contributions": np.nan, "other_receipts": np.nan,
            "in_kind_contributions": np.nan, "loans_received": np.nan,
            "expenditures": selected.total_expenses if selected is not None else np.nan,
            "ending_cash": np.nan, "report_count": np.nan,
            "period_start": pd.Timestamp(int(match["cycle"]) - 1, 1, 1),
            "period_end": pd.Timestamp(int(match["cycle"]), 12, 31),
            "finance_observation_status": status,
            "aggregation_status": "provider_candidate_election_registration_total",
            "source_name": "Kentucky Registry of Election Finance candidate search",
            "source_measure": "total_campaign_receipts_for_selected_election_registration",
            "source_path": selected.source_path if selected is not None else "",
        })
    return pd.DataFrame(rows)


_MS_OCR_ENGINE = None


def _ms_ocr_text(path: Path) -> str:
    global _MS_OCR_ENGINE
    if fitz is None or RapidOCR is None:
        return ""
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    cache = FINANCE / "mississippi_ocr_text" / f"{source_hash}_v2.json"
    if cache.exists():
        return "\n\f\n".join(json.loads(cache.read_text(encoding="utf-8"))["pages_text"])
    if _MS_OCR_ENGINE is None:
        _MS_OCR_ENGINE = RapidOCR()
    document = fitz.open(path)
    pages_text = []
    # Summary totals are on one of the first two form pages.  Itemized
    # schedules after that are not needed for a cycle aggregate.
    document_pages = list(document)
    summary_pages = document_pages[:2]
    for page in summary_pages:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        result, _ = _MS_OCR_ENGINE(pixels)
        pages_text.append("\n".join(item[1] for item in (result or [])))
    cache.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "source_sha256": source_hash,
        "ocr_engine": "rapidocr_onnxruntime",
        "render_scale": 1.5,
        "pages_ocrd": len(pages_text),
        "generated_at_utc": pd.Timestamp.now(tz="UTC").floor("s").isoformat(),
        "build_code_sha256": build_code_sha256(),
        "pages_text": pages_text,
    }
    cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return "\n\f\n".join(pages_text)


def _parse_ms_ocr_summary(text: str) -> dict[str, float]:
    lines = [line.strip() for line in text.splitlines()]
    totals = []
    for index, line in enumerate(lines):
        compact = re.sub(r"[^A-Z]", "", line.upper())
        if "TOTALAMTOFCONTRIBUTIONS" not in compact:
            continue
        values = []
        for following in lines[index:index + 10]:
            following_compact = re.sub(r"[^A-Z]", "", following.upper())
            if following is not line and "TOTALAMTOFDISBURSEMENTS" in following_compact:
                break
            for token in re.findall(r"\(?-?\d[\d,]*\.\d{1,2}\)?", following):
                value = token.replace(",", "")
                if value.startswith("(") and value.endswith(")"):
                    value = "-" + value[1:-1]
                values.append(float(value))
            # Handwritten zeroes are commonly recognized as the letter O.
            # Limit this correction to standalone currency fields so names and
            # labels cannot become fabricated amounts.
            if re.fullmatch(r"\s*\$\s*-?[O0](?:[.,][O0]{1,2})?\s*", following, re.I):
                values.append(0.0)
        if values:
            # The form columns end with Calendar Year-to-Date.  Separate
            # pre-2018 and post-2018 blocks are additive when both are used.
            totals.append(values[-1])
    if not totals:
        return {}
    return {"aggregate_ytd": float(sum(totals)), "parse_method": "rapidocr_summary"}


def parse_ms_pdf_summary(path: Path, *, allow_ocr: bool = True) -> dict[str, float]:
    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return {}
    block = re.search(
        r"Current Contributions\s+Prior Period Balance\s+Itemized\s+Non-Itemized\s+"
        r"Period Total\s+Aggregate YTD\s+"
        r"(\$[\d,.()\-]+)\s+(\$[\d,.()\-]+)\s+(\$[\d,.()\-]+)\s+"
        r"(\$[\d,.()\-]+)\s+(\$[\d,.()\-]+)",
        text, flags=re.I,
    )
    if block:
        values = [float(value.replace("$", "").replace(",", "").replace("(", "-").replace(")", "")) for value in block.groups()]
        return {
            "prior_contributions": values[0], "itemized": values[1],
            "non_itemized": values[2], "period_total": values[3],
            "aggregate_ytd": values[4], "parse_method": "embedded_text_summary",
        }
    return _parse_ms_ocr_summary(_ms_ocr_text(path)) if allow_ocr else {}


def mississippi_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest_path = ROOT / "data/processed/source_audits/southern_finance_summary_manifest.csv"
    match_path = ROOT / "data/processed/source_audits/southern_finance_summary_candidate_matches.csv"
    if not manifest_path.exists() or not match_path.exists():
        return pd.DataFrame(), pd.DataFrame()
    manifest = pd.read_csv(manifest_path, dtype=str)
    manifest = manifest[
        manifest.state.eq("MS") & manifest.data_kind.eq("selected_filing_pdf")
    ].copy()
    period_rows = []
    for item in manifest.to_dict("records"):
        params = json.loads(item["request_parameters"])
        path = ROOT / item["local_path"]
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        cached_ocr = (
            FINANCE / "mississippi_ocr_text" / f"{source_hash}_v2.json"
        ).exists()
        parsed = parse_ms_pdf_summary(
            path, allow_ocr=int(item.get("cycle", 0)) == 2023 or cached_ocr
        )
        period_rows.append({
            "entity_id": params["entity_id"],
            "summary_year": int(params["summary_year"]),
            "report_name": params["report_name"],
            "monetary_receipts": parsed.get("aggregate_ytd", np.nan),
            "itemized_contributions": parsed.get("itemized", np.nan),
            "non_itemized_contributions": parsed.get("non_itemized", np.nan),
            "pdf_text_status": parsed.get("parse_method", "unknown_scanned_or_unrecognized_pdf"),
            "source_path": item["local_path"], "source_url": item["source_url"],
        })
    periods = pd.DataFrame(period_rows)
    matches = pd.read_csv(match_path, dtype=str)
    matches["cycle"] = pd.to_numeric(matches.cycle, errors="coerce")
    matches = matches[
        matches.state.eq("MS") & matches.match_status.eq("accepted_automatic")
    ]
    rows = []
    for match in matches.to_dict("records"):
        selected = periods[
            periods.entity_id.eq(match["provider_identity"])
            & periods.summary_year.isin([int(match["cycle"]) - 1, int(match["cycle"])])
        ].drop_duplicates(["summary_year", "monetary_receipts", "source_path"])
        years = set(selected.loc[selected.monetary_receipts.notna(), "summary_year"])
        complete = years == {int(match["cycle"]) - 1, int(match["cycle"])}
        total = selected.groupby("summary_year").monetary_receipts.max().sum() if complete else np.nan
        status = (
            "unknown_no_selected_filing" if selected.empty
            else "unknown_scanned_or_unrecognized_pdf" if not complete
            else "observed_zero" if total == 0
            else "observed_positive"
        )
        rows.append({
            "state": "MS", "cycle": int(match["cycle"]),
            "chamber": match["chamber"], "district": int(float(match["district"])),
            "party": match["party"], "candidate": match["candidate"],
            "provider_candidate": match["provider_candidate"],
            "committee_id": match["provider_identity"],
            "total_fundraising": total,
            "cash_contributions": total, "other_receipts": np.nan,
            "in_kind_contributions": np.nan, "loans_received": np.nan,
            "expenditures": np.nan, "ending_cash": np.nan,
            "report_count": len(selected),
            "period_start": pd.Timestamp(int(match["cycle"]) - 1, 1, 1),
            "period_end": pd.Timestamp(int(match["cycle"]), 12, 31),
            "finance_observation_status": status,
            "aggregation_status": "sum_of_two_calendar_year_aggregate_ytd_report_summaries",
            "source_name": "Mississippi Secretary of State selected disclosure PDFs",
            "source_measure": "current_contributions_aggregate_ytd",
            "source_path": ";".join(sorted(selected.source_path.unique())),
        })
    return pd.DataFrame(rows), periods


def missouri_rows() -> pd.DataFrame:
    match_path = ROOT / "data/processed/source_audits/southern_finance_summary_candidate_matches.csv"
    if not match_path.exists():
        return pd.DataFrame()
    matches = pd.read_csv(match_path, dtype=str)
    matches["cycle"] = pd.to_numeric(matches.cycle, errors="coerce")
    matches = matches[
        matches.state.eq("MO") & matches.match_status.eq("accepted_automatic")
    ]
    rows = []
    for match in matches.to_dict("records"):
        rows.append({
            "state": "MO", "cycle": int(match["cycle"]),
            "chamber": match["chamber"], "district": int(float(match["district"])),
            "party": match["party"], "candidate": match["candidate"],
            "provider_candidate": match["provider_candidate"],
            "committee_id": match["provider_identity"],
            "total_fundraising": np.nan, "cash_contributions": np.nan,
            "other_receipts": np.nan, "in_kind_contributions": np.nan,
            "loans_received": np.nan, "expenditures": np.nan,
            "ending_cash": np.nan, "report_count": np.nan,
            "period_start": pd.Timestamp(int(match["cycle"]) - 1, 1, 1),
            "period_end": pd.Timestamp(int(match["cycle"]), 12, 31),
            "finance_observation_status": "unknown_official_report_download_blocked_by_recaptcha",
            "aggregation_status": "candidate_committee_identified_report_summary_not_acquired",
            "source_name": "Missouri Ethics Commission candidates-by-election search",
            "source_measure": "unknown",
            "source_path": "data/raw/finance/southern_summaries/MO/modeled_candidate_mec_ids.jsonl",
        })
    return pd.DataFrame(rows)


def tn_summary_value(text: str, label: str) -> float:
    match = re.search(
        re.escape(label) + r"\s+\$([\d,]+\.\d{2}|\([\d,]+\.\d{2}\)|-[\d,]+\.\d{2})",
        text, flags=re.I,
    )
    if match is None:
        return np.nan
    value = match.group(1).replace(",", "")
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    return float(value)


def tn_zero_when_section_is_empty(
    text: str, label: str, next_label: str,
) -> float:
    """Parse a TN amount while recognizing a provider-explicit empty section.

    Older Tennessee report pages omit the numeric value after ``Contribution
    Adjustments`` when the section contains no rows. The label is immediately
    followed by the next receipt-section label in that layout. Non-empty
    unparsed sections remain unknown.
    """
    parsed = tn_summary_value(text, label)
    if pd.notna(parsed):
        return parsed
    section = re.search(
        re.escape(label) + r"\s*(.*?)\s*" + re.escape(next_label),
        text, flags=re.I | re.S,
    )
    if section is not None and not section.group(1).strip():
        return 0.0
    return np.nan


def tn_workbook_summary_value(frame: pd.DataFrame, label: str) -> float:
    """Read a summary amount from an official TN full-report XLS workbook."""
    label_rows = frame.index[
        frame.apply(
            lambda row: any(
                str(value).strip().casefold() == label.casefold()
                for value in row if pd.notna(value)
            ),
            axis=1,
        )
    ].tolist()
    if len(label_rows) != 1:
        return np.nan
    for row_index in range(label_rows[0] + 1, min(label_rows[0] + 4, len(frame))):
        for value in frame.iloc[row_index].dropna():
            match = re.fullmatch(r"\$?\(?([\d,]+\.\d{2})\)?", str(value).strip())
            if match:
                amount = float(match.group(1).replace(",", ""))
                return -amount if "(" in str(value) else amount
    return np.nan


def tennessee_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    indexes = sorted((SUMMARY_RAW / "TN").glob("*/matched_candidate_report_index_v2.jsonl"))
    if not indexes:
        indexes = sorted((SUMMARY_RAW / "TN").glob("*/matched_candidate_report_index.jsonl"))
    adjudicated_indexes = sorted(
        (SUMMARY_RAW / "TN").glob("*/adjudicated_candidate_report_index_v2.jsonl")
    )
    if not adjudicated_indexes:
        adjudicated_indexes = sorted(
            (SUMMARY_RAW / "TN").glob("*/adjudicated_candidate_report_index_v1.jsonl")
        )
    indexes += adjudicated_indexes
    match_path = ROOT / "data/processed/source_audits/southern_finance_summary_candidate_matches.csv"
    if not indexes or not match_path.exists():
        return pd.DataFrame(), pd.DataFrame()
    period_rows = []
    index_rows = []
    for path in indexes:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                index_rows.append(json.loads(line))
    # An approved identity can upgrade an existing automatic match. Its
    # supplemental index therefore repeats the same official report IDs; keep
    # one report per exact candidate-cycle key and prefer the entry carrying an
    # official workbook fallback.
    deduplicated_index: dict[tuple[object, ...], dict[str, object]] = {}
    for item in index_rows:
        index_key = (
            int(item["cycle"]), item["chamber"], int(item["district"]),
            item["party"], str(item["report_id"]),
        )
        existing = deduplicated_index.get(index_key)
        if existing is None or (
            item.get("report_workbook_path")
            and not existing.get("report_workbook_path")
        ):
            deduplicated_index[index_key] = item
    index_rows = list(deduplicated_index.values())
    for item in index_rows:
        report_path = SUMMARY_RAW / "TN" / "reports" / f"{item['report_id']}.html"
        if not report_path.exists():
            continue
        text = BeautifulSoup(
            report_path.read_bytes(), "html.parser"
        ).get_text(" ", strip=True)
        contributions = tn_summary_value(
            text, "TOTAL CONTRIBUTIONS (other than adjustments, loans, and interest)"
        )
        adjustments = tn_zero_when_section_is_empty(
            text, "Contribution Adjustments", "Loans Received"
        )
        interest = tn_summary_value(text, "Interest Received This Reporting Period")
        loans = tn_summary_value(text, "Loans Received")
        total_receipts = tn_summary_value(text, "TOTAL RECEIPTS")
        expenditures = tn_summary_value(text, "TOTAL EXPENDITURES")
        omitted_zero_receipt_section = (
            all(pd.isna(value) for value in (contributions, adjustments, interest))
            and "Beginning Balance" in text and "ENDING BALANCE" in text
        )
        if omitted_zero_receipt_section:
            contributions = adjustments = interest = 0.0
        component_complete = all(
            pd.notna(value) for value in (contributions, adjustments, interest)
        )
        monetary = (
            total_receipts - loans
            if pd.notna(total_receipts) and pd.notna(loans)
            else contributions + adjustments + interest if component_complete else np.nan
        )
        workbook_source = item.get("report_workbook_path", "")
        if pd.isna(monetary) and workbook_source:
            workbook_path = ROOT / workbook_source
            workbook = pd.read_excel(workbook_path, header=None)
            contributions = tn_workbook_summary_value(
                workbook, "Total Contributions"
            )
            interest = tn_workbook_summary_value(workbook, "Interest Received")
            if pd.isna(interest):
                interest = 0.0
            monetary = contributions + interest if pd.notna(contributions) else np.nan
            adjustments = 0.0
        complete = pd.notna(monetary)
        period_rows.append({
            "state": "TN", "cycle": int(item["cycle"]),
            "chamber": item["chamber"], "district": int(item["district"]),
            "party": item["party"], "candidate": item["candidate"],
            "provider_candidate": item["provider_candidate"],
            "committee_id": str(item["provider_identity"]),
            "report_id": str(item["report_id"]), "report_type": item["report_name"],
            "period_start": pd.Timestamp(int(item["report_year"]), 1, 1),
            "period_end": pd.Timestamp(int(item["report_year"]), 12, 31),
            "filed_or_updated_at": item["submitted_on"],
            "monetary_receipts": monetary,
            "cash_contributions": contributions,
            "other_receipts": (
                monetary - contributions
                if pd.notna(monetary) and pd.notna(contributions) else np.nan
            ),
            "loans_received": loans, "expenditures": expenditures,
            "parse_status": "parsed_summary" if complete else "unknown_summary_layout",
            "source_path": (
                workbook_source if workbook_source and pd.notna(monetary)
                else report_path.relative_to(ROOT).as_posix()
            ),
            "source_url": item["report_url"],
        })
    periods = pd.DataFrame(period_rows)
    matches = pd.read_csv(match_path, dtype=str)
    matches["cycle"] = pd.to_numeric(matches.cycle, errors="coerce")
    matches = matches[
        matches.state.eq("TN") & matches.match_status.eq("accepted_automatic")
    ].copy()
    matches["adjudication_id"] = ""
    adjudicated_matches = []
    for decision in approved_finance_identity_adjudications("TN").itertuples(index=False):
        for cycle in range(decision.cycle_start, decision.cycle_end + 1, 2):
            target = candidate_universe("TN")
            target = target[
                target.cycle.eq(cycle) & target.chamber.eq(decision.chamber)
                & target.district.eq(decision.district) & target.party.eq(decision.party)
            ]
            if len(target) != 1:
                raise ValueError(
                    "Approved Tennessee identity decision does not resolve one candidate: "
                    f"{decision.adjudication_id}"
                )
            existing_mask = (
                matches.cycle.eq(cycle)
                & matches.chamber.eq(decision.chamber)
                & pd.to_numeric(matches.district, errors="coerce").eq(decision.district)
                & matches.party.eq(decision.party)
            )
            if existing_mask.any():
                if int(existing_mask.sum()) != 1:
                    raise ValueError(
                        "Approved Tennessee identity overlaps multiple automatic rows: "
                        f"{decision.adjudication_id}"
                    )
                existing_id = str(
                    matches.loc[existing_mask, "provider_identity"].iloc[0]
                )
                if existing_id != str(decision.provider_identity):
                    raise ValueError(
                        "Approved Tennessee identity conflicts with automatic filer: "
                        f"{decision.adjudication_id}"
                    )
                matches.loc[existing_mask, "provider_candidate"] = (
                    decision.provider_candidate_name
                )
                matches.loc[existing_mask, "match_status"] = (
                    "accepted_manual_adjudication"
                )
                matches.loc[existing_mask, "adjudication_id"] = (
                    decision.adjudication_id
                )
                continue
            adjudicated_matches.append({
                "state": "TN", "cycle": cycle, "chamber": decision.chamber,
                "district": decision.district, "party": decision.party,
                "candidate": target.iloc[0].candidate,
                "provider_candidate": decision.provider_candidate_name,
                "provider_identity": decision.provider_identity,
                "match_status": "accepted_manual_adjudication",
                "adjudication_id": decision.adjudication_id,
            })
    if adjudicated_matches:
        matches = pd.concat(
            [matches, pd.DataFrame(adjudicated_matches)], ignore_index=True, sort=False
        )
    normalized_match_key = matches.assign(
        district=pd.to_numeric(matches.district, errors="raise").astype(int)
    )
    if normalized_match_key.duplicated(KEY).any():
        raise ValueError("Tennessee automatic and adjudicated identities overlap")
    rows = []
    for match in matches.to_dict("records"):
        selected = periods[
            periods.cycle.eq(int(match["cycle"]))
            & periods.chamber.eq(match["chamber"])
            & periods.district.eq(int(float(match["district"])))
            & periods.party.eq(match["party"])
        ] if not periods.empty else pd.DataFrame()
        complete = bool(not selected.empty and selected.monetary_receipts.notna().all())
        total = selected.monetary_receipts.sum() if complete else np.nan
        status = (
            "unknown_no_report_summary" if selected.empty
            else "unknown_summary_layout" if not complete
            else "observed_zero" if total == 0 else "observed_positive"
        )
        rows.append({
            "state": "TN", "cycle": int(match["cycle"]),
            "chamber": match["chamber"], "district": int(float(match["district"])),
            "party": match["party"], "candidate": match["candidate"],
            "provider_candidate": match["provider_candidate"],
            "committee_id": match["provider_identity"],
            "total_fundraising": total,
            "cash_contributions": selected.cash_contributions.sum() if complete else np.nan,
            "other_receipts": selected.other_receipts.sum() if complete else np.nan,
            "in_kind_contributions": np.nan,
            "loans_received": selected.loans_received.sum(min_count=1) if not selected.empty else np.nan,
            "expenditures": selected.expenditures.sum(min_count=1) if not selected.empty else np.nan,
            "ending_cash": np.nan, "report_count": len(selected),
            "period_start": pd.Timestamp(int(match["cycle"]) - 1, 1, 1),
            "period_end": pd.Timestamp(int(match["cycle"]), 12, 31),
            "finance_observation_status": status,
            "aggregation_status": (
                "sum_current_portal_report_summaries_for_two_calendar_year_cycle"
                + (
                    ";identity=approved_identity_adjudication:"
                    + str(match.get("adjudication_id"))
                    if match.get("match_status") == "accepted_manual_adjudication"
                    else ";identity=automatic_candidate_match"
                )
            ),
            "source_name": "Tennessee Registry of Election Finance report summaries",
            "source_measure": "contributions_plus_adjustments_plus_interest_excluding_loans",
            "source_path": ";".join(sorted(selected.source_path.unique())) if not selected.empty else "",
        })
    return pd.DataFrame(rows), periods


def xml_number(root: ET.Element, name: str) -> float:
    element = root.find(f".//{{*}}{name}")
    if element is None or element.text is None:
        return np.nan
    return pd.to_numeric(element.text, errors="coerce")


def virginia_period_rows() -> pd.DataFrame:
    versioned_indexes = [
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v18.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v17.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v16.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v15.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v14.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v13.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v12.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v11.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v10.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v9.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v8.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v7.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v6.jsonl",
        SUMMARY_RAW / "VA" / "matched_candidate_committee_report_indexes_v5.jsonl",
    ]
    index_path = next((path for path in versioned_indexes if path.exists()), versioned_indexes[0])
    match_path = ROOT / "data/processed/source_audits/southern_finance_summary_candidate_matches.csv"
    if not index_path.exists() or not match_path.exists():
        return pd.DataFrame()
    report_indexes = {}
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            report_indexes[item["committee_id"]] = parse_va_committee_reports(
                __import__("base64").b64decode(item["content_base64"])
            )
    matches = pd.read_csv(match_path, dtype=str)
    matches["cycle"] = pd.to_numeric(matches.cycle, errors="coerce")
    matches = matches[
        matches.state.eq("VA") & matches.match_status.eq("accepted_automatic")
    ]
    cache_path = FINANCE / ".cache" / "virginia_period_rows.csv.gz"
    cache_meta_path = FINANCE / ".cache" / "virginia_period_rows.meta.json"
    cache_digest = hashlib.sha256()
    cache_digest.update(b"virginia-period-parser-v2")
    cache_digest.update(index_path.read_bytes())
    cache_digest.update(
        matches.sort_values(
            ["cycle", "chamber", "district", "party"]
        ).to_csv(index=False).encode("utf-8")
    )
    xml_root = SUMMARY_RAW / "VA" / "selected_report_xml"
    xml_metadata = [
        f"{path.name}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
        for path in sorted(xml_root.glob("*.xml"))
    ]
    cache_digest.update("\n".join(xml_metadata).encode("utf-8"))
    cache_key = cache_digest.hexdigest()
    if cache_path.exists() and cache_meta_path.exists():
        cache_meta = json.loads(cache_meta_path.read_text(encoding="utf-8"))
        if cache_meta.get("cache_key") == cache_key:
            return pd.read_csv(
                cache_path,
                compression="gzip",
                parse_dates=["period_start", "period_end"],
                low_memory=False,
            )
    rows = []
    for match in matches.to_dict("records"):
        committee_ids = [
            value for value in str(match["provider_identity"]).split("|") if value
        ]
        cycle_start = pd.Timestamp(int(match["cycle"]) - 1, 1, 1)
        cycle_end = pd.Timestamp(int(match["cycle"]), 12, 31)
        relevant_reports = 0
        for committee_id in committee_ids:
            for report in report_indexes.get(committee_id, []):
                report_start = pd.to_datetime(report["period_start"], errors="coerce")
                report_end = pd.to_datetime(report["period_end"], errors="coerce")
                if (
                    pd.isna(report_start) or pd.isna(report_end)
                    or report_end < cycle_start or report_start > cycle_end
                ):
                    continue
                relevant_reports += 1
                path = SUMMARY_RAW / "VA" / "selected_report_xml" / f"{report['report_id']}.xml"
                if not path.exists():
                    continue
                root = ET.parse(path).getroot()
                schedule_a = xml_number(root, "ScheduleATotal")
                unitemized = xml_number(root, "UnItemizedTotal")
                other = xml_number(root, "ScheduleCTotal")
                schedule_b = xml_number(root, "ScheduleBTotal")
                unitemized_in_kind = xml_number(root, "UnItemizedInKindTotal")
                cash = schedule_a + unitemized if pd.notna(schedule_a) and pd.notna(unitemized) else np.nan
                monetary = cash + other if pd.notna(cash) and pd.notna(other) else np.nan
                rows.append({
                    "state": "VA", "cycle": int(match["cycle"]),
                    "chamber": match["chamber"], "district": int(float(match["district"])),
                    "party": match["party"], "candidate": match["candidate"],
                    "provider_candidate": match["provider_candidate"],
                    "committee_id": committee_id, "report_id": report["report_id"],
                    "report_type": "scheduled", "period_start": pd.to_datetime(report["period_start"]),
                    "period_end": pd.to_datetime(report["period_end"]),
                    "filed_or_updated_at": report["filed"], "amendment": report["amendment"],
                    "monetary_receipts": monetary, "cash_contributions": cash,
                    "other_receipts": other,
                    "in_kind_contributions": (
                        schedule_b + unitemized_in_kind
                        if pd.notna(schedule_b) and pd.notna(unitemized_in_kind) else np.nan
                    ),
                    "loans_received": xml_number(root, "LoansReceivedTotal"),
                    "expenditures": xml_number(root, "ScheduleDTotal"),
                    "ending_cash": xml_number(root, "EndingBalance"),
                    "source_path": path.relative_to(ROOT).as_posix(),
                    "source_url": report["xml_url"],
                })
        if (
            committee_ids and relevant_reports == 0
            and all(committee_id in report_indexes for committee_id in committee_ids)
        ):
            rows.append({
                "state": "VA", "cycle": int(match["cycle"]),
                "chamber": match["chamber"], "district": int(float(match["district"])),
                "party": match["party"], "candidate": match["candidate"],
                "provider_candidate": match["provider_candidate"],
                "committee_id": "|".join(committee_ids), "report_id": "",
                "report_type": "official_no_scheduled_reports_in_cycle_window",
                "period_start": cycle_start, "period_end": cycle_end,
                "filed_or_updated_at": "", "amendment": "",
                "monetary_receipts": 0.0, "cash_contributions": 0.0,
                "other_receipts": 0.0, "in_kind_contributions": np.nan,
                "loans_received": np.nan, "expenditures": np.nan,
                "ending_cash": np.nan,
                "source_path": index_path.relative_to(ROOT).as_posix(),
                "source_url": VA_BASE + "Committee/Index/{id}",
            })
    frame = pd.DataFrame(rows)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False, compression="gzip")
    cache_meta_path.write_text(json.dumps({
        "cache_key": cache_key,
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "code_version": build_code_sha256(),
        "configuration": "virginia-period-parser-v2",
        "committee_index": index_path.relative_to(ROOT).as_posix(),
        "match_audit": match_path.relative_to(ROOT).as_posix(),
        "row_count": len(frame),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return frame


def aggregate_virginia() -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = virginia_period_rows()
    if periods.empty:
        return pd.DataFrame(), periods
    periods["amendment_num"] = pd.to_numeric(periods.amendment, errors="coerce").fillna(0)
    periods["filed_sort"] = pd.to_datetime(periods.filed_or_updated_at, errors="coerce")
    periods = periods.sort_values(["amendment_num", "filed_sort", "report_id"]).drop_duplicates(
        KEY + ["committee_id", "period_start", "period_end"], keep="last"
    )
    periods = pd.concat([
        drop_superseded_near_duplicate_periods(group)
        for _, group in periods.groupby(KEY + ["committee_id"], dropna=False)
    ], ignore_index=True)
    rows = []
    for key, group in periods.groupby(KEY, dropna=False):
        state, cycle, chamber, district, party = key
        start = pd.Timestamp(int(cycle) - 1, 1, 1)
        end = pd.Timestamp(int(cycle), 12, 31)
        selected = group[group.period_start.ge(start) & group.period_end.le(end)].copy()
        selected = drop_zero_overlapping_periods(selected)
        boundary = group[
            group.period_start.lt(start) & group.period_end.ge(start)
            & group.monetary_receipts.ne(0)
        ]
        # Distinct committee IDs are separate legal accounts, so their report
        # calendars may legitimately cover the same dates.  Only an overlap
        # within one committee creates a double-counting ambiguity.
        overlap = bool(
            not selected.empty
            and any(
                intervals_overlap(committee_periods)
                for _, committee_periods in selected.groupby(
                    "committee_id", dropna=False
                )
            )
        )
        complete = bool(not selected.empty and selected.monetary_receipts.notna().all())
        status = (
            "unknown_no_report_summary" if selected.empty
            else "review_boundary_spanning_report" if not boundary.empty
            else "review_overlapping_report_periods_or_multiple_committees" if overlap
            else "unknown_missing_report_amount" if not complete
            else "observed_zero" if selected.monetary_receipts.sum() == 0
            else "observed_positive"
        )
        usable = status in {"observed_zero", "observed_positive"}
        last = selected.sort_values("period_end").tail(1)
        rows.append({
            "state": state, "cycle": int(cycle), "chamber": chamber,
            "district": int(district), "party": party,
            "candidate": group.candidate.iloc[0],
            "provider_candidate": group.provider_candidate.iloc[0],
            "committee_id": "|".join(sorted(group.committee_id.unique())),
            "total_fundraising": selected.monetary_receipts.sum() if usable else np.nan,
            "cash_contributions": selected.cash_contributions.sum() if usable else np.nan,
            "other_receipts": selected.other_receipts.sum() if usable else np.nan,
            "in_kind_contributions": selected.in_kind_contributions.sum(min_count=1),
            "loans_received": selected.loans_received.sum(min_count=1),
            "expenditures": selected.expenditures.sum(min_count=1),
            "ending_cash": last.ending_cash.iloc[0] if not last.empty else np.nan,
            "report_count": len(selected),
            "period_start": selected.period_start.min() if not selected.empty else pd.NaT,
            "period_end": selected.period_end.max() if not selected.empty else pd.NaT,
            "finance_observation_status": status,
            "aggregation_status": (
                "latest_amendment_per_exact_period_then_nonoverlap_within_"
                "committee_then_sum_distinct_accepted_committee_accounts"
            ),
            "source_name": "Virginia Department of Elections scheduled report XML",
            "source_measure": "schedule_a_plus_unitemized_cash_plus_schedule_c_other_receipts",
            "source_path": ";".join(sorted(selected.source_path.unique())),
        })
    return pd.DataFrame(rows), periods.drop(columns=["amendment_num", "filed_sort"])


def oklahoma_rows() -> pd.DataFrame:
    raw_root = ROOT / "data/raw/finance/southern/OK"
    if not raw_root.exists():
        return pd.DataFrame()
    receipt_frames = []
    expenditure_frames = []
    for path in sorted(raw_root.glob("*_ContributionLoanExtract.csv.zip")):
        with zipfile.ZipFile(path) as zipped:
            member = zipped.namelist()[0]
            frame = pd.read_csv(
                zipped.open(member), dtype=str, encoding="latin1",
                usecols=[
                    "Receipt ID", "Receipt Type", "Receipt Date", "Receipt Amount",
                    "Candidate Name", "Committee Type", "Amended",
                ], low_memory=False,
            )
        frame = frame[
            frame["Candidate Name"].notna()
            & frame["Candidate Name"].str.strip().ne("")
            & frame["Committee Type"].eq("Candidate Committee")
        ].copy()
        frame["source_path"] = path.relative_to(ROOT).as_posix()
        receipt_frames.append(frame)
    for path in sorted(raw_root.glob("*_ExpenditureExtract.csv.zip")):
        with zipfile.ZipFile(path) as zipped:
            member = zipped.namelist()[0]
            frame = pd.read_csv(
                zipped.open(member), dtype=str, encoding="latin1",
                usecols=[
                    "Expenditure ID", "Expenditure Date", "Expenditure Amount",
                    "Candidate Name", "Committee Type", "Amended",
                ], low_memory=False,
            )
        frame = frame[
            frame["Candidate Name"].notna()
            & frame["Candidate Name"].str.strip().ne("")
            & frame["Committee Type"].eq("Candidate Committee")
        ].copy()
        frame["source_path"] = path.relative_to(ROOT).as_posix()
        expenditure_frames.append(frame)
    receipts = pd.concat(receipt_frames, ignore_index=True)
    expenditures = pd.concat(expenditure_frames, ignore_index=True)
    receipts = receipts.drop_duplicates("Receipt ID", keep="last")
    expenditures = expenditures.drop_duplicates("Expenditure ID", keep="last")
    receipts["date"] = pd.to_datetime(receipts["Receipt Date"], errors="coerce")
    receipts["amount"] = pd.to_numeric(receipts["Receipt Amount"], errors="coerce")
    expenditures["date"] = pd.to_datetime(expenditures["Expenditure Date"], errors="coerce")
    expenditures["amount"] = pd.to_numeric(expenditures["Expenditure Amount"], errors="coerce")
    receipts["identity"] = receipts["Candidate Name"].map(
        lambda value: " ".join(normalized_tokens(value))
    )
    expenditures["identity"] = expenditures["Candidate Name"].map(
        lambda value: " ".join(normalized_tokens(value))
    )
    universe = candidate_universe("OK", prefer_final_names=True)
    reciprocal_by_key: dict[tuple[int, str, int, str], list[str]] = {}
    for cycle, cycle_targets in universe.groupby("cycle", sort=True):
        start = pd.Timestamp(int(cycle) - 1, 1, 1)
        end = pd.Timestamp(int(cycle), 12, 31)
        cycle_identities = pd.concat([
            receipts.loc[
                receipts.date.between(start, end), ["identity", "Candidate Name"]
            ],
            expenditures.loc[
                expenditures.date.between(start, end), ["identity", "Candidate Name"]
            ],
        ], ignore_index=True).drop_duplicates()
        local_targets = cycle_targets.reset_index(drop=True)
        assignments, _ = reciprocal_identity_assignments(
            local_targets, cycle_identities,
            identity_column="identity", name_column="Candidate Name",
        )
        for target in local_targets.itertuples(index=True):
            reciprocal_by_key[(
                int(target.cycle), target.chamber, int(target.district), target.party,
            )] = assignments[target.Index]
    rows = []
    loan_types = {"Loan"}
    in_kind_types = {"In-Kind"}
    nonmonetary_types = {
        "Loan Forgiveness", "Loan Balance Decrease due to Loan Forgiveness",
    }
    for target in universe.itertuples(index=False):
        start = pd.Timestamp(int(target.cycle) - 1, 1, 1)
        end = pd.Timestamp(int(target.cycle), 12, 31)
        window = receipts[receipts.date.between(start, end)]
        expenditure_window = expenditures[expenditures.date.between(start, end)]
        identities = pd.concat([
            window[["identity", "Candidate Name"]],
            expenditure_window[["identity", "Candidate Name"]],
        ], ignore_index=True).drop_duplicates("identity")
        scored = sorted([
            (
                max(
                    candidate_score(target.candidate, row["Candidate Name"]),
                    candidate_identity_score(target.candidate, row["Candidate Name"]),
                ),
                row["identity"], row["Candidate Name"],
            )
            for row in identities.to_dict("records")
        ], reverse=True)
        best = scored[0] if scored else (0.0, "", "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = best[0] - second
        accepted_best = bool(best[1] and best[0] >= 88.0 and margin >= 5.0)
        accepted_identities = set(reciprocal_by_key.get((
            int(target.cycle), target.chamber, int(target.district), target.party,
        ), []))
        if accepted_best:
            accepted_identities.add(best[1])
        accepted = bool(accepted_identities)
        selected = (
            window[window.identity.isin(accepted_identities)]
            if accepted else window.iloc[0:0]
        )
        selected_exp = expenditures[
            expenditures.date.between(start, end)
            & expenditures.identity.isin(accepted_identities)
        ] if accepted else expenditures.iloc[0:0]
        provider_names = sorted(set(
            identities.loc[
                identities.identity.isin(accepted_identities), "Candidate Name"
            ].astype(str)
        ))
        monetary = selected[
            ~selected["Receipt Type"].isin(loan_types | in_kind_types | nonmonetary_types)
        ]
        # Guardian's annual bulk extract is exhaustive at this grain.  Once a
        # candidate identity is resolved and has monetary receipt activity,
        # an absent compatible subcategory is an explicit category zero.
        cash = monetary[monetary["Receipt Type"].eq("Monetary")].amount.sum()
        other = monetary[~monetary["Receipt Type"].eq("Monetary")].amount.sum()
        total = monetary.amount.sum() if accepted else np.nan
        status = (
            "unknown_candidate_transaction_identity_unresolved" if not accepted
            else "observed_zero" if total == 0
            else "observed_positive"
        )
        rows.append({
            "state": "OK", "cycle": int(target.cycle), "chamber": target.chamber,
            "district": int(target.district), "party": target.party,
            "candidate": target.candidate,
            "provider_candidate": "|".join(provider_names),
            "committee_id": "|".join(sorted(accepted_identities)),
            "total_fundraising": total,
            "cash_contributions": cash, "other_receipts": other,
            "in_kind_contributions": selected[
                selected["Receipt Type"].isin(in_kind_types)
            ].amount.sum(min_count=1),
            "loans_received": selected[
                selected["Receipt Type"].isin(loan_types)
            ].amount.sum(min_count=1),
            "expenditures": selected_exp.amount.sum(min_count=1),
            "ending_cash": np.nan, "report_count": np.nan,
            "period_start": start, "period_end": end,
            "finance_observation_status": status,
            "aggregation_status": (
                "official_bulk_transactions_deduplicated_by_provider_id;"
                "identity=union_of_unique_reciprocal_aliases_and_unambiguous_best_match"
            ),
            "source_name": "Oklahoma Ethics Commission Guardian bulk extracts",
            "source_measure": "monetary_and_other_receipts_excluding_loans_in_kind_and_forgiveness",
            "source_path": ";".join(sorted(set(
                selected.source_path.unique()
            ) | set(selected_exp.source_path.unique()))),
        })
    return pd.DataFrame(rows)


def _louisiana_transactions(
    kind: str, date_column: str, amount_column: str, extra_columns: list[str],
) -> pd.DataFrame:
    """Read the immutable Louisiana bulk blocks needed by modeled cycles."""
    raw_root = ROOT / "data/raw/finance/southern/LA"
    frames = []
    for block in ("2016_to_2019", "2020_to_2023", "2024_to_2027"):
        path = raw_root / f"{kind}_{block}.csv"
        if not path.exists():
            continue
        columns = [
            "FilerNumber", "FilerLastName", "FilerFirstName",
            date_column, amount_column, *extra_columns,
        ]
        frame = pd.read_csv(
            path, dtype={"FilerNumber": str}, usecols=columns, low_memory=False,
        )
        frame = frame[
            frame.FilerNumber.notna()
            & frame.FilerFirstName.notna()
            & frame.FilerLastName.notna()
        ].copy()
        frame["date"] = pd.to_datetime(
            frame[date_column], format="mixed", errors="coerce"
        )
        frame["amount"] = pd.to_numeric(frame[amount_column], errors="coerce")
        frame["provider_candidate"] = (
            frame.FilerFirstName.str.strip() + " " + frame.FilerLastName.str.strip()
        )
        frame["source_path"] = path.relative_to(ROOT).as_posix()
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def louisiana_rows() -> pd.DataFrame:
    """Aggregate complete Louisiana bulk transactions for modeled cycles.

    The provider exposes no stable transaction identifier in these extracts,
    so legitimate same-day, same-amount transactions are retained rather than
    guessed to be duplicates. Loans and in-kind contributions remain outside
    the canonical monetary-receipt total.
    """
    contributions = _louisiana_transactions(
        "Contributions", "ContributionDate", "ContributionAmt",
        ["ContributionType"],
    )
    expenditures = _louisiana_transactions(
        "Expenditures", "ExpenditureDate", "ExpenditureAmt", [],
    )
    loans = _louisiana_transactions("Loans", "LoanDate", "LoanAmt", [])
    if contributions.empty:
        return pd.DataFrame()
    universe = candidate_universe("LA")
    adjudications = approved_finance_identity_adjudications("LA")
    rows = []
    for target in universe.itertuples(index=False):
        start = pd.Timestamp(int(target.cycle) - 1, 1, 1)
        end = pd.Timestamp(int(target.cycle), 12, 31)
        contribution_window = contributions[contributions.date.between(start, end)]
        expenditure_window = expenditures[expenditures.date.between(start, end)]
        loan_window = loans[loans.date.between(start, end)]
        identities = pd.concat([
            frame[["FilerNumber", "provider_candidate"]]
            for frame in (contribution_window, expenditure_window, loan_window)
            if not frame.empty
        ], ignore_index=True).drop_duplicates()
        # Resolve one representative spelling per provider filer ID before
        # applying the same conservative score-and-margin rule used elsewhere.
        identities = identities.sort_values(
            ["FilerNumber", "provider_candidate"]
        ).drop_duplicates("FilerNumber")
        scored = sorted([
            (
                candidate_score(target.candidate, row.provider_candidate),
                str(row.FilerNumber), row.provider_candidate,
            )
            for row in identities.itertuples(index=False)
        ], reverse=True)
        best = scored[0] if scored else (0.0, "", "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        accepted = bool(best[1] and best[0] >= 92.0 and best[0] - second >= 5.0)
        applicable = adjudications[
            adjudications.cycle_start.le(int(target.cycle))
            & adjudications.cycle_end.ge(int(target.cycle))
            & adjudications.chamber.eq(target.chamber)
            & adjudications.district.eq(int(target.district))
            & adjudications.party.eq(target.party)
        ]
        if len(applicable) > 1:
            raise ValueError(
                "Overlapping approved Louisiana finance identities for "
                f"{target.cycle} {target.chamber} {target.district} {target.party}"
            )
        adjudication_id = ""
        if len(applicable) == 1:
            decision = applicable.iloc[0]
            provider_id = str(decision.provider_identity)
            provider = identities[identities.FilerNumber.astype(str).eq(provider_id)]
            if provider.empty:
                raise ValueError(
                    f"Approved Louisiana provider identity is absent: {provider_id}"
                )
            if candidate_score(target.candidate, decision.candidate_name) < 75.0:
                raise ValueError(
                    "Approved Louisiana identity candidate drift for "
                    f"{decision.adjudication_id}"
                )
            best = (100.0, provider_id, provider.iloc[0].provider_candidate)
            accepted = True
            adjudication_id = str(decision.adjudication_id)
        selected_contrib = (
            contribution_window[contribution_window.FilerNumber.eq(best[1])]
            if accepted else contributions.iloc[0:0]
        )
        selected_exp = (
            expenditure_window[expenditure_window.FilerNumber.eq(best[1])]
            if accepted else expenditures.iloc[0:0]
        )
        selected_loans = (
            loan_window[loan_window.FilerNumber.eq(best[1])]
            if accepted else loans.iloc[0:0]
        )
        monetary = selected_contrib[
            selected_contrib.ContributionType.isin(["CONTRIB", "ANON", "OTHER"])
        ]
        # The official bulk blocks are exhaustive for this filer/window. Once
        # identity is resolved, no monetary rows is a reported category zero,
        # including an in-kind-only, loan-only, or expenditure-only filer.
        total = monetary.amount.sum() if accepted else np.nan
        if monetary.empty:
            cash = other = 0.0 if accepted else np.nan
        else:
            cash = selected_contrib[
                selected_contrib.ContributionType.isin(["CONTRIB", "ANON"])
            ].amount.sum()
            other = selected_contrib[
                selected_contrib.ContributionType.eq("OTHER")
            ].amount.sum()
        status = (
            "unknown_candidate_transaction_identity_unresolved" if not accepted
            else "observed_zero" if total == 0
            else "observed_positive"
        )
        selected_sources = pd.concat(
            [selected_contrib, selected_exp, selected_loans], ignore_index=True,
            sort=False,
        )
        rows.append({
            "state": "LA", "cycle": int(target.cycle),
            "chamber": target.chamber, "district": int(target.district),
            "party": target.party, "candidate": target.candidate,
            "provider_candidate": best[2], "committee_id": best[1],
            "total_fundraising": total,
            "cash_contributions": cash, "other_receipts": other,
            "in_kind_contributions": selected_contrib[
                selected_contrib.ContributionType.eq("IN-KIND")
            ].amount.sum(min_count=1),
            "loans_received": selected_loans.amount.sum(min_count=1),
            "expenditures": selected_exp.amount.sum(min_count=1),
            "ending_cash": np.nan, "report_count": np.nan,
            "period_start": start, "period_end": end,
            "finance_observation_status": status,
            "aggregation_status": (
                "official_bulk_transactions_by_provider_filer_id"
                + (
                    ";identity=approved_identity_adjudication:" + adjudication_id
                    if adjudication_id else ";identity=automatic_candidate_match"
                )
            ),
            "source_name": "Louisiana Board of Ethics bulk transaction extracts",
            "source_measure": "contributions_plus_anonymous_and_other_receipts_excluding_in_kind_and_loans",
            "source_path": ";".join(sorted(selected_sources.source_path.unique())),
        })
    return pd.DataFrame(rows)


def _georgia_legacy_contributions(years: set[int]) -> pd.DataFrame:
    frames = []
    root = ROOT / "data/raw/finance/southern/GA/contributions"
    for year in sorted(years):
        path = root / f"{year}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(
            path, dtype={"FilerID": str}, low_memory=False,
            usecols=[
                "FilerID", "Type", "Date", "Cash_Amount", "In_Kind_Amount",
                "Candidate_FirstName", "Candidate_MiddleName",
                "Candidate_LastName", "Candidate_Suffix", "Committee_Name",
            ],
        )
        frame = frame[
            frame.FilerID.notna() & frame.Candidate_LastName.notna()
        ].copy()
        frame["provider_candidate"] = frame[[
            "Candidate_FirstName", "Candidate_MiddleName",
            "Candidate_LastName", "Candidate_Suffix",
        ]].fillna("").agg(" ".join, axis=1).str.replace(r"\s+", " ", regex=True).str.strip()
        frame["provider_id"] = "legacy:" + frame.FilerID.str.strip()
        frame["provider_committee"] = frame.Committee_Name.fillna("").str.strip()
        frame["date"] = pd.to_datetime(frame.Date, format="mixed", errors="coerce")
        frame["cash"] = pd.to_numeric(frame.Cash_Amount, errors="coerce")
        frame["in_kind"] = pd.to_numeric(frame.In_Kind_Amount, errors="coerce")
        frame["receipt_type"] = frame.Type
        frame["source_path"] = path.relative_to(ROOT).as_posix()
        frames.append(frame[[
            "provider_id", "provider_candidate", "provider_committee", "date",
            "cash", "in_kind", "receipt_type", "source_path",
        ]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _georgia_recordsearch_contributions(years: set[int]) -> pd.DataFrame:
    frames = []
    for year in sorted(years):
        collection = "recordsearch_v2" if year == 2024 else "recordsearch"
        root = ROOT / f"data/raw/finance/southern/GA/{collection}/contributions"
        for path in sorted((root / str(year)).rglob("*.csv")):
            frame = pd.read_csv(
                path, skiprows=1, dtype=str, low_memory=False,
                usecols=[
                    "Filing Entity Id", "Candidate Last Name", "Candidate First Name",
                    "Candidate Middle Name", "Campaign Committee", "Transaction Date",
                    "Transaction Amount", "Contribution Type", "Filer Type",
                ],
            )
            frame = frame[
                frame["Filing Entity Id"].notna()
                & frame["Candidate Last Name"].notna()
                & frame["Filer Type"].eq("Candidate")
            ].copy()
            if frame.empty:
                continue
            frame["provider_candidate"] = frame[[
                "Candidate First Name", "Candidate Middle Name", "Candidate Last Name",
            ]].fillna("").agg(" ".join, axis=1).str.replace(r"\s+", " ", regex=True).str.strip()
            frame["provider_id"] = "recordsearch:" + frame["Filing Entity Id"].str.strip()
            frame["provider_committee"] = frame["Campaign Committee"].fillna("").str.strip()
            frame["date"] = pd.to_datetime(frame["Transaction Date"], errors="coerce")
            amount = frame["Transaction Amount"].str.replace("$", "", regex=False).str.replace(
                ",", "", regex=False
            )
            frame["amount"] = pd.to_numeric(amount, errors="coerce")
            frame["cash"] = np.where(
                frame["Contribution Type"].isin(["Monetary Itemized", "Monetary Non-Itemized"]),
                frame.amount, 0.0,
            )
            frame["in_kind"] = np.where(
                frame["Contribution Type"].eq("In-Kind"), frame.amount, 0.0
            )
            frame["receipt_type"] = frame["Contribution Type"]
            frame["source_path"] = path.relative_to(ROOT).as_posix()
            frames.append(frame[[
                "provider_id", "provider_candidate", "provider_committee", "date",
                "cash", "in_kind", "receipt_type", "amount", "source_path",
            ]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _georgia_recordsearch_registrations() -> list[dict]:
    registrations = []
    root = SUMMARY_RAW / "GA" / "recordsearch_candidate_search_v1"
    for path in sorted(root.glob("*.json")):
        for item in parse_ga_recordsearch_candidate_response(path.read_bytes()):
            registrations.append({
                **item, "_source_path": path.relative_to(ROOT).as_posix(),
            })
    return registrations


def _georgia_legacy_registrations() -> list[dict]:
    registrations = []
    root = SUMMARY_RAW / "GA" / "legacy_candidate_details_v1"
    for path in sorted(root.glob("*.html")):
        for item in parse_ga_legacy_candidate_detail(path.read_bytes()):
            registrations.append({
                **item, "source_path": path.relative_to(ROOT).as_posix(),
            })
    return registrations


def _georgia_expected_contribution_partitions(cycle: int) -> list[Path]:
    """Return every authoritative raw contribution partition for a cycle."""
    paths: list[Path] = []
    for year in (cycle - 1, cycle):
        if year <= 2021:
            paths.append(
                ROOT / f"data/raw/finance/southern/GA/contributions/{year}.csv"
            )
        elif year == 2022:
            root = ROOT / "data/raw/finance/southern/GA/recordsearch/contributions/2022"
            paths.append(root / "01.csv")
            paths.extend(
                root / f"{day.month:02d}" / f"{day.day:02d}.csv"
                for day in pd.date_range("2022-02-01", "2022-12-31")
            )
        elif year == 2023:
            root = ROOT / "data/raw/finance/southern/GA/recordsearch/contributions/2023"
            paths.extend(
                root / f"{day.month:02d}" / f"{day.day:02d}.csv"
                for day in pd.date_range("2023-01-01", "2023-12-31")
            )
        elif year == 2024:
            root = ROOT / "data/raw/finance/southern/GA/recordsearch_v2/contributions/2024"
            paths.extend(root / f"{month:02d}.csv" for month in range(1, 13))
        else:
            raise ValueError(f"Unsupported Georgia finance year: {year}")
    return paths


def _georgia_contribution_window_complete(cycle: int) -> bool:
    """Require raw presence and manifest registration for every partition."""
    expected = _georgia_expected_contribution_partitions(cycle)
    if not expected or not all(path.is_file() for path in expected):
        return False
    if not TRANSACTION_MANIFEST.exists():
        return False
    manifest = pd.read_csv(
        TRANSACTION_MANIFEST,
        usecols=["state_code", "data_kind", "ingest_status", "local_path"],
        low_memory=False,
    )
    registered = set(
        manifest.loc[
            manifest.state_code.eq("GA")
            & manifest.data_kind.eq("contributions")
            & manifest.ingest_status.eq("acquired_unparsed"),
            "local_path",
        ].dropna().astype(str)
    )
    return all(path.relative_to(ROOT).as_posix() in registered for path in expected)


def georgia_rows() -> pd.DataFrame:
    """Aggregate non-overlapping Georgia legacy and Record Search exports."""
    legacy = _georgia_legacy_contributions({2015, 2016, 2017, 2018, 2019, 2020, 2021})
    modern = _georgia_recordsearch_contributions({2022, 2023, 2024})
    transactions = pd.concat([legacy, modern], ignore_index=True, sort=False)
    if transactions.empty:
        return pd.DataFrame()
    monetary_modern = {
        "Monetary Itemized", "Monetary Non-Itemized", "Interest Earned", "Anonymous",
        "Investment - Cash Dividends", "Investment - Sold", "Intra-Candidate Transfer",
        "Investment - Interest Paid Out",
    }
    transactions["monetary"] = np.where(
        transactions.receipt_type.eq("Monetary"), transactions.cash,
        np.where(transactions.receipt_type.isin(monetary_modern), transactions.get("amount"), np.nan),
    )
    transactions["other"] = np.where(
        transactions.receipt_type.isin(monetary_modern - {"Monetary Itemized", "Monetary Non-Itemized"}),
        transactions.get("amount"), 0.0,
    )
    universe = candidate_universe("GA", prefer_final_names=True)
    registrations = _georgia_recordsearch_registrations()
    legacy_registrations = _georgia_legacy_registrations()
    refreshed_2024 = any(
        (ROOT / "data/raw/finance/southern/GA/recordsearch_v2/contributions/2024").rglob("*.csv")
    )
    rows = []
    for cycle, cycle_targets in universe.groupby("cycle", sort=True):
        cycle = int(cycle)
        start, end = pd.Timestamp(cycle - 1, 1, 1), pd.Timestamp(cycle, 12, 31)
        complete_contribution_window = _georgia_contribution_window_complete(cycle)
        target_frame = cycle_targets.reset_index(drop=True)
        window = transactions[transactions.date.between(start, end)].copy()
        candidate_aliases = window[["provider_id", "provider_candidate"]].rename(
            columns={"provider_candidate": "identity_name"}
        )
        committee_aliases = window[["provider_id", "provider_committee"]].rename(
            columns={"provider_committee": "identity_name"}
        )
        identities = pd.concat(
            [candidate_aliases, committee_aliases], ignore_index=True
        )
        identities = identities[
            identities.identity_name.notna()
            & identities.identity_name.astype(str).str.strip().ne("")
        ].drop_duplicates()
        assignments, evidence = reciprocal_identity_assignments(
            target_frame, identities,
            identity_column="provider_id", name_column="identity_name",
            committee_names=True,
        )
        registry_matches = match_ga_recordsearch_registrations(
            target_frame, registrations
        )
        registry_evidence: dict[int, dict[str, object]] = {}
        for target_index, match in registry_matches.iterrows():
            if match.match_status != "accepted_automatic":
                continue
            # Exact official cycle/office/district/party registration evidence
            # supersedes a weaker Record Search alias, while legacy IDs from
            # the prior calendar year remain eligible for the cycle sum.
            assignments[target_index] = sorted(set(
                [
                    provider_id for provider_id in assignments[target_index]
                    if not provider_id.startswith("recordsearch:")
                ]
                + [str(match.provider_identity)]
            ))
            registry_evidence[target_index] = {
                "provider_candidate": str(match.provider_candidate),
                "source_path": str(match.source_path),
                "source_reported_total": pd.to_numeric(
                    match.source_reported_total, errors="coerce"
                ),
                "registration_cycle": int(match.registration_cycle),
                "match_scope": str(match.match_scope),
            }
        legacy_matches = match_ga_legacy_registrations(
            target_frame, legacy_registrations
        )
        legacy_evidence: dict[int, dict[str, object]] = {}
        for target_index, match in legacy_matches.iterrows():
            if match.match_status != "accepted_automatic":
                continue
            legacy_ids = [
                value for value in str(match.provider_identity).split("|") if value
            ]
            assignments[target_index] = sorted(set(
                assignments[target_index] + legacy_ids
            ))
            legacy_evidence[target_index] = {
                "provider_candidate": str(match.provider_candidate),
                "source_paths": [
                    value for value in str(match.source_path).split(";") if value
                ],
                "match_scope": str(match.match_scope),
            }
        for target_index, target in enumerate(target_frame.itertuples(index=False)):
            if cycle == 2024 and not refreshed_2024:
                missing_reason = "provider_returned_only_january_2024_transactions"
                rows.append({
                    "state": "GA", "cycle": cycle, "chamber": target.chamber,
                    "district": int(target.district), "party": target.party,
                    "candidate": target.candidate, "provider_candidate": "",
                    "committee_id": "", "total_fundraising": np.nan,
                    "cash_contributions": np.nan, "other_receipts": np.nan,
                    "in_kind_contributions": np.nan, "loans_received": np.nan,
                    "expenditures": np.nan, "ending_cash": np.nan,
                    "report_count": np.nan, "period_start": start, "period_end": end,
                    "finance_observation_status": f"unknown_incomplete_cycle_window_{missing_reason}",
                    "aggregation_status": "not_aggregated_incomplete_or_anomalous_two_year_window",
                    "source_name": "Georgia campaign-finance transaction exports",
                    "source_measure": "unknown", "source_path": "",
                })
                continue
            matched_ids = sorted(assignments[target_index])
            match_evidence = evidence[target_index]
            official_registration = registry_evidence.get(target_index, {})
            legacy_registration = legacy_evidence.get(target_index, {})
            selected = window[window.provider_id.isin(matched_ids)]
            monetary = selected[selected.monetary.notna()]
            total = monetary.monetary.sum(min_count=1)
            official_total = official_registration.get(
                "source_reported_total", np.nan
            )
            explicit_registration_zero = bool(
                pd.isna(total) and pd.notna(official_total)
                and float(official_total) == 0.0
            )
            explicit_complete_export_zero = bool(
                pd.isna(total) and matched_ids and complete_contribution_window
            )
            if explicit_registration_zero or explicit_complete_export_zero:
                total = 0.0
            status = (
                "unknown_candidate_transaction_identity_unresolved" if not matched_ids
                else "unknown_no_monetary_receipt_records" if pd.isna(total)
                else "observed_zero" if total == 0
                else "observed_positive"
            )
            rows.append({
                "state": "GA", "cycle": cycle, "chamber": target.chamber,
                "district": int(target.district), "party": target.party,
                "candidate": target.candidate,
                "provider_candidate": "|".join(sorted(set(
                    selected.provider_candidate.dropna().astype(str).tolist()
                    + ([official_registration["provider_candidate"]]
                       if official_registration.get("provider_candidate") else [])
                    + ([legacy_registration["provider_candidate"]]
                       if legacy_registration.get("provider_candidate") else [])
                ))),
                "committee_id": "|".join(matched_ids),
                "total_fundraising": total,
                "cash_contributions": (
                    0.0 if explicit_registration_zero or explicit_complete_export_zero
                    else monetary.cash.sum(min_count=1)
                ),
                "other_receipts": (
                    0.0 if explicit_registration_zero or explicit_complete_export_zero
                    else monetary.other.sum(min_count=1)
                ),
                "in_kind_contributions": selected.in_kind.sum(min_count=1),
                "loans_received": selected.loc[
                    selected.receipt_type.eq("Loans Received"), "amount"
                ].sum(min_count=1),
                "expenditures": np.nan, "ending_cash": np.nan, "report_count": np.nan,
                "period_start": start, "period_end": end,
                "finance_observation_status": status,
                "aggregation_status": (
                    "reciprocal_provider_identity_then_legacy_through_2021_plus_"
                    f"recordsearch_from_2022;name_score={match_evidence['score']:.2f};"
                    f"margin={match_evidence['margin']:.2f}"
                    + (
                        ";identity=recordsearch_registration_office_district_party;"
                        f"registration_cycle={official_registration['registration_cycle']};"
                        f"identity_scope={official_registration['match_scope']}"
                        if official_registration else ""
                    )
                    + (
                        ";identity=legacy_official_registration;"
                        f"identity_scope={legacy_registration['match_scope']}"
                        if legacy_registration else ""
                    )
                ),
                "source_name": "Georgia Government Transparency and Campaign Finance Commission exports",
                "source_measure": (
                    "recordsearch_candidate_grid_explicit_zero"
                    if explicit_registration_zero else
                    "complete_official_contribution_export_absence"
                    if explicit_complete_export_zero else
                    "monetary_contributions_plus_compatible_other_receipts_excluding_loans_and_in_kind"
                ),
                "source_path": ";".join(sorted(set(
                    selected.source_path.dropna().astype(str).tolist()
                    + ([official_registration["source_path"]]
                       if official_registration.get("source_path") else [])
                    + list(legacy_registration.get("source_paths", []))
                ))),
                "source_reported_total": official_total,
            })
    return pd.DataFrame(rows)


NC_RECEIPT_CASH_TYPES = {
    "Individual", "General", "Non-Party Comm", "Party Comm", "Nonprofit",
}
NC_RECEIPT_OTHER_TYPES = {
    "Outside Source", "Interest",
}
NC_EXPENDITURE_TYPES = {
    "Operating Exp", "Cont to Other Comm", "Independent Exp",
    "Coord Party Exp", "Debt Payment", "Loan Repayment",
}


def _north_carolina_cycle_chamber(
    targets: pd.DataFrame, cycle: int, chamber: str,
) -> list[dict[str, object]]:
    """Match candidate committees, then aggregate an exact two-calendar-year window."""
    targeted_indexes = [
        SUMMARY_RAW / "NC" / "targeted_transaction_batches_v3.jsonl",
        SUMMARY_RAW / "NC" / "targeted_transaction_batches_v2.jsonl",
        SUMMARY_RAW / "NC" / "targeted_transaction_batches_v1.jsonl",
    ]
    targeted_index = next(
        (path for path in targeted_indexes if path.exists()), targeted_indexes[0]
    )
    targeted_batches = []
    if targeted_index.exists():
        targeted_batches = [
            item for item in (
                json.loads(line) for line in targeted_index.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ) if int(item["cycle"]) == cycle and (ROOT / item["local_path"]).exists()
        ]
    targeted_paths_by_committee: dict[str, set[str]] = defaultdict(set)
    for item in targeted_batches:
        for committee_id in item.get("committee_ids", []):
            targeted_paths_by_committee[str(committee_id)].add(str(item["local_path"]))
    office_files = (
        ["NCSN.csv", "NSHS.csv"] if chamber == "both"
        else ["NCSN.csv" if chamber == "senate" else "NSHS.csv"]
    )
    versioned_root = ROOT / "data/raw/finance/southern/NC/transactions_v2"
    legacy_root = ROOT / "data/raw/finance/southern/NC/transactions"
    root = versioned_root if all(
        (versioned_root / str(year) / office_file).exists()
        for year in (cycle - 1, cycle)
        for office_file in office_files
    ) else legacy_root
    full_office_paths = [
        root / str(year) / office_file
        for year in (cycle - 1, cycle)
        for office_file in office_files
    ]
    targeted_paths = [ROOT / item["local_path"] for item in targeted_batches]
    # Exact-query batches remain the only source that can prove an explicit
    # zero. The complete official House/Senate exports are also valid positive
    # evidence and contain historical committees that the current directory
    # search no longer returns. Search both for identities and transactions;
    # the per-committee/year selection below prevents duplicated portal rows.
    paths = list(dict.fromkeys(targeted_paths + full_office_paths))
    identities = []
    identity_paths_by_committee: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        if not path.exists():
            continue
        for chunk in pd.read_csv(
            path, usecols=["Committee Name", "Committee SBoE ID"],
            dtype=str, chunksize=250_000, low_memory=False,
        ):
            selected_identities = chunk.dropna(
                subset=["Committee SBoE ID"]
            ).drop_duplicates()
            identities.append(selected_identities)
            for committee_id in selected_identities["Committee SBoE ID"].astype(str):
                identity_paths_by_committee[committee_id].add(
                    path.relative_to(ROOT).as_posix()
                )
    identity = (
        pd.concat(identities, ignore_index=True).drop_duplicates()
        if identities else pd.DataFrame(columns=["Committee Name", "Committee SBoE ID"])
    )
    target_frame = targets.reset_index(drop=True)
    assignments, evidence = reciprocal_identity_assignments(
        target_frame, identity,
        identity_column="Committee SBoE ID", name_column="Committee Name",
        committee_names=True,
    )
    identity_adjudications = apply_north_carolina_identity_adjudications(
        target_frame, identity, assignments, evidence, cycle
    )
    accepted_ids = {
        committee_id for committee_ids in assignments.values()
        for committee_id in committee_ids
    }
    path_aggregates: dict[tuple[str, str], dict[str, float]] = {}
    for path in paths:
        if not path.exists() or not accepted_ids:
            continue
        for chunk in pd.read_csv(
            path,
            usecols=["Committee SBoE ID", "Transction Type", "Amount"],
            dtype={"Committee SBoE ID": str, "Transction Type": str},
            chunksize=250_000, low_memory=False,
        ):
            chunk = chunk[chunk["Committee SBoE ID"].isin(accepted_ids)].copy()
            if chunk.empty:
                continue
            chunk["Amount"] = pd.to_numeric(chunk.Amount, errors="coerce")
            for committee_id, group in chunk.groupby("Committee SBoE ID"):
                bucket = path_aggregates.setdefault((str(path), str(committee_id)), {
                    "cash": 0.0, "other": 0.0, "in_kind": 0.0,
                    "loans": 0.0, "expenditures": 0.0, "monetary_count": 0.0,
                    "row_count": 0.0,
                })
                receipt_type = group["Transction Type"]
                bucket["cash"] += group.loc[
                    receipt_type.isin(NC_RECEIPT_CASH_TYPES), "Amount"
                ].sum()
                bucket["other"] += group.loc[
                    receipt_type.isin(NC_RECEIPT_OTHER_TYPES), "Amount"
                ].sum()
                bucket["in_kind"] += group.loc[
                    receipt_type.eq("Nonmonetary Gift"), "Amount"
                ].sum()
                bucket["loans"] += group.loc[
                    receipt_type.eq("Loan"), "Amount"
                ].sum()
                bucket["expenditures"] += group.loc[
                    receipt_type.isin(NC_EXPENDITURE_TYPES), "Amount"
                ].sum()
                bucket["monetary_count"] += float(
                    receipt_type.isin(NC_RECEIPT_CASH_TYPES | NC_RECEIPT_OTHER_TYPES).sum()
                )
                bucket["row_count"] += float(len(group))

    # A very small number of committee IDs appear in both office exports. The
    # portal's current-office classification can duplicate their transactions;
    # retain the more complete file for each committee/calendar year.
    selected_buckets: dict[tuple[int, str], dict[str, float]] = {}
    for (source_path, committee_id), bucket in path_aggregates.items():
        source_year = int(Path(source_path).parent.name)
        key = (source_year, committee_id)
        if key not in selected_buckets or bucket["row_count"] > selected_buckets[key]["row_count"]:
            selected_buckets[key] = bucket
    aggregates: dict[str, dict[str, float]] = {}
    for (_, committee_id), bucket in selected_buckets.items():
        combined = aggregates.setdefault(committee_id, {
            "cash": 0.0, "other": 0.0, "in_kind": 0.0,
            "loans": 0.0, "expenditures": 0.0, "monetary_count": 0.0,
        })
        for field in combined:
            combined[field] += bucket[field]

    rows = []
    start, end = pd.Timestamp(cycle - 1, 1, 1), pd.Timestamp(cycle, 12, 31)
    source_path = ";".join(path.relative_to(ROOT).as_posix() for path in paths if path.exists())
    registry_path = ROOT / "data/processed/source_audits/southern_finance_summary_candidate_matches.csv"
    registry_by_key = {}
    if targeted_batches and registry_path.exists():
        registry = pd.read_csv(registry_path, dtype=str)
        registry["cycle"] = pd.to_numeric(registry.cycle, errors="coerce")
        registry["district"] = pd.to_numeric(registry.district, errors="coerce")
        registry = registry[
            registry.state.eq("NC")
            & registry.cycle.eq(cycle)
            & registry.match_status.eq("accepted_automatic")
        ]
        registry_by_key = {
            (row.chamber, int(row.district), row.party): row
            for row in registry.itertuples(index=False)
        }
    for target_index, target in enumerate(target_frame.itertuples(index=False)):
        committee_ids = sorted(assignments[target_index])
        match_evidence = evidence[target_index]
        registry_match = registry_by_key.get(
            (target.chamber, int(target.district), target.party)
        )
        exhaustive_targeted_query = registry_match is not None
        registry_committee_ids = (
            [
                value for value in str(registry_match.provider_identity).split("|")
                if value and value.lower() != "nan"
            ]
            if registry_match is not None and pd.notna(registry_match.provider_identity)
            else []
        )
        target_source_paths = sorted({
            path
            for committee_id in set(committee_ids) | set(registry_committee_ids)
            for path in (
                targeted_paths_by_committee.get(committee_id, set())
                | identity_paths_by_committee.get(committee_id, set())
            )
        })
        target_source_path = ";".join(target_source_paths) if target_source_paths else source_path
        matched_values = [aggregates[key] for key in committee_ids if key in aggregates]
        values = {
            field: sum(item[field] for item in matched_values)
            for field in ("cash", "other", "in_kind", "loans", "expenditures", "monetary_count")
        } if matched_values else None
        observed = bool(values and values["monetary_count"] > 0)
        exact_zero = bool(exhaustive_targeted_query and not observed)
        total = (
            values["cash"] + values["other"] if observed
            else 0.0 if exact_zero else np.nan
        )
        status = (
            "observed_zero" if exact_zero
            else "unknown_candidate_committee_identity_unresolved" if not committee_ids
            else "unknown_no_monetary_receipt_records" if not observed
            else "observed_zero" if total == 0 else "observed_positive"
        )
        provider_candidate = "|".join(sorted(set(match_evidence["provider_names"])))
        if (
            not provider_candidate
            and registry_match is not None
            and pd.notna(registry_match.provider_candidate)
        ):
            provider_candidate = str(registry_match.provider_candidate)
        matched_committee_id = "|".join(committee_ids)
        if not matched_committee_id and registry_committee_ids:
            matched_committee_id = "|".join(
                f"org_group:{committee_id}" for committee_id in registry_committee_ids
            )
        rows.append({
            "state": "NC", "cycle": cycle, "chamber": target.chamber,
            "district": int(target.district), "party": target.party,
            "candidate": target.candidate,
            "provider_candidate": provider_candidate,
            "committee_id": matched_committee_id,
            "total_fundraising": total,
            "cash_contributions": values["cash"] if observed else 0.0 if exact_zero else np.nan,
            "other_receipts": values["other"] if observed else 0.0 if exact_zero else np.nan,
            "in_kind_contributions": values["in_kind"] if values else 0.0 if exact_zero else np.nan,
            "loans_received": values["loans"] if values else 0.0 if exact_zero else np.nan,
            "expenditures": values["expenditures"] if values else 0.0 if exact_zero else np.nan,
            "ending_cash": np.nan, "report_count": np.nan,
            "period_start": start, "period_end": end,
            "finance_observation_status": status,
            "aggregation_status": (
                "official_exact_committee_cycle_query_then_reciprocal_candidate_identity;"
                f"name_score={match_evidence['score']:.2f};"
                f"margin={match_evidence['margin']:.2f}"
                + (
                    ";identity=approved_identity_adjudication:"
                    + identity_adjudications[target_index]
                    if target_index in identity_adjudications else ""
                )
            ),
            "source_name": "North Carolina State Board of Elections transaction exports",
            "source_measure": "cash_contributions_plus_interest_and_outside_income_excluding_refunds_loans_and_nonmonetary_gifts",
            "source_path": target_source_path,
        })
    return rows


def north_carolina_rows() -> pd.DataFrame:
    universe = candidate_universe("NC", prefer_final_names=True)
    rows: list[dict[str, object]] = []
    for cycle in sorted(universe.cycle.unique()):
        targets = universe[universe.cycle == cycle]
        versioned_root = ROOT / "data/raw/finance/southern/NC/transactions_v2"
        legacy_root = ROOT / "data/raw/finance/southern/NC/transactions"
        source_root = versioned_root if all(
            (versioned_root / str(year) / office_file).exists()
            for year in (int(cycle) - 1, int(cycle))
            for office_file in ("NCSN.csv", "NSHS.csv")
        ) else legacy_root
        source_files = [
            source_root / str(year) / office_file
            for year in (int(cycle) - 1, int(cycle))
            for office_file in ("NCSN.csv", "NSHS.csv")
        ]
        if not all(path.exists() for path in source_files):
            for target in targets.itertuples(index=False):
                rows.append({
                    "state": "NC", "cycle": int(cycle), "chamber": target.chamber,
                    "district": int(target.district), "party": target.party,
                    "candidate": target.candidate, "provider_candidate": "",
                    "committee_id": "", "total_fundraising": np.nan,
                    "cash_contributions": np.nan, "other_receipts": np.nan,
                    "in_kind_contributions": np.nan, "loans_received": np.nan,
                    "expenditures": np.nan, "ending_cash": np.nan,
                    "report_count": np.nan,
                    "period_start": pd.Timestamp(int(cycle) - 1, 1, 1),
                    "period_end": pd.Timestamp(int(cycle), 12, 31),
                    "finance_observation_status": "unknown_incomplete_cycle_window_missing_source_year",
                    "aggregation_status": "not_aggregated_incomplete_two_year_window",
                    "source_name": "North Carolina State Board of Elections transaction exports",
                    "source_measure": "unknown", "source_path": "",
                })
        else:
            rows.extend(_north_carolina_cycle_chamber(targets, int(cycle), "both"))
    return pd.DataFrame(rows)


def texas_period_rows() -> pd.DataFrame:
    archive = TX_ROOT / "data/raw/tx_ethics/tec_cf_csv/TEC_CF_CSV.zip"
    crosswalk_path = TX_ROOT / "data/processed/features/tec_candidate_filer_crosswalk.csv"
    if not archive.exists() or not crosswalk_path.exists():
        return pd.DataFrame()
    crosswalk = pd.read_csv(crosswalk_path, dtype=str)
    crosswalk["cycle"] = pd.to_numeric(crosswalk.cycle, errors="coerce")
    crosswalk = crosswalk[crosswalk.cycle.between(2016, 2024)].copy()
    crosswalk = apply_texas_identity_adjudications(crosswalk)
    filer_ids = set(crosswalk.filer_id.dropna().astype(str))
    columns = [
        "reportInfoIdent", "receivedDt", "infoOnlyFlag", "filerIdent",
        "filerTypeCd", "filerName", "reportTypeCd1", "sourceCategoryCd",
        "dueDt", "filedDt", "periodStartDt", "periodEndDt",
        "unitemizedContribAmount", "totalContribAmount", "totalExpendAmount", "loanBalanceAmount",
        "contribsMaintainedAmount", "noActivityFlag",
    ]
    with zipfile.ZipFile(archive) as zipped:
        covers = pd.read_csv(
            zipped.open("cover.csv"), dtype=str, usecols=columns, low_memory=False
        )
    covers = covers[
        covers.filerIdent.isin(filer_ids)
        & covers.filerTypeCd.eq("COH")
        & ~covers.infoOnlyFlag.fillna("N").eq("Y")
    ].copy()
    for column in [
        "receivedDt", "filedDt", "reportInfoIdent", "periodStartDt", "periodEndDt",
        "totalContribAmount", "totalExpendAmount", "loanBalanceAmount",
        "contribsMaintainedAmount", "unitemizedContribAmount",
    ]:
        covers[column + "_num"] = pd.to_numeric(covers[column], errors="coerce")
    covers = covers.sort_values(
        ["receivedDt_num", "filedDt_num", "reportInfoIdent_num"]
    ).drop_duplicates(
        ["filerIdent", "periodStartDt", "periodEndDt"], keep="last"
    )
    joined = crosswalk.merge(
        covers, left_on="filer_id", right_on="filerIdent", how="left",
        validate="many_to_many",
    )
    joined["state"] = "TX"
    joined["candidate"] = joined.candidate_name
    joined["provider_candidate"] = joined.filerName
    joined["committee_id"] = joined.filer_id
    joined["report_id"] = joined.reportInfoIdent
    joined["report_type"] = joined.reportTypeCd1
    joined["period_start"] = pd.to_datetime(
        joined.periodStartDt, format="%Y%m%d", errors="coerce"
    )
    joined["period_end"] = pd.to_datetime(
        joined.periodEndDt, format="%Y%m%d", errors="coerce"
    )
    joined["monetary_receipts"] = joined.totalContribAmount_num
    explicit_no_activity = joined.noActivityFlag.eq("Y")
    # TEC's official CFS-ReadMe contract defines numeric fields as "Blank When
    # Zero".  A blank totalContribAmount on an otherwise valid report cover is
    # therefore an observed zero, not missing data.  This also covers reports
    # with expenditure activity but no contribution activity.
    blank_when_zero = joined.report_id.notna() & joined.monetary_receipts.isna()
    joined.loc[blank_when_zero, "monetary_receipts"] = 0.0
    window_start = pd.to_datetime((joined.cycle.astype(int) - 1).astype(str) + "-01-01")
    window_end = pd.to_datetime(joined.cycle.astype(int).astype(str) + "-12-31")
    fallback_mask = (
        joined.report_id.notna() & joined.monetary_receipts.isna()
        & joined.period_start.ge(window_start) & joined.period_end.le(window_end)
    )
    joined["contribution_amount_source"] = np.where(
        joined.totalContribAmount_num.notna(), "cover_total",
        np.where(explicit_no_activity, "explicit_no_activity", "cover_blank_when_zero"),
    )
    fallback_ids = set(joined.loc[fallback_mask, "report_id"].astype(str))
    if fallback_ids:
        fallback = texas_report_contribution_fallback(
            archive, covers, fallback_ids
        )
        fallback_map = fallback.set_index("report_id").derived_total_contributions
        resolved_fallback_ids = set(fallback_map[fallback_map.notna()].index)
        attempted_fallback_ids = set(fallback_map.index)
        joined.loc[fallback_mask, "monetary_receipts"] = joined.loc[
            fallback_mask, "report_id"
        ].astype(str).map(fallback_map)
        joined["contribution_amount_source"] = np.where(
            joined.totalContribAmount_num.notna(), "cover_total",
            np.where(explicit_no_activity, "explicit_no_activity",
                     np.where(joined.report_id.astype(str).isin(resolved_fallback_ids),
                              "itemized_plus_cover_unitemized_fallback",
                              np.where(joined.report_id.astype(str).isin(attempted_fallback_ids),
                                       "missing_cover_and_no_detail", "missing"))),
        )
    joined["cash_contributions"] = joined.monetary_receipts
    joined["other_receipts"] = np.nan
    joined["in_kind_contributions"] = np.nan
    joined["loans_received"] = joined.loanBalanceAmount_num
    joined["expenditures"] = joined.totalExpendAmount_num
    joined["ending_cash"] = joined.contribsMaintainedAmount_num
    joined["source_path"] = archive.relative_to(ROOT.parent).as_posix()
    joined["source_url"] = "https://prd.tecprd.ethicsefile.com/public/cf/public/TEC_CF_CSV.zip"
    return joined[[
        *KEY, "candidate", "provider_candidate", "committee_id", "report_id",
        "report_type", "period_start", "period_end", "filedDt",
        "monetary_receipts", "cash_contributions", "other_receipts",
        "in_kind_contributions", "loans_received", "expenditures", "ending_cash",
        "noActivityFlag", "source_path", "source_url", "filer_match_method",
        "contribution_amount_source",
    ]]


def texas_report_contribution_fallback(
    archive: Path, covers: pd.DataFrame, report_ids: set[str],
) -> pd.DataFrame:
    existing = pd.DataFrame()
    if TX_FALLBACK.exists():
        existing = pd.read_csv(TX_FALLBACK, dtype={"report_id": str})
    resolved = set(existing.report_id) if not existing.empty else set()
    needed = set(map(str, report_ids)) - resolved
    if needed:
        detail_sum = {report_id: 0.0 for report_id in needed}
        detail_count = {report_id: 0 for report_id in needed}
        with zipfile.ZipFile(archive) as zipped:
            names = sorted(
                name for name in zipped.namelist()
                if re.fullmatch(r"contribs_\d+\.csv", name)
            )
            for name in names:
                chunks = pd.read_csv(
                    zipped.open(name), dtype=str,
                    usecols=[
                        "reportInfoIdent", "infoOnlyFlag", "contributionAmount"
                    ], chunksize=250_000, low_memory=False,
                )
                for chunk in chunks:
                    selected = chunk[
                        chunk.reportInfoIdent.isin(needed)
                        & ~chunk.infoOnlyFlag.fillna("N").eq("Y")
                    ].copy()
                    if selected.empty:
                        continue
                    selected["amount"] = pd.to_numeric(
                        selected.contributionAmount, errors="coerce"
                    )
                    grouped = selected.groupby("reportInfoIdent").amount.agg(
                        ["sum", "count"]
                    )
                    for report_id, values in grouped.iterrows():
                        detail_sum[str(report_id)] += float(values["sum"])
                        detail_count[str(report_id)] += int(values["count"])
        unitemized = covers.drop_duplicates("reportInfoIdent", keep="last").set_index(
            "reportInfoIdent"
        ).unitemizedContribAmount_num
        rows = []
        for report_id in sorted(needed, key=int):
            unitemized_amount = pd.to_numeric(
                unitemized.get(report_id, np.nan), errors="coerce"
            )
            derived = (
                detail_sum[report_id] + float(unitemized_amount)
                if pd.notna(unitemized_amount) else np.nan
            )
            rows.append({
                "report_id": report_id,
                "detail_itemized_contributions": detail_sum[report_id],
                "detail_record_count": detail_count[report_id],
                "cover_unitemized_contributions": unitemized_amount,
                "derived_total_contributions": derived,
                "source_archive": archive.relative_to(ROOT.parent).as_posix(),
                "source_archive_size": archive.stat().st_size,
                "derivation": "non_superseded_itemized_contribution_sum_plus_cover_unitemized",
            })
        existing = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True, sort=False)
        TX_FALLBACK.parent.mkdir(parents=True, exist_ok=True)
        existing.sort_values("report_id").to_csv(TX_FALLBACK, index=False)
    return existing[existing.report_id.isin(set(map(str, report_ids)))].copy()


def aggregate_texas() -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = texas_period_rows()
    if periods.empty:
        return pd.DataFrame(), periods
    rows = []
    for key, group in periods.groupby(KEY, dropna=False):
        state, cycle, chamber, district, party = key
        start = pd.Timestamp(date(int(cycle) - 1, 1, 1))
        end = pd.Timestamp(date(int(cycle), 12, 31))
        selected = group[group.period_start.ge(start) & group.period_end.le(end)].copy()
        selected = drop_zero_overlapping_periods(selected)
        boundary = group[
            group.period_start.lt(start) & group.period_end.ge(start)
            & group.monetary_receipts.ne(0)
        ]
        overlap = intervals_overlap(selected) if not selected.empty else False
        filer_resolved = group.committee_id.notna().any()
        amounts_complete = bool(
            not selected.empty and selected.monetary_receipts.notna().all()
        )
        status = (
            "unknown_filer_unresolved" if not filer_resolved
            else "unknown_no_report_summary" if selected.empty
            else "review_boundary_spanning_report" if not boundary.empty
            else "review_overlapping_report_periods" if overlap
            else "unknown_missing_report_amount" if not amounts_complete
            else "observed_zero" if selected.monetary_receipts.sum() == 0
            else "observed_positive"
        )
        usable = status in {"observed_zero", "observed_positive"}
        adjudication_methods = sorted(set(
            group.filer_match_method.fillna("").loc[
                group.filer_match_method.fillna("").str.startswith(
                    "approved_identity_adjudication:"
                )
            ].astype(str)
        ))
        identity_method = (
            "|".join(adjudication_methods)
            if adjudication_methods else "tec_candidate_filer_crosswalk"
        )
        last = selected.sort_values("period_end").tail(1)
        rows.append({
            "state": state, "cycle": int(cycle), "chamber": chamber,
            "district": int(district), "party": party,
            "candidate": group.candidate.iloc[0],
            "provider_candidate": group.provider_candidate.dropna().iloc[0]
            if group.provider_candidate.notna().any() else "",
            "committee_id": group.committee_id.dropna().iloc[0]
            if group.committee_id.notna().any() else "",
            "total_fundraising": selected.monetary_receipts.sum() if usable else np.nan,
            "cash_contributions": selected.cash_contributions.sum() if usable else np.nan,
            "other_receipts": np.nan,
            "in_kind_contributions": np.nan,
            "loans_received": selected.loans_received.iloc[-1] if not selected.empty else np.nan,
            "expenditures": selected.expenditures.sum(min_count=1) if not selected.empty else np.nan,
            "ending_cash": last.ending_cash.iloc[0] if not last.empty else np.nan,
            "report_count": len(selected),
            "period_start": selected.period_start.min() if not selected.empty else pd.NaT,
            "period_end": selected.period_end.max() if not selected.empty else pd.NaT,
            "finance_observation_status": status,
            "aggregation_status": (
                "latest_tec_cover_per_exact_period_with_targeted_detail_reconciliation;"
                f"identity={identity_method}"
            ),
            "source_name": "Texas Ethics Commission report-cover summaries",
            "source_measure": "reported_total_contributions",
            "source_path": group.source_path.iloc[0],
        })
    return pd.DataFrame(rows), periods


def align_to_universe(observed: pd.DataFrame) -> pd.DataFrame:
    universe = candidate_universe()
    observed = observed.rename(columns={"candidate": "observed_candidate"})
    out = universe.merge(
        observed, on=KEY, how="left",
        validate="one_to_one",
    )
    # State adapters may resolve a newer authoritative display name on the
    # exact modeled key (notably NC after the final election warehouse load).
    # Preserve it instead of silently restoring a stale panel alias.
    out["candidate"] = out.observed_candidate.fillna(out.candidate)
    out = out.drop(columns="observed_candidate")
    out["finance_observation_status"] = out.finance_observation_status.fillna(
        "unknown_summary_adapter_not_available"
    )
    out["aggregation_status"] = out.aggregation_status.fillna("not_acquired")
    out["source_name"] = out.source_name.fillna("none")
    out["source_measure"] = out.source_measure.fillna("unknown")
    return out


def coverage(candidate: pd.DataFrame) -> pd.DataFrame:
    candidate = candidate.assign(
        observed=candidate.finance_observation_status.isin(
            ["observed_zero", "observed_positive"]
        )
    )
    result = candidate.groupby(["state", "cycle"], as_index=False).agg(
        target_candidates=("candidate", "size"),
        observed_candidates=("observed", "sum"),
        positive_candidates=(
            "finance_observation_status", lambda values: values.eq("observed_positive").sum()
        ),
        zero_candidates=(
            "finance_observation_status", lambda values: values.eq("observed_zero").sum()
        ),
    )
    result["candidate_coverage"] = result.observed_candidates / result.target_candidates
    return result


def main() -> None:
    sc_candidates, sc_periods = aggregate_sc()
    tx_candidates, tx_periods = aggregate_texas()
    ms_candidates, ms_periods = mississippi_rows()
    va_candidates, va_periods = aggregate_virginia()
    tn_candidates, tn_periods = tennessee_rows()
    observed = pd.concat(
        [
            frame for frame in (
                alabama_rows(), arkansas_rows(), florida_rows(),
                georgia_rows(), kentucky_rows(), ms_candidates, missouri_rows(),
                louisiana_rows(), north_carolina_rows(), oklahoma_rows(), sc_candidates,
                tn_candidates, tx_candidates, va_candidates
            ) if not frame.empty
        ],
        ignore_index=True, sort=False,
    )
    observed["source_reported_total"] = observed.source_reported_total.fillna(
        observed.total_fundraising
    )
    if observed.duplicated(KEY).any():
        raise RuntimeError("candidate-cycle finance is not unique on the canonical key")
    candidate = align_to_universe(observed)
    periods = pd.concat(
        [frame.assign(provider=provider) for frame, provider in (
            (sc_periods, "South Carolina State Ethics Commission"),
            (tx_periods, "Texas Ethics Commission"),
            (ms_periods, "Mississippi Secretary of State"),
            (tn_periods, "Tennessee Registry of Election Finance"),
            (va_periods, "Virginia Department of Elections"),
        ) if not frame.empty],
        ignore_index=True, sort=False,
    )
    result_coverage = coverage(candidate)
    review = candidate[~candidate.finance_observation_status.isin(
        ["observed_zero", "observed_positive"]
    )].copy()
    generated_at = pd.Timestamp.now(tz="UTC").floor("s").isoformat()
    code_sha = build_code_sha256()
    run_id = f"southern-finance-summary-{generated_at[:10]}-{code_sha[:12]}"
    for frame in (candidate, periods, result_coverage, review):
        frame["data_run_id"] = run_id
        frame["generated_at_utc"] = generated_at
        frame["build_code_sha256"] = code_sha
        frame["build_config_id"] = "candidate_cycle_calendar_window_v1"

    FINANCE.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(OUTPUT, index=False)
    periods.to_csv(PERIOD_OUTPUT, index=False)
    result_coverage.to_csv(COVERAGE_OUTPUT, index=False)
    review.to_csv(REVIEW_OUTPUT, index=False)
    print(result_coverage.to_string(index=False, formatters={
        "candidate_coverage": "{:.1%}".format
    }))


if __name__ == "__main__":
    main()
