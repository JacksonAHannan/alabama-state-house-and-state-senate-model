"""Apply the source-confirmed 2026-09-05 audit repairs, with backup and evidence.

This repairs historical source storage, not models or published scores. Unresolved
source errors and stale dependent materializations remain explicit review items.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from shapely import from_wkb

from build_election_database import _observations
from load_southern_2016_vest_warehouse import load_state
from sos_precinct import _legacy_2002, _workbook_sheets, load_sos_year, normalize_workbook
from warehouse import ROOT, begin_run, connect, database_path, file_sha256, finish_run, register_table, utcnow

TARGET = "source_quality_repair_2026_09_05"
SCOPE = "source='alabama_sos' AND (year=1994 OR (year=2002 AND county_key='MARSHALL') OR (year=2014 AND county_key='JEFFERSON'))"
KEY = "source,year,county_key,precinct_key,office,district,candidate_key"
SCRIPTS = Path(__file__).parent


def scoped_digest(connection):
    digest = hashlib.sha256()
    for row in connection.execute(f'SELECT * FROM vote_observations WHERE {SCOPE} ORDER BY rowid'):
        digest.update(json.dumps(row, ensure_ascii=True).encode())
        digest.update(b'\n')
    return digest.hexdigest()


def execute_statements(connection, script):
    """Execute DDL without executescript's implicit transaction commit."""
    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        raise ValueError("Incomplete SQL statement")


def evidence(connection, run, issue, table, scope, status, details):
    connection.execute("INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)",
                       (issue, run, table, scope, status, json.dumps(details, sort_keys=True), utcnow()))


def registered_source(connection, suffix):
    rows = connection.execute("SELECT source_file_id,local_path,sha256 FROM warehouse_source_file WHERE local_path LIKE ?",
                              ('%' + suffix,)).fetchall()
    if len(rows) != 1:
        raise ValueError(f"Expected one registered source: {suffix}")
    identifier, relative, digest = rows[0]
    path = ROOT / relative
    if file_sha256(path) != digest:
        raise ValueError(f"Source hash changed: {relative}")
    return identifier, path, digest


def stage_votes(connection):
    sources = {year: registered_source(connection, filename) for year, filename in {
        1994: '94g-prec.zip', 2002: '2002-GeneralElection-PrecinctLevel_0.xls',
        2014: '2014General-precinctLevel.zip'}.items()}
    frames = [load_sos_year(ROOT, 1994)]
    rows = _workbook_sheets(sources[2002][1].read_bytes())['MARSHALL']
    marshall = _legacy_2002(rows, 'MARSHALL')
    marshall['year'] = 2002
    marshall['source_file'] = sources[2002][1].name + '::MARSHALL'
    marshall['source_sheet'] = 'MARSHALL'
    from oe_normalize import norm_party
    marshall['party_norm'] = marshall.party.map(norm_party)
    marshall['county_key'] = 'MARSHALL'
    marshall['precinct_key'] = marshall.precinct.str.upper().str.strip()
    frames.append(marshall)
    with ZipFile(sources[2014][1]) as archive:
        member = 'Jefferson 2014 General Precinct.xls'
        jefferson = normalize_workbook(archive.read(member), 'Jefferson', 2014)
        jefferson['source_file'] = member
    frames.append(jefferson)
    staged = _observations(pd.concat(frames, ignore_index=True), 'alabama_sos', 1)
    staged['source_file_id'] = staged.year.map({year: source[0] for year, source in sources.items()})
    if staged.duplicated(['source_file_id', 'source_file', 'source_sheet', 'source_row', 'source_column']).any():
        raise ValueError('Repeated source cell in staged repairs')
    # 1994 identity/party repair must not drop or alter a single vote value.
    old = pd.read_sql_query("SELECT county_key,office,candidate_key,votes FROM vote_observations WHERE source='alabama_sos' AND year=1994", connection)
    new = staged[staged.year.eq(1994)][old.columns]
    columns = list(old.columns)
    pd.testing.assert_frame_equal(old.sort_values(columns).reset_index(drop=True),
                                  new.sort_values(columns).reset_index(drop=True), check_dtype=False)
    # Every repaired county result must reconcile to its own printed summary.
    checks = []
    for year, county, frame, raw, total_col in [
        (2002, 'MARSHALL', marshall, rows, 6),
        (2014, 'JEFFERSON', jefferson, _workbook_sheets(archive_bytes(sources[2014][1], member))['Jefferson_Crosstab'], 3),
    ]:
        for row_number, group in frame.groupby('source_row'):
            source = raw[int(row_number)-1]
            total = float(source[total_col])
            if abs(float(group.votes.sum()) - total) > 1e-8:
                raise ValueError(f'Source total disagreement: {year}/{county}/row {row_number}')
            checks.append({'year': year, 'county': county, 'source_row': int(row_number),
                           'summary_column': total_col+1, 'reported': total,
                           'precinct_sum': float(group.votes.sum()), 'precinct_cells': len(group)})
    return staged, sources, checks


