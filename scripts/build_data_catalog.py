"""Publish the initial machine-readable catalog and sync it into the warehouse."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from warehouse import ROOT, connect, initialize

ASSETS = [
    ("raw_sos_elections","raw_file","raw","data/raw/alabama_elections_and_geography/","scripts/sos_precinct.py","provider file + county/sheet","active",None,"Immutable official election archives"),
    ("source_vote_observations","database_table","source","vote_observations","scripts/build_election_database.py","source/year/county/precinct/office/district/candidate","active",None,"Normalized source observations; conflicting providers coexist"),
    ("canonical_votes","database_view","canonical","canonical_vote_observations","scripts/build_election_database.py","source observation natural key","active",None,"Authority-ranked election observations"),
    ("canonical_candidates","database_table","canonical","canonical_candidates","scripts/build_candidate_identity.py","canonical_candidate_id","active",None,"Canonical candidate-election identities"),
    ("people","database_view","canonical","dim_person","scripts/build_candidate_identity.py","person_id","active",None,"Canonical person dimension"),
    ("candidate_elections","database_view","canonical","fact_candidate_election","scripts/build_candidate_identity.py","canonical_candidate_id","active",None,"Canonical candidate-election facts"),
    ("candidate_aliases","database_view","canonical","bridge_person_alias","scripts/build_candidate_identity.py","person/source/year/candidate_key","active",None,"Accepted source alias evidence"),
    ("cmo_feature_mart","csv_export","mart","data/processed/elections/canonical_cmo_features.csv","scripts/build_canonical_cmo_features.py","cycle/chamber/district","compatibility",None,"Compatibility export pending mart table migration"),
    ("cmo_candidate_export","csv_export","mart","data/processed/elections/canonical_cmo_candidates.csv","scripts/build_canonical_cmo_features.py","canonical_candidate_id","compatibility","canonical_candidates","Compatibility export of canonical candidates"),
    ("historical_cmo_extension","csv_export","mart","data/processed/elections/historical_cmo_extension.csv","scripts/build_canonical_cmo_features.py","canonical_candidate_id","compatibility",None,"Provisional pre-2010 analytical extension"),
    ("raw_legiscan","raw_file","raw","data/raw/legiscan/alabama/","scripts/import_legiscan_alabama_rollcalls.py","LegiScan source IDs","active",None,"Immutable LegiScan session packages"),
    ("legiscan_bills_table","database_table","source","source_legiscan_bill","scripts/load_legislative_warehouse.py","bill_id","active",None,"Normalized LegiScan bills"),
    ("legiscan_rollcalls_table","database_table","source","source_legiscan_roll_call","scripts/load_legislative_warehouse.py","roll_call_id","active",None,"Recorded roll calls"),
    ("legiscan_votes_table","database_table","source","source_legiscan_member_vote","scripts/load_legislative_warehouse.py","roll_call_id/people_id","active",None,"Individual recorded votes"),
    ("legiscan_sponsors_table","database_table","source","source_legiscan_bill_sponsor","scripts/load_legislative_warehouse.py","bill_id/people_id/sponsor_order","active",None,"Bill sponsorship observations"),
    ("canonical_legislator_identity","database_view","canonical","canonical_legislator_identity","scripts/load_legislative_warehouse.py","people_id/person_id","active",None,"Human-approved candidate/legislator links"),
    ("legiscan_bills_csv","csv_export","source","data/processed/legislative/legiscan_alabama_bills.csv","scripts/import_legiscan_alabama_rollcalls.py","bill_id","compatibility","legiscan_bills_table","Compatibility export validated against warehouse"),
    ("legiscan_votes_csv","csv_export","source","data/processed/legislative/legiscan_alabama_individual_votes.csv","scripts/import_legiscan_alabama_rollcalls.py","roll_call/person","compatibility","legiscan_votes_table","Compatibility export validated against warehouse"),
    ("raw_finance","raw_file","raw","data/raw/finance/","scripts/build_multisource_finance_features.py","provider record ID","active",None,"Immutable state and FollowTheMoney files"),
    ("candidate_finance_mart","csv_export","mart","data/processed/war/ftm_race_finance_features.csv","scripts/build_multisource_finance_features.py","cycle/chamber/district","compatibility",None,"Planned finance mart table"),
    ("raw_census","raw_file","raw","data/raw/census/","scripts/build_geographic_crosswalks.py","Census GEOID","active",None,"Immutable Census archives and manifests"),
    ("precinct_district_weights","csv_export","canonical","data/processed/elections/canonical_precinct_district_weights.csv","scripts/build_canonical_geographic_weights.py","cycle/chamber/node/district","compatibility",None,"Planned canonical geography table"),
    ("forecast_features","csv_export","mart","data/processed/war/2026_prospective_features_and_forecast.csv","scripts/fit_2026_prospective_model.py","chamber/district","compatibility",None,"Versioned forecast mart migration pending"),
    ("published_cmo_data","csv_export","publication","docs/data/preliminary_cmo_candidates.csv","scripts/build_site.py","candidate-cycle","active",None,"Publication-only export; never an upstream input"),
]

LINEAGE = [
    ("raw_sos_elections","source_vote_observations","normalizes"),
    ("source_vote_observations","canonical_votes","reconciles"),
    ("source_vote_observations","canonical_candidates","reconciles"),
    ("canonical_candidates","people","reconciles"),
    ("canonical_candidates","candidate_elections","reconciles"),
    ("canonical_candidates","candidate_aliases","reconciles"),
    ("canonical_candidates","cmo_feature_mart","features"),
    ("cmo_feature_mart","published_cmo_data","exports"),
    ("raw_legiscan","legiscan_bills_csv","normalizes"),
    ("raw_legiscan","legiscan_votes_csv","normalizes"),
    ("legiscan_bills_csv","legiscan_bills_table","normalizes"),
    ("legiscan_votes_csv","legiscan_votes_table","normalizes"),
    ("legiscan_bills_table","legiscan_rollcalls_table","reconciles"),
    ("legiscan_rollcalls_table","legiscan_votes_table","reconciles"),
    ("legiscan_bills_table","legiscan_sponsors_table","reconciles"),
    ("candidate_elections","canonical_legislator_identity","reconciles"),
    ("raw_finance","candidate_finance_mart","features"),
    ("raw_census","precinct_district_weights","reconciles"),
]


def main() -> None:
    columns=["asset_id","asset_kind","layer","locator","owner_script","key_description",
             "status","replacement_asset_id","notes"]
    frame=pd.DataFrame(ASSETS,columns=columns)
    output=ROOT/"project_docs"/"data_catalog.csv"
    frame.to_csv(output,index=False)
    with closing(connect()) as connection:
        initialize(connection)
        connection.executemany("""INSERT INTO warehouse_asset
          (asset_id,asset_kind,layer,locator,owner_script,key_description,status,replacement_asset_id,notes)
          VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET
          asset_kind=excluded.asset_kind,layer=excluded.layer,locator=excluded.locator,
          owner_script=excluded.owner_script,key_description=excluded.key_description,
          status=excluded.status,replacement_asset_id=excluded.replacement_asset_id,notes=excluded.notes""",ASSETS)
        connection.executemany("INSERT OR REPLACE INTO warehouse_asset_lineage VALUES (?,?,?)",LINEAGE)
        connection.commit()
    print(f"Cataloged {len(frame)} assets and {len(LINEAGE)} lineage edges: {output}")


if __name__=="__main__":main()
