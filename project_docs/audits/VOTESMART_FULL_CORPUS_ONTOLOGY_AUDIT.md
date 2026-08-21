# Vote Smart full-corpus ontology audit

## Scope

This audit covers every item currently present in the downloaded Vote Smart PCT
corpus, not only the 114 unresolved items attached to canonical CMO candidates.
The corpus contains 26,792 candidate-option response rows, 1,729 distinct
year-items, and 1,001 normalized option wordings. The stored material spans
1996-2024 and includes state and federal questionnaires, despite the current raw
filename referring to 1998-2022.

Of the 1,729 year-items, 589 are covered by deterministic ideological rules, 66
are position-only, 147 are non-scorable, and 927 remain unmapped under the legacy
binary framework. Another 115 items lack an election year and require source
metadata repair before temporal integration.

Context is essential: 359 year-items have blank question text, 32 normalized
option wordings occur in more than one policy family, and 278 items belong to
ordinal funding/tax batteries. Rules must therefore use section, prompt, option,
response mode, and answer together rather than classify normalized option text
alone.

## Policy-family inventory

| Family | Year-items | Distinct wordings | Legacy mapped share |
|---|---:|---:|---:|
| Fiscal, tax, and budget | 365 | 160 | 40.3% |
| Criminal justice | 134 | 78 | 39.6% |
| Campaigns, elections, and government | 133 | 75 | 9.8% |
| Education | 128 | 93 | 56.3% |
| Foreign policy and aid | 116 | 94 | 0.0% |
| Health care | 113 | 75 | 27.4% |
| Environment, energy, and resources | 111 | 79 | 31.5% |
| Abortion and reproduction | 99 | 46 | 77.8% |
| Guns | 84 | 48 | 69.0% |
| Labor, employment, and civil rights | 83 | 55 | 32.5% |
| Welfare, poverty, and housing | 69 | 50 | 20.3% |
| Social, civil, and family policy | 53 | 35 | 56.6% |
| Legislative priorities | 43 | 31 | 11.6% |
| Economy and business | 42 | 23 | 54.8% |
| Immigration | 41 | 33 | 0.0% |
| Defense, security, and terrorism | 31 | 26 | 0.0% |
| Drugs | 23 | 18 | 13.0% |
| Social Security and retirement | 23 | 20 | 4.3% |
| Technology, communications, and privacy | 19 | 18 | 0.0% |
| Federalism | 11 | 11 | 0.0% |
| Trade and globalization | 8 | 8 | 0.0% |

The counts show why the old broad dimensions are insufficient. Government
reform, foreign policy, immigration, security, technology, federalism, and trade
have almost no deterministic coverage, while the broad economic and environment
labels combine substantively different positions.

## Recommended measurement architecture

### Layer 1: descriptive position primitives

The source-level codebook should retain narrow axes and allow one response to
load on more than one axis.

- Fiscal and economic: tax burden, tax distribution, domain-specific spending,
  deficit discipline, market regulation, public/private provision,
  privatization, economic stimulus, welfare generosity, welfare conditionality,
  labor rights, public-employee compensation, business subsidies, and targeted
  small-business or large-business constituency tags.
- Child and family support: childcare generosity, childcare delivery mechanism,
  child-support enforcement, Head Start, and family cash/service supports.
- Health care: coverage generosity, public responsibility, public/private
  delivery, insurance regulation and patient rights, Medicaid structure,
  malpractice liability, and end-of-life or bioethical policy.
- Education: public funding, market choice, standards and accountability,
  teacher labor/compensation, higher-education access, curriculum, sex education,
  and religion in schools.
- Environment and rural land: pollution control, conservation/preservation,
  resource extraction, active resource management, climate policy, renewable
  energy, fossil-energy development, property/land-use rights, agriculture, and
  hunting/fishing/rural recreation.
