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

NON_GEOGRAPHIC_RE = re.compile(
    r"\b(ABSENTEE|PROVISIONAL|FAILSAFE|OVERSEAS|UOCAVA|TOTAL|TOTALS|ELECTION SYSTEMS)\b"
)

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
    return data
