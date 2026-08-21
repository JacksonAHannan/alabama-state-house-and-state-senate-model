"""Build a bill-deduplicated ledger for frontier-model legislative review."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; LEG=ROOT/"data"/"processed"/"legislative"; REVIEW=ROOT/"research"/"cmo_ideology"/"frontier_legislative_review"
MANUAL=ROOT/"data"/"manual"/"ideology"/"frontier_legislative_bill_adjudications.csv"
DEPRECATED={"tax_burden","civil_social_liberty","marriage_equality","anti_discrimination"}

def joined(series): return "|".join(sorted({str(x) for x in series if pd.notna(x) and str(x)}))

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
    print(summary.to_string(index=False)); print("taxonomy warnings",ledger.taxonomy_warning.value_counts().to_dict())

if __name__=="__main__": main()