- Civil and social: abortion legality, abortion access/funding/procedure,
  marriage equality, anti-discrimination, affirmative action, religious
  establishment/liberty, sexual policy, temperance/public-health regulation, and
  reproductive research.
- Order and justice: punishment severity, death penalty, incarceration,
  rehabilitation, juvenile justice, due process, police authority, drug
  criminalization, drug treatment, and privacy/civil liberty.
- Guns: possession/carry access, purchase screening/licensing, weapon-type
  restrictions, safe-storage/product rules, and hunting exceptions.
- Immigration: legal admissions, legalization/citizenship, enforcement and
  detention, border security, immigrant public benefits, language/national
  identity, and state/federal enforcement authority.
- Institutions: contribution restrictions, disclosure, public campaign funding,
  spending limits, voting access, election integrity, term limits, direct
  democracy, redistricting governance, constitutional reform, ethics, and
  executive or judicial power.
- Federal supplemental positions: defense spending, military interventionism,
  multilateralism, foreign-aid internationalism, human-rights conditionality,
  trade openness, Social Security privatization/generosity/revenue, federalism,
  digital privacy, content regulation, surveillance, and cyber enforcement.

Business scale should not be a bipolar small-business-versus-big-business score.
A policy can support one, both, or neither. Store independent constituency tags.
Likewise, spending and tax category items require their ordinal response; the
category label alone has no direction.

### Layer 2: higher-order CMO ideological families

The Alabama candidate model should use a smaller number of composites than the
source ontology. Eight families are defensible from the available state-policy
content:

1. market autonomy versus government economic direction;
2. redistribution and material-support generosity versus restriction;
3. labor alignment versus capital/management alignment;
4. social traditionalism versus civil equality and personal liberty;
5. punitive order/enforcement versus rehabilitation and due process;
6. immigration restriction/national identity versus inclusion;
7. environmental protection/preservation versus extraction and property-rights
   priority;
8. institutional populism and democratic reform versus institutional control.

Childcare, education, and health care remain reportable issue profiles even when
their components contribute to the first three higher-order families. Economic
populism should be tested separately from labor alignment: support for small
business, opposition to concentrated corporate power, and support for workers
need not move together.

Military interventionism, internationalism, trade openness, and federalism are
valid supplemental axes for federal questionnaires but should not increase the
dimension count of the Alabama legislative CMO model unless same-cycle state
candidate evidence actually identifies them.

## Axes to narrow or remove from direct scoring

- `welfare_policy` must be limited to benefits, eligibility, generosity, and
  conditions. It cannot serve as a catch-all for policies that might affect
  well-being. The provisional small-model layer assigned it to 70 of 114 items,
  demonstrating severe construct contamination.
- `market_governance` should require a direct change in regulation, ownership,
  competition, subsidy, or provision. Any government action is not automatically
  market intervention.
- `institutional_populism` should be derived from explicit institutional
  positions, not assigned directly whenever a reform sounds popular.
- `business_scale_alignment` should become two nonexclusive constituency tags.
- `public_spending` and `tax_burden` are descriptive directions, not universal
  ideological scores. Their meaning depends on the funded domain, tax base, and
  distribution.
- Highly specific one-item primitives should remain issue evidence but should not
  become standalone regression covariates. They can contribute to a documented
  higher-order family when conceptually justified.

## Scoring recommendation

Do not average every primitive axis. First aggregate repeated items within a
policy key, then aggregate policy keys within a higher-order family. Require
minimum policy coverage, retain missingness indicators, and report the primitive
positions alongside composites. Pole-to-family loadings should be versioned and
reviewable. Cross-family items may contribute to multiple composites with
explicit weights, while nonideological delivery mechanisms remain descriptive.

The 91 additive small-model adjudications are not sufficiently reliable for
final scoring merely because the models did not express opposite poles. Shared
hallucinations can produce false agreement. Direct rules, direct text review, or
a calibrated validation sample remain necessary before those rows enter the CMO
feature table.