def archive_bytes(path, member):
    with ZipFile(path) as archive:
        return archive.read(member)


def stage_geometry(connection):
    cursor = connection.execute("""SELECT v.*,s.local_path,s.sha256 FROM source_southern_vest_context_file v
                                   JOIN warehouse_source_file s USING(source_file_id) WHERE v.state_code='AR'""")
    row = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))
    if file_sha256(ROOT / row['local_path']) != row['sha256']:
        raise ValueError('Arkansas VEST source hash mismatch')
    tables = ['dim_southern_geography_layer', 'dim_southern_geography_unit',
              'source_southern_presidential_geography_result', 'bridge_southern_result_geography']
    repairs = []
    with closing(sqlite3.connect(':memory:')) as staged:
        for table in tables:
            staged.execute(connection.execute('SELECT sql FROM sqlite_master WHERE name=?', (table,)).fetchone()[0])
        audit = load_state(staged, row, 'STAGING')
        old_results = connection.execute("SELECT result_observation_id,dem_votes,rep_votes,other_votes,total_votes FROM source_southern_presidential_geography_result WHERE source_file_id=? ORDER BY 1", (row['source_file_id'],)).fetchall()
        new_results = staged.execute("SELECT result_observation_id,dem_votes,rep_votes,other_votes,total_votes FROM source_southern_presidential_geography_result ORDER BY 1").fetchall()
        if old_results != new_results:
            raise ValueError('Geometry repair changed source results or identifiers')
        for identifier, old_wkb in connection.execute("SELECT geography_unit_id,geometry_wkb FROM dim_southern_geography_unit WHERE state_code='AR' AND cycle=2016 AND geography_type='precinct'"):
            shape = from_wkb(old_wkb)
            if shape.is_valid:
                continue
            replacement = staged.execute("SELECT geometry_wkb,geometry_sha256,min_x,min_y,max_x,max_y,area_sq_km FROM dim_southern_geography_unit WHERE geography_unit_id=?", (identifier,)).fetchone()
            if replacement is None or not from_wkb(replacement[0]).is_valid:
                raise ValueError('Invalid staged replacement geometry')
            delta = abs(shape.area - from_wkb(replacement[0]).area)
            if delta > 1e-10:
                raise ValueError('Geometry repair changes material polygon area; requires review')
            repairs.append((identifier, hashlib.sha256(old_wkb).hexdigest(), replacement, delta))
    return repairs, row, audit


