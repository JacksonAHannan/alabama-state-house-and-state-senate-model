# OpenElections historical staging

This pipeline normalizes relevant legislative and top-ticket observations from
the commit-pinned OpenElections gap bundle. It preserves raw office, district,
party, candidate, and vote fields alongside normalized values and file/hash/row
provenance.

Georgia election-day, advance, absentee, and provisional modes are summed once
when no total-vote column is supplied. Missouri 2000 district numbers are
parsed from office labels. Party normalization is deliberately conservative;
unrecognized labels remain outside Democratic/Republican aggregates.

Outputs are staging evidence. OpenElections never outranks official returns,
Georgia 2014 remains explicitly unofficial, and files without legislative
district identifiers cannot create district election results.

Missing party labels are resolved first from the same candidate elsewhere in
the same state-cycle-office and then from an exact normalized candidate key in
the Klarner contest archive. The original party field and resolution method
remain visible. The deterministic build manifest records all input and output
hashes and row counts.
