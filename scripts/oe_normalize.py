"""Shared normalization for Alabama OpenElections precinct CSVs.

Every cycle sourced from openelections-data-al goes through this module so
party mapping, pseudo-candidate detection, and precinct-name normalization
are identical across cycles instead of being redefined per script.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

PARTY_MAP = {
    "D": "D",
    "DEM": "D",
    "DEMOCRAT": "D",
    "R": "R",
    "REP": "R",
    "REPUBLICAN": "R",
}

PSEUDOCANDIDATE_RE = re.compile(r"Over Votes|Under Votes|Write", re.IGNORECASE)

# Two kinds of row in these files are not a named polling place, and they must
# be treated in OPPOSITE ways. A single combined pattern (the former
# NON_GEOGRAPHIC_RE) conflated them and silently deleted 303,177 real 2020
# presidential votes -- ~13% of the electorate, ~65% Democratic, enough to move
# the statewide two-party margin 8.8 points and flip the sign of the downstream
# presidential-swing feature. Keep them separate.

# 1. Literal duplicates. A "TOTAL" / "CALCULATED TOTALS" / "REPORTED TOTALS"
#    precinct row restates the sum of that county's real precinct rows, so
#    counting it double-counts the whole county. Dropped in load_oe() below, on
#    behalf of every caller.
SUMMARY_ROW_RE = re.compile(r"\bTOTALS?\b")

# 2. Real, distinct ballots reported at county level rather than at a named
#    polling place. These must be RETAINED and redistributed within their county
#    downstream -- never dropped, and never name-matched against a target
#    precinct list, since both source and target files can contain a precinct
#    literally named "ABSENTEE" and matching them to each other would allocate a
#    whole county's ballots by one unrepresentative sliver of activity.
COUNTY_LEVEL_BALLOT_RE = re.compile(r"\b(ABSENTEE|PROVISIONAL|FAILSAFE|OVERSEAS|UOCAVA)\b")


def is_county_level_ballot(precinct: object) -> bool:
    """True for county-level ballot batches (absentee, provisional, ...)."""
    return bool(COUNTY_LEVEL_BALLOT_RE.search(str(precinct).upper()))

TOKEN_REPLACEMENTS = {
    "1ST": "FIRST",
    "CTR": "CENTER",
    "CNTR": "CENTER",
    "COMM": "COMMUNITY",
    "DEPT": "DEPARTMENT",
    "DEPTMENT": "DEPARTMENT",
    "FD": "FIRE DEPARTMENT",
    "VFD": "VOLUNTEER FIRE DEPARTMENT",
    "VOL": "VOLUNTEER",
    "BAPT": "BAPTIST",
    "CH": "CHURCH",
    "CHUR": "CHURCH",
    "ELEM": "ELEMENTARY",
    "SCH": "SCHOOL",
    "MT": "MOUNT",
    "ST": "SAINT",
    "CO": "COUNTY",
    "CTY": "COUNTY",
    "REC": "RECREATION",
    "BLDG": "BUILDING",
}


def norm_party(value: object) -> str:
    return PARTY_MAP.get(str(value).strip().upper(), "O")


def is_pseudocandidate(candidate: object) -> bool:
    return bool(PSEUDOCANDIDATE_RE.search(str(candidate)))


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = text.upper().replace("&", " AND ")
    text = re.sub(r"[_/\\\-]+", " ", text)
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    tokens: list[str] = []
    for token in text.split():
        token = str(int(token)) if token.isdigit() else token
        tokens.extend(TOKEN_REPLACEMENTS.get(token, token).split())
    return " ".join(tokens)


def normalize_for_match(value: object) -> str:
    """Normalize a precinct name while stripping codes and machine suffixes."""
    text = str(value).strip()
    text = re.sub(r"^\s*\d{3,4}\s*[-:]?\s*", "", text)
    text = re.sub(r"\s*#\s*\d+\s*$", "", text)
    text = re.sub(r"\s+(?:BOX|BX)\s*\d+\s*$", "", text, flags=re.I)
    text = re.sub(r"\s+[123]\s*$", "", text)
    return normalize_name(text)


def load_oe(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, low_memory=False)
    data["votes"] = pd.to_numeric(data["votes"], errors="coerce").fillna(0.0)
    data["district"] = pd.to_numeric(data["district"], errors="coerce")
    data["party_norm"] = data["party"].map(norm_party)
    data["county_key"] = data["county"].astype(str).str.upper().str.strip()
    data["precinct_key"] = data["precinct"].astype(str).str.upper().str.strip()
    # Drop county-level summary rows once, here, so no caller can accidentally
    # double-count a county by summing its precinct rows plus its own restated
    # total. Affects the 2012 file ("TOTAL") and the 2014 file ("TOTAL",
    # "CALCULATED TOTALS", "REPORTED TOTALS", "TOTAL OF REGISTERED VOTERS");
    # 2016/2018/2020 contain no such rows.
    data = data[~data["precinct_key"].str.contains(SUMMARY_ROW_RE, na=False)]
    return data.reset_index(drop=True)
