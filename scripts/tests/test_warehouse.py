import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
import pandas as pd

from warehouse import atomic_database, connect, initialize, install_identity_contracts
import build_election_database


def test_control_schema_has_version_and_enforces_enums(tmp_path):
    path=tmp_path/"warehouse.sqlite"
    with closing(connect(path)) as connection:
        initialize(connection)
        assert connection.execute("select max(version) from warehouse_schema_version").fetchone()[0]==1
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("""insert into warehouse_table_registry values
              ('bad','unknown','owner',null,null,'replace','bad layer')""")


def test_atomic_database_preserves_working_copy_on_failure(tmp_path):
    target=tmp_path/"warehouse.sqlite"
    with closing(sqlite3.connect(target)) as connection:
        connection.execute("create table marker(value text)")
        connection.execute("insert into marker values ('working')")
        connection.commit()
    with pytest.raises(RuntimeError):
        with atomic_database(target) as building:
            with closing(sqlite3.connect(building)) as connection:
                connection.execute("create table replacement(value text)")
                connection.commit()
            raise RuntimeError("validation failed")
    with closing(sqlite3.connect(target)) as connection:
        assert connection.execute("select value from marker").fetchone()[0]=="working"


def test_identity_contract_rejects_duplicate_candidate_election(tmp_path):
    path=tmp_path/"warehouse.sqlite"
    with closing(connect(path)) as connection:
        initialize(connection)
        connection.executescript("""
          create table canonical_candidates(
            year integer,chamber text,district integer,canonical_party text,canonical_votes real,
            canonical_name text,canonical_source text,person_id text,canonical_candidate_id text,
            incumbent integer,winner integer);
          create table candidate_party_affiliations(
            person_id text,canonical_candidate_id text,year integer,chamber text,district integer,
            canonical_party text);
          create table candidate_aliases(
            year integer,source text,chamber text,district integer,candidate_key text,ballot_name text,
            source_party text,source_votes real,resolved_party text,canonical_candidate_id text,
            canonical_name text,canonical_party text,canonical_votes real,name_score real,vote_score real,
            composite_score real,match_status text);
          insert into canonical_candidates values
            (2022,'house',1,'D',10,'Alice','sos','P1','C1',0,1);
        """)
        install_identity_contracts(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("""insert into canonical_candidates values
              (2022,'house',1,'D',9,'Alicia','sos','P2','C2',0,0)""")
        assert connection.execute("select count(*) from dim_person").fetchone()[0]==1


def test_election_build_installs_control_plane_and_source_registry(tmp_path, monkeypatch):
    root=tmp_path
    raw=root/"data"/"raw"/"alabama_elections_and_geography"
    raw.mkdir(parents=True)
    (raw/"fake.zip").write_bytes(b"immutable source")
    frame=pd.DataFrame([{
        "year":1994,"county":"Autauga","county_key":"AUTAUGA","precinct":"P1",
        "precinct_key":"P1","office":"Governor","district":None,"candidate":"Alice",
        "party":"DEM","party_norm":"D","votes":10.0,
    }])
    monkeypatch.setitem(build_election_database.YEAR_SOURCES,1994,"fake")
    monkeypatch.setattr(build_election_database,"load_sos_year",lambda _root,_year:frame.copy())
    database=build_election_database.build(root,[1994])
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("select count(*) from vote_observations").fetchone()[0]==1
        assert connection.execute("select max(version) from warehouse_schema_version").fetchone()[0]==1
        source=connection.execute("select provider,extraction_status from warehouse_source_file").fetchone()
        assert source==("alabama_sos","normalized")
        assert connection.execute("pragma integrity_check").fetchone()[0]=="ok"


def test_legislative_schema_enforces_rollcall_vote_relationships(tmp_path):
    path=tmp_path/"warehouse.sqlite"
    schema=Path(__file__).resolve().parents[1]/"warehouse_legislative_schema.sql"
    with closing(connect(path)) as connection:
        initialize(connection)
        connection.execute("create table dim_person(person_id text primary key,preferred_name text)")
        connection.executescript(schema.read_text(encoding="utf-8"))
        connection.execute("insert into source_legiscan_session values (1,2022,'2022 Regular')")
        connection.execute("insert into source_legiscan_person values (10,'Member','MEMBER','roster')")
        connection.execute("""insert into source_legiscan_bill
          (bill_id,session_id,session_year,session_name,bill_number,source_archive)
          values (100,1,2022,'2022 Regular','HB1','archive.zip')""")
        connection.execute("""insert into source_legiscan_roll_call
          (roll_call_id,bill_id,session_year,source_archive) values (200,100,2022,'archive.zip')""")
        connection.execute("""insert into source_legiscan_member_vote
          (roll_call_id,people_id,bill_id,session_year,vote,source_archive)
          values (200,10,100,2022,'Yea','archive.zip')""")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("""insert into source_legiscan_member_vote
              (roll_call_id,people_id,bill_id,session_year,vote,source_archive)
              values (999,10,100,2022,'Yea','archive.zip')""")


def test_canonical_legislator_view_requires_approved_match(tmp_path):
    path=tmp_path/"warehouse.sqlite"
    schema=Path(__file__).resolve().parents[1]/"warehouse_legislative_schema.sql"
    with closing(connect(path)) as connection:
        initialize(connection)
        connection.execute("create table dim_person(person_id text primary key,preferred_name text)")
        connection.execute("insert into dim_person values ('P1','Canonical Member')")
        connection.executescript(schema.read_text(encoding="utf-8"))
        connection.execute("insert into source_legiscan_person values (10,'Member','MEMBER','roster')")
        base=(10,'P1','exact_name_candidate','proposed','review.csv',None)
        connection.execute("insert into canonical_legislator_person_match values (?,?,?,?,?,?)",base)
        assert connection.execute("select count(*) from canonical_legislator_identity").fetchone()[0]==0
        connection.execute("update canonical_legislator_person_match set review_status='approved'")
        assert connection.execute("select count(*) from canonical_legislator_identity").fetchone()[0]==1
