# CMO hypothesis and variable registry

## Purpose

This document records every currently identified variable or mechanism that may
help explain or predict Alabama legislative candidate margin overperformance.
The machine-readable companion is `cmo_hypothesis_registry.csv`.

The registry is deliberately broader than the production model. Inclusion here
means a hypothesis deserves documentation and a disciplined test; it does not
mean the variable belongs in headline CMO, has a causal interpretation, or has
passed forward validation.

## The estimand and the incumbency correction

Headline **Total CMO** is the candidate-signed residual from legislative margin
relative to a district baseline and contextual expectation. It is descriptive
candidate margin overperformance among contested Democratic-Republican races.
It is not wins above replacement or a fully identified causal candidate effect.

The headline definition now deliberately excludes incumbency and prior candidate
performance. This corrects an important conceptual problem in the earlier
approach: for Alabama Democrats, incumbency is often acquired *because a
candidate previously overperformed enough to win*. The observed incumbent pool
then further selects candidates who rerun, survive, and sometimes deter serious
challengers. A single incumbent coefficient therefore mixes at least four
processes:

1. **Selection into office:** unusually strong nonincumbents win.
2. **A possible officeholding effect:** service, visibility, and constituent work
   may improve later performance.
3. **Challenger deterrence:** strong incumbents may become unopposed or draw
   weaker opponents, removing some of their strongest cycles from the contested
   CMO sample.
4. **Survival and regression to the mean:** only persistent winners enter the
   observed long-tenure pool, while unusually large first wins tend not to
   repeat in full.

Accordingly, incumbency is handled in three separate products:

- **Total CMO:** does not condition candidate strength away with incumbency.
- **Predictive Total:** may use party-specific incumbency as a forecast feature,
  but makes no causal claim.
- **Candidate-history forecast sensitivity:** decomposes incumbency into prior
  CMO, prior winner/contest status, first-term versus established incumbent,
  cycle gap, and prior incumbent appearances.

The preferred research design is a linked process: contest entry, candidate
entry/rerunning, winning, transition into incumbency, and subsequent contested
performance. Cross-sectional incumbent-versus-challenger differences are not
estimates of the causal incumbency advantage.

## Variable roles

Every registry row is assigned a role:

- **Baseline component:** defines the comparator and cannot be used to explain
  its own residual mechanically.
- **Context/confounder:** district or election environment that may affect both
  candidate selection and performance.
- **Candidate trait:** potentially meaningful candidate characteristic.
- **Mediator:** a pathway through which candidate quality operates, such as
  fundraising or spending. Adjusting for it changes the estimand.
- **Selection mechanism:** determines which candidates and contests become
  observable.
- **Measurement quality:** affects confidence in a feature or outcome but is not
  substantive candidate strength.
- **Effect modifier:** tests whether candidate fit depends on district context.

## Core hypothesis families

### Partisan baselines and nationalization

The project has discussed state-office, governor, prior-presidential, and
same-cycle federal comparators. The evidence so far does not support one heavy
federal weight across every era. Federal voting becomes more competitive as a
baseline after 2016, but the honest 2018-to-2022 promotion test did not beat the
state baseline. Federal-relative performance remains valuable as a research
outcome and as context for testing cultural conservatism.

The central nationalization hypothesis is conditional: culturally conservative
Democrats may have historically performed best where voters were strongly
Republican in federal elections but retained greater willingness to support
state-level Democrats. That relationship is expected to weaken after 2008 or
2016 as down-ballot partisanship catches up.

### Demographic composition

The current core fields are nonwhite share and directly measured white
non-Hispanic college share. The improved 2014-2022 data permit sharper tests of
Black, Hispanic, other-nonwhite, white-college, white-noncollege, joint
race-education, age, sex, turnout, urbanicity, and demographic change. These
should normally be tested as nonlinear context or candidate-fit modifiers, not
as claims that demographic composition itself is candidate quality.

### Candidate history and incumbency

The longitudinal fields must be strictly lagged. Prior unopposed margins are
never converted into candidate quality. Repeat-candidate validation must group
by candidate and hold out future cycles; random race folds overstate evidence
when the same person appears in training and testing.

