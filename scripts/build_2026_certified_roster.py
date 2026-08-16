"""OCR and reconcile the scanned 2026 major-party certification PDFs."""
from pathlib import Path
import re
import numpy as np
import pandas as pd
import fitz
from rapidocr_onnxruntime import RapidOCR
from rapidfuzz import fuzz
from build_incumbency_features import best_match
from build_candidate_finance_features import canonical_person

ROOT=Path(__file__).resolve().parents[1]; MAPS=ROOT/"data"/"raw"/"alabama_elections_and_geography"; OUT=ROOT/"data"/"processed"/"war"
PDFS={"D":MAPS/"CertificationofDemocraticPartyCandidates-2026General.pdf",
      "R":MAPS/"CertificationofRepublicanPartyCandidates-2026General.pdf"}
OFFICE=re.compile(r"(?:Alabama )?(?:House of Representatives|State Representative|State House) District\s*(\d+)?|(?:Alabama )?State Senate District\s*(\d+)?|State Senator",re.I)

def center(box): return ((box[0][0]+box[2][0])/2,(box[0][1]+box[2][1])/2)

def ocr_pages(path):
    engine=RapidOCR(); pages=[]
    for number,page in enumerate(fitz.open(path),1):
        pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
        image=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n)
        result,_=engine(image)
        pages.append([{"page":number,"text":item[1],"confidence":item[2],"x":center(item[0])[0],"y":center(item[0])[1]} for item in (result or [])])
    return pages

def chamber_for(text):
    return "house" if re.search(r"House|Representative",text,re.I) else "senate"

def republican(pages):
    rows=[]
    for page in pages:
        for office in page:
            match=OFFICE.search(office["text"])
            if not match or not any(match.groups()): continue
            district=int(next(x for x in match.groups() if x))
            names=[line for line in page if line["x"]>600 and abs(line["y"]-office["y"])<15]
            if not names: continue
            name=min(names,key=lambda x:abs(x["y"]-office["y"]))
            rows.append({"cycle":2026,"chamber":chamber_for(office["text"]),"district":district,"party":"R",
                         "candidate":name["text"],"ocr_confidence":min(office["confidence"],name["confidence"]),
                         "certification_page":office["page"],"parse_method":"office_name_row"})
    return rows

def democratic(pages,provisional):
    rows=[]
    for page in pages[1:]:
        offices=[line for line in page if re.fullmatch(r"State\s*(?:Senator|Representative)",line["text"],re.I)]
        names=[line for line in page if 250<line["y"]<650 and re.search(r"[A-Za-z]{2}",line["text"])]
        districts=[line for line in page if 700<line["y"]<1100 and re.fullmatch(r"\d{1,3}",line["text"].strip())]
        for office in offices:
            nearby=[line for line in names if abs(line["x"]-office["x"])<18]
            if not nearby: continue
            name=min(nearby,key=lambda x:abs(x["x"]-office["x"])); chamber=chamber_for(office["text"])
            pool=provisional[(provisional.party.eq("D"))&(provisional.chamber.eq(chamber))]
            compact=re.sub(r"[^A-Z]","",canonical_person(name["text"]))
            compact_hits=[candidate for candidate in pool.candidate
                          if re.sub(r"[^A-Z]","",canonical_person(candidate))==compact]
            scored=sorted([(float(fuzz.token_set_ratio(canonical_person(name["text"]),canonical_person(candidate))),candidate)
                           for candidate in pool.candidate],reverse=True)
            score=(scored[0][0]/100) if scored else 0; margin=(scored[0][0]-scored[1][0]) if len(scored)>1 else 100
            found=compact_hits[0] if len(compact_hits)==1 else (scored[0][1] if scored and scored[0][0]>=75 and margin>=8 else None)
            district_value=None; method="name_to_provisional"
            if found:
                district_value=int(pool.loc[pool.candidate.eq(found),"district"].iloc[0])
            else:
                nearby_d=[line for line in districts if abs(line["x"]-office["x"])<18]
                if nearby_d:
                    district_value=int(min(nearby_d,key=lambda x:abs(x["x"]-office["x"]))["text"]); method="ocr_district_review"
            rows.append({"cycle":2026,"chamber":chamber,"district":district_value,"party":"D",
                         "candidate":name["text"],"ocr_confidence":min(office["confidence"],name["confidence"]),
                         "certification_page":office["page"],"parse_method":method,"provisional_match":found,"match_score":score})
    # Runoff certificate on page 1 explicitly supersedes earlier certification.
    rows.extend([
        {"cycle":2026,"chamber":"senate","district":2,"party":"D","candidate":"Rudolph Valentino Drake","ocr_confidence":1.0,"certification_page":1,"parse_method":"runoff_certificate"},
        {"cycle":2026,"chamber":"house","district":52,"party":"D","candidate":"GiGi Hayes","ocr_confidence":1.0,"certification_page":1,"parse_method":"runoff_certificate"},
        {"cycle":2026,"chamber":"house","district":82,"party":"D","candidate":"Pebblin W. Warren","ocr_confidence":1.0,"certification_page":1,"parse_method":"runoff_certificate"},
    ])
    return rows

def main():
    provisional=pd.read_csv(OUT/"2026_candidate_roster_provisional.csv")
    pages={party:ocr_pages(path) for party,path in PDFS.items()}
    raw=pd.DataFrame(republican(pages["R"])+democratic(pages["D"],provisional))
    raw.to_csv(OUT/"2026_certified_roster_ocr_raw.csv",index=False)
    valid=raw[raw.district.notna()].copy(); valid["district"]=valid.district.astype(int)
    # Prefer the runoff certificate, then stronger OCR when duplicate rows exist.
    valid["priority"]=valid.parse_method.map({"runoff_certificate":2,"name_to_provisional":1}).fillna(0)
    valid=valid.sort_values(["priority","ocr_confidence"],ascending=False).drop_duplicates(["chamber","district","party"])
    valid["roster_status"]="certified_party_nominee_ocr"
    valid["source_file"]=valid.party.map({p:path.name for p,path in PDFS.items()})
    valid.to_csv(OUT/"2026_certified_candidate_roster.csv",index=False)
    keys=["chamber","district","party"]
    comparison=valid.merge(provisional[keys+["candidate"]],on=keys,how="outer",suffixes=("_certified","_wikipedia"),indicator=True)
    comparison["name_match_score"]=comparison.apply(lambda r:best_match(r.candidate_certified,[r.candidate_wikipedia])[1]
        if pd.notna(r.candidate_certified) and pd.notna(r.candidate_wikipedia) else 0,axis=1)
    comparison["review_required"]=comparison._merge.ne("both")|comparison.name_match_score.lt(.86)
    comparison.to_csv(OUT/"2026_certified_roster_reconciliation.csv",index=False)
    print(valid.groupby(["party","chamber"]).size().to_string())
    print(f"Certified rows: {len(valid)}; reconciliation reviews: {comparison.review_required.sum()}")

if __name__=="__main__": main()
