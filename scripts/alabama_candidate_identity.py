"""Publishable names and career identity for Alabama candidates.

The canonical 2022 rows carry source stubs such as `GSL019DHAL` and
`GSU33DFIG` instead of names, and their `person_id` values do not link to any
earlier cycle. Three products need the same two answers - what do we call this
person, and is this the same person as that earlier row - so they are answered
here once instead of three times.

Names come from the verified adjudications in `candidate_research_aliases.csv`;
the 2022 stubs were resolved against the registered SOS precinct archive, where
each stub's own surname prefix matches the printed label and the observed
precinct subtotal equals the canonical total exactly.

Nothing here guesses. A stub with no verified alias keeps its unresolved state,
and a career is folded across cycles only when the resolved name matches exactly
one earlier person.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ALIASES = ROOT / "data" / "manual" / "ideology" / "candidate_research_aliases.csv"

# Source stubs: chamber letter, two- or three-digit district, party, surname prefix.
NAME_STUB = re.compile(r"^GS[LU]\d{2,3}[A-Z][A-Z]{3}$")
PERSON_STUB = re.compile(r"^ALPERSON-GS[LU]\d{2,3}[A-Z][A-Z]{3}$")
# The older identifier shape retained for pre-2022 source rows.
LEGACY_ID = re.compile(r"^[A-Z]{3}\d{3}[A-Z]{4,}$")
SUFFIXES = re.compile(r"\b(JR|SR|II|III|IV|DR|MR|MRS|MS)\b")


def is_stub_name(value: object) -> bool:
    text = str(value).strip()
    return bool(NAME_STUB.fullmatch(text) or LEGACY_ID.fullmatch(text))


def is_stub_person(value: object) -> bool:
    return bool(PERSON_STUB.fullmatch(str(value).strip()))


def normalize(name: object) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"[^A-Z ]", " ", text)
    return " ".join(SUFFIXES.sub(" ", text).split())


@lru_cache(maxsize=1)
def verified_aliases() -> dict[str, str]:
    """Adjudicated publishable names, keyed by canonical candidate id."""
    aliases = pd.read_csv(ALIASES, low_memory=False)
    accepted = aliases[aliases.identity_status.astype(str).str.startswith("verified_")]
    if accepted.canonical_candidate_id.duplicated().any():
        raise ValueError("Verified candidate adjudications are not unique")
    return dict(zip(accepted.canonical_candidate_id, accepted.research_name))


def resolve_names(frame: pd.DataFrame, *, id_column: str = "canonical_candidate_id",
                  name_column: str = "canonical_name") -> pd.DataFrame:
    """Add `resolved_name` and `name_source`; stubs without an adjudication stay unresolved."""
    aliases = verified_aliases()
    result = frame.copy()
    stub = result[name_column].map(is_stub_name)
    adjudicated = result[id_column].map(aliases)
    result["resolved_name"] = np.where(stub, adjudicated, result[name_column])
    result["name_source"] = np.where(
        stub & adjudicated.notna(), "verified_adjudication",
        np.where(stub, "unresolved_source_stub", "canonical_election_record"))
    return result


def career_identity(frame: pd.DataFrame, *, person_column: str = "person_id",
                    name_column: str = "resolved_name") -> pd.DataFrame:
    """Add `career_person_id` and `career_identity_method`.

    A stub person is folded into an earlier person only when its resolved name
    matches exactly one of them; ambiguous or unnamed stubs stay separate, which
    understates a career rather than merging two people on a guess.
    """
    result = frame.copy()
    stub = result[person_column].map(is_stub_person)
    stable = result[~stub]
    keys = stable.assign(_key=stable[name_column].map(normalize))
    unique = keys.groupby("_key")[person_column].nunique().loc[lambda s: s.eq(1)].index
    lookup = (keys[keys._key.isin(unique) & keys._key.ne("")]
              .drop_duplicates("_key").set_index("_key")[person_column])
    folded = result[name_column].map(normalize).map(lookup)
    result["career_person_id"] = result[person_column].where(~stub | folded.isna(), folded)
    result["career_identity_method"] = np.where(
        ~stub, "canonical_person_id",
        np.where(folded.notna(), "stub_folded_by_exact_unique_name", "unresolved_source_stub"))
    return result
