"""Extract crosstabs from supported Silver B+ or better pollster formats."""
from __future__ import annotations

import argparse
import re
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import fitz
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data" / "processed" / "polling" / "votehub_silver_bplus_crosstab_review_queue.csv"
CATALOG = ROOT / "data" / "raw" / "polling" / "votehub_generic_ballot_catalog.json"
OUT = ROOT / "data" / "processed" / "polling" / "votehub_silver_bplus_extracted_candidates.csv"
REVIEWED = ROOT / "data" / "raw" / "polling" / "votehub_crosstabs_reviewed.csv"
PCT = re.compile(r"^(<?\d+)%$")


def row(poll_id, dimension, group, dem, rep, source, table, method, population="rv", base=None):
    return {"poll_id": poll_id, "dimension": dimension, "group": group, "dem_pct": float(dem),
            "rep_pct": float(rep), "cell_base": base, "population_override": population,
            "source_url": source, "page_or_table": table, "extraction_method": method, "reviewed": True}


def cleaned_workbook(path: Path) -> BytesIO:
    source, target = ZipFile(path), BytesIO()
    with ZipFile(target, "w", ZIP_DEFLATED) as output:
        for name in source.namelist():
            content = source.read(name)
            if name == "xl/styles.xml":
                content = re.sub(br'\sapplyColorFormat="[^"]*"', b"", content)
            output.writestr(name, content)
    target.seek(0)
    return target


def extract_tipp(path: Path, poll_id: str, source: str) -> pd.DataFrame:
    book = cleaned_workbook(path)
    one = pd.read_excel(book, "Banner One", header=None)
    book.seek(0); two = pd.read_excel(book, "Banner Two", header=None)
    if "Which party do you prefer to control Congress" not in str(one.iloc[6, 2]):
        raise ValueError("Unexpected TIPP question")
    # Stable MT1 banner columns, guarded by their published labels.
    if str(one.iloc[10, 14]).strip() != "WHITE" or str(two.iloc[11, 9]).strip() != "BLACK":
        raise ValueError("Unexpected TIPP banner schema")
    def cell(frame, col, dimension, group):
        dem_row = frame.index[frame.iloc[:, 2].eq("The Democratic Party")][0]
        rep_row = frame.index[frame.iloc[:, 2].eq("The Republican Party")][0]
        base_row = frame.index[frame.iloc[:, 2].eq("Unweighted Total")][0]
        return row(poll_id, dimension, group, 100*frame.iloc[dem_row+1, col],
                   100*frame.iloc[rep_row+1, col], source, "MT1 banner table",
                   "tipp_xlsx_banner_adapter_v1", base=int(frame.iloc[base_row, col]))
    result = [cell(one, 3, "overall", "all"), cell(one, 14, "race", "white"),
              cell(two, 9, "race", "black"), cell(two, 10, "race", "hispanic"),
              cell(two, 13, "education", "tipp_high_school"),
              cell(two, 14, "education", "tipp_some_college"),
              cell(two, 15, "education", "tipp_college_plus")]
    return pd.DataFrame(result)


def pct_values_after(lines, index, count):
    values=[]
    for value in lines[index+1:]:
        match=PCT.match(value)
        if match: values.append(float(match.group(1).replace("<", "")))
        elif values: break
        if len(values)==count: break
    if len(values)!=count: raise ValueError("Could not parse expected percentage row")
    return values


def extract_marist(path: Path, poll_id: str, source: str) -> pd.DataFrame:
    doc=fitz.open(path); text=None; page=None
    for i,p in enumerate(doc):
        candidate=p.get_text("text")
        if "USCNGS01." in candidate and "USCNGS01TRND" not in candidate:
            text=candidate;page=i+1;break
    if text is None: raise ValueError("Marist generic-ballot crosstab page not found")
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    leading=[float(PCT.match(x).group(1).replace("<", "")) for x in lines if PCT.match(x)][:4]
    if len(leading)<4: raise ValueError("Marist overall row not found")
    result=[row(poll_id,"overall","all",leading[0],leading[1],source,f"PDF page {page}","marist_pdf_table_adapter_v1")]
    def labelled(label, occurrence=0):
        indices=[i for i,x in enumerate(lines) if x==label]
        return pct_values_after(lines,indices[occurrence],4)[:2]
    # The second White occurrence belongs to the White/Black/Latino banner.
    for label,group,occ in [("White","white",1),("Black","black",0),("Latino","hispanic",0),
                            ("Not college graduate","marist_not_college_grad",0),
                            ("College graduate","marist_college_grad",0),
                            ("White - Not College Graduate","white_noncollege",0),
                            ("White - College Graduate","white_college",0)]:
        dem,rep=labelled(label,occ);dim="race_education" if group.startswith("white_") else ("race" if group in {"white","black","hispanic"} else "education")
        result.append(row(poll_id,dim,group,dem,rep,source,f"PDF page {page}","marist_pdf_table_adapter_v1"))
    return pd.DataFrame(result)