def repair(database: Path, backup: Path):
    database, backup = database.resolve(), backup.resolve()
    if database == backup or backup.exists():
        raise FileExistsError('Backup must be a new, separate path')
    with closing(connect(database, readonly=True)) as source:
        prior = source.execute("SELECT build_run_id,validation_json FROM warehouse_build_run WHERE target=? AND status='validated'", (TARGET,)).fetchall()
        if prior:
            return {'already_applied': prior[0][0], 'validation': json.loads(prior[0][1])}
        print('Staging source-grounded vote and geometry repairs', flush=True)
        staged_digest = scoped_digest(source)
        staged, sources, reconciliations = stage_votes(source)
        geometries, geometry_source, geometry_audit = stage_geometry(source)
        backup.parent.mkdir(parents=True, exist_ok=True)
        with backup.open('xb'):
            pass
        with closing(sqlite3.connect(backup)) as destination:
            source.backup(destination)
            if destination.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Backup failed SQLite quick_check')
    print(f'Backup verified: {backup}', flush=True)
    with closing(connect(database)) as connection:
        connection.execute('BEGIN IMMEDIATE')
        try:
            # Refuse stale staging if an overlapping writer changed source rows.
            connection.execute('ATTACH DATABASE ? AS before_repair', (backup.as_posix(),))
            old_count = connection.execute(f'SELECT COUNT(*) FROM vote_observations WHERE {SCOPE}').fetchone()[0]
            backup_count = connection.execute(f'SELECT COUNT(*) FROM before_repair.vote_observations WHERE {SCOPE}').fetchone()[0]
            if old_count != backup_count:
                raise ValueError('Source rows changed during repair staging')
            if scoped_digest(connection) != staged_digest:
                raise ValueError('Source values changed during repair staging')
            configuration = {'backup': str(backup), 'source_hashes': {str(y): s[2] for y, s in sources.items()},
                             'code_hashes': {p.name: file_sha256(p) for p in [Path(__file__), SCRIPTS/'sos_precinct.py', SCRIPTS/'load_southern_2016_vest_warehouse.py', SCRIPTS/'warehouse_legislative_quality.sql', SCRIPTS/'warehouse_southern_war_preparation_schema.sql']}}
            run = begin_run(connection, TARGET, configuration)
            connection.execute("""CREATE TABLE IF NOT EXISTS qa_warehouse_source_repair(
              issue_id TEXT PRIMARY KEY,build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
              warehouse_object TEXT NOT NULL,scope TEXT NOT NULL,status TEXT NOT NULL,
              evidence_json TEXT NOT NULL,recorded_at_utc TEXT NOT NULL)""")
            existing = {r[1] for r in connection.execute('PRAGMA table_info(vote_observations)')}
            staged['build_run_id'] = run
            for column in staged.columns:
                if column not in existing:
                    kind = 'INTEGER' if column in {'source_row', 'source_column'} else 'TEXT'
                    connection.execute(f'ALTER TABLE vote_observations ADD COLUMN {column} {kind}')
            connection.execute(f'DELETE FROM vote_observations WHERE {SCOPE}')
            connection.executemany(f"INSERT INTO vote_observations ({','.join(staged.columns)}) VALUES ({','.join('?' for _ in staged.columns)})",
                                   (tuple(None if pd.isna(v) else v for v in row) for row in staged.itertuples(index=False, name=None)))
            evidence(connection, run, 'WQA-01-02', 'vote_observations', 'Jefferson 2014; Marshall 2002', 'repaired',
                     {'reconciliation': reconciliations, 'before_images': str(backup), 'old_scoped_rows': old_count, 'new_scoped_rows': len(staged)})
            evidence(connection, run, 'WQA-03-04', 'vote_observations', 'Alabama 1994', 'repaired_with_review',
                     {'rows': int(staged.year.eq(1994).sum()), 'source_cells_preserved': True,
                      'precinct_key': 'provider precinct number; display name retained',
                      'party_encoding': 'AG1=D; AG2=R', 'unresolved': 'Remaining key collisions and source fractional vote retained in qa_vote_observation_quality'})
            execute_statements(connection, f"""
DROP VIEW IF EXISTS qa_vote_observation_quality;
CREATE VIEW qa_vote_observation_quality AS
SELECT {KEY},COUNT(*) AS observations,'duplicate_natural_key' AS issue
FROM vote_observations GROUP BY {KEY} HAVING COUNT(*)>1
UNION ALL
SELECT {KEY},COUNT(*),'fractional_source_vote'
FROM vote_observations WHERE votes<>CAST(votes AS INTEGER) GROUP BY {KEY};
""")
            for identifier, old_hash, replacement, delta in geometries:
                updated = connection.execute("UPDATE dim_southern_geography_unit SET geometry_wkb=?,geometry_sha256=?,min_x=?,min_y=?,max_x=?,max_y=?,area_sq_km=? WHERE geography_unit_id=? AND geometry_sha256=?", (*replacement, identifier, old_hash))
                if updated.rowcount != 1:
                    raise ValueError('Geometry changed during repair staging')
                evidence(connection, run, 'WQA-05-' + identifier, 'dim_southern_geography_unit', identifier, 'repaired',
                         {'source_file_id': geometry_source['source_file_id'], 'source_sha256': geometry_source['sha256'],
                          'old_geometry_sha256': old_hash, 'new_geometry_sha256': replacement[1], 'area_delta_square_degrees': delta,
                          'method': 'source reload; make_valid after WGS84 reprojection; retain polygonal area', 'source_results_unchanged': True})
            execute_statements(connection, (SCRIPTS/'warehouse_legislative_quality.sql').read_text())
            rollcalls = pd.read_sql_query("SELECT * FROM qa_legiscan_roll_call_reconciliation WHERE validation_status='review'", connection)
            for record in rollcalls.to_dict('records'):
                locator = connection.execute('SELECT local_path FROM warehouse_source_file WHERE source_file_id=?', (record['source_file_id'],)).fetchone()[0]
                raw = json.loads(archive_bytes(ROOT/locator, record['source_member']))
                raw = raw.get('roll_call', raw.get('rollcall', raw))
                for field, raw_field in [('reported_total','total'), ('reported_yea','yea'), ('reported_nay','nay'),
                                         ('reported_not_voting','nv'), ('reported_absent','absent')]:
                    if record[field] != raw[raw_field]:
                        raise ValueError('LegiScan reported tally does not match original JSON')
                source_votes = sorted((int(v['people_id']), int(v['vote_id'])) for v in raw['votes'])
                stored_votes = connection.execute('SELECT people_id,vote_id FROM source_legiscan_member_vote WHERE roll_call_id=? ORDER BY people_id,vote_id', (record['roll_call_id'],)).fetchall()
                if source_votes != stored_votes:
                    raise ValueError('LegiScan source/member mismatch requires a separate repair')
                evidence(connection, run, 'WQA-06-' + str(record['roll_call_id']), 'source_legiscan_roll_call', str(record['roll_call_id']), 'source_review',
                         {**record, 'raw_member_array_matches': True, 'source_path': locator})
            finance_sql = (SCRIPTS/'warehouse_southern_war_preparation_schema.sql').read_text()
            finance_view = finance_sql.split('DROP VIEW IF EXISTS mart_southern_war_training_with_finance;')[1].split('DROP VIEW IF EXISTS qa_southern_war_training_with_finance_coverage;')[0]
            connection.execute('DROP VIEW mart_southern_war_training_with_finance')
            execute_statements(connection, finance_view)
            evidence(connection, run, 'WQA-07', 'mart_southern_war_training_with_finance', 'incomplete finance inputs', 'repaired',
                     {'method': 'Mask amounts and ratio when finance_complete != 1; preserve all source/race-mart amounts'})
            manifest = json.loads((ROOT/'data/processed/war/dime_finance_build_manifest.json').read_text())
            if manifest['source']['retrieved_at'] is None:
                updated = connection.execute("UPDATE warehouse_source_file SET retrieved_at_utc=NULL WHERE source_file_id=? AND sha256=?",
                                             (manifest['source']['source_file_id'], manifest['source']['sha256']))
                if updated.rowcount != 1:
                    raise ValueError('DIME source registration no longer matches evidence')
                evidence(connection, run, 'WQA-08-DIME', 'warehouse_source_file', 'DIME', 'repaired',
                         {'evidence': 'data/processed/war/dime_finance_build_manifest.json', 'retrieval_time': 'unknown; not registration time'})
            for table, key in {
                'mart_historical_precinct_district_weight': 'cycle/chamber/county_key/precinct_key/district',
                'mart_historical_district_office_baseline': 'cycle/chamber/district/office',
                'source_historical_presidential_precinct': 'cycle/county_key/precinct_key',
            }.items():
                connection.execute('UPDATE warehouse_table_registry SET primary_key_description=? WHERE table_name=?', (key, table))
            evidence(connection, run, 'WQA-08-remaining', 'warehouse_source_file', 'legacy provenance', 'review',
                     {'unresolved': ['Missing source terms/scope require original acquisition evidence',
                                     'Legacy Alabama canonical build lineage cannot be inferred from a later registration',
                                     'Older running jobs require liveness/recovery evidence; statuses unchanged']})
            evidence(connection, run, 'WQA-dependencies', 'warehouse_asset_lineage', 'affected materializations and compatibility files', 'stale_review',
                     {'source_scope': SCOPE, 'not_rebuilt': ['precinct_nodes', 'precinct_vote_fingerprints', 'precinct_source_links',
                       'precinct_match_candidates', 'historical precinct/district weights and baselines for 1994/2002',
                       'geometry-based Arkansas allocations', 'dependent model and publication files'],
                      'note': 'Do not certify existing materializations from this source repair. No models or published scores rebuilt.'})
            for table, layer, key in [('qa_warehouse_source_repair','qa','issue_id'), ('qa_vote_observation_quality','qa',KEY+'/issue'),
                                      ('qa_legiscan_roll_call_reconciliation','qa','roll_call_id'), ('canonical_legiscan_roll_call','canonical','roll_call_id'),
                                      ('canonical_legiscan_member_vote','canonical','roll_call_id/people_id')]:
                register_table(connection, table, layer, 'scripts/repair_warehouse_source_defects.py', key,
                               'Source-backed repairs; unresolved evidence retained', 'append' if table=='qa_warehouse_source_repair' else 'view',
                               '2026-09-05 source quality repair and reconciliation')
            validation = validate(connection)
            validation.update({'repaired_geometry_rows': len(geometries), 'source_summary_checks': len(reconciliations),
                               'legiscan_source_conflicts': len(rollcalls), 'backup': str(backup)})
            connection.execute('INSERT INTO warehouse_schema_version VALUES (26,?,?)', (utcnow(), 'Source-grounded audit repairs and explicit quality/review interfaces'))
            finish_run(connection, run, validation)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return {'build_run_id': run, 'validation': validation}


