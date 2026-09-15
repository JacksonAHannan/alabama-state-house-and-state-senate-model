#!/usr/bin/env python3
"""Aggregate Alabama candidate-cycle WAR into career cumulative WAR per person.

Owner decision Q14: single-cycle WAR under the lag specification credits the
first defiant cycle fully and later ones only net of the decayed prior gap, so a
legislator who beat partisan gravity for five straight cycles shows one large
WAR and several small ones. Career cumulative WAR is the quantity that expresses
"defied gravity for longer than expected".

Identity needs care: 2022 canonical rows carry source stubs
(`ALPERSON-GSL003DTHO`) that do not link to earlier cycles, so a career keyed on
`person_id` alone would silently split. Stubs are folded into an earlier person
only when the normalized name matches exactly one of them; the method used is
recorded per person and never guessed.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "data" / "processed" / "war" / "alabama_historical_war_v1"
SOURCE = HISTORICAL / "candidate_cycle_war.csv"
SOURCE_MANIFEST = HISTORICAL / "manifest.json"
OUT = ROOT / "data" / "processed" / "war" / "alabama_career_war_v1"
STUB = re.compile(r"^ALPERSON-[A-Z]{3}\d{3}[A-Z]{4,}$")
SUFFIXES = re.compile(r"\b(JR|SR|II|III|IV|DR|MR|MRS|MS)\b")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"[^A-Z ]", " ", text)
    return " ".join(SUFFIXES.sub(" ", text).split())


def resolve_identity(frame: pd.DataFrame) -> pd.DataFrame:
    """Fold stub identifiers into an earlier person only on an exact unique name."""
    frame = frame.copy()
    frame["match_name"] = frame.canonical_name.map(normalize)
    stable = frame[~frame.person_id.astype(str).str.fullmatch(STUB, na=False)]
    unique_names = (stable.groupby("match_name").person_id.nunique()
                    .loc[lambda s: s.eq(1)].index)
    lookup = (stable[stable.match_name.isin(unique_names)]
              .drop_duplicates("match_name").set_index("match_name").person_id)
    is_stub = frame.person_id.astype(str).str.fullmatch(STUB, na=False)
    folded = frame.match_name.map(lookup)
    frame["career_person_id"] = frame.person_id.where(~is_stub | folded.isna(), folded)
    frame["career_identity_method"] = "canonical_person_id"
    frame.loc[is_stub & folded.notna(), "career_identity_method"] = "stub_folded_by_exact_unique_name"
    frame.loc[is_stub & folded.isna(), "career_identity_method"] = "unresolved_source_stub"
    return frame


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = pd.read_csv(SOURCE, low_memory=False)
    scored = candidates[candidates.candidate_cycle_war.notna()].copy()
    resolved = resolve_identity(scored)
    career = (resolved.sort_values("cycle").groupby("career_person_id")
              .agg(display_name=("canonical_name", "last"),
                   canonical_party=("canonical_party", "last"),
                   cycles_scored=("cycle", "size"),
                   first_cycle=("cycle", "min"), last_cycle=("cycle", "max"),
                   chambers=("chamber", lambda s: "/".join(sorted(set(s)))),
                   career_war=("candidate_cycle_war", "sum"),
                   mean_cycle_war=("candidate_cycle_war", "mean"),
                   best_cycle_war=("candidate_cycle_war", "max"),
                   worst_cycle_war=("candidate_cycle_war", "min"),
                   identity_methods=("career_identity_method", lambda s: "/".join(sorted(set(s)))))
              .reset_index())
    career["career_span_years"] = career.last_cycle - career.first_cycle
    career = career.sort_values("career_war", ascending=False).reset_index(drop=True)
    return career, resolved


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    career, resolved = build()
    career.to_csv(OUT / "career_war.csv", index=False)
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    manifest = {
        "career_war_version": "alabama_career_war_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "historical_war_run_id": source_manifest["historical_war_run_id"],
        "definition": "career_war = sum of a person's scored candidate-cycle WAR, in two-party margin points",
        "identity_rule": ("canonical person_id; 2022 source stubs are folded into an earlier person only when "
                          "the normalized name matches exactly one of them, otherwise left unresolved"),
        "inputs": [{"path": str(SOURCE.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(SOURCE)}],
        "outputs": [{"path": "data/processed/war/alabama_career_war_v1/career_war.csv",
                     "rows": int(len(career)), "sha256": sha256(OUT / "career_war.csv")}],
        "diagnostics": {
            "people": int(len(career)),
            "scored_candidate_cycles": int(len(resolved)),
            "multi_cycle_people": int(career.cycles_scored.gt(1).sum()),
            "identity_methods": resolved.career_identity_method.value_counts().to_dict(),
            "max_career_war": float(career.career_war.max()),
            "min_career_war": float(career.career_war.min()),
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{len(career)} careers from {len(resolved)} scored candidate-cycles; "
          f"{int(career.cycles_scored.gt(1).sum())} span more than one cycle")
    print(career.head(8)[["display_name", "canonical_party", "cycles_scored", "career_war"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
