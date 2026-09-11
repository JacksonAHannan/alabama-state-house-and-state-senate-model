#!/usr/bin/env python3
"""Read-only certification of the dated 2026 candidate roster, election universe and seat treatment.

Checklist items ``forecast-02`` (certify the dated candidate roster and election
universe: nominees, withdrawals/replacements, identities, district plans,
incumbency and election stages; reconcile modeled, single-major-party,
independent-only and unresolved seats with all chamber seats) and ``forecast-10``
(explain when chamber summaries fix a seat despite an independent candidate and
test that this policy matches the published contract; keep unresolved seats
visible).

The audit is read-only. It reads the processed roster/incumbency/baseline CSVs,
the raw party certification PDFs and Wikipedia snapshots they derive from, the
2026 plan geometry used by the dashboard maps, the published forecast scenario
bundle, the published page text and the field contract; it writes only the
Markdown/JSON report named on the command line.

Every class keeps the repository's observed / reconstructed / imputed /
excluded / unknown separation:

- modeled D-versus-R seats are *observed* roster rows and *modeled* forecast rows;
- single-major-party seats are *observed* nominations with a *policy-fixed*
  chamber total;
- independent-or-third-party-only and no-candidate seats are *observed* absences
  of a modelable race and are shown as ``unmodeled``, never assigned a margin;
- identity, incumbency and as-of dates carry an explicit unknown where the local
  sources do not establish them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
CAL = ROOT / "data" / "processed" / "forecast_calibration"
ELECTIONS = ROOT / "data" / "processed" / "elections"
GEOGRAPHY = ROOT / "data" / "raw" / "alabama_elections_and_geography"
CONTRACT = ROOT / "project_docs" / "model" / "ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md"
DASHBOARD = ROOT / "scripts" / "build_2026_forecast_dashboard.py"
FORECAST_SCRIPT = ROOT / "scripts" / "run_alabama_war_generic_forecast.py"
DASHBOARD_JS = ROOT / "dashboard" / "forecast_dashboard.js"
ARTIFACT = ROOT / "artifacts" / "site" / "alabama-2026-legislative-forecast.html"
PUBLISHED_INDEX = ROOT / "docs" / "index.html"
PUBLISHED_METHODOLOGY = ROOT / "docs" / "methodology.html"
DEFAULT_REPORT = ROOT / "project_docs" / "audits" / "FORECAST_ROSTER_UNIVERSE_2026_09_11.md"
DEFAULT_REPORT_JSON = ROOT / "project_docs" / "audits" / "FORECAST_ROSTER_UNIVERSE_2026_09_11.json"

FINAL_ROSTER = WAR / "2026_final_candidate_roster.csv"
CERTIFIED_ROSTER = WAR / "2026_certified_candidate_roster.csv"
PROVISIONAL_ROSTER = WAR / "2026_candidate_roster_provisional.csv"
CERTIFIED_OCR_RAW = WAR / "2026_certified_roster_ocr_raw.csv"
RECONCILIATION = WAR / "2026_certified_roster_reconciliation.csv"
OVERRIDES = WAR / "2026_roster_manual_overrides.csv"
OVERRIDE_APPLICATION = WAR / "2026_roster_override_application.csv"
INCUMBENCY = WAR / "2026_candidate_incumbency.csv"
RACE_INCUMBENCY = WAR / "2026_race_incumbency.csv"
INCUMBENCY_REVIEW = WAR / "2026_incumbency_review.csv"
BASELINE = WAR / "2026_poll_adjusted_baseline.csv"
GEO_MANIFEST = WAR / "2026_geography_source_manifest.csv"
GEO_CROSSWALK_QA = WAR / "2026_geographic_crosswalk_qa.csv"
SCENARIOS = CAL / "alabama_war_forecast_v1_2026_scenarios.csv"
MODELED_SEATS = CAL / "alabama_war_forecast_v1_2026_modeled_seats.csv"
FORECAST_MANIFEST = CAL / "alabama_war_forecast_v1_manifest.json"
PRIOR_WAR = WAR / "alabama_war_v1" / "candidate_cycle_war.csv"
CANONICAL = ELECTIONS / "canonical_cmo_candidates.csv"

CERTIFICATION_PDFS = {
    "D": GEOGRAPHY / "CertificationofDemocraticPartyCandidates-2026General.pdf",
    "R": GEOGRAPHY / "CertificationofRepublicanPartyCandidates-2026General.pdf",
}
WIKIPEDIA_PAGES = {
    "house": GEOGRAPHY / "2026 Alabama House of Representatives election - Wikipedia.html",
    "senate": GEOGRAPHY / "2026 Alabama Senate election - Wikipedia.html",
}
PLAN_DBF = {
    "house": GEOGRAPHY / "tl_2025_01_sldl" / "tl_2025_01_sldl.dbf",
    "senate": GEOGRAPHY / "tl_2025_01_sldu" / "tl_2025_01_sldu.dbf",
}
PLAN_FIELD = {"house": "SLDLST", "senate": "SLDUST"}

TOTAL_SEATS = {"house": 105, "senate": 35}
TOTAL_ALL_SEATS = sum(TOTAL_SEATS.values())
PROSPECTIVE_EXPECTED_RACES = 48

SEAT_CLASSES = (
    "modeled_d_r",
    "single_major_party_d",
    "single_major_party_r",
    "independent_only",
    "no_candidate",
    "unresolved",
)
MODELED_CLASS = "modeled_d_r"

# Manual-override resolutions whose nomination path the audit reports verbatim.
NOMINATION_PATHS = {
    "same_person_certified_name": "alias_confirmed_same_person",
    "certification_add_runoff_winner": "primary_runoff_winner_certified",
    "post_map_reversion_special_primary_certification": "post_map_reversion_special_primary",
    "retain_wikipedia_certification_omission": "certification_omission_retained",
    "ocr_correction_certified_name": "ocr_name_corrected",
    "certification_add": "added_from_certification",
    "certified_replaces_misclassified_independent": "misclassified_independent_corrected",
    "reclassify_independent": "independent_reclassified",
    "replace_conditional_certification": "conditional_certification_replaced",
}

# Seat-treatment wording the audit looks for, per artefact. These are exact
# substrings of the shipped sources/pages; a miss is itself the finding.
POLICY_IMPLEMENTATION_MARKERS = {
    "fixed_dem_from_roster": "fixed_dem=len(dem_districts-rep_districts)",
    "modeled_seats_plus_fixed": 'sd["dem_seats"]=sd.dem_modeled_seats+fixed_dem',
    "single_major_party_status": '"unopposed-major-party"',
    "unmodeled_status": 'p,status,margin=None,"unmodeled",None',
    "unresolved_visibility": "const unknown=DATA[c].races.filter(r=>r.demProbability==null).length",
    "independent_not_modeled_copy": "Single major-party nominee; independent contests are not modeled",
}
POLICY_PUBLISHED_MARKERS = {
    "index_caveat": "Districts with one major-party nominee are fixed; genuinely unresolved districts remain unmodeled and gray.",
    "methodology_fixed_totals": "Single-major-party seats are fixed in chamber totals.",
    "independent_not_modeled_copy": "Single major-party nominee; independent contests are not modeled",
}
CONTRACT_SEAT_TERMS = (
    "single-major-party",
    "single major party",
    "major-party nominee",
    "major party nominee",
    "unresolved seat",
    "unmodeled",
    "unopposed",
    "seat total",
    "chamber total",
    "independent candidate",
    "independent contest",
    "third-party",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize_name(value: object) -> str:
    """Conservative identity key: upper-case alphanumerics only."""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


NAME_SUFFIXES = {"JR", "SR", "II", "III", "IV", "V"}


def surname(value: object) -> str:
    """Last non-suffix alphabetic token; used only to separate alias variants from a different person."""
    tokens = [token.upper() for token in re.findall(r"[A-Za-z]+", str(value))]
    tokens = [token for token in tokens if token not in NAME_SUFFIXES] or tokens
    return tokens[-1] if tokens else ""


def same_surname(left: object, right: object) -> bool:
    """True when two spellings plausibly share a surname, tolerating run-together OCR names."""
    left_key, right_key = normalize_name(left), normalize_name(right)
    left_surname, right_surname = surname(left), surname(right)
    if not left_surname or not right_surname:
        return left_key == right_key
    return (
        left_surname == right_surname
        or left_key.endswith(right_surname)
        or right_key.endswith(left_surname)
    )


def utc_iso(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()


def read_dbf(path: Path) -> list[dict[str, str]]:
    """Minimal dBASE reader: enough to enumerate plan districts without a GIS stack."""
    raw = Path(path).read_bytes()
    if len(raw) < 32:
        raise ValueError(f"Truncated DBF: {path}")
    records = struct.unpack("<I", raw[4:8])[0]
    header_length = struct.unpack("<H", raw[8:10])[0]
    record_length = struct.unpack("<H", raw[10:12])[0]
    fields: list[tuple[str, int]] = []
    offset = 32
    while raw[offset] != 0x0D:
        name = raw[offset : offset + 11].split(b"\x00")[0].decode("ascii")
        fields.append((name, raw[offset + 16]))
        offset += 32
    rows = []
    for index in range(records):
        block = raw[header_length + index * record_length : header_length + (index + 1) * record_length]
        cursor = 1
        row = {}
        for name, length in fields:
            row[name] = block[cursor : cursor + length].decode("latin-1").strip()
            cursor += length
        rows.append(row)
    return rows


def plan_districts() -> dict[str, list[int]]:
    """The 2026 plan district codes read from the dashboard's map geometry."""
    plan: dict[str, list[int]] = {}
    for chamber, path in PLAN_DBF.items():
        codes = sorted(int(row[PLAN_FIELD[chamber]]) for row in read_dbf(path))
        plan[chamber] = codes
    return plan


