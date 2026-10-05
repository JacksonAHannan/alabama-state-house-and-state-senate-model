import sqlite3

import numpy as np
import pandas as pd
import pytest

import repair_alabama_1994_party_labels as party_repair
from build_1994_context_features import (KNOWN_1992_PRESIDENTIAL_GAPS, candidates,
    combined_context, district_demographics, finance_coverage, incumbency, incumbency_adjudications,
    presidential_features, presidential_precincts, require_1994_party_repair, shor_1996_party_disagreements)


def test_1994_demographics_cover_both_plans_and_reconcile_population():
    result= district_demographics()
    assert result.groupby("chamber").district.nunique().to_dict()=={"house":105,"senate":35}
    population=result.groupby("chamber").total_population.sum()
    assert abs(population.house-population.senate)/population.house<1e-8
    assert result.source_population_coverage.min()>0.999
    assert result.nonwhite_share.between(0,1).all()
    assert result.white_college_share.between(0,1).all()
    assert result.allocation_method.eq("1990_sf3_tract_area_interpolation_provisional").all()


def test_1992_presidential_archive_has_only_documented_gaps():
    precincts=presidential_precincts()
    assert precincts.county_key.nunique()==64
    assert not KNOWN_1992_PRESIDENTIAL_GAPS.intersection(set(precincts.county_key))
    district,matches=presidential_features(precincts)
    assert district.groupby("chamber").district.nunique().to_dict()=={"house":105,"senate":35}
    assert district.dem_margin.notna().sum()>=120
    assert not district.loc[district.dem_margin.isna(),"source_complete"].any()
    assert district.fallback_share.dropna().between(0,1+1e-12).all()
    assert {"exact","fuzzy","unmatched","county_level_ballot"}.issuperset(set(matches.match_method))


def test_1994_incumbency_is_positive_evidence_and_finance_unknown_not_zero():
    candidate=candidates();inc=incumbency(candidate);finance=finance_coverage(candidate)
    # The owner-adjudicated 1994 party-label repair (repair_alabama_1994_party_labels.py)
    # re-keys Sanderford to R, retires third-party rows and restores House 92 and the
    # split contests, which changes the unique-surname matches from 75 to 74; the
    # owner's SD31 Ellis incumbency adjudication then removes one false match (73).
    # The owner-directed Wikipedia research (2026-10-05, ALABAMA-1994-INCUMBENCY-20261005)
    # adds 24 incumbents the matcher missed and removes the HD75 Holley false match (96).
    repaired="AL-1994-house-20-R-SANDERFORD" in set(candidate.canonical_candidate_id)
    assert int(inc.incumbent.sum())==(96 if repaired else 75)
    adjudicated=set(incumbency_adjudications().canonical_candidate_id)&set(candidate.canonical_candidate_id)
    assert set(inc.loc[inc.review_status.eq("owner_adjudicated"),"canonical_candidate_id"])==adjudicated
    assert inc.loc[inc.incumbent.eq(0)&inc.review_status.ne("owner_adjudicated"),"review_status"].eq("unknown").all()
    assert finance.total_resources_raised.isna().all()
    assert finance.observation_status.eq("not_observed_unknown_not_zero").all()
    # Party is the canonical label; no later roster replaces it. Before the
    # warehouse repair is applied that label is the stale ballot-order "D".
    assert inc.party.tolist()==candidate.party.tolist()
    sanderford=inc[(inc.chamber.eq("house"))&(inc.district.eq(20))].iloc[0]
    assert sanderford.party==("R" if repaired else "D")


def test_1994_party_is_the_canonical_label_and_shor_1996_is_only_a_diagnostic():
    candidate=pd.DataFrame({"canonical_candidate_id":["AL-1994-house-89-D-FLOWERS","AL-1994-house-10-R-HANEY",
                                                      "AL-1994-house-11-D-DRAKE","AL-1994-house-11-R-ODEN"],
                            "cycle":1994,"chamber":"house","district":[89,10,11,11],"party":["D","R","D","R"],
                            "candidate":["Flowers","Haney","Drake","Oden"]})
    prior=pd.DataFrame({"year":1990,"winner":1,"chamber":"house","party":["D","D"],
                        "candidate_name":["Steve Flowers","Tom Drake"],"normalized_name":["STEVE FLOWERS","TOM DRAKE"]})
    inc=incumbency(candidate,prior=prior)
    assert inc.party.tolist()==["D","R","D","R"]
    assert inc.incumbent.tolist()==[1,0,1,0]
    assert inc.match_method.str.endswith("+canonical_1994_ballot_label").all()
    # Flowers ran as a Democrat in 1994 and served as a Republican by 1996: the
    # serving roster reports it for review but does not change the 1994 label.
    shor=pd.DataFrame({"name":["Flowers, Steve","Haney, Jim","Oden, Jeremy"],"party":["R","R","R"],"st":"AL",
                       "house1996":[1.0,1.0,1.0],"senate1996":np.nan})
    disagreements=shor_1996_party_disagreements(candidate,shor=shor)
    assert disagreements.to_dict("records")==[{"canonical_candidate_id":"AL-1994-house-89-D-FLOWERS","chamber":"house",
        "district":89,"candidate":"Flowers","party_1994":"D","shor_1996_party":"R"}]


