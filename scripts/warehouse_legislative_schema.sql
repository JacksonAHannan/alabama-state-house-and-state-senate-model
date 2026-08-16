PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO warehouse_schema_version(version,applied_at_utc,description)
VALUES (2,strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'Normalized LegiScan legislative records and reviewed legislator identity views');

CREATE TABLE IF NOT EXISTS source_legiscan_session (
  session_id INTEGER PRIMARY KEY,
  session_year INTEGER,
  session_name TEXT,
  UNIQUE(session_year,session_name)
);

CREATE TABLE IF NOT EXISTS source_legiscan_person (
  people_id INTEGER PRIMARY KEY,
  preferred_name TEXT,
  normalized_name TEXT,
  record_status TEXT NOT NULL CHECK(record_status IN ('roster','vote_only_stub'))
);

CREATE TABLE IF NOT EXISTS source_legiscan_legislator_session (
  session_year INTEGER NOT NULL,
  people_id INTEGER NOT NULL REFERENCES source_legiscan_person(people_id),
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  first_name TEXT,middle_name TEXT,last_name TEXT,suffix TEXT,
  party TEXT,party_id INTEGER,role TEXT,role_id INTEGER,district TEXT,
  source_archive TEXT NOT NULL,source_member TEXT,
  source_file_id TEXT REFERENCES warehouse_source_file(source_file_id),
  PRIMARY KEY(session_year,people_id)
);

CREATE TABLE IF NOT EXISTS source_legiscan_bill (
  bill_id INTEGER PRIMARY KEY,
  session_id INTEGER REFERENCES source_legiscan_session(session_id),
  session_year INTEGER,session_name TEXT,bill_number TEXT,title TEXT,description TEXT,
  status INTEGER,status_date TEXT,url TEXT,state_link TEXT,
  source_archive TEXT NOT NULL,source_member TEXT,
  source_file_id TEXT REFERENCES warehouse_source_file(source_file_id)
);

CREATE TABLE IF NOT EXISTS source_legiscan_roll_call (
  roll_call_id INTEGER PRIMARY KEY,
  bill_id INTEGER NOT NULL REFERENCES source_legiscan_bill(bill_id),
  session_year INTEGER,vote_date TEXT,chamber TEXT,vote_description TEXT,
  yea INTEGER,nay INTEGER,not_voting INTEGER,absent INTEGER,total INTEGER,passed INTEGER,
  url TEXT,state_link TEXT,source_archive TEXT NOT NULL,source_member TEXT,
  source_file_id TEXT REFERENCES warehouse_source_file(source_file_id)
);

CREATE TABLE IF NOT EXISTS source_legiscan_member_vote (
  roll_call_id INTEGER NOT NULL REFERENCES source_legiscan_roll_call(roll_call_id),
  people_id INTEGER NOT NULL REFERENCES source_legiscan_person(people_id),
  bill_id INTEGER NOT NULL REFERENCES source_legiscan_bill(bill_id),
  session_year INTEGER,vote_date TEXT,chamber TEXT,vote_id INTEGER,vote TEXT,
  source_archive TEXT NOT NULL,source_file_id TEXT REFERENCES warehouse_source_file(source_file_id),
  PRIMARY KEY(roll_call_id,people_id)
);

CREATE TABLE IF NOT EXISTS source_legiscan_bill_sponsor (
  bill_id INTEGER NOT NULL REFERENCES source_legiscan_bill(bill_id),
  people_id INTEGER NOT NULL REFERENCES source_legiscan_person(people_id),
  sponsor_order INTEGER NOT NULL,sponsor_type_id INTEGER,committee_sponsor INTEGER,
  bill_number TEXT,session_id INTEGER,session_name TEXT,name TEXT,party TEXT,role TEXT,district TEXT,
  PRIMARY KEY(bill_id,people_id,sponsor_order)
);

CREATE TABLE IF NOT EXISTS source_legiscan_bill_history (
  bill_id INTEGER NOT NULL REFERENCES source_legiscan_bill(bill_id),
  history_order INTEGER NOT NULL,bill_number TEXT,session_id INTEGER,session_name TEXT,
  action_date TEXT,action TEXT,chamber TEXT,importance INTEGER,
  PRIMARY KEY(bill_id,history_order)
);

CREATE TABLE IF NOT EXISTS source_legiscan_bill_subject (
  bill_id INTEGER NOT NULL REFERENCES source_legiscan_bill(bill_id),
  subject_id INTEGER NOT NULL,bill_number TEXT,session_id INTEGER,session_name TEXT,subject_name TEXT,
  PRIMARY KEY(bill_id,subject_id)
);

CREATE TABLE IF NOT EXISTS source_legiscan_amendment (
  amendment_id INTEGER PRIMARY KEY,
  bill_id INTEGER NOT NULL REFERENCES source_legiscan_bill(bill_id),
  bill_number TEXT,session_id INTEGER,session_name TEXT,date TEXT,chamber TEXT,title TEXT,
  description TEXT,adopted INTEGER,url TEXT,state_link TEXT,amendment_hash TEXT
);

CREATE TABLE IF NOT EXISTS source_legiscan_bill_document (
  doc_id INTEGER PRIMARY KEY,
  bill_id INTEGER NOT NULL REFERENCES source_legiscan_bill(bill_id),
  bill_number TEXT,session_id INTEGER,session_name TEXT,document_date TEXT,document_type TEXT,
  mime TEXT,url TEXT,state_link TEXT,text_size INTEGER,text_hash TEXT,source_archive TEXT,
  source_file_id TEXT REFERENCES warehouse_source_file(source_file_id)
);

CREATE TABLE IF NOT EXISTS canonical_legislator_person_match (
  people_id INTEGER NOT NULL REFERENCES source_legiscan_person(people_id),
  person_id TEXT NOT NULL,
  match_method TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('proposed','approved','rejected','superseded')),
  evidence_locator TEXT NOT NULL,
  review_note TEXT,
  PRIMARY KEY(people_id,person_id,match_method)
);

CREATE INDEX IF NOT EXISTS legiscan_bill_session_idx ON source_legiscan_bill(session_year,session_id);
CREATE INDEX IF NOT EXISTS legiscan_roll_bill_idx ON source_legiscan_roll_call(bill_id,vote_date);
CREATE INDEX IF NOT EXISTS legiscan_vote_person_idx ON source_legiscan_member_vote(people_id,session_year);
CREATE INDEX IF NOT EXISTS legiscan_sponsor_person_idx ON source_legiscan_bill_sponsor(people_id,bill_id);

DROP VIEW IF EXISTS canonical_legislator_identity;
CREATE VIEW canonical_legislator_identity AS
SELECT m.people_id,m.person_id,p.preferred_name AS legiscan_name,d.preferred_name AS canonical_name,
       m.match_method,m.evidence_locator,m.review_note
FROM canonical_legislator_person_match m
JOIN source_legiscan_person p USING(people_id)
JOIN dim_person d USING(person_id)
WHERE m.review_status='approved'
  AND NOT EXISTS (
    SELECT 1 FROM canonical_legislator_person_match newer
    WHERE newer.people_id=m.people_id AND newer.person_id=m.person_id
      AND newer.review_status='superseded');

DROP VIEW IF EXISTS canonical_legislator_service;
CREATE VIEW canonical_legislator_service AS
SELECT i.person_id,s.session_year,s.people_id,s.name,s.party,s.role,s.district,
       s.source_archive,s.source_file_id
FROM source_legiscan_legislator_session s
JOIN canonical_legislator_identity i USING(people_id);