def extract_ppp(path: Path, poll_id: str, source: str) -> pd.DataFrame:
    doc=fitz.open(path); race=[x.strip() for x in doc[3].get_text("text").splitlines() if x.strip()]
    education=[x.strip() for x in doc[4].get_text("text").splitlines() if x.strip()]
    def tail_values(lines, marker, needed):
        starts=[i for i,x in enumerate(lines) if x==marker]
        segment=lines[starts[-1]:]
        pos=next(i for i,x in enumerate(segment) if x=="Not Sure")
        vals=[float(PCT.match(x).group(1)) for x in segment[pos+1:] if PCT.match(x)]
        if len(vals)<needed: raise ValueError("PPP table has too few percentages")
        return vals[:needed]
    rv=tail_values(race,"Generic Ballot",15)
    result=[row(poll_id,"overall","all",rv[0],rv[5],source,"PDF pages 4-5","ppp_pdf_table_adapter_v1")]
    for j,group in enumerate(["hispanic","white","black","other"]):
        result.append(row(poll_id,"race",group,rv[1+j],rv[6+j],source,"PDF page 4","ppp_pdf_table_adapter_v1"))
    ev=tail_values(education,"Generic Ballot",18)
    for j,group in enumerate(["ppp_hs_or_less","ppp_some_college","ppp_associate","ppp_bachelors","ppp_postgrad"]):
        result.append(row(poll_id,"education",group,ev[1+j],ev[7+j],source,"PDF page 5","ppp_pdf_table_adapter_v1"))
    return pd.DataFrame(result)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--promote-reviewed",action="store_true");args=parser.parse_args()
    queue=pd.read_csv(QUEUE);catalog=pd.read_json(CATALOG).set_index("id");results=[];failures=[]
    # TIPP: the March file supersedes the February attachment on the same poll record.
    targets=[]
    tipp=queue[(queue.pollster=="TIPP Insights")&queue.asset_kind.eq("xlsx")]
    if len(tipp): targets.append((tipp.sort_values("asset_url").iloc[-1],extract_tipp))
    for pollster,adapter in [("Marist University",extract_marist),("Marist College",extract_marist),
                             ("Public Policy Polling",extract_ppp)]:
        for _,candidate in queue[(queue.pollster==pollster)&queue.local_path.notna()].drop_duplicates("id").iterrows():
            targets.append((candidate,adapter))
    for candidate,adapter in targets:
        try:
            extracted=adapter(ROOT/str(candidate.local_path).replace("\\","/"),str(candidate.id),str(candidate.asset_url))
            answers={str(x.get("choice","")).lower():float(x["pct"]) for x in catalog.loc[str(candidate.id),"answers"]}
            dem=next((v for k,v in answers.items() if k in {"dem","democrat","democratic"}),None)
            rep=next((v for k,v in answers.items() if k in {"rep","republican","gop"}),None)
            total=extracted[extracted.dimension.eq("overall")].iloc[0]
            if dem is not None and (abs(total.dem_pct-dem)>1.1 or abs(total.rep_pct-rep)>1.1):
                raise ValueError(f"Extracted topline {total.dem_pct:.1f}/{total.rep_pct:.1f} does not match VoteHub {dem:.1f}/{rep:.1f}")
            results.append(extracted)
        except Exception as exc: failures.append({"poll_id":candidate.id,"pollster":candidate.pollster,"reason":str(exc)})
    result=pd.concat(results,ignore_index=True) if results else pd.DataFrame();result.to_csv(OUT,index=False)
    pd.DataFrame(failures).to_csv(OUT.with_name("votehub_silver_bplus_extraction_failures.csv"),index=False)
    print(f"Extracted {len(result)} cells from {result.poll_id.nunique()} B+ or better polls; failures={len(failures)}")
    if args.promote_reviewed and len(result):
        existing=pd.read_csv(REVIEWED);methods=set(result.extraction_method)
        existing=existing[~existing.extraction_method.isin(methods)]
        pd.concat([existing,result],ignore_index=True).drop_duplicates(["poll_id","dimension","group"],keep="last").to_csv(REVIEWED,index=False)

if __name__=="__main__":main()