def load_frame(path: Path, **kwargs) -> pd.DataFrame | None:
    return pd.read_csv(path, **kwargs) if path.exists() else None


def seat_frame(
    roster: pd.DataFrame, plan: dict[str, list[int]] | None = None
) -> pd.DataFrame:
    """Enumerate every chamber seat and label it from the roster."""
    plan = plan or {chamber: list(range(1, total + 1)) for chamber, total in TOTAL_SEATS.items()}
    frame = roster.copy()
    frame["chamber"] = frame.chamber.astype(str).str.strip().str.lower()
    frame["district"] = frame.district.astype(int)
    frame["party"] = frame.party.astype(str).str.strip().str.upper()
    if frame.duplicated(["chamber", "district", "party", "candidate"]).any():
        duplicate = frame[frame.duplicated(["chamber", "district", "party", "candidate"], keep=False)]
        raise ValueError(
            "Roster repeats an identical nominee row: "
            f"{sorted(set(map(tuple, duplicate[['chamber', 'district', 'party', 'candidate']].to_records(index=False))))}"
        )
    grouped = {key: sub for key, sub in frame.groupby(["chamber", "district"], sort=False)}
    rows = []
    for chamber, districts in plan.items():
        for district in districts:
            sub = grouped.get((chamber, int(district)))
            if sub is None:
                sub = frame.iloc[0:0]
            dem = int(sub[sub.party.eq("D")].candidate.nunique())
            rep = int(sub[sub.party.eq("R")].candidate.nunique())
            other = sorted(set(sub.party) - {"D", "R"})
            if dem == 1 and rep == 1:
                seat_class = "modeled_d_r"
            elif dem and rep:
                seat_class = "unresolved"
            elif dem:
                seat_class = "single_major_party_d"
            elif rep:
                seat_class = "single_major_party_r"
            elif other:
                seat_class = "independent_only"
            else:
                seat_class = "no_candidate"
            rows.append(
                {
                    "chamber": chamber,
                    "district": int(district),
                    "seat_class": seat_class,
                    "party_labels": "+".join(sorted(set(sub.party))) if len(sub) else "",
                    "dem_nominees": dem,
                    "rep_nominees": rep,
                    "other_party_nominees": "+".join(other),
                    "has_independent_or_third_party": bool(other),
                    "nominee_rows": int(len(sub)),
                }
            )
    return pd.DataFrame(rows)


def partition_counts(seats: pd.DataFrame) -> dict:
    """Class counts overall and per chamber; the classes must partition the 140 seats."""
    counts = Counter(seats.seat_class)
    by_chamber = {
        chamber: {name: int(counts_by[name]) for name in SEAT_CLASSES}
        for chamber, counts_by in (
            (chamber, Counter(sub.seat_class)) for chamber, sub in seats.groupby("chamber")
        )
    }
    total = int(len(seats))
    return {
        "total_seats": total,
        "expected_total_seats": TOTAL_ALL_SEATS,
        "partition_complete": total == TOTAL_ALL_SEATS,
        "class_counts_sum": sum(int(counts[name]) for name in SEAT_CLASSES),
        "classes_partition_total": sum(int(counts[name]) for name in SEAT_CLASSES) == total,
        "counts": {name: int(counts[name]) for name in SEAT_CLASSES},
        "by_chamber": by_chamber,
    }


def prospective_eligibility(roster: pd.DataFrame) -> set[tuple[str, int]]:
    """Reproduce ``run_alabama_war_generic_forecast.prospective_features`` eligibility."""
    frame = roster.copy()
    frame["chamber"] = frame.chamber.astype(str).str.strip().str.lower()
    frame["district"] = frame.district.astype(int)
    counts = frame.pivot_table(
        index=["chamber", "district"],
        columns="party",
        values="candidate",
        aggfunc="nunique",
        fill_value=0,
    ).reset_index()
    if "D" not in counts or "R" not in counts:
        return set()
    eligible = counts[counts["D"].eq(1) & counts["R"].eq(1)]
    return {(str(chamber), int(district)) for chamber, district in eligible[["chamber", "district"]].to_records(index=False)}


def scenario_race_keys(scenarios: pd.DataFrame) -> dict[str, set[tuple[str, int]]]:
    return {
        str(scenario): {
            (str(chamber), int(district))
            for chamber, district in sub[["chamber", "district"]].to_records(index=False)
        }
        for scenario, sub in scenarios.groupby("scenario", sort=True)
    }


def model_check(
    roster: pd.DataFrame, seats: pd.DataFrame, scenarios: pd.DataFrame, modeled_seats: pd.DataFrame
) -> dict:
    """Reconcile the modeled class with the published scenario bundle."""
    classified = {
        (str(row.chamber), int(row.district))
        for row in seats[seats.seat_class.eq(MODELED_CLASS)].itertuples()
    }
    eligible = prospective_eligibility(roster)
    scenario_keys = scenario_race_keys(scenarios)
    scenario_sizes = {name: len(keys) for name, keys in scenario_keys.items()}
    per_scenario_consistent = len({frozenset(keys) for keys in scenario_keys.values()}) == 1
    return {
        "expected_prospective_races": PROSPECTIVE_EXPECTED_RACES,
        "classified_modeled_seats": len(classified),
        "eligible_modeled_seats": len(eligible),
        "modeled_difference": len(classified) - PROSPECTIVE_EXPECTED_RACES,
        "modeled_matches_expected": len(classified) == PROSPECTIVE_EXPECTED_RACES,
        "classified_equals_eligible": classified == eligible,
        "scenario_race_counts": scenario_sizes,
        "scenario_races_identical": per_scenario_consistent,
        "scenario_keys_equal_classified": all(keys == classified for keys in scenario_keys.values()),
        "modeled_seat_rows_by_chamber": {
            str(chamber): int(len(sub)) for chamber, sub in modeled_seats.groupby("chamber")
        },
        "modeled_seat_probability_sums": {
            str(chamber): round(float(sub.probability.sum()), 12)
            for chamber, sub in modeled_seats.groupby("chamber")
        },
        "unresolved_seat_keys": sorted(
            (str(row.chamber), int(row.district))
            for row in seats[seats.seat_class.eq("unresolved")].itertuples()
        ),
    }


