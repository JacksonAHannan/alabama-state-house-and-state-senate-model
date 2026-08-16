"""Classify the complete Alabama roll-call archive with auditable rules.

This deliberately separates topic detection from ideological direction.  A bill
can concern guns, taxes, or schools without having a safely inferable left/right
direction.  Human-reviewed anchors always override machine rules; unresolved
records remain visible in a prioritized review queue rather than being forced.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
RESEARCH = ROOT / "research" / "cmo_ideology"
DB = LEG / "alabama_legislative_rollcalls_1998_2026.sqlite"

# Ordered, intentionally conservative vocabulary.  First matching issue wins;
# all matching issues are retained in issue_codes for later multi-label work.
ISSUES: dict[str, tuple[str, ...]] = {
    "abortion": (r"\babortion\b", r"unborn child", r"fetal remains", r"dilation and evacuation"),
    "guns": (r"\bfirearms?\b", r"\bhandguns?\b", r"concealed carry", r"second amendment", r"pistol permit"),
    "labor_unions": (r"labor union", r"collective bargaining", r"right[- ]to[- ]work", r"prevailing wage"),
    "taxes_budget": (r"\btax(?:es|ation)?\b", r"tax credit", r"appropriat", r"general fund", r"earmark"),
    "criminal_justice": (r"death penalty", r"capital murder", r"parole", r"sentencing", r"correction", r"\bprison", r"criminal penalt"),
    "immigration": (r"immigra", r"alien status", r"e-verify"),
    "school_choice": (r"charter school", r"education savings account", r"school choice", r"private school.*(credit|scholarship)"),
    "public_education": (r"public schools?", r"education trust fund", r"teachers?'? pay", r"classroom"),
    "healthcare": (r"medicaid", r"health care", r"health insurance", r"hospital"),
    "voting_elections": (r"voter id", r"absentee ballot", r"election law", r"campaign contribution", r"political action committee"),
    "lgbtq_rights": (r"same[- ]sex", r"sexual orientation", r"gender identity", r"transgender"),
    "environment_energy": (r"environmental", r"renewable energy", r"coal mining", r"oil and gas", r"pollution"),
    "business_regulation": (r"occupational licens", r"business license", r"economic development", r"industrial development"),
    "social_services": (r"public assistance", r"food stamp", r"temporary assistance", r"welfare"),
    "ethics_government": (r"ethics commission", r"public corruption", r"lobbyist", r"open meetings", r"campaign finance"),
    "rural_local": (r"rural", r"agricultur", r"farmers?", r"county commission", r"municipal"),
}

# Direction rules require an issue context plus one of these explicit policy
# constructions. +1 is conservative and -1 progressive throughout the project.
DIRECTION_RULES: dict[str, tuple[tuple[int, str, str], ...]] = {
    "abortion": ((1, r"prohibit|ban|criminal|right to life|parental consent", "restricts abortion"),
                 (-1, r"reproductive choice|abortion access|repeal.{0,35}(ban|prohibit)", "expands abortion access")),
    "guns": ((1, r"permitless|constitutional carry|remove.{0,30}(permit|restriction)|right to (keep|bear)", "expands gun rights"),
             (-1, r"background check|safe storage|red flag|prohibit.{0,30}(firearm|weapon)|assault weapon", "adds gun regulation")),
    "labor_unions": ((1, r"right[- ]to[- ]work|prohibit.{0,30}(union|collective bargaining)|repeal.{0,30}prevailing wage", "restricts organized labor"),
                     (-1, r"collective bargaining rights|prevailing wage|union recognition", "expands labor rights")),
    "taxes_budget": ((1, r"tax (cut|reduction|exemption)|reduce.{0,25}tax|repeal.{0,25}tax|spending limit|\bexempt.{0,35}\btax|\btax.{0,35}\bexempt", "reduces taxes or spending"),
                     (-1, r"tax increase|increase.{0,25}tax|lev(?:y|ies|ied|ying).{0,25}tax|expand.{0,25}(funding|appropriation)", "increases revenue or public spending")),
    "criminal_justice": ((1, r"death penalty|mandatory minimum|increase.{0,25}(penalty|sentence)|restrict.{0,25}parole", "increases criminal punishment"),
                         (-1, r"reduce.{0,25}(penalty|sentence)|expung|decriminal|parole reform|rehabilitation|eligib.{0,35}parole|resentenc.{0,35}nonviolent", "reduces punishment or expands rehabilitation")),
    "immigration": ((1, r"e-verify|proof of citizenship|unlawful alien|restrict.{0,30}(alien|immigra)", "restricts immigration-related eligibility"),
                    (-1, r"in-state tuition.{0,30}(immigra|alien)|expand.{0,30}(immigra|alien)", "expands immigrant eligibility")),
    "school_choice": ((1, r"charter school|education savings account|school choice|private school.{0,30}(credit|scholarship)", "expands school choice"),),
    "public_education": ((-1, r"teacher pay (raise|increase)|increase.{0,30}(school|education) funding|fund.{0,25}public schools", "increases public-education investment"),),
    "healthcare": ((-1, r"expand.{0,25}medicaid|medicaid expansion|expand.{0,25}(coverage|insurance)", "expands health coverage"),
                   (1, r"restrict.{0,25}medicaid|work requirement|repeal.{0,25}(coverage|mandate)", "restricts public health coverage")),
    "voting_elections": ((1, r"photo voter id|proof of citizenship|restrict.{0,25}absentee", "tightens voting access"),
                         (-1, r"early voting|same[- ]day registration|expand.{0,25}absentee|automatic voter", "expands voting access")),
    "lgbtq_rights": ((1, r"prohibit.{0,35}(gender|transgender|same[- ]sex)|biological sex|religious freedom", "restricts LGBTQ recognition"),
                     (-1, r"protect.{0,30}(sexual orientation|gender identity)|nondiscrimination|same[- ]sex marriage", "expands LGBTQ protections")),
}

PROCEDURAL = re.compile(r"(motion to (adopt|reconsider|table)|cloture|previous question|budget isolation|reading at length|suspend the rules)", re.I)
FINAL = re.compile(r"(third reading|final passage|passage|concur|override|adopt)", re.I)


def classify_text(title: object, description: object) -> dict[str, object]:
    text = re.sub(r"\s+", " ", f"{title or ''} {description or ''}").strip().lower()
    hits = [issue for issue, patterns in ISSUES.items() if any(re.search(p, text, re.I) for p in patterns)]
    directional: list[tuple[int, str, str]] = []
    for issue in hits:
        for value, pattern, reason in DIRECTION_RULES.get(issue, ()):
            if re.search(pattern, text, re.I):
                directional.append((value, issue, reason))
    values = {x[0] for x in directional}
    if len(values) == 1:
        value = directional[0][0]
        reason = "; ".join(sorted({x[2] for x in directional}))
        status = "rule_directional"
    elif len(values) > 1:
        value, reason, status = np.nan, "conflicting directional rules", "direction_conflict"
    else:
        value, reason = np.nan, "topic detected but direction not safely inferable" if hits else "no ideological topic detected"
        status = "topic_only" if hits else "unclassified"
    return {"issue_code": hits[0] if hits else "", "issue_codes": "|".join(hits),
            "yea_direction": value, "classification_reason": reason, "classification_status": status}


def motion_disposition(description: object) -> str:
    text = str(description or "")
    if PROCEDURAL.search(text) and not re.search(r"final passage|third reading|override", text, re.I):
        return "procedural_or_amendment"
    return "bill_direction_applies" if FINAL.search(text) else "motion_ambiguous"


def extract_historical_synopsis(context: object, bill_type: object, bill_number: object) -> str:
    """Extract the target measure's synopsis from a journal context window.

    Context windows can mention several bills, so extraction is anchored to the
    exact measure identifier and rejects text that is primarily a vote list.
    """
    text = re.sub(r"\s+", " ", str(context or "")).strip()
    try:
        number = str(int(float(bill_number)))
    except (TypeError, ValueError):
        return ""
    kind = str(bill_type or "").upper().strip()
    if kind not in {"HB", "SB", "HJR", "SJR"}:
        return ""
    target = re.escape(kind + number)
    candidates: list[str] = []
    # Prefer the formal synopsis introduced after the exact bill identifier.
    pattern = re.compile(rf"\b{target}\b\s*(?:\([^)]*\)\s*)*:?[ ]*(.*?)(?=(?:\bas amended,?\s+)?was (?:read|taken up)|AMENDMENT (?:OFFERED|ADOPTED|TABLED)|Yeas?\s+\d+|Nays?\s+\d+|<<<PAGE|\bAnd the bill\b|$)", re.I)
    for match in pattern.finditer(text):
        value = match.group(1).strip(" :;,-")
        if 8 <= len(value) <= 12000 and not re.match(r"^(Yea|Nay):", value, re.I):
            candidates.append(value)
    if not candidates:
        return ""
    # Legislative synopses usually begin with To/Relating/Providing. Favor
    # those, then the longest candidate as the most informative fallback.
    candidates.sort(key=lambda x: (bool(re.match(r"^(To|Relating|Providing|Making|Proposing)\b", x, re.I)), len(x)), reverse=True)
    return candidates[0]


def infer_historical_measure(context: object, bill_type: object, bill_number: object) -> tuple[str, object, str]:
    """Prefer formal journal measure markers over incidental statutory citations."""
    text = re.sub(r"\s+", " ", str(context or ""))
    patterns = [
        r"(?:THE BILL|And the bill|And the resolution)\s*[:,]?\s*(HB|SB|HJR|SJR|HR|SR)\s*[- ]?\s*(\d+)",
        r"B\.?\s*I\.?\s*R\.?,?\s*(HB|SB)\s*[- ]?\s*(\d+)",
        r"Budget Isolation Resolution relating to (?:the )?bill,?\s*(HB|SB)\s*[- ]?\s*(\d+)",
    ]
    hits: list[tuple[int, str, int]] = []
    for pattern in patterns:
        hits.extend((m.start(), m.group(1).upper(), int(m.group(2))) for m in re.finditer(pattern, text, re.I))
    if hits:
        _, resolved_type, resolved_number = max(hits, key=lambda x: x[0])
        changed = resolved_type != str(bill_type or "").upper() or resolved_number != pd.to_numeric(bill_number, errors="coerce")
        return resolved_type, resolved_number, "formal_journal_marker_corrected" if changed else "formal_journal_marker_confirmed"
    return str(bill_type or "").upper(), bill_number, "parser_measure_retained_no_formal_marker"


def main() -> None:
    bills = pd.read_csv(LEG / "legiscan_alabama_bills.csv", low_memory=False)
    classified = pd.DataFrame([classify_text(r.title, r.description) for r in bills.itertuples()])
    bills = pd.concat([bills.reset_index(drop=True), classified], axis=1)

    anchors = pd.read_csv(RESEARCH / "anchor_vote_human_codes.csv")
    # A roll call may intentionally have more than one reviewed issue label.
    # The primary issue drives the scalar score while every label is retained.
    anchors = anchors.sort_values(["roll_call_id", "human_issue_code"])
    anchor_labels = anchors.groupby("roll_call_id").human_issue_code.agg(lambda x: "|".join(dict.fromkeys(x))).to_dict()
    anchor_map = anchors.drop_duplicates("roll_call_id").set_index("roll_call_id").to_dict("index")
    rolls = pd.read_csv(LEG / "legiscan_alabama_rollcalls.csv", low_memory=False).merge(
        bills[["bill_id", "bill_number", "title", "description", "issue_code", "issue_codes",
               "yea_direction", "classification_reason", "classification_status"]], on="bill_id", how="left", validate="many_to_one")
    rolls["motion_disposition"] = rolls.vote_description.map(motion_disposition)
    rolls.loc[rolls.motion_disposition.ne("bill_direction_applies"), "yea_direction"] = np.nan
    rolls.loc[rolls.motion_disposition.ne("bill_direction_applies") & rolls.classification_status.eq("rule_directional"), "classification_status"] = "motion_not_directional"
    rolls["classification_source"] = np.where(rolls.classification_status.eq("rule_directional"), "deterministic_high_precision_rule", "none")
    rolls["human_review_status"] = "unreviewed"
    rolls["original_bill_type"] = ""
    rolls["original_bill_number"] = np.nan
    rolls["measure_identity_status"] = "legiscan_structured_bill_id"
    for idx, row in rolls[rolls.roll_call_id.isin(anchor_map)].iterrows():
        a = anchor_map[row.roll_call_id]
        rolls.at[idx, "issue_code"] = a["human_issue_code"]
        rolls.at[idx, "issue_codes"] = anchor_labels[row.roll_call_id]
        val = str(a["ideological_valence"]).lower()
        rolls.at[idx, "yea_direction"] = {"conservative": 1.0, "progressive": -1.0}.get(val, np.nan)
        rolls.at[idx, "classification_status"] = "human_reviewed_directional" if pd.notna(rolls.at[idx, "yea_direction"]) else "human_reviewed_non_directional"
        rolls.at[idx, "classification_source"] = "human_anchor_review"
        rolls.at[idx, "human_review_status"] = a["review_status"]
        rolls.at[idx, "classification_reason"] = a["policy_direction_of_yea"]

    # Add the pre-LegiScan journal archive. It currently lacks reliable bill
    # synopsis linkage, so each row is processed but not silently inferred from
    # nearby OCR context. Existing human codes can still override when present.
    hist = pd.read_csv(LEG / "historical_rollcall_issue_classification_queue.csv", low_memory=False)
    resolved = [infer_historical_measure(r.context, r.bill_type, r.bill_number) for r in hist.itertuples()]
    hist["original_bill_type"] = hist.bill_type
    hist["original_bill_number"] = hist.bill_number
    hist["bill_type"] = [x[0] for x in resolved]
    hist["bill_number"] = [x[1] for x in resolved]
    hist["measure_identity_status"] = [x[2] for x in resolved]
    hist["extracted_synopsis"] = [extract_historical_synopsis(r.context, r.bill_type, r.bill_number)
                                    for r in hist.itertuples()]
    recovery_path = LEG / "historical_rollcall_synopsis_recovery.csv"
    if recovery_path.exists():
        recovery = pd.read_csv(recovery_path, usecols=["rollcall_id", "best_synopsis", "synopsis_source"])
        hist = hist.merge(recovery, on="rollcall_id", how="left", validate="one_to_one")
        recovered = hist.extracted_synopsis.eq("") & hist.best_synopsis.fillna("").ne("")
        hist.loc[recovered, "extracted_synopsis"] = hist.loc[recovered, "best_synopsis"]
    else:
        hist["synopsis_source"] = np.where(hist.extracted_synopsis.ne(""), "context_window", "unavailable")
    hist_rules = pd.DataFrame([classify_text(r.title, r.extracted_synopsis) for r in hist.itertuples()])
    hist_motion = hist.motion_type.map(motion_disposition)
    hist_direction = hist_rules.yea_direction.where(hist_motion.eq("bill_direction_applies"))
    hist_status = hist_rules.classification_status.copy()
    hist_status = hist_status.mask(hist.extracted_synopsis.eq(""), "synopsis_extraction_failed")
    hist_status = hist_status.mask(
        hist.extracted_synopsis.eq("") & hist_motion.ne("bill_direction_applies"),
        "motion_text_not_required")
    hist_status = hist_status.mask(
        hist.extracted_synopsis.eq("") & hist.bill_type.fillna("").isin(["HR", "SR", "HJR", "SJR"])
        & hist_motion.eq("bill_direction_applies"),
        "resolution_text_not_extracted")
    hist_status = hist_status.mask(hist_motion.ne("bill_direction_applies") & hist_rules.yea_direction.notna(), "motion_not_directional")
    hist_out = pd.DataFrame({
        "canonical_rollcall_id": hist.rollcall_id,
        "roll_call_id": np.nan, "bill_id": np.nan, "session_year": hist.session_year,
        "chamber": hist.chamber, "bill_number": hist.bill_type.fillna("") + hist.bill_number.fillna("").astype(str),
        "vote_description": hist.motion_type, "title": hist.title, "description": hist.extracted_synopsis,
        "issue_code": hist_rules.issue_code, "issue_codes": hist_rules.issue_codes,
        "yea_direction": hist_direction,
        "classification_reason": hist_rules.classification_reason,
        "classification_status": hist_status,
        "classification_source": np.where(hist_direction.notna(),
            "historical_journal_" + hist.synopsis_source.fillna("unknown").astype(str) + "_rule", "none"),
        "human_review_status": hist.coding_status.fillna("unreviewed"),
        "motion_disposition": hist_motion,
        "yea": np.nan, "nay": np.nan,
        "original_bill_type": hist.original_bill_type,
        "original_bill_number": hist.original_bill_number,
        "measure_identity_status": hist.measure_identity_status,
    })
    rolls["canonical_rollcall_id"] = "LS-" + rolls.roll_call_id.astype(str)
    common = [c for c in hist_out if c in rolls.columns]
    all_rolls = pd.concat([rolls, hist_out.reindex(columns=rolls.columns)], ignore_index=True)
    all_rolls.to_csv(LEG / "comprehensive_rollcall_classifications.csv", index=False)
    bills.to_csv(LEG / "comprehensive_bill_classifications.csv", index=False)

    recorded = pd.to_numeric(all_rolls.get("yea"), errors="coerce").fillna(0) + pd.to_numeric(all_rolls.get("nay"), errors="coerce").fillna(0)
    minority = pd.concat([pd.to_numeric(all_rolls.get("yea"), errors="coerce"), pd.to_numeric(all_rolls.get("nay"), errors="coerce")], axis=1).min(axis=1).fillna(0)
    queue = all_rolls[all_rolls.yea_direction.isna()].copy()
    queue["review_priority"] = minority * np.log1p(recorded) + queue.issue_code.ne("").astype(int) * 100
    queue = queue.sort_values(["review_priority", "session_year"], ascending=[False, False])
    queue.to_csv(LEG / "comprehensive_rollcall_direction_review_queue.csv", index=False)

    with sqlite3.connect(DB) as con:
        all_rolls.to_sql("rollcall_issue_classification", con, if_exists="replace", index=False)
        bills.to_sql("bill_issue_classification", con, if_exists="replace", index=False)
        con.execute("CREATE INDEX IF NOT EXISTS idx_rc_issue_classification_id ON rollcall_issue_classification(canonical_rollcall_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_bill_issue_classification_id ON bill_issue_classification(bill_id)")
    print(f"Processed {len(bills):,} LegiScan bills and {len(all_rolls):,} roll calls")
    print(all_rolls.classification_status.value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
