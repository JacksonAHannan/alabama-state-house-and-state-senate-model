import pandas as pd
import pytest
from scripts.build_precinct_identity import build_nodes, precinct_code, vote_similarity


def observations():
    return pd.DataFrame([
        [1994, 'alabama_sos', 'COUNTY', '002 B', 'Governor', 10.0],
        [1994, 'alabama_sos', 'COUNTY', '001 A', 'Governor', 20.0],
        [1994, 'alabama_sos', 'COUNTY', '002 B', 'Governor', 5.0],
    ], columns=['year', 'source', 'county_key', 'precinct_key', 'office', 'votes'])


def test_default_nodes_keep_first_seen_order_and_sum_fingerprints():
    nodes, totals = build_nodes(observations())
    assert nodes.precinct_key.tolist() == ['002 B', '001 A']
    assert nodes.node_id.tolist() == [1, 2]
    assert dict(zip(totals.node_id, totals.votes)) == {1: 15.0, 2: 20.0}

def test_precinct_code_normalizes_leading_zeroes():
    assert precinct_code("0040 - East Memorial") == "40"
    assert precinct_code("East Memorial") == ""

def test_vote_fingerprint_uses_shared_offices():
    left = pd.DataFrame({"office":["President","Governor"],"votes":[100,80]})
    right = pd.DataFrame({"office":["President","Governor"],"votes":[100,72]})
    score, shared = vote_similarity(left,right)
    assert shared == 2
    assert round(score,1) == 95.0


def test_existing_nodes_keep_ids_and_allocate_sorted_new_keys_above_retired_max():
    old, _ = build_nodes(observations())
    old.loc[old.precinct_key.eq('002 B'), 'node_id'] = 40
    old.loc[old.precinct_key.eq('001 A'), 'node_id'] = 90
    votes = observations().iloc[:1].copy()
    new = pd.concat([votes, votes.assign(precinct_key='004 D'), votes.assign(precinct_key='003 C')])
    nodes, _ = build_nodes(new, old)
    assert dict(zip(nodes.precinct_key, nodes.node_id)) == {'002 B': 40, '004 D': 92, '003 C': 91}
    reordered, _ = build_nodes(new.iloc[::-1], old)
    assert dict(zip(reordered.precinct_key, reordered.node_id)) == dict(zip(nodes.precinct_key, nodes.node_id))
    with pytest.raises(ValueError, match='duplicate'):
        build_nodes(new, pd.concat([old, old.iloc[:1]]))
    with pytest.raises(ValueError, match='positive integers'):
        build_nodes(new, old.assign(node_id=[1.5, 2.5]))


def identity_fixture():
    from scripts.build_precinct_identity import match_sources
    votes = pd.concat([observations(), observations().assign(source='openelections'),
                       observations().assign(year=2002),
                       observations().assign(year=2002, source='openelections')], ignore_index=True)
    nodes, fingerprints = build_nodes(votes)
    candidates, links = match_sources(nodes, fingerprints, 'alabama_sos', 'openelections')
    links['relationship'] = 'one_to_one'
    return votes, nodes, fingerprints, candidates, links


def test_staging_preserves_unaffected_links_and_quarantines_changed_inputs():
    from scripts.stage_precinct_identity_repair import prepare
    votes, nodes, fingerprints, candidates, links = identity_fixture()
    edited = votes.copy()
    edited.loc[edited.year.eq(1994) & edited.source.eq('alabama_sos'), 'precinct_key'] = '002 B UPDATED'
    frames, evidence = prepare(edited, nodes, fingerprints, candidates, links)
    staged_links = frames['precinct_source_links']
    unaffected = set(nodes.loc[nodes.year.eq(2002), 'node_id'])
    pd.testing.assert_frame_equal(staged_links[staged_links.left_node_id.isin(unaffected)].reset_index(drop=True),
                                  links[links.left_node_id.isin(unaffected)].reset_index(drop=True))
    changed = staged_links[~staged_links.left_node_id.isin(unaffected)]
    assert not changed.empty
    assert changed.accepted.eq(0).all()
    assert changed.match_method.eq('review').all()
    assert len(evidence['retired_ids']) == 2
    assert frames['precinct_nodes'].node_id.is_unique


def test_staging_empty_opposite_pool_and_missing_values():
    from scripts.stage_precinct_identity_repair import prepare
    votes, nodes, fingerprints, candidates, links = identity_fixture()
    # An actually absent old opposite pool, not unrelated current-source drift.
    nodes = nodes[nodes.source.eq('alabama_sos')].copy()
    fingerprints = fingerprints[fingerprints.node_id.isin(nodes.node_id)].copy()
    candidates, links = candidates.iloc[:0], links.iloc[:0]
    edited = votes[votes.source.eq('alabama_sos')].copy()
    edited.loc[edited.year.eq(1994), 'precinct_key'] = '003 C'
    frames, evidence = prepare(edited, nodes, fingerprints, candidates, links)
    assert frames['precinct_source_links'].empty
    assert evidence['affected_nodes_without_suggestion']
    with pytest.raises(ValueError, match='Missing'):
        prepare(edited.assign(votes=None), nodes, fingerprints, candidates, links)