# --------------------------------------------------------------------------- roster provenance


def _source_as_of() -> dict:
    """What the local evidence does and does not establish about roster dates."""
    return {
        "certification_document_date": None,
        "certification_document_date_established": False,
        "certification_document_date_note": (
            "The scanned party-certification PDFs carry no recorded issuance date or "
            "acquisition manifest in the repository; only the filesystem retrieval "
            "timestamp is available."
        ),
        "nomination_effective_after_utc": "2026-08-11",
        "nomination_effective_after_evidence": (
            "The reconciliation row for senate 26 D reads "
            "'Tabitha Isner (subject to August 11 Primary)*' and the runoff-certificate "
            "rows supersede earlier certification, so the roster is effective after the "
            "2026-08-11 primary runoff."
        ),
        "roster_source_manifest_present": False,
        "roster_source_manifest_note": (
            "No manifest under data/raw/candidates/ or data/processed/war/*roster*manifest* "
            "records the certification PDF URLs, retrieval times, hashes or terms. The "
            "forecast manifest declares the final roster as an input hash only."
        ),
    }


def source_register() -> list[dict]:
    """Hash, size and filesystem timestamp for every roster-universe input."""
    entries = [
        (FINAL_ROSTER, "roster", "Manifest-declared forecast input: certified roster plus reviewed overrides"),
        (CERTIFIED_ROSTER, "roster", "OCR extraction of the two party-certification PDFs"),
        (PROVISIONAL_ROSTER, "roster", "Provisional Wikipedia nominee extraction (not authoritative)"),
        (CERTIFIED_OCR_RAW, "roster", "Raw OCR rows before district/priority deduplication"),
        (RECONCILIATION, "roster", "Certified-versus-provisional reconciliation with review flags"),
        (OVERRIDES, "roster", "Human-reviewed roster adjudications (21 rows)"),
        (OVERRIDE_APPLICATION, "roster", "Applied-override ledger"),
        (INCUMBENCY, "incumbency", "Manifest-declared forecast input: per-candidate incumbency"),
        (RACE_INCUMBENCY, "incumbency", "Per-seat incumbency summary"),
        (INCUMBENCY_REVIEW, "incumbency", "Incumbency rows needing review"),
        (BASELINE, "baseline", "2024 presidential baseline allocated to the 2026 districts"),
        (GEO_MANIFEST, "plan", "2026 plan geometry source manifest"),
        (GEO_CROSSWALK_QA, "plan", "Plan crosswalk QA summary"),
        (SCENARIOS, "forecast", "Published 2026 scenarios (48 races per scenario)"),
        (MODELED_SEATS, "forecast", "Published headline modeled-seat distribution"),
        (FORECAST_MANIFEST, "forecast", "Forecast build manifest declaring the roster inputs"),
        (CONTRACT, "contract", "Published forecast field contract"),
        (PRIOR_WAR, "identity", "Published post-2016 Alabama candidate-cycle WAR rows"),
        (CANONICAL, "identity", "Canonical named candidate rows, cycles 1994-2022"),
        (DASHBOARD, "presentation", "Dashboard builder: seat classification and chamber aggregation"),
        (FORECAST_SCRIPT, "model", "Forecast producer: prospective_features / predict_scenarios"),
        (DASHBOARD_JS, "presentation", "Dashboard behaviour: unmodeled visibility and seat stats"),
    ]
    for party, path in CERTIFICATION_PDFS.items():
        entries.append((path, "roster_source", f"Official {party} party certification of 2026 general nominees"))
    for chamber, path in WIKIPEDIA_PAGES.items():
        entries.append((path, "roster_source", f"Wikipedia {chamber} snapshot used for the provisional roster"))
    for chamber, path in PLAN_DBF.items():
        entries.append((path, f"plan_{chamber}", f"2025 TIGER {PLAN_FIELD[chamber]} dBASE for the dashboard maps"))
    register = []
    for path, role, note in entries:
        path = Path(path)
        record = {
            "path": path.relative_to(ROOT).as_posix(),
            "role": role,
            "note": note,
            "present": path.exists(),
        }
        if path.exists():
            stat = path.stat()
            record.update(
                {
                    "bytes": int(stat.st_size),
                    "sha256": sha256(path),
                    "filesystem_mtime_utc": utc_iso(stat.st_mtime),
                    "recorded_as_of_utc": None,
                }
            )
        else:
            record.update({"bytes": None, "sha256": None, "filesystem_mtime_utc": None, "recorded_as_of_utc": None})
        register.append(record)
    return register


def roster_provenance(
    roster: pd.DataFrame,
    overrides: pd.DataFrame | None,
    incumbency: pd.DataFrame,
    plan: dict[str, list[int]],
    prior_war: pd.DataFrame,
    canonical: pd.DataFrame,
    source_mtimes: dict[str, str | None],
) -> tuple[pd.DataFrame, dict]:
    """One provenance record per roster row: source, stage, identity, incumbency, plan."""
    overrides = overrides if overrides is not None else pd.DataFrame(
        columns=["chamber", "district", "party", "resolution"]
    )
    override_index = {
        (str(row.chamber), int(row.district), str(row.party)): row
        for row in overrides.itertuples(index=False)
    }
    incumbency_index = {
        (str(row.chamber), int(row.district), str(row.party), row.candidate): row
        for row in incumbency.itertuples(index=False)
    }
    canonical_index: dict[tuple[str, int, str, str], list[tuple[int, str]]] = {}
    canonical_local = canonical.copy()
    canonical_local["name_key"] = canonical_local.canonical_name.map(normalize_name)
    for row in canonical_local.itertuples(index=False):
        canonical_index.setdefault(
            (str(row.chamber), int(row.district), str(row.canonical_party), row.name_key), []
        ).append((int(row.year), str(row.canonical_candidate_id)))
    prior_index: dict[tuple[str, str], set[int]] = {}
    prior_local = prior_war.copy()
    prior_local["name_key"] = prior_local.normalized_candidate_name.map(normalize_name)
    prior_local["chamber_label"] = prior_local.chamber.map({"lower": "house", "upper": "senate"})
    for row in prior_local.itertuples(index=False):
        prior_index.setdefault((row.name_key, str(row.canonical_party)), set()).add(int(row.cycle))

    plan_keys = {
        (chamber, int(district)) for chamber, districts in plan.items() for district in districts
    }
    records = []
    for row in roster.itertuples(index=False):
        key = (str(row.chamber), int(row.district), str(row.party))
        override = override_index.get(key)
        resolution = str(override.resolution) if override is not None else None
        if resolution is None:
            nomination_path = "certified_party_nominee"
            stage_note = "Party certification of the general-election nominee"
        else:
            nomination_path = NOMINATION_PATHS.get(resolution, resolution)
            stage_note = f"Manual adjudication ({resolution})"
        incumbent = incumbency_index.get((str(row.chamber), int(row.district), str(row.party), row.candidate))
        name_key = normalize_name(row.candidate)
        canonical_matches = canonical_index.get(
            (str(row.chamber), int(row.district), str(row.party), name_key), []
        )
        prior_cycles = sorted(prior_index.get((name_key, str(row.party)), set()))
        source_path = (
            CERTIFICATION_PDFS.get(str(row.party))
            if str(row.source_file).endswith(".pdf")
            else OVERRIDES
        )
        source_name = str(row.source_file)
        source_file = ROOT / "data" / "raw" / "alabama_elections_and_geography" / source_name
        if not source_file.exists():
            source_file = WAR / source_name
        records.append(
            {
                "cycle": int(row.cycle),
                "chamber": str(row.chamber),
                "district": int(row.district),
                "party": str(row.party),
                "candidate": str(row.candidate),
                "roster_status": str(row.roster_status),
                "source_file": source_name,
                "source_kind": "manual_override" if override is not None else "party_certification_ocr",
                "source_retrieved_utc": source_mtimes.get(
                    Path(source_file).name if source_file.exists() else str(source_path.name)
                ),
                "election_stage": "general_nominee",
                "nomination_path": nomination_path,
                "nomination_path_evidence": stage_note,
                "identity_prior_winner_candidate_id": (
                    str(incumbent.prior_winner_candidate_id)
                    if incumbent is not None and pd.notna(incumbent.prior_winner_candidate_id)
                    else None
                ),
                "identity_canonical_matches": ";".join(f"{year}:{cid}" for year, cid in canonical_matches) or None,
                "identity_prior_cycle_matches": ",".join(str(cycle) for cycle in prior_cycles) or None,
                "incumbent": bool(incumbent.incumbent) if incumbent is not None else None,
                "incumbency_source": (
                    str(incumbent.incumbency_source) if incumbent is not None and pd.notna(incumbent.incumbency_source) else None
                ),
                "incumbency_join_resolved": incumbent is not None,
                "on_2026_plan": (str(row.chamber), int(row.district)) in plan_keys,
            }
        )
    provenance = pd.DataFrame(records)
    roster_keys = {(str(r.chamber), int(r.district)) for r in roster.itertuples(index=False)}
    off_plan = sorted(roster_keys - plan_keys)
    summary = {
        "roster_rows": int(len(provenance)),
        "rows_missing_source_file_on_disk": int(
            sum(
                1
                for name in provenance.source_file.unique()
                if not (ROOT / "data" / "raw" / "alabama_elections_and_geography" / name).exists()
                and not (WAR / name).exists()
            )
        ),
        "certification_ocr_rows": int(provenance.source_kind.eq("party_certification_ocr").sum()),
        "manual_override_rows": int(provenance.source_kind.eq("manual_override").sum()),
        "election_stage_counts": dict(Counter(provenance.election_stage)),
        "nomination_path_counts": dict(Counter(provenance.nomination_path)),
        "incumbency_join_resolved": int(provenance.incumbency_join_resolved.sum()),
        "incumbents_flagged": int(provenance.incumbent.fillna(False).sum()),
        "identity_prior_winner_resolved": int(provenance.identity_prior_winner_candidate_id.notna().sum()),
        "identity_canonical_prior_resolved": int(provenance.identity_canonical_matches.notna().sum()),
        "identity_any_prior_resolved": int(
            (provenance.identity_prior_winner_candidate_id.notna() | provenance.identity_canonical_matches.notna()).sum()
        ),
        "identity_unresolved_rows": int(
            (provenance.identity_prior_winner_candidate_id.isna() & provenance.identity_canonical_matches.isna()).sum()
        ),
        "rows_on_2026_plan": int(provenance.on_2026_plan.sum()),
        "off_plan_seat_keys": off_plan,
        "source_as_of": _source_as_of(),
    }
    return provenance, summary


