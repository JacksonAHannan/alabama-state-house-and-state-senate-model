"""Build a bill-deduplicated ledger for frontier-model legislative review."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; LEG=ROOT/"data"/"processed"/"legislative"; REVIEW=ROOT/"research"/"cmo_ideology"/"frontier_legislative_review"
MANUAL=ROOT/"data"/"manual"/"ideology"/"frontier_legislative_bill_adjudications.csv"
DEPRECATED={"tax_burden","civil_social_liberty","marriage_equality","anti_discrimination"}

def joined(series): return "|".join(sorted({str(x) for x in series if pd.notna(x) and str(x)}))

ONTOLOGY=LEG/"frontier_rollcall_ontology_v3.csv"
LUNA_QUEUE=LEG/"frontier_legislative_bill_adjudications_luna_review_queue.csv"
OPENAI_QUEUE=LEG/"legislative_rollcall_ontology_v3_openai_review_queue.csv"
LOW_CONFIDENCE_REASON="low_confidence_admitted_mapping"
SCORING={"map","multi_axis"}
LUNA_QUEUE_COLUMNS=["bill_id","session_year","bill_number","reviewed_document_type","confidence","rationale",
                    "reviewer","review_date","supersedes_authority","decision","primitive_axes","policy_poles","review_reason"]
OPENAI_QUEUE_COLUMNS=["unit_id","issue_code","title","decision","primitive_axis","policy_pole","confidence",
                      "terminal_status","rationale","review_reason"]
ONTOLOGY_COLUMNS=["canonical_rollcall_id","bill_id","session_year","bill_number","vote_description",
                  "decision","primitive_axis","policy_pole","frontier_confidence","terminal_status"]

def norm_bill_id(value):
    text=str(value).strip()
    if text in ("","nan","None","NaN"): return ""
    return text[:-2] if text.endswith(".0") else text

def _read_table(path,columns):
    return pd.read_csv(path,usecols=list(columns),dtype=str,low_memory=False).fillna("")

def _read_queue(path,columns):
    if not Path(path).exists(): return pd.DataFrame(columns=columns)
    return pd.read_csv(path,dtype=str,low_memory=False).reindex(columns=columns).fillna("")

def reconcile_low_confidence_review_queues(manual_path=MANUAL,ontology_path=ONTOLOGY,
                                           luna_queue_path=LUNA_QUEUE,openai_queue_path=OPENAI_QUEUE):
    """Queue every admitted low-confidence mapping; idempotent and row-preserving.

    A ``map``/``multi_axis`` bill that only reaches ``confidence=low`` is still
    scored -- the 2026-09-08 owner contract queues it, it does not exclude it --
    so it must appear in a review queue. The Luna adjudicator queues its own
    output at generation time; this step enforces the same invariant for queues
    built or overwritten by other stages and for the roll-call-level queue.
    Existing rows are preserved and only missing units are appended, so
    re-running is a no-op. Raises when a low-confidence admitted mapping is
    still unqueued.
    """
    manual=_read_table(manual_path,["bill_id","session_year","bill_number","reviewed_document_type","confidence",
                                    "rationale","reviewer","review_date","supersedes_authority","decision",
                                    "primitive_axes","policy_poles"])
    low=manual[manual.decision.isin(SCORING)&manual.confidence.eq("low")]
    luna=_read_queue(luna_queue_path,LUNA_QUEUE_COLUMNS)
    queued_bills={norm_bill_id(x) for x in luna.bill_id}
    added_luna=[]
    for record in low.to_dict("records"):
        bill=norm_bill_id(record.get("bill_id"))
        if not bill or bill in queued_bills: continue
        entry={column:str(record.get(column,"") or "") for column in LUNA_QUEUE_COLUMNS}
        entry["bill_id"]=bill; entry["review_reason"]=LOW_CONFIDENCE_REASON
        added_luna.append(entry); queued_bills.add(bill)
    if added_luna:
        luna=pd.concat([luna,pd.DataFrame(added_luna)],ignore_index=True).reindex(columns=LUNA_QUEUE_COLUMNS)
        luna.to_csv(luna_queue_path,index=False)

    onto=_read_table(ontology_path,ONTOLOGY_COLUMNS)
    mapped_low=onto[onto.decision.eq("map")&onto.frontier_confidence.eq("low")]
    openai=_read_queue(openai_queue_path,OPENAI_QUEUE_COLUMNS)
    queued_units=set(openai.unit_id.astype(str))
    added_openai=[]
    for record in mapped_low.to_dict("records"):
        unit=str(record.get("canonical_rollcall_id") or "").strip()
        if not unit or unit in queued_units: continue
        added_openai.append({
            "unit_id":unit,"issue_code":"",
            "title":f"{record.get('bill_number','')} {record.get('vote_description','')}".strip(),
            "decision":"map","primitive_axis":record.get("primitive_axis",""),
            "policy_pole":record.get("policy_pole",""),"confidence":"low",
            "terminal_status":record.get("terminal_status",""),
            "rationale":("Admitted to scoring from a low-confidence frontier bill mapping "
                         f"(bill_id {norm_bill_id(record.get('bill_id'))}); queued for review."),
            "review_reason":LOW_CONFIDENCE_REASON})
        queued_units.add(unit)
    if added_openai:
        openai=pd.concat([openai,pd.DataFrame(added_openai)],ignore_index=True).reindex(columns=OPENAI_QUEUE_COLUMNS)
        openai.to_csv(openai_queue_path,index=False)

    unqueued=({norm_bill_id(x) for x in low.bill_id}|{norm_bill_id(x) for x in mapped_low.bill_id})-queued_bills
    if unqueued:
        raise AssertionError(f"low-confidence admitted mappings absent from the Luna review queue: {sorted(unqueued)}")
    return {"luna_queue_rows_appended":len(added_luna),"openai_queue_rows_appended":len(added_openai),
            "luna_queue_rows":len(luna),"openai_queue_rows":len(openai)}

def main():
    bills=pd.read_csv(LEG/"legiscan_alabama_bills.csv",low_memory=False)
    calls=pd.read_csv(LEG/"legislative_rollcall_ontology_v3_audit.csv",low_memory=False)
    final=pd.read_csv(LEG/"legislative_rollcall_ontology_v3_final_adjudications.csv",low_memory=False)
    calls=calls.merge(final[["canonical_rollcall_id","decision","primitive_axis","policy_pole","terminal_status","authority","confidence","rationale"]],on="canonical_rollcall_id",how="left",validate="one_to_one")
    roll=(calls.groupby("bill_id",as_index=False).agg(rollcalls=("canonical_rollcall_id","nunique"),mapped_rollcalls=("decision",lambda x:(x=="map").sum()),
          current_axes=("primitive_axis",joined),current_poles=("policy_pole",joined),authorities=("authority",joined),terminal_statuses=("terminal_status",joined),
          issue_codes=("issue_code",joined),classification_sources=("classification_source",joined)))
    docs=pd.read_csv(LEG/"alabama_bill_text_archive_reconciliation.csv",low_memory=False)
    doc=(docs.groupby("bill_id",as_index=False).agg(text_documents=("doc_id","nunique"),documents_present=("archive_status",lambda x:(x=="present").sum()),document_types=("document_type",joined)))
    ledger=bills.merge(roll,on="bill_id",how="left").merge(doc,on="bill_id",how="left")
    for c in ["rollcalls","mapped_rollcalls","text_documents","documents_present"]: ledger[c]=ledger[c].fillna(0).astype(int)
    text=(ledger.title.fillna("")+" "+ledger.description.fillna("")).str.lower()
    ledger["taxonomy_warning"]=""
    ledger.loc[ledger.current_axes.fillna("").apply(lambda x:any(a in DEPRECATED for a in x.split("|"))),"taxonomy_warning"]="deprecated_or_overbroad_axis"
    ledger.loc[text.str.contains(r"sales tax|grocery|corporate tax|income tax|property tax|capital gains",regex=True)&ledger.current_axes.fillna("").str.contains("tax_burden"),"taxonomy_warning"]="tax_incidence_collapsed"
    ledger.loc[text.str.contains(r"same.sex|sexual orientation|gender identity|affirmative action|confederate",regex=True)&ledger.current_axes.fillna("").str.contains("civil_social_liberty|anti_discrimination|marriage_equality",regex=True),"taxonomy_warning"]="social_or_racial_domain_collapsed"
    small=ledger.authorities.fillna("").str.contains("ministral")
    ledger["review_priority"]=5
    ledger.loc[ledger.rollcalls.gt(0),"review_priority"]=4
    ledger.loc[ledger.mapped_rollcalls.gt(0),"review_priority"]=3
    ledger.loc[small,"review_priority"]=2
    ledger.loc[ledger.taxonomy_warning.ne(""),"review_priority"]=1
    ledger.loc[small&ledger.mapped_rollcalls.gt(0),"review_priority"]=0
    ledger["frontier_review_status"]="pending"
    ledger["frontier_decision"]=""; ledger["frontier_axes"]=""; ledger["frontier_poles"]=""; ledger["frontier_confidence"]=""; ledger["frontier_rationale"]=""
    if MANUAL.exists():
        manual=pd.read_csv(MANUAL,low_memory=False)
        if manual.bill_id.duplicated().any():
            raise ValueError("Duplicate bill_id values in frontier manual adjudications")
        cols={"decision":"frontier_decision","primitive_axes":"frontier_axes","policy_poles":"frontier_poles",
              "confidence":"frontier_confidence","rationale":"frontier_rationale"}
        manual=manual[["bill_id",*cols]].rename(columns=cols)
        ledger=ledger.drop(columns=list(cols.values())).merge(manual,on="bill_id",how="left",validate="one_to_one")
        ledger["frontier_review_status"]=ledger.frontier_decision.notna().map({True:"reviewed",False:"pending"})
        for c in cols.values(): ledger[c]=ledger[c].fillna("")
    ledger=ledger.sort_values(["review_priority","session_year","bill_number"])
    REVIEW.mkdir(parents=True,exist_ok=True); ledger.to_csv(REVIEW/"bill_review_ledger.csv",index=False)
    queue=ledger[(ledger.review_priority.le(3))].copy(); queue.to_csv(REVIEW/"substantive_review_queue.csv",index=False)
    # A reviewed row is not necessarily a final directional judgment.  Preserve a
    # separate, reproducible queue for cases where the synopsis could not support
    # more than a low-confidence disposition and bill text is known to exist.
    followup = ledger[
        ledger.frontier_review_status.eq("reviewed")
        & (
            ledger.frontier_confidence.eq("low")
            | ledger.frontier_decision.eq("insufficient_text")
        )
    ].copy()
    followup["full_text_available"] = followup.documents_present.gt(0)
    followup["followup_reason"] = followup.apply(
        lambda r: "explicit_insufficient_text"
        if r.frontier_decision == "insufficient_text"
        else "low_confidence_synopsis_judgment",
        axis=1,
    )
    followup_cols = [
        "bill_id", "session_year", "session_name", "bill_number", "title",
        "description", "frontier_decision", "frontier_axes", "frontier_poles",
        "frontier_confidence", "frontier_rationale", "text_documents",
        "documents_present", "document_types", "full_text_available",
        "followup_reason", "url", "state_link", "source_archive", "source_member",
    ]
    followup[followup_cols].sort_values(
        ["full_text_available", "session_year", "bill_number"],
        ascending=[False, True, True],
    ).to_csv(REVIEW/"full_text_followup_queue.csv", index=False)
    summary=(ledger.groupby(["review_priority","frontier_review_status"],as_index=False).agg(bills=("bill_id","nunique"),with_rollcalls=("rollcalls",lambda x:(x>0).sum()),mapped=("mapped_rollcalls",lambda x:(x>0).sum())))
    summary.to_csv(REVIEW/"review_summary.csv",index=False)
    queue_counts=reconcile_low_confidence_review_queues()
    print("low-confidence review queues",queue_counts)
    print(summary.to_string(index=False)); print("taxonomy warnings",ledger.taxonomy_warning.value_counts().to_dict())

if __name__=="__main__": main()