def validate(connection):
    if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise ValueError('SQLite quick_check failed')
    if connection.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('Foreign key violation')
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall():
        connection.execute(f'SELECT * FROM "{name}" LIMIT 0')
    malformed = connection.execute("SELECT COUNT(*) FROM vote_observations WHERE source='alabama_sos' AND ((year=2014 AND county_key='JEFFERSON' AND precinct_key='TOTAL OF REGISTERED VOTERS') OR (year=2002 AND county_key='MARSHALL' AND office='MARSHALL') OR (year=1994 AND office='Attorney General' AND ballot_code='AG2' AND party_norm<>'R'))").fetchone()[0]
    incomplete = connection.execute("SELECT COUNT(*) FROM mart_southern_war_training_with_finance WHERE finance_complete=0 AND (democratic_fundraising IS NOT NULL OR republican_fundraising IS NOT NULL OR log_fundraising_ratio_d_to_r IS NOT NULL)").fetchone()[0]
    invalid_geometry = sum(not from_wkb(wkb).is_valid for (wkb,) in connection.execute('SELECT geometry_wkb FROM dim_southern_geography_unit'))
    if malformed or incomplete or invalid_geometry:
        raise ValueError(f'Repair failed: {malformed=}, {incomplete=}, {invalid_geometry=}')
    issues = connection.execute('SELECT issue,COUNT(*),SUM(observations-1) FROM qa_vote_observation_quality GROUP BY issue').fetchall()
    return {'sqlite_quick_check': 'ok', 'foreign_key_violations': 0, 'repaired_pattern_failures': malformed,
            'incomplete_finance_numeric_rows': incomplete, 'invalid_geometry_rows': invalid_geometry,
            'remaining_vote_review_groups': issues, 'dependent_outputs': 'stale_review; not rebuilt'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=database_path())
    parser.add_argument('--backup', type=Path, required=True, help='New path for verified pre-repair SQLite backup')
    args = parser.parse_args()
    print(json.dumps(repair(args.database, args.backup), indent=2))