def test_scoped_stage_ignores_2008_drift_and_preserves_unchanged_sibling():
    from scripts.build_precinct_identity import match_sources
    from scripts.stage_precinct_identity_repair import prepare, repair_scope
    votes, _, _, _, _ = identity_fixture()
    votes = pd.concat([votes, observations().assign(year=2008),
                       observations().assign(year=2008, source='openelections')], ignore_index=True)
    nodes, fingerprints = build_nodes(votes)
    candidates, links = match_sources(nodes, fingerprints, 'alabama_sos', 'openelections')
    links['relationship'] = 'one_to_one'
    edited = votes.copy()
    edited.loc[edited.year.eq(2008), 'precinct_key'] = 'UNRELATED NEW LABEL'
    changed = edited.year.eq(1994) & edited.source.eq('alabama_sos') & edited.precinct_key.eq('002 B')
    edited.loc[changed, 'votes'] += 1
    frames, evidence = prepare(edited, nodes, fingerprints, candidates, links)
    outside = nodes[~repair_scope(nodes)]
    pd.testing.assert_frame_equal(frames['precinct_nodes'][~repair_scope(frames['precinct_nodes'])].reset_index(drop=True), outside.reset_index(drop=True))
    pd.testing.assert_frame_equal(frames['precinct_vote_fingerprints'][frames['precinct_vote_fingerprints'].node_id.isin(outside.node_id)].reset_index(drop=True),
                                  fingerprints[fingerprints.node_id.isin(outside.node_id)].reset_index(drop=True))
    changed_ids = set(nodes.loc[nodes.year.eq(1994) & nodes.source.eq('alabama_sos') & nodes.precinct_key.eq('002 B'), 'node_id'])
    assert evidence['changed_fingerprint_or_identity_ids'] == sorted(changed_ids)
    assert evidence['new_ids'] == evidence['retired_ids'] == []
    for name, before in [('precinct_source_links', links), ('precinct_match_candidates', candidates)]:
        pd.testing.assert_frame_equal(frames[name][~frames[name].left_node_id.isin(changed_ids)].reset_index(drop=True),
                                      before[~before.left_node_id.isin(changed_ids)].reset_index(drop=True))


def test_scoped_stage_updates_only_genuinely_changed_sibling_relationship():
    from scripts.stage_precinct_identity_repair import prepare, repair_scope
    votes, nodes, fingerprints, candidates, links = identity_fixture()
    left = nodes[nodes.year.eq(1994) & nodes.source.eq('alabama_sos')].node_id.tolist()
    right = nodes[nodes.year.eq(1994) & nodes.source.eq('openelections')].node_id.iloc[0]
    links.loc[links.left_node_id.isin(left), ['right_node_id', 'accepted', 'relationship']] = [right, 1, 'many_sos_to_one_oe']
    edited = votes.copy()
    edited.loc[edited.year.eq(1994) & edited.source.eq('alabama_sos') & edited.precinct_key.eq('002 B'), 'votes'] += 1
    frames, evidence = prepare(edited, nodes, fingerprints, candidates, links)
    sibling = frames['precinct_source_links'].set_index('left_node_id').loc[left[1]]
    assert sibling.accepted == 1
    assert sibling.relationship == 'one_to_one'
    assert evidence['relationship_only_changes'] == [{'left_node_id': left[1], 'before': 'many_sos_to_one_oe', 'after': 'one_to_one'}]
    scope_examples = pd.DataFrame([[2002, 'MARSHALL'], [2002, 'OTHER'], [2014, 'JEFFERSON'], [2014, 'OTHER']], columns=['year', 'county_key']).assign(source='alabama_sos')
    assert repair_scope(scope_examples).tolist() == [True, False, True, False]


def test_staging_cli_is_read_only_and_refuses_existing_output(tmp_path):
    import hashlib
    import json
    import sqlite3
    from scripts.stage_precinct_identity_repair import stage
    votes, nodes, fingerprints, candidates, links = identity_fixture()
    database = tmp_path / 'source.sqlite'
    with sqlite3.connect(database) as connection:
        for name, frame in [('vote_observations', votes), ('precinct_nodes', nodes),
                            ('precinct_vote_fingerprints', fingerprints),
                            ('precinct_match_candidates', candidates), ('precinct_source_links', links)]:
            frame.to_sql(name, connection, index=False)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    output = tmp_path / 'new-stage'
    report = stage(database, output)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert report['status'] == 'staged_review_only'
    assert report['validation']['preserved_link_rows'] == len(links)
    assert json.loads((output / 'manifest.json').read_text())['validation']['new_ids'] == []
    for filename, details in report['outputs'].items():
        assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == details['sha256']
    with pytest.raises(FileExistsError):
        stage(tmp_path / 'nonexistent.sqlite', output)
    assert not (tmp_path / 'nonexistent.sqlite').exists()
