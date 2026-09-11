"""Refuse unusable literal reported counts before aggregation; never repair them.

This guard is only for raw vote_observations, not derived fractional allocations.
Callers supply trusted SQL scope and bound parameters for their actual inputs.
"""
import json


def require_reported_vote_quality(connection, where="1", params=()):
    """Raise with source-cell evidence for unknown or invalid reported votes.

    No observations are changed, dropped, rounded, or substituted. Legacy schemas
    may lack physical locators; include every available locator without inventing
    one. Limit diagnostic samples, not the validation scope.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(vote_observations)")}
    fields = [name for name in (
        "source", "year", "county_key", "precinct_key", "office", "district",
        "candidate_key", "votes", "source_file_id", "source_file", "source_sheet",
        "source_row", "source_column") if name in columns]
    issue = """CASE
        WHEN votes IS NULL THEN 'unknown_missing_votes'
        WHEN typeof(votes) NOT IN ('integer','real') THEN 'nonnumeric_source_vote'
        WHEN (votes - votes) IS NULL THEN 'nonfinite_source_vote'
        WHEN votes < 0 THEN 'negative_source_vote'
        WHEN votes <> CAST(votes AS INTEGER) THEN 'fractional_source_vote'
        END"""
    predicate = f"({where}) AND ({issue}) IS NOT NULL"
    count = connection.execute(
        f"SELECT COUNT(*) FROM vote_observations WHERE {predicate}", params).fetchone()[0]
    if not count:
        return
    rows = connection.execute(
        f"SELECT {','.join(fields)}, {issue} FROM vote_observations WHERE {predicate} LIMIT 20",
        params).fetchall()
    evidence = [dict(zip([*fields, "issue"], row)) for row in rows]
    raise ValueError(
        f"Unusable reported votes: {count} source observations; "
        f"no zero/partial aggregation permitted. Evidence: {json.dumps(evidence, default=str)}")