### Finance

Fundraising and spending are both plausible mechanisms and signals of candidate
strength. Full-cycle totals are endogenous because strong candidates attract
money and competitive races attract spending. Therefore Total CMO excludes
finance, while fundraising-adjusted and expenditure-adjusted scores answer
different questions. Pre-election cash and cutoff-date receipts are preferable
for prediction. Ending cash is descriptive, and missing finance is unknown—not
zero.

### Ideology, issue positions, and local fit

The registry separates social ideology from economic direction, material
support, labor alignment, criminal justice, guns, abortion, education, health
care, environment/resources, reform, and immigration. It also includes
legislative behavior, sponsorship priorities, amendments, committee conduct,
campaign positions, endorsements, and localism.

The main hypothesis is congruence rather than a universal moderation effect.
For example, gun-rights or socially conservative positions might help in rural
or strongly Republican federal-voting districts, while producing no advantage
elsewhere. Economic populism may operate independently of social conservatism.
All evidence must predate the election being explained; later roll calls cannot
be projected backward onto an earlier candidacy.

### Biography, campaign organization, and opponents

Candidate biographies and research memos have also raised local tenure, prior
office, constituent service, civic and church networks, occupation, education
ties, business leadership, military or law-enforcement service, campaign
organization, endorsements, localist messaging, party switching, and scandal.
The opponent side matters equally: prior performance, experience, resources,
ideological fit, scandal, recruitment quality, open-seat status, third-party
presence, salience, and locally dominant issues. These are mostly qualitative
or proposed variables. They must be coded from evidence available before the
election rather than inferred from the result that CMO is meant to explain.

## Testing protocol

Each hypothesis should receive a registered test record before analysis:

1. Name one focal variable and its temporal cutoff.
2. Use a frozen outcome that did not condition on that focal variable. If the
   focal variable helped construct a CMO specification, rebuild a leave-focal-
   out outcome.
3. State whether the goal is description, mechanism research, or prediction.
4. Use expanding-window future-cycle validation for predictive claims. Random
   folds are secondary diagnostics only.
5. Group repeat candidates and district families where relevant.
6. Compare against the zero-overperformance and transparent baseline models.
7. Report coverage, missingness, effect uncertainty, outlier sensitivity,
   chamber and era heterogeneity, and rank stability.
8. For 2014-2022, run the primary comparable-data analysis using harmonized
   demographics and the improved finance sources. Use earlier cycles as a
   separate historical-regime sensitivity rather than silently pooling them.
9. Correct for multiple exploratory tests within each hypothesis family and
   label underpowered results as descriptive.
10. Record null and adverse findings in the registry; promotion depends on
    repeated forward-cycle improvement, not statistical significance alone.

## Recommended first test sequence

1. Freeze a 2014-2022 analytical panel and audit comparable finance cutoffs and
   demographic vintages.
2. Reproduce Total CMO without incumbency, candidate history, finance, or
   ideology in its expectation.
3. Test incumbency acquisition and persistence using prior CMO, transitions,
   rerunning, contest entry, and challenger deterrence.
4. Test finance as separate signal and mediator specifications.
5. Test social and economic ideology jointly, including district-fit,
   majority-white, white-noncollege, rurality, federal-state gap, and era
   interactions.
6. Compare linear regression with regularized models, generalized additive
   models, tree-based discovery, mutual information, matched comparisons, and
   hierarchical partial pooling. Treat flexible methods as discovery tools
   unless their signals survive future-cycle validation.
7. Convert the most consistently documented biography and opponent constructs
   into a blinded coding rubric before inspecting their CMO values.

## Ideological-valence hypothesis ledger

The focused, cumulative ledger for issue stance, federal-relative performance,
era attenuation, district fit, and multi-cycle durability is generated at
`data/processed/elections/validation/issue_stance_durable_hypotheses.csv`.
Its current evidence review is documented in
`project_docs/model/ISSUE_STANCE_DURABLE_OVERPERFORMANCE.md`. The ledger retains
mixed, null, and underpowered findings rather than only successful hypotheses.

No variable should be promoted merely because it improves in-sample fit.
