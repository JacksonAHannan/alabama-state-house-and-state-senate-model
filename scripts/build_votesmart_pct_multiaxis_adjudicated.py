"""Combine automatic and manual Vote Smart v2 adjudications for auditing."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from serve_votesmart_adjudication import AUTO, MANUAL
from votesmart_position_ontology import ONTOLOGY_VERSION, validate_effect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "ideology" / "votesmart_pct_multiaxis_v2_adjudications.csv"
EFFECT_OUT = ROOT / "data" / "processed" / "ideology" / "votesmart_pct_multiaxis_v2_effects.csv"


def main() -> None:
    automatic = pd.read_csv(AUTO).fillna("")
    manual = pd.read_csv(MANUAL).fillna("")
    automatic = automatic[~automatic.review_id.isin(set(manual.review_id))]
    automatic["adjudication_authority"] = "model_consensus_provisional"
    manual["adjudication_authority"] = "direct_text_review"
    combined = pd.concat([automatic, manual], ignore_index=True, sort=False)
    if len(combined) != 114 or combined.review_id.nunique() != 114:
        raise ValueError("expected exactly 114 unique adjudications")
    if combined.ontology_version.astype(str).ne(ONTOLOGY_VERSION).any():
        raise ValueError("mixed ontology versions")
    effect_rows = []
    for row in combined.itertuples(index=False):
        for position_effect in json.loads(row.effects_json or "[]"):
            validate_effect(position_effect)
            effect_rows.append({
                "ontology_version": ONTOLOGY_VERSION, "review_id": row.review_id,
                "election_year": row.election_year, "option_text": getattr(row, "option_text", ""),
                "primary_domain": row.primary_domain, "policy_key": row.policy_key,
                "response_mode": getattr(row, "response_mode", "") or "binary",
                "adjudication_authority": row.adjudication_authority, **position_effect,
            })
    combined.to_csv(OUT, index=False)
    pd.DataFrame(effect_rows).to_csv(EFFECT_OUT, index=False)
    print(f"Adjudications: {len(combined)} ({len(manual)} direct; {len(automatic)} provisional)")
    print(f"Position effects: {len(effect_rows)}")
    print("Provisional model-consensus rows remain ineligible for final CMO scoring.")


if __name__ == "__main__":
    main()
