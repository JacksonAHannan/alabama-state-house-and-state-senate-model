DROP VIEW IF EXISTS qa_legiscan_roll_call_reconciliation;
CREATE VIEW qa_legiscan_roll_call_reconciliation AS
WITH counted AS (
  SELECT roll_call_id, COUNT(*) AS recorded_total,
    SUM(vote_id=1) AS recorded_yea, SUM(vote_id=2) AS recorded_nay,
    SUM(vote_id=3) AS recorded_not_voting, SUM(vote_id=4) AS recorded_absent,
    SUM(vote_id IS NULL OR vote_id NOT IN (1,2,3,4)) AS unknown_vote_codes
  FROM source_legiscan_member_vote GROUP BY roll_call_id
)
SELECT r.roll_call_id,r.source_file_id,r.source_member,
  r.total AS reported_total,r.yea AS reported_yea,r.nay AS reported_nay,
  r.not_voting AS reported_not_voting,r.absent AS reported_absent,
  COALESCE(v.recorded_total,0) AS recorded_total,
  COALESCE(v.recorded_yea,0) AS recorded_yea,
  COALESCE(v.recorded_nay,0) AS recorded_nay,
  COALESCE(v.recorded_not_voting,0) AS recorded_not_voting,
  COALESCE(v.recorded_absent,0) AS recorded_absent,
  CASE WHEN r.total=COALESCE(v.recorded_total,0)
    AND r.yea=COALESCE(v.recorded_yea,0) AND r.nay=COALESCE(v.recorded_nay,0)
    AND r.not_voting=COALESCE(v.recorded_not_voting,0)
    AND r.absent=COALESCE(v.recorded_absent,0)
    AND COALESCE(v.unknown_vote_codes,0)=0
    THEN 'passed' ELSE 'review' END AS validation_status
FROM source_legiscan_roll_call r LEFT JOIN counted v USING(roll_call_id);

DROP VIEW IF EXISTS canonical_legiscan_roll_call;
CREATE VIEW canonical_legiscan_roll_call AS
SELECT r.* FROM source_legiscan_roll_call r
JOIN qa_legiscan_roll_call_reconciliation q USING(roll_call_id)
WHERE q.validation_status='passed';

DROP VIEW IF EXISTS canonical_legiscan_member_vote;
CREATE VIEW canonical_legiscan_member_vote AS
SELECT v.* FROM source_legiscan_member_vote v
JOIN canonical_legiscan_roll_call r USING(roll_call_id);
