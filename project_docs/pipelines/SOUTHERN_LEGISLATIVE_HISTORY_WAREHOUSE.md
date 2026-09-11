# Southern legislative history warehouse

## Scope

`scripts/load_southern_legislative_history_warehouse.py` loads every locally
available Southern state-legislative election year into the central SQLite
warehouse. It covers all 14 project states, reaches from 1968 through 2024,
and includes every scheduled state-cycle-chamber from 2018 through 2024.
Special elections appearing in general-election MEDSL files are retained even
when they are outside the regular schedule.

## Source layers and authority

1. Alabama's reviewed canonical candidate results.
2. Direct official state observations, including the schema-version-10 source
   layer and Virginia 2023.
3. The official-derived RDH/OpenElections Mississippi 2023 package.
4. Versioned MEDSL individual-state GitHub releases for acquired 2022/2024
   gaps.
5. MEDSL national precinct releases for 2018, 2020, and 2024.
6. Klarner State Legislative Election Returns for the remaining 1968-2022
   candidate-contest history.

Authority is applied to a whole contest observation set. Missing higher-rank
contests fall through to the next observed source, but candidates from two
providers are never combined. Competing observations remain queryable through
`all_southern_legislative_candidate_election_observations`.

## Parsing and validation

- MEDSL vote modes use a documented `TOTAL`-over-components rule at the
  precinct/candidate key; otherwise components are summed.
- MEDSL precinct votes reconcile exactly to emitted district candidate totals.
- Klarner null vote fields remain unknown, particularly for unopposed races.
- Klarner's `dontuse` analytical flag remains in source quality JSON; it does
  not erase an otherwise structurally valid election observation from the
  warehouse, and downstream models must apply their own documented gate.
- Mississippi candidate fields are decoded from the README shipped inside the
  immutable ZIP and reconcile exactly.
- Virginia 2023 precinct rows are aggregated by provider candidate and
  provider-reported legislative district.
- Source and canonical keys, foreign keys, vote shares, and the complete
  2018-2024 scheduled state/chamber matrix are release gates.

MEDSL 2024 is not treated as a full ballot universe. Some files contain only
contested legislative races; the coverage view reports observed districts and
does not synthesize absent uncontested seats.

## Final-stage modeling interface

`fact_southern_legislative_final_candidate_election` resolves the election
sequence before modeling. For the validated Louisiana official series beginning
in 1995, it uses the runoff for a district only when a
runoff exists and otherwise uses the first round; votes from the two stages are
never summed. Other states use the regular general stage. Specials remain in
the stage-level fact.

`qa_southern_legislative_final_competition_coverage` reports final contests,
observed multi-candidate competitions, and WAR-eligible D-versus-R contests.
This is distinct from seat-universe coverage: Louisiana's official exports
list contested first-round races and their runoffs, while districts resolved
without a reported competition need not appear in the WAR training universe.

## Reproduction

```powershell
python scripts/load_southern_election_warehouse.py
python scripts/load_southern_legislative_history_warehouse.py
python -m pytest scripts/tests/test_southern_legislative_history_warehouse.py -q
```

Outputs include the stage-level and final-stage candidate-history archives,
source and coverage audits under `data/processed/source_audits/`, and the
schema-version-13 tables and views in
`data/processed/elections/alabama_elections.sqlite`.
