# OpenElections historical Southern gap acquisition

The acquisition pipeline downloads verified general-election precinct CSVs
from commit-pinned OpenElections repositories. It covers fourteen state-cycle
combinations not already represented by confirmed official downloads:

- Arkansas 2008;
- Georgia 2012, 2014, and 2016;
- Missouri every even cycle from 2000 through 2016;
- South Carolina 2006.

Run `python scripts/acquire_openelections_historical_gaps.py`. Raw files are
stored under `data/raw/openelections_historical_gaps/`; existing unequal files
are never overwritten. The manifest records repository, commit, source member,
raw URL, retrieval time, size, and SHA-256.

OpenElections is a secondary normalized source. Georgia 2014 is explicitly
labeled unofficial. These files can fill experimental coverage gaps and
validate other sources, but official returns retain higher authority.
