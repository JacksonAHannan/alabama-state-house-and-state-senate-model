"""Build SOS-anchored candidate identities enriched by secondary sources."""
from __future__ import annotations
import re, sqlite3
from pathlib import Path
import pandas as pd
from rapidfuzz.fuzz import WRatio
from oe_normalize import is_pseudocandidate, normalize_name
from warehouse import (begin_run, finish_run, initialize, install_identity_contracts,
                       register_table)

ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/"data"/"processed"/"elections"/"alabama_elections.sqlite"
WAR=ROOT/"data"/"processed"/"war"; OUT=ROOT/"data"/"processed"/"elections"

def chamber_for(office): return {"State House":"house","State Senate":"senate"}.get(office)
def name_score(a,b): return float(WRatio(normalize_name(a),normalize_name(b)))

def candidate_score(source_name,source_votes,canonical_name,canonical_votes):
    name=name_score(source_name,canonical_name); denom=max(float(source_votes),float(canonical_votes),1)
    vote=max(0.0,100*(1-abs(float(source_votes)-float(canonical_votes))/denom))
    return name,vote,.72*name+.28*vote

def best_name(name,pool):
    scored=sorted([(name_score(name,r.candidate),r) for r in pool.itertuples(index=False)],reverse=True,key=lambda x:x[0])
    if not scored:return None,0,0
    return scored[0][1],scored[0][0],scored[0][0]-(scored[1][0] if len(scored)>1 else 0)

def opposing_party_alias(name, party, pool):
    """Return a strong same-race name match carried under the other party."""
    named=pool.rename(columns={"canonical_name":"candidate"})
    found,score,margin=best_name(name,named)
    conflict=bool(found is not None and score>=88 and margin>=5 and found.canonical_party != party)
    return found,score,margin,conflict

def apply_incumbency_roster(canonical, roster):
    """Overlay prior-winner incumbency evidence onto canonical candidates."""
    result=canonical.copy()
    for row in roster.itertuples(index=False):
        pool=result[(result.year.eq(int(row.cycle)))&
                    (result.chamber.eq(row.chamber))&
                    (result.district.eq(int(row.district)))&
                    (result.canonical_party.eq(row.incumbent_party))]
        if pool.empty: continue
        named=pool.rename(columns={"canonical_name":"candidate"})
        found,score,margin=best_name(row.incumbent_candidate,named)
        if found is not None and score>=90 and margin>=5:
            result.loc[result.canonical_candidate_id.eq(found.canonical_candidate_id),"incumbent"]=True
    return result

def apply_validated_incumbency_transitions(canonical, transitions):
    """Recover validated incumbents whose current source name is abbreviated."""
    result=canonical.copy()
    valid=transitions[(transitions.transition_status.eq("continuing_incumbent"))&
                      transitions.current_incumbent_match.notna()]
    for row in valid.itertuples(index=False):
        source_tokens=set(normalize_name(row.current_incumbent_match).split())
        if len(source_tokens)<2: continue
        pool=result[(result.year.eq(int(row.cycle)))&
                    (result.chamber.eq(row.chamber))&
                    (result.canonical_party.eq(row.prior_party))]
        candidates=[]
        for candidate in pool.itertuples(index=False):
            target_tokens=set(normalize_name(candidate.canonical_name).split())
            if source_tokens.issubset(target_tokens): candidates.append(candidate)
        if len(candidates)==1:
            result.loc[result.canonical_candidate_id.eq(candidates[0].canonical_candidate_id),"incumbent"]=True
    return result