def test_1994_context_has_no_fabricated_finance_ratio():
    demographics=district_demographics();precincts=presidential_precincts()
    president,_=presidential_features(precincts);candidate=candidates()
    context=combined_context(demographics,president,incumbency(candidate),finance_coverage(candidate))
    assert len(context)==140
    assert not context.finance_complete.any()
    assert context.log_resource_ratio_d_to_r.isna().all()


def test_sd31_ellis_incumbency_adjudication_overrides_only_its_surname_match():
    candidate=pd.DataFrame({"canonical_candidate_id":["AL-1994-senate-31-D-ELLIS","AL-1994-senate-31-R-ADAMS"],
                            "cycle":1994,"chamber":"senate","district":31,"party":["D","R"],"candidate":["Ellis","Adams"]})
    prior=pd.DataFrame({"year":1990,"winner":1,"chamber":"senate","party":["R"],
                        "candidate_name":["Frank Ellis, Jr."],"normalized_name":["FRANK ELLIS"]})
    records=incumbency_adjudications()
    inc=incumbency(candidate,prior=prior,adjudications=records).set_index("canonical_candidate_id")
    ellis=inc.loc["AL-1994-senate-31-D-ELLIS"]
    assert ellis.incumbent==0 and ellis.prior_candidate_name is None and ellis.review_status=="owner_adjudicated"
    assert ellis.match_method.endswith("+owner_adjudication:ADJ-1994-AL-INC-SD031-ELLIS-NOT-INCUMBENT")
    # Without the record the unchanged surname rule still makes the false match.
    raw=incumbency(candidate,prior=prior,adjudications=records.iloc[0:0]).set_index("canonical_candidate_id")
    assert raw.loc["AL-1994-senate-31-D-ELLIS","incumbent"]==1
    # A record whose match no longer occurs is stale and stops the build.
    with pytest.raises(ValueError,match="Stale incumbency adjudication"):
        incumbency(candidate,prior=prior.assign(normalized_name="FRANK JONES",candidate_name="Frank Jones"),adjudications=records)


def _guard_db(path,*,run=True,adjudications=True,old_id=False,second_position_d=False,undistricted=False):
    with sqlite3.connect(path) as c:
        c.executescript("""CREATE TABLE warehouse_build_run (build_run_id TEXT, target TEXT, status TEXT);
          CREATE TABLE warehouse_manual_adjudication (adjudication_id TEXT, review_status TEXT);
          CREATE TABLE canonical_candidates (canonical_candidate_id TEXT);
          CREATE TABLE vote_observations (year INTEGER, source TEXT, office TEXT, ballot_code TEXT, party TEXT, district REAL);""")
        if run:
            c.execute("INSERT INTO warehouse_build_run VALUES ('RUN-1',?,'validated')",(party_repair.TARGET,))
        if adjudications:
            c.executemany("INSERT INTO warehouse_manual_adjudication VALUES (?,'approved')",
                          [(a,) for a in party_repair.adjudication_ids()])
        c.executemany("INSERT INTO canonical_candidates VALUES (?)",
                      [("AL-1994-house-10-R-HANEY",),("AL-1994-house-91-R-MOORE",)]+([("AL-1994-house-10-D-HANEY",)] if old_id else []))
        c.execute("INSERT INTO vote_observations VALUES (1994,'alabama_sos','State House','BHS91','R',91.0)")
        c.execute("INSERT INTO vote_observations VALUES (1994,'alabama_sos','State House','AHS10','D',10.0)")
        if second_position_d:
            c.execute("INSERT INTO vote_observations VALUES (1994,'alabama_sos','State Senate','BSENAT31','D',31.0)")
        if undistricted:
            c.execute("INSERT INTO vote_observations VALUES (1994,'alabama_sos','State House','AHS92','D',NULL)")


@pytest.mark.parametrize("state,message",[
    ({"run":False},"not applied"),({"adjudications":False},"adjudications missing"),
    ({"old_id":True},"Superseded"),({"second_position_d":True},"pre-repair state"),({"undistricted":True},"pre-repair state")])
def test_context_build_refuses_a_pre_repair_1994_warehouse(tmp_path,state,message):
    path=tmp_path/"w.sqlite";_guard_db(path,**state)
    with sqlite3.connect(path) as c, pytest.raises(ValueError,match=message):
        require_1994_party_repair(c)


def test_context_build_accepts_the_repaired_1994_warehouse(tmp_path):
    path=tmp_path/"w.sqlite";_guard_db(path)
    with sqlite3.connect(path) as c:
        require_1994_party_repair(c)