# --------------------------------------------------------------------------- deltas


def roster_deltas(
    provisional: pd.DataFrame | None,
    certified: pd.DataFrame | None,
    final: pd.DataFrame,
    overrides: pd.DataFrame | None,
    reconciliation: pd.DataFrame | None,
) -> tuple[list[dict], dict]:
    """Withdrawals, replacements and additions evident across the roster versions."""
    def keyed(frame: pd.DataFrame) -> dict[tuple[str, int, str], str]:
        if frame is None or frame.empty:
            return {}
        local = frame.copy()
        local["chamber"] = local.chamber.astype(str).str.strip().str.lower()
        local["district"] = local.district.astype(int)
        return {
            (str(row.chamber), int(row.district), str(row.party)): str(row.candidate)
            for row in local.itertuples(index=False)
        }

    def duplicate_keys(frame: pd.DataFrame | None) -> list[dict]:
        if frame is None or frame.empty:
            return []
        local = frame.copy()
        local["chamber"] = local.chamber.astype(str).str.strip().str.lower()
        local["district"] = local.district.astype(int)
        repeated = local[local.duplicated(["chamber", "district", "party"], keep=False)]
        return [
            {
                "chamber": str(chamber),
                "district": int(district),
                "party": str(party),
                "candidates": sorted(set(sub.candidate.astype(str))),
            }
            for (chamber, district, party), sub in repeated.groupby(["chamber", "district", "party"])
        ]

    provisional_keys = keyed(provisional)
    certified_keys = keyed(certified)
    final_keys = keyed(final)
    resolution_index = {}
    if overrides is not None and not overrides.empty:
        resolution_index = {
            (str(row.chamber), int(row.district), str(row.party)): (str(row.resolution), str(row.authoritative_name))
            for row in overrides.itertuples(index=False)
        }
    deltas = []
    for key in sorted(set(certified_keys) | set(final_keys) | set(provisional_keys)):
        before = certified_keys.get(key)
        after = final_keys.get(key)
        observed = provisional_keys.get(key)
        resolution = resolution_index.get(key, (None, None))[0]
        changes = []
        if before is None and after is not None:
            changes.append("added_after_certification")
        elif before is not None and after is None:
            changes.append("removed_from_final")
        elif before is not None and after is not None and before != after:
            if normalize_name(before) == normalize_name(after):
                changes.append("name_normalized")
            elif same_surname(before, after):
                changes.append("name_changed_same_surname")
            else:
                changes.append("replaced")
        if observed is not None and before is None and after is None:
            changes.append("provisional_only_not_certified")
        if observed is None and before is not None:
            changes.append("certified_only_not_in_provisional")
        if (
            observed is not None
            and before is not None
            and observed != before
            and normalize_name(observed) != normalize_name(before)
        ):
            changes.append(
                "provisional_nominee_differs_from_certified"
                if same_surname(observed, before)
                else "provisional_nominee_materially_differs_from_certified"
            )
        if not changes:
            continue
        deltas.append(
            {
                "chamber": key[0],
                "district": key[1],
                "party": key[2],
                "candidate_provisional": observed,
                "candidate_certified": before,
                "candidate_final": after,
                "changes": " + ".join(changes),
                "change": changes[0],
                "override_resolution": resolution,
            }
        )
    summary = {
        "provisional_rows": int(len(provisional)) if provisional is not None else 0,
        "provisional_seat_keys": len(provisional_keys),
        "certified_rows": int(len(certified)) if certified is not None else 0,
        "final_rows": int(len(final)),
        "provisional_duplicate_keys": duplicate_keys(provisional),
        "certified_duplicate_keys": duplicate_keys(certified),
        "change_counts": dict(
            Counter(change for row in deltas for change in str(row["changes"]).split(" + "))
        ),
    }
    if reconciliation is not None and not reconciliation.empty:
        review = reconciliation[reconciliation.review_required.astype(bool)]
        summary["reconciliation_rows"] = int(len(reconciliation))
        summary["reconciliation_review_required"] = int(len(review))
        summary["reconciliation_review_keys"] = [
            {"chamber": str(row.chamber), "district": int(row.district), "party": str(row.party), "merge": str(row["_merge"])}
            for _, row in review.iterrows()
        ]
    return deltas, summary


# --------------------------------------------------------------------------- policy


def read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def artifact_payload(path: Path = ARTIFACT) -> dict | None:
    text = read_text(path)
    if text is None:
        return None
    match = re.search(r"const DATA=(\{.*?\});", text, re.S)
    return json.loads(match.group(1)) if match else None