def main():
    with sqlite3.connect(DB) as c:
        votes=pd.read_sql("""select year,source,office,district,candidate,candidate_key,party_norm,votes
          from vote_observations where office in ('State House','State Senate') and district is not null""",c)
    votes["chamber"]=votes.office.map(chamber_for); votes["district"]=votes.district.astype(int)
    aliases=(votes.groupby(["year","source","chamber","district","candidate_key"],as_index=False)
             .agg(ballot_name=("candidate",lambda x:x.value_counts().index[0]),
                  source_party=("party_norm",lambda x:next((p for p in x if p in {'D','R'}),'O')),
                  source_votes=("votes","sum")))
    aliases=aliases[~aliases.ballot_name.map(is_pseudocandidate)]
    wiki=pd.read_csv(WAR/"wikipedia_legislative_candidates.csv"); wiki["district"]=wiki.district.astype(int)
    model_cycles=[1994,1998,2002,2006,2010,2014,2018,2022]
    wiki=wiki[wiki.party.isin(["D","R"]) & wiki.cycle.isin(model_cycles)]

    # SOS is canonical. Only 2010 lacks printed party codes, so attach its party
    # by conservative name matching to the secondary general-election roster.
    sos=aliases[aliases.source.eq("alabama_sos")].copy(); sos["resolved_party"]=sos.source_party
    unresolved=[]
    for idx,row in sos[sos.year.eq(2010)].iterrows():
        pool=wiki[(wiki.cycle.eq(2010))&(wiki.chamber.eq(row.chamber))&(wiki.district.eq(row.district))]
        found,score,margin=best_name(row.ballot_name,pool)
        if found is not None and score>=86 and margin>=5:
            sos.loc[idx,"resolved_party"]=found.party
        else: unresolved.append({**row.to_dict(),"name_score":score,"score_margin":margin,"reason":"2010_party_unresolved"})
    sos=sos[sos.resolved_party.isin(["D","R"])]

    # One D and one R general-election nominee per race. County-specific name
    # fragments are aliases whose votes must be summed, not separate people.
    keys=["year","chamber","district","resolved_party"]
    representatives=(sos.assign(name_length=sos.ballot_name.str.len())
                     .sort_values(["name_length","source_votes"],ascending=False)
                     .drop_duplicates(keys)[keys+["ballot_name"]])
    canonical=(sos.groupby(keys,as_index=False).source_votes.sum().merge(representatives,on=keys)
               .rename(columns={"resolved_party":"canonical_party","source_votes":"canonical_votes","ballot_name":"canonical_name"}))
    canonical["canonical_source"]="alabama_sos"
    # If an SOS county workbook omits an entire major-party side, use the
    # secondary normalized record only when the SOS race has no independent
    # candidate that explains the missing D/R slot (e.g. 2014 SD30).
    sos_other=set(map(tuple,aliases[(aliases.source.eq("alabama_sos"))&aliases.source_party.eq("O")]
                      [["year","chamber","district"]].drop_duplicates().values))
    existing=set(map(tuple,canonical[["year","chamber","district","canonical_party"]].values))
    oe=aliases[(aliases.source.eq("openelections"))&aliases.source_party.isin(["D","R"])].copy()
    oe=oe[[tuple(x) not in existing and tuple(x[:3]) not in sos_other
           for x in oe[["year","chamber","district","source_party"]].values]]
    # A secondary county fragment can carry the wrong party label. Do not turn
    # it into a phantom opponent when its name clearly identifies the SOS
    # nominee on the other party line (2014 Holmes/HD31 and Baker/HD66).
    opposing_aliases=[]
    keep=[]
    for row in oe.itertuples(index=False):
        pool=canonical[(canonical.year.eq(row.year))&(canonical.chamber.eq(row.chamber))&
                       (canonical.district.eq(row.district))]
        found,score,margin,conflict=opposing_party_alias(row.ballot_name,row.source_party,pool)
        keep.append(not conflict)
        if conflict:
            opposing_aliases.append({**row._asdict(),"matched_name":found.candidate,
                                     "matched_party":found.canonical_party,"name_score":score,
                                     "score_margin":margin,"reason":"opposing_party_name_alias"})
    oe=oe[keep]
    if not oe.empty:
        okeys=["year","chamber","district","source_party"]
        oreps=(oe.assign(name_length=oe.ballot_name.str.len()).sort_values(["name_length","source_votes"],ascending=False)
               .drop_duplicates(okeys)[okeys+["ballot_name"]])
        extra=(oe.groupby(okeys,as_index=False).source_votes.sum().merge(oreps,on=okeys)
               .rename(columns={"source_party":"canonical_party","source_votes":"canonical_votes","ballot_name":"canonical_name"}))
        extra["canonical_source"]="openelections_fallback"
        canonical=pd.concat([canonical,extra],ignore_index=True)
    canonical["person_id"]="ALPERSON-"+canonical.canonical_name.map(lambda x:re.sub(r"[^A-Z0-9]+","-",normalize_name(x)).strip("-"))
    canonical["canonical_candidate_id"]=[f"AL-{r.year}-{r.chamber}-{r.district}-{r.canonical_party}-{r.person_id[9:]}" for r in canonical.itertuples()]
    canonical["incumbent"]=False
    for idx,row in canonical.iterrows():
        pool=wiki[(wiki.cycle.eq(row.year))&(wiki.chamber.eq(row.chamber))&(wiki.district.eq(row.district))&
                  (wiki.party.eq(row.canonical_party))&wiki.incumbent_wikipedia]
        found,score,margin=best_name(row.canonical_name,pool)
        canonical.loc[idx,"incumbent"]=bool(found is not None and score>=90 and margin>=5)
    # The dedicated incumbency pipeline reconstructs continuity from prior
    # winners and is materially more complete than explicit "incumbent" labels
    # in saved Wikipedia tables. Overlay its candidate roster when available.
    # This is especially important after 2010: many ordinary reelection rows do
    # not carry an explicit annotation in the secondary table.
    roster_path=WAR/"incumbency_roster.csv"
    if roster_path.exists():
        roster=pd.read_csv(roster_path)
        canonical=apply_incumbency_roster(canonical,roster)
    transitions_path=WAR/"incumbency_transition_validation.csv"
    if transitions_path.exists():
        canonical=apply_validated_incumbency_transitions(canonical,pd.read_csv(transitions_path))
    canonical["winner"]=canonical.canonical_votes.eq(canonical.groupby(["year","chamber","district"]).canonical_votes.transform("max"))
    affiliations=canonical[["person_id","canonical_candidate_id","year","chamber","district","canonical_party"]].copy()
    history=affiliations.sort_values(["person_id","year"]).copy()
    history["previous_year"]=history.groupby("person_id").year.shift()
    history["previous_party"]=history.groupby("person_id").canonical_party.shift()
    switches=history[history.previous_party.notna() & history.previous_party.ne(history.canonical_party)].copy()
    switches["switch_evidence"]="cross_cycle_sos_identity"
    audit_path=WAR/"2014_incumbency_candidate_audit.csv"
    if audit_path.exists():
        audit=pd.read_csv(audit_path)
        audit=audit[audit.party_switch_flag.fillna(False).astype(bool)].copy()
        reviewed=pd.DataFrame({
            "person_id":"ALPERSON-"+audit.candidate.map(lambda x:re.sub(r"[^A-Z0-9]+","-",normalize_name(x)).strip("-")),
            "canonical_candidate_id":None,"year":audit.cycle.astype(int),"chamber":audit.chamber,
            "district":audit.district.astype(int),"canonical_party":audit.party,
            "previous_year":audit.cycle.astype(int)-4,"previous_party":audit.prior_party,
            "switch_evidence":"reviewed_incumbency_audit"})
        switches=(pd.concat([switches,reviewed],ignore_index=True,sort=False)
                  .sort_values("switch_evidence").drop_duplicates(["person_id","year"],keep="last"))

    # Map every source alias to the SOS-defined nominee of the same race/party.
    resolved=aliases.copy(); resolved["resolved_party"]=resolved.source_party
    party2010=dict(zip(sos.candidate_key,sos.resolved_party))
    mask=resolved.year.eq(2010)&resolved.source.eq("alabama_sos")
    resolved.loc[mask,"resolved_party"]=resolved.loc[mask,"candidate_key"].map(party2010).fillna("O")
    matches=[]
    pools={(r.year,r.chamber,r.district,r.canonical_party):r for r in canonical.itertuples(index=False)}
    for row in resolved.itertuples(index=False):
        target=pools.get((row.year,row.chamber,row.district,row.resolved_party))
        if target is None: continue
        name,vote,score=candidate_score(row.ballot_name,row.source_votes,target.canonical_name,target.canonical_votes)
        status="accepted" if row.source=="alabama_sos" or name==100 or (name>=75 and (score>=82 or vote==100)) else "review"
        matches.append({**row._asdict(),"canonical_candidate_id":target.canonical_candidate_id,
                        "canonical_name":target.canonical_name,"canonical_party":target.canonical_party,
                        "canonical_votes":target.canonical_votes,"name_score":name,"vote_score":vote,
                        "composite_score":score,"match_status":status})
    match=pd.DataFrame(matches); accepted=match[match.match_status.eq("accepted")]
    with sqlite3.connect(DB) as c:
        initialize(c)
        run_id=begin_run(c,"canonical_candidate_identity",{"years":model_cycles})
        canonical.to_sql("canonical_candidates",c,index=False,if_exists="replace")
        affiliations.to_sql("candidate_party_affiliations",c,index=False,if_exists="replace")
        switches.to_sql("candidate_party_switches",c,index=False,if_exists="replace")
        match.to_sql("candidate_alias_match_candidates",c,index=False,if_exists="replace")
        accepted.to_sql("candidate_aliases",c,index=False,if_exists="replace")
        install_identity_contracts(c)
        register_table(c,"canonical_candidates","canonical","scripts/build_candidate_identity.py",
                       "canonical_candidate_id","SOS candidates; reviewed secondary fallback only","replace",
                       "Canonical candidate-election identities")
        register_table(c,"dim_person","canonical","scripts/build_candidate_identity.py",
                       "person_id","Latest canonical candidate name","view","Canonical people dimension")
        register_table(c,"fact_candidate_election","canonical","scripts/build_candidate_identity.py",
                       "canonical_candidate_id","SOS candidates; reviewed secondary fallback only","view",
                       "Candidate-election fact view")
        register_table(c,"bridge_person_alias","canonical","scripts/build_candidate_identity.py",
                       "person_id + source + year + candidate_key","Accepted alias matches only","view",
                       "Auditable source aliases attached to canonical people")
        finish_run(c,run_id,{"canonical_candidates":len(canonical),"accepted_aliases":len(accepted),
                            "review_rows":len(review) if 'review' in locals() else 0})
    review=pd.concat([match[~match.match_status.eq("accepted")],pd.DataFrame(unresolved)],ignore_index=True,sort=False)
    review.to_csv(OUT/"candidate_identity_review.csv",index=False)
    pd.DataFrame(opposing_aliases).to_csv(OUT/"candidate_party_conflicts.csv",index=False)
    switches.to_csv(OUT/"candidate_party_switches.csv",index=False)
    print(match.groupby(["year","source","match_status"]).size().to_string())
    print(f"Canonical candidates: {len(canonical):,}; accepted aliases: {len(accepted):,}; "
          f"review: {len(review):,}; party switches: {len(switches):,}")

if __name__=="__main__":main()
