"""Extract count-validated House roll calls from 1998-2009 ADAH journals."""
from __future__ import annotations
from pathlib import Path
import hashlib,re
import fitz
import pandas as pd

from oe_normalize import normalize_name

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data'/'raw'/'alabama_legislature'/'house_journals'
OUT=ROOT/'data'/'processed'/'legislative';YEARS=range(1998,2010)
ANCHOR=re.compile(r'Yeas?\s+(\d+)\s*;\s*Nays?\s+(\d+)(?:\s*;\s*Abstains?\s+(\d+))?\s*\.',re.I)
BILL=re.compile(r'\b(HB|SB|HJR|SJR|HR|SR)\s*[- ]?\s*(\d+)\b',re.I)

def member_names(block:str)->list[str]:
    text=re.sub(r'\n\s*(?:REGULAR|SPECIAL|ORGANIZATIONAL) SESSION\s*\n\s*\d+\s*\n[^\n]*Day[^\n]*\n',' ',block,flags=re.I)
    text=re.sub(r'\bRepresentatives?\s+','',text,flags=re.I);text=re.sub(r'\bMr\. Speaker\b','SPEAKER',text,flags=re.I)
    text=re.sub(r'\s+',' ',text).strip(' .,-')
    if not text:return []
    text=re.sub(r'\s+and\s+',', ',text)
    return [name.strip(' .') for name in text.split(',') if name.strip(' .')]

def vote_block(after:str,label:str,count:int)->str|None:
    if count==0:return ''
    match=re.search(rf'(?:^|\n)\s*{label}:\s*(.*?)(?:\s*-\s*{count}\s*(?:\n|$))',after,re.I|re.S)
    return match.group(1) if match else None

def classify_motion(context:str)->str:
    upper=context.upper()
    if 'BUDGET ISOLATION RESOLUTION' in upper:return 'budget_isolation_resolution'
    if 'THIRD TIME' in upper and ('PASSED' in upper or 'PASSAGE' in upper):return 'final_passage'
    if 'AMENDMENT' in upper:return 'amendment_or_concurrence'
    if 'SUBSTITUTE' in upper:return 'substitute'
    if 'TABLED' in upper:return 'motion_to_table'
    if 'CARRY OVER' in upper:return 'carry_over'
    return 'other_recorded_motion'

def parse_document(text:str,session:str,asset:str,local_path:str)->tuple[list[dict],list[dict]]:
    rollcalls=[];votes=[]
    page_starts=[];position=0
    for marker in re.finditer(r'\n<<<PAGE (\d+)>>>\n',text):page_starts.append((marker.start(),int(marker.group(1))))
    for ordinal,anchor in enumerate(ANCHOR.finditer(text),1):
        yea,nay,abstain=int(anchor.group(1)),int(anchor.group(2)),int(anchor.group(3) or 0)
        after=text[anchor.end():anchor.end()+7000];blocks={
            'Yea':vote_block(after,'Yea',yea),'Nay':vote_block(after,'Nay',nay),'Abstain':vote_block(after,'Abstain',abstain)}
        names={key:(member_names(value) if value is not None else []) for key,value in blocks.items()}
        context=re.sub(r'\s+',' ',text[max(0,anchor.start()-2500):anchor.start()]).strip()
        refs=BILL.findall(context);bill_type,bill_number=(refs[-1][0].upper(),int(refs[-1][1])) if refs else (None,None)
        page=max((page for start,page in page_starts if start<=anchor.start()),default=None)
        token=f'{session}|{asset}|{ordinal}|{anchor.start()}';rollcall_id='JRC-'+hashlib.sha256(token.encode()).hexdigest()[:16].upper()
        parsed={'Yea':len(names['Yea']),'Nay':len(names['Nay']),'Abstain':len(names['Abstain'])}
        valid=(parsed['Yea']==yea and parsed['Nay']==nay and parsed['Abstain']==abstain)
        rollcalls.append({'rollcall_id':rollcall_id,'session':session,'session_year':int(session[:4]),'chamber':'house',
          'asset':asset,'local_path':local_path,'page':page,'ordinal_in_document':ordinal,'bill_type':bill_type,
          'bill_number':bill_number,'motion_type':classify_motion(context),'yea_total':yea,'nay_total':nay,
          'abstain_total':abstain,'parsed_yea':parsed['Yea'],'parsed_nay':parsed['Nay'],'parsed_abstain':parsed['Abstain'],
          'count_valid':valid,'context':context[-1600:]})
        for vote,named in names.items():
            for name in named:votes.append({'rollcall_id':rollcall_id,'session_year':int(session[:4]),'chamber':'house',
              'member_name':name,'member_name_norm':normalize_name(name),'vote':vote,'count_valid':valid})
    return rollcalls,votes

def extract_text(path:Path)->tuple[str,int,int]:
    document=fitz.open(path);parts=[];characters=0
    for page_number,page in enumerate(document,1):
        content=page.get_text('text');characters+=len(content);parts.append(f'\n<<<PAGE {page_number}>>>\n{content}')
    return ''.join(parts),len(document),characters

def main()->None:
    manifest=pd.read_csv(RAW/'manifest.csv');manifest['session_year']=pd.to_numeric(manifest.session.str[:4],errors='coerce')
    selected=manifest[manifest.session_year.isin(YEARS)&manifest.asset.str.contains('Day',case=False,na=False)&manifest.status.isin(['downloaded','existing'])]
    documents=[];rollcalls=[];votes=[]
    for index,row in enumerate(selected.itertuples(index=False),1):
        path=ROOT/row.local_path;text,pages,characters=extract_text(path)
        rc,mv=parse_document(text,row.session,row.asset,row.local_path);rollcalls.extend(rc);votes.extend(mv)
        documents.append({'session':row.session,'session_year':int(row.session_year),'asset':row.asset,'local_path':row.local_path,
          'sha256':row.sha256,'pages':pages,'text_characters':characters,'rollcall_anchors':len(rc)})
        if index%50==0:print(f'Processed {index}/{len(selected)} journals; {len(rollcalls):,} roll calls',flush=True)
    documents=pd.DataFrame(documents);rollcalls=pd.DataFrame(rollcalls);votes=pd.DataFrame(votes)
    documents.to_csv(OUT/'historical_house_journal_documents.csv',index=False)
    rollcalls.to_csv(OUT/'historical_house_journal_rollcalls.csv',index=False)
    votes.to_csv(OUT/'historical_house_journal_member_votes.csv',index=False)
    qa=(rollcalls.groupby('session_year',as_index=False).agg(rollcalls=('rollcall_id','size'),valid_rollcalls=('count_valid','sum'),
       bill_linked=('bill_number',lambda x:x.notna().sum()),member_votes=('parsed_yea',lambda x:0)))
    vote_counts=votes.groupby('session_year').size();qa['member_votes']=qa.session_year.map(vote_counts).fillna(0).astype(int)
    valid_vote_counts=votes[votes.count_valid].groupby('session_year').size()
    qa['valid_member_votes']=qa.session_year.map(valid_vote_counts).fillna(0).astype(int)
    qa['quarantined_rollcalls']=qa.rollcalls-qa.valid_rollcalls
    qa['valid_share']=qa.valid_rollcalls/qa.rollcalls;qa.to_csv(OUT/'historical_house_journal_rollcall_qa.csv',index=False)
    print(qa.to_string(index=False))

if __name__=='__main__':main()
