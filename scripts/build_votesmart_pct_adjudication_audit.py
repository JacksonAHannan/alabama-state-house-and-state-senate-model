"""Combine deterministic decisions and local-model reviews into one audit table."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
ITEMS = IDEOLOGY / "votesmart_pct_item_crosswalk.csv"
GROUP_MODELS = IDEOLOGY / "votesmart_pct_group_llm_classifications.csv"
OUT = IDEOLOGY / "votesmart_pct_adjudication_audit.csv"


def normalize(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return re.sub(r"^(?:[a-z]|[0-9]+)\)\s*", "", text)


def main() -> None:
    items = pd.read_csv(ITEMS)
    items["normalized_option"] = items.option_text.map(normalize)
    models = pd.read_csv(GROUP_MODELS)
    fields = ["dimension", "affirmative_direction", "scorable"]
    reviews = []
    for option, group in models.groupby("normalized_option"):
        two_models = group.model.nunique() >= 2
        agree = two_models and all(group[field].nunique(dropna=False) == 1 for field in fields)
        qwen = group[group.model.eq("qwen3.5:9b")]
        reviews.append({
            "normalized_option": option, "models_run": group.model.nunique(),
            "model_core_agreement": agree,
            "model_agreed_dimension": group.iloc[0].dimension if agree else "",
            "model_agreed_direction": group.iloc[0].affirmative_direction if agree else None,
            "model_agreed_scorable": group.iloc[0].scorable if agree else None,
            "qwen_suggested_scorable": bool(qwen.iloc[0].scorable) if len(qwen) else None,
        })
    audit = items.merge(pd.DataFrame(reviews), on="normalized_option", how="left", validate="many_to_one")
    audit["adjudication_status"] = "unresolved_after_model_review"
    audit.loc[audit.coding_status.eq("rule_mapped"), "adjudication_status"] = "accepted_deterministic_rule"
    audit.loc[audit.coding_status.eq("position_only"), "adjudication_status"] = "accepted_position_only"
    audit.loc[audit.coding_status.eq("non_scorable"), "adjudication_status"] = "accepted_non_scorable"
    remaining = audit.coding_status.eq("unmapped")
    audit.loc[remaining & audit.model_core_agreement.eq(True), "adjudication_status"] = "model_agreement_requires_rule"
    audit.loc[remaining & audit.models_run.ge(2) & ~audit.model_core_agreement.eq(True),
              "adjudication_status"] = "model_disagreement_requires_review"
    audit.loc[remaining & audit.models_run.eq(1) & audit.qwen_suggested_scorable.eq(False),
              "adjudication_status"] = "single_model_nonscorable_requires_review"
    audit.to_csv(OUT, index=False)
    print(audit.adjudication_status.value_counts().to_string())


if __name__ == "__main__":
    main()