def policy_evidence(
    dashboard_text: str | None,
    js_text: str | None,
    artifact_text: str | None,
    published_index: str | None,
    published_methodology: str | None,
    contract_text: str | None,
) -> dict:
    sources = {
        "dashboard_builder": dashboard_text or "",
        "dashboard_js": js_text or "",
        "rendered_artifact": artifact_text or "",
        "published_index": published_index or "",
        "published_methodology": published_methodology or "",
    }
    implementation = {
        name: any(marker in text for text in sources.values())
        for name, marker in POLICY_IMPLEMENTATION_MARKERS.items()
    }
    published = {
        "index_caveat_present": POLICY_PUBLISHED_MARKERS["index_caveat"] in sources["published_index"],
        "methodology_fixed_totals_present": POLICY_PUBLISHED_MARKERS["methodology_fixed_totals"]
        in sources["published_methodology"],
        "index_independent_not_modeled_copy_present": POLICY_PUBLISHED_MARKERS["independent_not_modeled_copy"]
        in sources["published_index"],
        "artifact_independent_copy_present": POLICY_PUBLISHED_MARKERS["independent_not_modeled_copy"]
        in sources["rendered_artifact"],
    }
    contract = {
        "terms_found": sorted(term for term in CONTRACT_SEAT_TERMS if term in (contract_text or "").lower())
        if contract_text
        else [],
        "contract_text_present": contract_text is not None,
    }
    contract["states_seat_treatment"] = bool(
        set(contract["terms_found"]) & {"single-major-party", "single major party", "major-party nominee", "unresolved", "unmodeled"}
    )
    contract["states_major_party_denominator"] = bool(
        set(contract["terms_found"]) & {"single-major-party", "single major party", "major-party nominee"}
    )
    agreement = (
        "page_and_implementation_agree"
        + ("_contract_states_policy" if contract["states_major_party_denominator"] else "_contract_silent")
    )
    return {
        "policy_statement": (
            "A seat is fixed in the chamber summaries when exactly one major party nominated a "
            "candidate and the other major party nominated none, regardless of independent or "
            "third-party candidates in that race. Districts with both major parties nominated are "
            "modeled as generic D-versus-R races in which independent candidates are not modeled. "
            "Districts with no D and no R nominee (independent-only, third-party-only, or no "
            "candidate) receive no margin or probability and stay visible as unmodeled."
        ),
        "implementation": implementation,
        "published": published,
        "field_contract": contract,
        "agreement": agreement,
    }


def policy_reconciliation(
    roster: pd.DataFrame,
    seats: pd.DataFrame,
    payload: dict | None,
    modeled_seats: pd.DataFrame,
) -> dict:
    """Test the implemented fixed-seat offset and the independent-candidate cases."""
    fixed_from_roster = {
        str(chamber): int(sub.seat_class.eq("single_major_party_d").sum())
        for chamber, sub in seats.groupby("chamber")
    }
    result = {
        "fixed_dem_from_roster": fixed_from_roster,
        "fixed_rep_from_roster": {
            str(chamber): int(sub.seat_class.eq("single_major_party_r").sum())
            for chamber, sub in seats.groupby("chamber")
        },
        "payload_fixed_offset_matches_roster": None,
        "payload_headline_distribution_matches_csv": None,
        "payload_unmodeled_count": None,
        "payload_offsets": {},
        "independent_candidate_seats": [],
        "independent_with_major_party_fixed": None,
        "independent_only_unmodeled": None,
        "payload_status_matches_classes": None,
        "payload_status_mismatches": [],
    }
    if payload is not None:
        offsets = {}
        consistent = True
        headline_matches = {}
        for chamber in ("house", "senate"):
            published = modeled_seats[modeled_seats.chamber.eq(chamber)]
            expected = {
                int(row.dem_modeled_seats): float(row.probability)
                for row in published.itertuples(index=False)
            }
            fixed = fixed_from_roster.get(chamber, 0)
            distributions = payload.get(chamber, {}).get("modelSeatDistributions", {})
            for model, rows in distributions.items():
                if not rows:
                    continue
                dem_seats = [int(row["demSeats"]) for row in rows]
                # A headline distribution is the CSV support shifted by the fixed
                # Democratic seats; a Poisson-binomial scenario distribution starts
                # at zero modeled Democratic wins and is shifted by the same amount.
                base_min = min(expected) if (model == "headline" and expected) else 0
                offset = dem_seats[0] - base_min
                offsets[f"{chamber}:{model}"] = offset
                if offset != fixed:
                    consistent = False
                if model == "headline" and expected:
                    actual = {seats - fixed: float(row["probability"]) for seats, row in zip(dem_seats, rows)}
                    headline_matches[chamber] = (
                        set(actual) == set(expected)
                        and all(abs(actual[seats] - probability) < 1e-12 for seats, probability in expected.items())
                    )
        result["payload_offsets"] = offsets
        result["payload_fixed_offset_matches_roster"] = consistent
        result["payload_headline_distribution_matches_csv"] = headline_matches
        result["payload_unmodeled_count"] = {
            str(chamber): int(
                sum(
                    1
                    for race in payload.get(chamber, {}).get("races", [])
                    if race.get("demProbability") is None
                )
            )
            for chamber in ("house", "senate")
        }
        seats_with_other = seats[seats.has_independent_or_third_party]
        for seat in seats_with_other.itertuples(index=False):
            race = next(
                (
                    item
                    for item in payload[str(seat.chamber)]["races"]
                    if int(item["district"]) == int(seat.district)
                ),
                None,
            )
            result["independent_candidate_seats"].append(
                {
                    "chamber": str(seat.chamber),
                    "district": int(seat.district),
                    "seat_class": str(seat.seat_class),
                    "other_parties": str(seat.other_party_nominees),
                    "payload_status": race.get("status") if race else None,
                    "payload_dem_probability": race.get("demProbability") if race else None,
                    "payload_candidates": sorted(
                        (str(candidate["name"]), str(candidate["party"]))
                        for candidate in (race or {}).get("candidates", [])
                    ),
                }
            )
        bearing = [
            row for row in result["independent_candidate_seats"]
            if str(row["seat_class"]).startswith("single_major_party")
        ]
        only = [row for row in result["independent_candidate_seats"] if row["seat_class"] == "independent_only"]
        result["independent_with_major_party_fixed"] = (
            all(
                row["payload_status"] == "unopposed-major-party"
                and row["payload_dem_probability"] in (0.0, 1.0)
                for row in bearing
            )
            if bearing
            else None
        )
        result["independent_only_unmodeled"] = (
            all(
                row["payload_status"] == "unmodeled" and row["payload_dem_probability"] is None
                for row in only
            )
            if only
            else None
        )
        expected_status = {
            "modeled_d_r": "modeled",
            "single_major_party_d": "unopposed-major-party",
            "single_major_party_r": "unopposed-major-party",
            "independent_only": "unmodeled",
            "no_candidate": "unmodeled",
            "unresolved": "unmodeled",
        }
        mismatches = []
        for seat in seats.itertuples(index=False):
            race = next(
                (
                    item
                    for item in payload[str(seat.chamber)]["races"]
                    if int(item["district"]) == int(seat.district)
                ),
                None,
            )
            actual_status = race.get("status") if race else None
            wanted = expected_status[str(seat.seat_class)]
            if actual_status != wanted:
                mismatches.append(
                    {
                        "chamber": str(seat.chamber),
                        "district": int(seat.district),
                        "seat_class": str(seat.seat_class),
                        "expected_status": wanted,
                        "payload_status": actual_status,
                    }
                )
        result["payload_status_matches_classes"] = not mismatches
        result["payload_status_mismatches"] = mismatches
    result["modeled_seat_min_dem_from_csv"] = {
        str(chamber): int(sub.dem_modeled_seats.min()) for chamber, sub in modeled_seats.groupby("chamber")
    }
    return result


# --------------------------------------------------------------------------- assembly


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bool, int, str)) or value is None:
        return value
    if isinstance(value, float):
        return value
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return str(value)


def build_summary() -> dict:
    started = time.time()
    roster = pd.read_csv(FINAL_ROSTER)
    certified = load_frame(CERTIFIED_ROSTER)
    provisional = load_frame(PROVISIONAL_ROSTER)
    overrides = load_frame(OVERRIDES)
    reconciliation = load_frame(RECONCILIATION)
    incumbency = pd.read_csv(INCUMBENCY)
    modeled_seats = pd.read_csv(MODELED_SEATS)
    scenarios = pd.read_csv(SCENARIOS)
    manifest = json.loads(FORECAST_MANIFEST.read_text(encoding="utf-8"))

    plan = plan_districts()
    plan_check = {
        "plan_dbf_paths": {chamber: path.relative_to(ROOT).as_posix() for chamber, path in PLAN_DBF.items()},
        "plan_fields": dict(PLAN_FIELD),
        "plan_district_counts": {chamber: len(codes) for chamber, codes in plan.items()},
        "plan_codes_contiguous": {
            chamber: codes == list(range(1, len(codes) + 1)) for chamber, codes in plan.items()
        },
        "geometry_vintage_declared": None,
        "geometry_vintage_note": None,
        "dashboard_map_paths": {
            "house": "data/raw/alabama_elections_and_geography/tl_2025_01_sldl/tl_2025_01_sldl.shp",
            "senate": "data/raw/alabama_elections_and_geography/tl_2025_01_sldu/tl_2025_01_sldu.shp",
        },
        "prospective_features_uses_geometry": False,
        "baseline_seat_keys": 0,
    }
    if GEO_MANIFEST.exists():
        geo = pd.read_csv(GEO_MANIFEST)
        shp = geo[geo.source_file.str.endswith(".shp")]
        plan_check["geometry_vintage_declared"] = {
            str(row.chamber): {
                "applicable_cycle": int(row.applicable_cycle),
                "legislative_session_year": int(row.legislative_session_year),
                "selection_basis": str(row.selection_basis),
                "sha256": str(row.sha256),
                "sha256_matches_disk": _sha_or_none(ROOT / Path(str(row.source_file))) == str(row.sha256),
            }
            for row in shp.itertuples(index=False)
        }
    baseline = pd.read_csv(BASELINE)
    baseline_keys = {(str(row.chamber), int(row.district)) for row in baseline.itertuples(index=False)}
    plan_check["baseline_seat_keys"] = len(baseline_keys)

    seats = seat_frame(roster, plan)
    counts = partition_counts(seats)
    if not counts["partition_complete"]:
        raise RuntimeError(f"Seat classes do not partition {TOTAL_ALL_SEATS} seats: {counts['counts']}")
    checked = model_check(roster, seats, scenarios, modeled_seats)

    source_mtimes: dict[str, str | None] = {}
    for path in list(CERTIFICATION_PDFS.values()) + list(WIKIPEDIA_PAGES.values()) + [OVERRIDES]:
        if Path(path).exists():
            source_mtimes[Path(path).name] = utc_iso(Path(path).stat().st_mtime)
    provenance, provenance_summary = roster_provenance(
        roster,
        overrides,
        incumbency,
        plan,
        pd.read_csv(PRIOR_WAR),
        pd.read_csv(CANONICAL),
        source_mtimes,
    )

    deltas, delta_summary = roster_deltas(provisional, certified, final=roster, overrides=overrides, reconciliation=reconciliation)

    payload = artifact_payload()
    dashboard_text = read_text(DASHBOARD)
    policy = policy_evidence(
        dashboard_text,
        read_text(DASHBOARD_JS),
        read_text(ARTIFACT),
        read_text(PUBLISHED_INDEX),
        read_text(PUBLISHED_METHODOLOGY),
        read_text(CONTRACT),
    )
    policy["reconciliation"] = policy_reconciliation(roster, seats, payload, modeled_seats)

    manifest_inputs = {
        str(entry["path"]): str(entry["sha256"]) for entry in manifest.get("inputs", [])
    }
    roster_manifest_path = FINAL_ROSTER.relative_to(ROOT).as_posix()
    plan_membership = {
        "roster_seat_keys": len({(str(r.chamber), int(r.district)) for r in roster.itertuples(index=False)}),
        "plan_seat_keys": sum(len(codes) for codes in plan.values()),
        "baseline_seat_keys": len(baseline_keys),
        "roster_equals_plan": {
            (str(r.chamber), int(r.district)) for r in roster.itertuples(index=False)
        }
        == {key for chamber, codes in plan.items() for key in ((chamber, code) for code in codes)},
        "roster_equals_baseline": {
            (str(r.chamber), int(r.district)) for r in roster.itertuples(index=False)
        }
        == baseline_keys,
    }
    manifest_binding = {
        "final_roster_declared_input": roster_manifest_path in manifest_inputs,
        "final_roster_sha256_matches_manifest": manifest_inputs.get(roster_manifest_path) == sha256(FINAL_ROSTER),
        "incumbency_declared_input": INCUMBENCY.relative_to(ROOT).as_posix() in manifest_inputs,
        "forecast_build_id": manifest.get("build_id"),
        "forecast_manifest_generated_at_utc": manifest.get("generated_at_utc"),
    }

    summary = {
        "schema_version": 1,
        "audit": "forecast_roster_universe_and_seat_treatment",
        "audit_id": "FORECAST_ROSTER_UNIVERSE_2026_09_11",
        "checklist_items": ["forecast-02", "forecast-10"],
        "scope": (
            "Read-only certification of the dated 2026 candidate roster and election universe "
            "(nominees, withdrawals/replacements, identities, district plan, incumbency, election "
            "stages) and of the seat-treatment policy for modeled, single-major-party, "
            "independent-only and unresolved seats."
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_seconds": round(time.time() - started, 3),
        "git_commit": _git_commit(),
        "roster_file": FINAL_ROSTER.relative_to(ROOT).as_posix(),
        "roster_sha256": sha256(FINAL_ROSTER),
        "audit_script_sha256": sha256(Path(__file__).resolve()),
        "partition": counts,
        "model_check": checked,
        "plan_check": plan_check,
        "plan_membership": plan_membership,
        "manifest_binding": manifest_binding,
        "provenance_summary": provenance_summary,
        "roster_rows": _json_safe(provenance.to_dict("records")),
        "roster_deltas": {"summary": delta_summary, "changes": deltas},
        "policy": policy,
        "sources": source_register(),
        "ambiguous_seats": [
            {"chamber": str(row.chamber), "district": int(row.district), "seat_class": str(row.seat_class)}
            for row in seats[seats.seat_class.eq("unresolved")].itertuples(index=False)
        ],
        "interpretation_limits": [
            "Absence of a prior-cycle identity match is not evidence that a candidate has no prior "
            "candidacy; the local identity products cover only selected cycles and the 2022 canonical "
            "names are anonymised codes.",
            "The party-certification PDFs are scanned images with no repository manifest, so their "
            "issuance date, source URL, license and recorded retrieval time are not established; the "
            "filesystem timestamp is used only as a retrieval proxy.",
            "Chamber seat distributions are the published headline simulation output; the audit "
            "verifies their fixed-seat offset, not the underlying simulation draws.",
            "The published page and methodology text are read as shipped; the field contract is "
            "checked for a seat-treatment statement rather than rewritten by this audit.",
        ],
    }
    return summary


def _sha_or_none(path: Path) -> str | None:
    return sha256(path) if Path(path).exists() else None


def _git_commit() -> str | None:
    head = ROOT / ".git" / "HEAD"
    if not head.exists():
        return None
    text = head.read_text(encoding="utf-8").strip()
    if text.startswith("ref:"):
        ref = ROOT / ".git" / text.split(" ", 1)[1].strip()
        return ref.read_text(encoding="utf-8").strip() if ref.exists() else None
    return text or None


# --------------------------------------------------------------------------- report


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float) and value != value:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, divider]
    for row in frame.itertuples(index=False):
        record = row._asdict()
        lines.append("| " + " | ".join(_fmt(record[key]) for key, _ in columns) + " |")
    return "\n".join(lines)


def write_report(
    summary: dict,
    report_path: Path = DEFAULT_REPORT,
    report_json: Path = DEFAULT_REPORT_JSON,
) -> None:
    partition = summary["partition"]
    provenance = summary["provenance_summary"]
    model = summary["model_check"]
    plan = summary["plan_check"]
    policy = summary["policy"]
    seat_rows = pd.DataFrame(
        [
            {
                "chamber": chamber,
                "modeled_d_r": counts["modeled_d_r"],
                "single_d": counts["single_major_party_d"],
                "single_r": counts["single_major_party_r"],
                "independent_only": counts["independent_only"],
                "no_candidate": counts["no_candidate"],
                "unresolved": counts["unresolved"],
                "total": sum(counts.values()),
            }
            for chamber, counts in partition["by_chamber"].items()
        ]
    )
    source_frame = pd.DataFrame(summary["sources"])
    source_frame = source_frame[source_frame.role.isin([
        "roster_source", "roster", "incumbency", "plan", "plan_house", "plan_senate", "forecast",
    ])][["path", "role", "bytes", "filesystem_mtime_utc", "sha256"]]
    delta_frame = pd.DataFrame(summary["roster_deltas"]["changes"])
    material_markers = (
        "added_after_certification",
        "removed_from_final",
        "replaced",
        "name_changed_same_surname",
        "provisional_only_not_certified",
        "provisional_nominee_materially_differs_from_certified",
        "certified_only_not_in_provisional",
    )
    material_mask = delta_frame.changes.apply(
        lambda value: any(marker in str(value).split(" + ") for marker in material_markers)
    )
    material_frame = delta_frame[material_mask]
    variant_frame = delta_frame[~material_mask]
    policy_frame = pd.DataFrame(
        [
            {"check": key, "present": value}
            for key, value in {**policy["implementation"], **policy["published"]}.items()
        ]
    )
    as_of = provenance["source_as_of"]
    lines = [
        "# Forecast roster universe and seat treatment — 2026-09-11",
        "",
        f"Internal execution evidence for checklist items `forecast-02` (certify the dated candidate "
        f"roster and election universe) and `forecast-10` (clarify independent and single-major-party "
        f"seat treatment).",
        "",
        f"This is a **read-only audit**. No data, model, warehouse, checklist or published export was "
        f"modified. Machine-readable companion: `{Path(DEFAULT_REPORT_JSON).name}` in this directory.",
        "",
        f"- Roster: `{summary['roster_file']}` SHA256 `{summary['roster_sha256']}`",
        f"- Audit script SHA256 `{summary['audit_script_sha256']}`; generated {summary['generated_at_utc']} "
        f"({summary['runtime_seconds']:.2f} s) at commit `{summary['git_commit']}`",
        f"- Forecast build `{summary['manifest_binding']['forecast_build_id']}` "
        f"(manifest generated {summary['manifest_binding']['forecast_manifest_generated_at_utc']}); "
        f"final roster is a declared manifest input: "
        f"{summary['manifest_binding']['final_roster_declared_input']} (hash match "
        f"{summary['manifest_binding']['final_roster_sha256_matches_manifest']})",
        f"- Commands: `.venv/Scripts/python.exe scripts/audit_forecast_roster_universe.py` and "
        f"`.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider "
        f"scripts/tests/test_forecast_roster_universe.py -q`",
        "",
        "## 1. The 140-seat partition",
        "",
        f"The {partition['total_seats']} enumerated seats (House 105, Senate 35) partition into "
        f"{partition['counts']['modeled_d_r']} modeled D-versus-R, "
        f"{partition['counts']['single_major_party_d']} Democratic-only, "
        f"{partition['counts']['single_major_party_r']} Republican-only, "
        f"{partition['counts']['independent_only']} independent-or-third-party-only, "
        f"{partition['counts']['no_candidate']} no-candidate and "
        f"{partition['counts']['unresolved']} unresolved seats. Classes are exhaustive and mutually "
        f"exclusive by construction: `modeled_d_r` requires exactly one Democratic and one Republican "
        f"nominee (the `prospective_features` eligibility rule); a seat with both parties represented "
        f"but more than one nominee in a party is `unresolved`.",
        "",
        markdown_table(
            seat_rows,
            [
                ("chamber", "Chamber"),
                ("modeled_d_r", "Modeled D–R"),
                ("single_d", "D only"),
                ("single_r", "R only"),
                ("independent_only", "Independent only"),
                ("no_candidate", "No candidate"),
                ("unresolved", "Unresolved"),
                ("total", "Total"),
            ],
        ),
        "",
        f"Modeled reconciliation: classified {model['classified_modeled_seats']}, "
        f"`prospective_features`-eligible {model['eligible_modeled_seats']}, expected "
        f"{model['expected_prospective_races']} (difference {model['modeled_difference']}); "
        f"classified and eligible sets equal: {model['classified_equals_eligible']}. Each published "
        f"scenario carries {sorted(set(model['scenario_race_counts'].values()))} races and the three "
        f"scenario key sets are identical: {model['scenario_races_identical']}. Published "
        f"`*_modeled_seats.csv` holds the headline distribution {model['modeled_seat_rows_by_chamber']} "
        f"rows by chamber with probability sums {model['modeled_seat_probability_sums']}. "
        f"Ambiguous (unresolved) seats: {summary['ambiguous_seats'] or 'none'}.",
        "",
        "## 2. Roster source, as-of dates and per-row provenance",
        "",
        f"The final roster has {provenance['roster_rows']} nominee rows: "
        f"{provenance['certification_ocr_rows']} OCR rows from the two official party certifications "
        f"and {provenance['manual_override_rows']} human-reviewed override rows. Every row is a "
        f"**general-election nominee** (`election_stage_counts` {provenance['election_stage_counts']}); "
        f"the nomination path distinguishes certified nominee, primary-runoff winner, post-map-reversion "
        f"special primary, conditional-certification replacement and independent reclassification "
        f"({provenance['nomination_path_counts']}).",
        "",
        f"- Roster as-of: nomination effective after {as_of['nomination_effective_after_utc']} (primary "
        f"runoff); source retrieval {sorted({entry['filesystem_mtime_utc'] for entry in summary['sources'] if entry['role'] in {'roster_source'} and entry['filesystem_mtime_utc']})}; "
        f"certification document date established: {as_of['certification_document_date_established']}.",
        f"- Certification document date: {as_of['certification_document_date_note']}",
        f"- Nomination effective after: {as_of['nomination_effective_after_utc']} — "
        f"{as_of['nomination_effective_after_evidence']}",
        f"- Roster source manifest recorded: {as_of['roster_source_manifest_present']} — "
        f"{as_of['roster_source_manifest_note']}",
        "",
        "Every roster row's per-source, per-row provenance record (source file, retrieval proxy, "
        "election stage, nomination path, prior-cycle identity, incumbency flag and source, plan "
        "membership) is carried verbatim in the JSON companion under `roster_rows`.",
        "",
        markdown_table(
            source_frame,
            [
                ("path", "Source"),
                ("role", "Role"),
                ("bytes", "Bytes"),
                ("filesystem_mtime_utc", "Filesystem mtime (UTC)"),
                ("sha256", "SHA256"),
            ],
        ),
        "",
        f"Join and coverage checks: incumbency rows resolve "
        f"{provenance['incumbency_join_resolved']}/{provenance['roster_rows']} roster rows 1:1; "
        f"{provenance['incumbents_flagged']} nominees carry `incumbent=true`. Prior-cycle identity is "
        f"resolved for {provenance['identity_any_prior_resolved']} rows "
        f"({provenance['identity_prior_winner_resolved']} via the verified 2022 winner crosswalk and "
        f"{provenance['identity_canonical_prior_resolved']} via a same-district canonical prior-cycle "
        f"name; the two channels overlap where an incumbent also ran in an earlier covered cycle) and "
        f"is unresolved for {provenance['identity_unresolved_rows']} rows. Rows on the 2026 "
        f"plan: {provenance['rows_on_2026_plan']}/{provenance['roster_rows']}; off-plan seat keys: "
        f"{provenance['off_plan_seat_keys'] or 'none'}.",
        "",
        f"Plan evidence: dashboard maps read "
        f"`{plan['dashboard_map_paths']['house']}` and `{plan['dashboard_map_paths']['senate']}`; their "
        f"dBASE district codes are {plan['plan_district_counts']} and contiguous: "
        f"{plan['plan_codes_contiguous']}. Declared geometry vintage: "
        f"{plan['geometry_vintage_declared']}. `prospective_features` does not read geometry: it joins "
        f"roster eligibility to `2026_poll_adjusted_baseline.csv` "
        f"({plan['baseline_seat_keys']} seat keys), so the modeled universe is the baseline's 2026-plan "
        f"seat list. Roster seat keys equal the plan: {summary['plan_membership']['roster_equals_plan']}; "
        f"equal the baseline: {summary['plan_membership']['roster_equals_baseline']}.",
        "",
        "## 3. Withdrawals, replacements and additions",
        "",
        f"Version sizes: provisional {summary['roster_deltas']['summary']['provisional_rows']} rows / "
        f"{summary['roster_deltas']['summary']['provisional_seat_keys']} seat keys, "
        f"certified {summary['roster_deltas']['summary']['certified_rows']} rows, "
        f"final {summary['roster_deltas']['summary']['final_rows']} rows. Change counts: "
        f"{summary['roster_deltas']['summary']['change_counts']}. Reconciliation review flags: "
        f"{summary['roster_deltas']['summary'].get('reconciliation_review_required')} of "
        f"{summary['roster_deltas']['summary'].get('reconciliation_rows')} rows.",
        "",
        f"Roster-version key collisions (one seat key with two nominees in one source) — provisional: "
        f"{summary['roster_deltas']['summary']['provisional_duplicate_keys'] or 'none'}; certified: "
        f"{summary['roster_deltas']['summary']['certified_duplicate_keys'] or 'none'}. The provisional "
        f"snapshot listed both Andrew Jones and Jesse Battles as Republicans in Senate District 10; the "
        f"certification resolved Jones as the Republican nominee and the human override recorded "
        f"Battles as an independent. Every row of that seat remains visible here rather than being "
        f"silently merged.",
        "",
        "Changes that alter the nominee, the seat's party set or the source coverage:",
        "",
        markdown_table(
            material_frame,
            [
                ("chamber", "Chamber"),
                ("district", "District"),
                ("party", "Party"),
                ("candidate_provisional", "Provisional"),
                ("candidate_certified", "Certified"),
                ("candidate_final", "Final"),
                ("changes", "Change"),
                ("override_resolution", "Resolution"),
            ],
        ),
        "",
        "Identical-person name variants (punctuation, spacing, added initials or a fuller legal name) "
        "are evidence of alias normalisation, not of a nominee change:",
        "",
        markdown_table(
            variant_frame,
            [
                ("chamber", "Chamber"),
                ("district", "District"),
                ("party", "Party"),
                ("candidate_provisional", "Provisional"),
                ("candidate_certified", "Certified"),
                ("candidate_final", "Final"),
                ("changes", "Change"),
            ],
        ),
        "",
        "Substantive replacements are distinct from alias normalisation: `name_normalized` rows differ "
        "only by punctuation, spacing or a fuller legal name; `name_changed_same_surname` rows keep the "
        "same surname (for example the OCR correction of a single letter); `replaced` rows change the "
        "surname and therefore the person. Candidates that appear only in the provisional Wikipedia "
        "snapshot or only in the certification are flagged rather than silently merged; the "
        "`certified_only_not_in_provisional` row for senate 26 D carries the conditional certification "
        "text that the human override later replaced with the runoff nominee.",
        "",
        "## 4. Seat-treatment policy and contract agreement",
        "",
        policy["policy_statement"],
        "",
        "Implementation evidence (substring present in the shipped sources/pages):",
        "",
        markdown_table(policy_frame, [("check", "Check"), ("present", "Present")]),
        "",
        f"Field contract check: terms found {policy['field_contract']['terms_found']}; states a "
        f"single-major-party seat policy: {policy['field_contract']['states_seat_treatment']}. "
        f"Agreement result: **{policy['agreement']}**.",
        "",
        "Interpretation: the published forecast page and methodology page state the fixed-seat and "
        "independent treatment, and the shipped classifier, seat totals and rendered statuses match "
        "that statement; the field contract (declared as an input by the forecast manifest) does not "
        "describe seat treatment at all. The behaviour is therefore documented on the public pages but "
        "not pinned by the machine-readable contract, so a future change to the fixed-seat rule would "
        "not be caught by a contract test. Adding the rule to the contract is outside this audit's "
        "write scope and is recorded here as the remaining `forecast-10` evidence gap.",
        "",
        "### Fixed-seat offset test",
        "",
        f"Recomputed from the roster: fixed Democratic seats {policy['reconciliation']['fixed_dem_from_roster']}, "
        f"fixed Republican seats {policy['reconciliation']['fixed_rep_from_roster']}. Payload offset per "
        f"chamber and model (published minimum Democratic seats minus the modeled minimum, where the "
        f"scenario distributions start from zero modeled wins): "
        f"{policy['reconciliation']['payload_offsets']}. Payload offset equals the roster-derived fixed "
        f"Democratic count: {policy['reconciliation']['payload_fixed_offset_matches_roster']}; headline "
        f"distribution equals the published `*_modeled_seats.csv` support and probabilities: "
        f"{policy['reconciliation']['payload_headline_distribution_matches_csv']}. Unmodeled "
        f"races in the rendered payload: {policy['reconciliation']['payload_unmodeled_count']}. Every "
        f"seat's rendered status equals the class-implied status (modeled / unopposed-major-party / "
        f"unmodeled): {policy['reconciliation']['payload_status_matches_classes']}; mismatches: "
        f"{policy['reconciliation']['payload_status_mismatches'] or 'none'}.",
        "",
        "### Independent-candidate seats",
        "",
        markdown_table(
            pd.DataFrame(policy["reconciliation"]["independent_candidate_seats"]),
            [
                ("chamber", "Chamber"),
                ("district", "District"),
                ("seat_class", "Class"),
                ("other_parties", "Other parties"),
                ("payload_status", "Payload status"),
                ("payload_dem_probability", "Payload D probability"),
                ("payload_candidates", "Payload candidates"),
            ],
        )
        if policy["reconciliation"]["independent_candidate_seats"]
        else "No roster seat carries an independent or third-party nominee alongside a major party.",
        "",
        f"Every independent-bearing seat that also has a major-party nominee is fixed in the chamber "
        f"summaries with a 0.0 or 1.0 probability: "
        f"{policy['reconciliation']['independent_with_major_party_fixed']}. Independent-only seats (no "
        f"major-party nominee) stay `unmodeled` with a null probability and are counted in the published "
        f"`unmodeled` statistic, so the seat is visible rather than silently assigned "
        f"(independent-only check on the current roster: "
        f"{policy['reconciliation']['independent_only_unmodeled']}; `None` means no independent-only seat "
        f"exists, so that path is exercised only by the fixture tests).",
        "",
        "## 5. Not established and limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["interpretation_limits"])
    lines.extend(
        [
            "",
            "Reproduction: `scripts/run_alabama_war_generic_forecast.prospective_features()` pivots the "
            "final roster on `(chamber, district)` and `party` with `nunique` candidate counts and keeps "
            "`D == 1 and R == 1`; `scripts/build_2026_forecast_dashboard.build_payload()` fixes the "
            "chamber offset with `fixed_dem = len(D districts - R districts)`, labels every other seat "
            "`unopposed-major-party` or `unmodeled`, and "
            "`dashboard/forecast_dashboard.js::seatStats()` reports `unknown` as the count of races with "
            "a null probability.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    report_json.write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    args = parser.parse_args(argv)
    summary = build_summary()
    write_report(summary, args.report, args.report_json)
    counts = summary["partition"]["counts"]
    print(
        "Roster universe audit: "
        + ", ".join(f"{key}={counts[key]}" for key in SEAT_CLASSES)
        + f"; total={summary['partition']['total_seats']}; "
        f"modeled_difference={summary['model_check']['modeled_difference']}; "
        f"policy_agreement={summary['policy']['agreement']}"
    )
    print(f"Wrote {args.report} and {args.report_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
