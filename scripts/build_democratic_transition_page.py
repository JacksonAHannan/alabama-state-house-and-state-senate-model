"""Build the merged Democratic transition and electoral-performance page."""
from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.build_ideology_thesis_page import ISSUES, payload as ideology_payload
    from scripts.build_caucus_analysis_page import payload as cluster_payload
except ModuleNotFoundError:
    from build_ideology_thesis_page import ISSUES, payload as ideology_payload
    from build_caucus_analysis_page import payload as cluster_payload


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "site" / "ideology-performance.html"
CURRENT_QUALITY = ROOT / "data" / "processed" / "war" / "cmo_v6_southern_candidates.csv"
PREFIX = "primitive_conservative_"
PROGRESSIVE = "Progressive-modern Democrats"
TRADITIONALIST = "Traditionalist-populist Democrats"


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


@lru_cache(maxsize=1)
def payload() -> dict:
    """Combine validated regression and cluster outputs without changing either analysis."""
    ideology = ideology_payload()
    clusters = deepcopy(cluster_payload())
    members = pd.DataFrame(clusters["members"])
    quality = pd.read_csv(
        CURRENT_QUALITY,
        usecols=["canonical_candidate_id", "candidate_quality_residual"],
    )
    if quality.canonical_candidate_id.duplicated().any():
        raise ValueError("Current candidate-quality output has duplicate candidate IDs")
    members = (members.drop(columns=["candidate_quality_residual"], errors="ignore")
               .merge(quality, on="canonical_candidate_id", how="left", validate="one_to_one"))
    if members.candidate_quality_residual.isna().any():
        missing = members.loc[members.candidate_quality_residual.isna(), "canonical_candidate_id"].tolist()
        raise ValueError(f"Cluster members missing current candidate-quality residual: {missing[:5]}")

    profiles = pd.DataFrame(clusters["profiles"])
    performance = pd.DataFrame(clusters["performance"])
    performance = performance[~performance.outcome.eq("candidate_cmo")].copy()
    quality_performance = (members.groupby(
        ["party", "cluster_id", "cluster_label"], as_index=False
    ).candidate_quality_residual.agg(["count", "mean", "median", "std"]).reset_index())
    quality_performance = quality_performance.rename(
        columns={"count": "n", "std": "sd"}
    )
    quality_performance["standard_error"] = (
        quality_performance.sd / np.sqrt(quality_performance.n)
    )
    quality_performance["outcome"] = "candidate_quality_residual"
    quality_performance = quality_performance[
        ["party", "cluster_id", "cluster_label", "outcome", "n", "mean",
         "median", "sd", "standard_error"]
    ]
    performance = pd.concat([performance, quality_performance], ignore_index=True)

    # Do not carry the superseded structural-residual field into the public
    # cluster payload under its former CMO name.
    members = members.drop(columns=["candidate_cmo"], errors="ignore")
    clusters["members"] = _records(members)
    clusters["performance"] = _records(performance)
    democrats = members[members.party.eq("D")].copy()

    transition = (democrats.groupby(["cycle", "cluster_id", "cluster_label"], as_index=False)
                  .agg(n=("canonical_candidate_id", "size")))
    totals = transition.groupby("cycle").n.transform("sum")
    transition["share"] = transition.n / totals

    dem_profiles = profiles[profiles.party.eq("D")].set_index("cluster_label")
    issue_meta = {row["key"]: row for row in ideology["issueMeta"]}
    differences = []
    if {PROGRESSIVE, TRADITIONALIST}.issubset(dem_profiles.index):
        for column in [c for c in dem_profiles if c.startswith(PREFIX)]:
            key = column.removeprefix(PREFIX)
            progressive = dem_profiles.at[PROGRESSIVE, column]
            traditionalist = dem_profiles.at[TRADITIONALIST, column]
            if pd.isna(progressive) or pd.isna(traditionalist):
                continue
            differences.append({
                "issue": key,
                "label": issue_meta.get(key, {}).get("label", key.replace("_", " ").title()),
                "progressive": float(progressive),
                "traditionalist": float(traditionalist),
                "difference": float(traditionalist - progressive),
            })
    differences.sort(key=lambda row: abs(row["difference"]), reverse=True)

    case_rows = []
    for label in (TRADITIONALIST, PROGRESSIVE):
        subset = democrats[democrats.cluster_label.eq(label)].copy()
        subset = subset[subset.candidate_federal_overperformance.notna()]
        if subset.empty:
            continue
        # Include an upper-decile performer and an observation near the bloc median;
        # this avoids presenting the single most extreme record as representative.
        median = subset.candidate_federal_overperformance.median()
        upper_decile = subset.candidate_federal_overperformance.quantile(0.90)
        picks = [(subset.candidate_federal_overperformance - upper_decile).abs().idxmin(),
                 (subset.candidate_federal_overperformance - median).abs().idxmin()]
        for kind, index in zip(("Upper-decile federal performance", "Near bloc median"), picks):
            row = subset.loc[index]
            case_rows.append({
                "kind": kind, "canonical_candidate_id": row.canonical_candidate_id,
                "name": row.canonical_name, "cycle": int(row.cycle), "chamber": row.chamber,
                "district": int(row.district), "cluster_label": label,
                "candidate_quality_residual": row.candidate_quality_residual,
                "candidate_federal_overperformance": row.candidate_federal_overperformance,
                "candidate_presidential_overperformance": row.candidate_presidential_overperformance,
                "dimensions": int(row.cluster_dimensions_observed),
            })

    dem_performance = performance[performance.party.eq("D")].copy()
    headline = []
    for outcome in ("candidate_quality_residual", "candidate_federal_overperformance",
                    "candidate_presidential_overperformance"):
        rows = dem_performance[dem_performance.outcome.eq(outcome)].set_index("cluster_label")
        if {PROGRESSIVE, TRADITIONALIST}.issubset(rows.index):
            p, t = rows.loc[PROGRESSIVE], rows.loc[TRADITIONALIST]
            headline.append({
                "outcome": outcome,
                "progressive_mean": float(p["mean"]), "progressive_se": float(p.standard_error),
                "progressive_n": int(p.n), "traditionalist_mean": float(t["mean"]),
                "traditionalist_se": float(t.standard_error), "traditionalist_n": int(t.n),
                "difference": float(t["mean"] - p["mean"]),
            })

    ideology["cluster"] = clusters
    ideology["democraticTransition"] = _records(transition)
    ideology["blocDifferences"] = differences
    ideology["headlineBlocPerformance"] = headline
    ideology["caseStudies"] = case_rows
    return ideology


@lru_cache(maxsize=1)
def build() -> str:
    complete = payload()
    # Keep the public payload limited to records used by this page. The full
    # analysis contract remains available through payload() for tests and other
    # research consumers.
    public = {key: complete[key] for key in (
        "issueMeta", "era", "cluster", "democraticTransition",
        "blocDifferences", "headlineBlocPerformance", "caseStudies",
    )}
    public["era"] = [
        row for row in complete["era"]
        if row.get("outcome") == "candidate_federal_overperformance"
    ]
    public["cluster"] = {
        key: complete["cluster"][key]
        for key in ("members", "issues", "constellation")
    }
    data = json.dumps(public, separators=(",", ":"), allow_nan=False)
    return r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Historical Democratic ideology and electoral performance in Alabama"><link rel="icon" href="data:,"><title>Democratic ideology and performance · Jackson Hannan</title><style>
:root{--ink:#25191d;--muted:#6d6064;--line:#bcaeb2;--paper:#fff;--blue:#b9d9ec;--blue-dark:#3b718f;--ox:#651c2c;--ox-dark:#42101b;--pale:#eef7fb;--gold:#ae7b26;--green:#2f6f56}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--blue);color:var(--ink);font:15px/1.55 Arial,Helvetica,sans-serif}header,footer{background:var(--ox);color:#fff}.mast,.shell{width:min(1180px,calc(100% - 40px));margin:auto}.mast{display:flex;justify-content:space-between;align-items:center;gap:22px;padding:18px 0}.brand{font:bold 23px Georgia,serif}.tag,.eyebrow,.kicker{font:bold 10px Arial,sans-serif;letter-spacing:1.1px;text-transform:uppercase}.tag{color:#eadde1;margin-top:3px}.nav{display:flex;gap:16px;flex-wrap:wrap}.nav a,footer a{color:#fff;text-decoration:none;font-size:11px}.nav a[aria-current=page]{border-bottom:2px solid #fff;padding-bottom:3px}.shell{background:var(--paper);padding:52px clamp(18px,4vw,52px) 90px;border-left:1px solid #9ebaca;border-right:1px solid #9ebaca}.hero{max-width:880px}.eyebrow{color:var(--ox)}h1{font:bold clamp(39px,6vw,70px)/1.02 Georgia,serif;letter-spacing:-2px;margin:10px 0 19px}.dek{font:20px/1.55 Georgia,serif;margin:0}.thesis{margin:28px 0 36px;border:1px solid var(--ox);border-left:8px solid var(--ox);padding:18px 20px;background:#fff9fa;font:16px/1.6 Georgia,serif}.contents{display:flex;gap:8px;flex-wrap:wrap;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:11px 0;margin-bottom:60px}.contents a{color:var(--ox);text-decoration:none;font:bold 10px Arial;padding:5px 8px;background:#f8f3f4}section{margin:74px 0;scroll-margin-top:20px}.section-head{max-width:820px;margin-bottom:25px}.section-head h2{font:bold 33px/1.1 Georgia,serif;margin:7px 0 10px}.section-head p{margin:0;color:#4d4246}.panel{border:1px solid var(--line);background:#fff}.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap;padding:13px 15px;border-bottom:1px solid var(--line);background:#f8f4f5}.controls label{font:bold 9px Arial;text-transform:uppercase;letter-spacing:.7px;color:var(--muted)}select,input{display:block;margin-top:4px;border:1px solid #9c8c91;background:#fff;padding:8px 30px 8px 9px;color:var(--ink)}.headline-grid{display:grid;grid-template-columns:1fr 1fr 1fr}.headline-card{padding:22px;border-right:1px solid var(--line)}.headline-card:last-child{border:0}.headline-card b{display:block;font:bold 32px Georgia;color:var(--ox)}.headline-card span{display:block;font-size:11px;color:var(--muted)}.headline-card small{display:block;margin-top:10px}.key{display:flex;gap:18px;flex-wrap:wrap;font-size:11px;color:var(--muted);margin:10px 0}.key i{display:inline-block;width:11px;height:11px;margin-right:5px;vertical-align:-1px}.trad{background:var(--ox)}.prog{background:var(--blue-dark)}.transition{padding:18px}.transition-row{display:grid;grid-template-columns:58px 1fr 58px;gap:10px;align-items:center;padding:8px 0;border-top:1px solid #e2d9dc}.transition-row:first-child{border:0}.stack{height:27px;display:flex;border:1px solid #9e8d92}.stack button{height:100%;border:0;min-width:2px;cursor:pointer}.stack button:hover,.stack button:focus{filter:brightness(1.2);outline:2px solid var(--ink);z-index:2}.transition-row strong{font-size:12px}.transition-row small{text-align:right;color:var(--muted)}.profile-chart{padding:16px}.profile-row{display:grid;grid-template-columns:190px 1fr 70px;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #e2d9dc}.profile-row:first-child{border:0}.profile-row label{font-size:12px}.profile-track{position:relative;height:24px;background:linear-gradient(90deg,#dcecf5,#fff 49.5%,#f0dce1)}.profile-track:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #8e7c82}.profile-track i{position:absolute;top:5px;width:13px;height:13px;border-radius:50%;transform:translateX(-50%);border:2px solid #fff}.profile-row output{text-align:right;font:bold 12px Arial}.distribution{height:390px;position:relative;margin:20px 32px 50px 112px;border-left:1px solid var(--line);border-bottom:1px solid var(--line);background:repeating-linear-gradient(to right,transparent 0,transparent calc(20% - 1px),#eee 20%)}.distribution .lane{position:absolute;left:-105px;width:100px;font-size:10px;text-align:right;transform:translateY(50%)}.distribution .zero{position:absolute;top:0;bottom:0;width:1px;background:#7b6c71}.performance-dot{position:absolute;border:1px solid #fff;box-shadow:0 0 0 1px #57484d;width:9px;height:9px;border-radius:50%;transform:translate(-50%,50%);cursor:pointer;opacity:.7}.mean-mark{position:absolute;width:4px;height:34px;transform:translate(-50%,50%);background:var(--ink)}.mean-ci{position:absolute;height:3px;transform:translateY(50%);background:var(--ink)}.axis-note{position:absolute;bottom:-32px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted);white-space:nowrap}.era-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line)}.era-card{background:#fff;padding:18px}.era-card b{font:bold 29px Georgia,serif;display:block}.era-card span{font-size:11px;color:var(--muted)}.era-card p{font-size:12px;margin:10px 0 0}.issue-layout{display:grid;grid-template-columns:280px 1fr}.issue-copy{padding:20px;background:#f7f2f4;border-right:1px solid var(--line)}.issue-copy h3{font:bold 23px Georgia;margin:0 0 8px}.issue-copy p{font-size:12px}.poles{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding-top:10px;font:bold 9px Arial;text-transform:uppercase;color:var(--muted)}.issue-plot{height:390px;position:relative;margin:20px 25px 50px 70px;border-left:1px solid var(--line);border-bottom:1px solid var(--line);background:linear-gradient(90deg,#e4f1f8,#fff 49.5%,#f3e1e5)}.issue-plot:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #8e7c82}.coverage{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border-top:1px solid var(--line)}.coverage div{background:#fff;padding:12px}.coverage b{display:block;font-size:19px}.coverage span{font-size:9px;color:var(--muted)}.cases{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.case{border-top:5px solid var(--ox);background:#fff;border-left:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:17px}.case.progressive{border-top-color:var(--blue-dark)}.case h3{font:bold 20px Georgia;margin:4px 0}.case .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:15px}.case .metrics div{background:#f5f1f2;padding:9px}.case .metrics b{display:block}.constellation-wrap{display:grid;grid-template-columns:minmax(0,1fr) 310px}.constellation-main{padding:16px;border-right:1px solid var(--line)}#constellation{display:block;width:100%;height:auto;background:#f7fbfd;border:1px solid var(--line)}#constellation .grid{stroke:#dae3e7}#constellation .envelope{stroke-width:2;stroke-dasharray:5 4}#constellation .member{stroke:#fff;stroke-width:1.5;cursor:pointer}#constellation .member.selected{stroke:var(--ink);stroke-width:3}.candidate-detail{padding:20px}.candidate-detail h3{font:bold 24px Georgia;margin:0}.candidate-detail .score{font:bold 36px Georgia;color:var(--ox);margin:18px 0}.candidate-detail .score span{display:block;font:9px Arial;text-transform:uppercase;color:var(--muted)}.candidate-detail dl{font-size:11px}.candidate-detail dt{float:left;clear:left;color:var(--muted)}.candidate-detail dd{text-align:right;border-bottom:1px solid #e2d9dc;padding:4px 0}.table-tools{padding:14px;border-top:1px solid var(--line)}.table-wrap{max-height:390px;overflow:auto;border-top:1px solid var(--line)}table{border-collapse:collapse;width:100%;font-size:11px}th{position:sticky;top:0;background:var(--ox);color:#fff;text-align:left;padding:8px}td{padding:8px;border-top:1px solid #e2d9dc}tbody tr{cursor:pointer}tbody tr:hover{background:var(--pale)}.num{text-align:right}.method{border-left:6px solid var(--ox);background:#f8f3f4;padding:18px 20px;margin:12px 0}.method h3{font:bold 18px Georgia;margin:0 0 7px}.method p{margin:0;font-size:12px}.tip{position:fixed;display:none;z-index:20;pointer-events:none;max-width:290px;background:var(--ox-dark);color:#fff;padding:10px 12px;font-size:11px;box-shadow:0 8px 22px #0004}footer{padding:25px max(20px,calc((100vw - 1140px)/2));font-size:11px}@media(max-width:780px){.mast{align-items:flex-start;flex-direction:column}.headline-grid,.era-grid{grid-template-columns:1fr}.headline-card{border-right:0;border-bottom:1px solid var(--line)}.profile-row{grid-template-columns:125px 1fr 55px}.issue-layout,.constellation-wrap{grid-template-columns:1fr}.issue-copy,.constellation-main{border-right:0;border-bottom:1px solid var(--line)}.cases{grid-template-columns:1fr}}@media(max-width:520px){.mast,.shell{width:100%}.mast{padding:15px}.shell{padding:36px 14px 65px;border:0}h1{font-size:39px}.transition-row{grid-template-columns:45px 1fr 42px}.profile-row{grid-template-columns:1fr 50px}.profile-track{grid-column:1/-1}.distribution{height:330px;margin-left:78px}.case .metrics{grid-template-columns:1fr}.nav{gap:9px}}
</style></head><body><header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative elections</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">CMO</a><a href="ideology-performance.html" aria-current="page">Ideology &amp; caucuses</a><a href="cmo-methodology.html">Methodology</a></nav></div></header><main class="shell"><div class="hero"><div class="eyebrow">Historical Democratic ideology and performance</div><h1>Alabama Democratic blocs, 1998–2022</h1><p class="dek">This page compares two groupings found in the available issue-position records and measures how their candidates performed on the current candidate-quality residual, against same-cycle federal results, and against the previous presidential result.</p><div class="thesis"><b>Result:</b> the traditionalist-populist bloc ran substantially farther ahead of federal and presidential baselines than the progressive-modern bloc. The association is strongest in the pre-2008 data. It is descriptive evidence of a durable coalition, not proof that any one issue caused the advantage.</div></div><nav class="contents" aria-label="On this page"><a href="#performance">Bloc performance</a><a href="#transition">Transition</a><a href="#positions">Bloc positions</a><a href="#time">Change over time</a><a href="#issues">Issue evidence</a><a href="#cases">Candidates</a><a href="#candidate-explorer">Caucus map</a><a href="#methods">Methods</a></nav>

<section id="performance"><div class="section-head"><div class="kicker">Bloc comparison</div><h2>Performance relative to three expectations</h2><p>Means and standard errors are calculated after clustering. Election performance was not used to assign candidates to a bloc.</p></div><div class="panel"><div class="controls"><label>Performance measure<select id="headlineOutcome"><option value="candidate_federal_overperformance">Raw vs. federal baseline</option><option value="candidate_presidential_overperformance">Raw vs. previous president</option><option value="candidate_quality_residual">Candidate quality residual</option></select></label></div><div id="headline" class="headline-grid" aria-live="polite"></div><div class="key" style="padding:0 20px 12px"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="prog"></i>Progressive-modern</span></div></div></section>

<section id="transition"><div class="section-head"><div class="kicker">Composition</div><h2>The observed caucus changed over time</h2><p>Each bar shows the share of Democratic candidate-cycles assigned to each bloc in that election year. Coverage reflects candidates with enough issue evidence to enter the cluster analysis.</p></div><div class="panel"><div id="transitionChart" class="transition"></div></div></section>

<section id="positions"><div class="section-head"><div class="kicker">Issue profile</div><h2>Where the two blocs differed most</h2><p>Dots are bloc means on conservative-oriented issue axes. Positive values indicate the conservative-coded pole named in the issue explorer; negative values indicate the opposite pole.</p></div><div class="panel"><div class="key" style="padding:12px 16px 0"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="prog"></i>Progressive-modern</span></div><div id="profileChart" class="profile-chart"></div></div></section>

<section><div class="section-head"><div class="kicker">Candidate distribution</div><h2>The bloc result is not only a difference in averages</h2><p>Candidate-cycles remain visible behind each bloc mean and approximate 95% interval. Use the era filter to inspect how much of the evidence comes from different political periods.</p></div><div class="panel"><div class="controls"><label>Measure<select id="distributionOutcome"><option value="candidate_federal_overperformance">Raw vs. federal baseline</option><option value="candidate_presidential_overperformance">Raw vs. previous president</option><option value="candidate_quality_residual">Candidate quality residual</option></select></label><label>Era<select id="distributionEra"><option value="all">All eras</option><option value="pre_2008">Before 2008</option><option value="2008_2014">2008–2014</option><option value="post_2016">2016 and later</option></select></label></div><div id="performanceDistribution" class="distribution"><span class="axis-note">Candidate-oriented margin points →</span></div></div></section>

<section id="time"><div class="section-head"><div class="kicker">Absolute ideology by era</div><h2>The strongest estimate is concentrated before 2008</h2><p>These are regression slopes for Democratic candidates using nationally comparable Shor–McCarty ideology. They are separate from the descriptive bloc averages above.</p></div><div id="eraEvidence" class="era-grid panel"></div></section>

<section id="issues"><div class="section-head"><div class="kicker">Issue explorer</div><h2>Candidate evidence by issue</h2><p>Use this view to inspect individual observations, evidence balance, and performance. Sparse or one-sided issue records should not be read as clean causal comparisons.</p></div><div class="panel"><div class="controls"><label>Issue<select id="issueSelect"></select></label><label>Measure<select id="issueOutcome"><option value="candidate_federal_overperformance">Raw vs. federal baseline</option><option value="candidate_presidential_overperformance">Raw vs. previous president</option><option value="candidate_quality_residual">Candidate quality residual</option></select></label><label>Era<select id="issueEra"><option value="all">All eras</option><option value="pre_2008">Before 2008</option><option value="2008_2014">2008–2014</option><option value="post_2016">2016 and later</option></select></label></div><div id="issueWarning" class="method" hidden></div><div class="issue-layout"><aside id="issueCopy" class="issue-copy"></aside><div><div id="issuePlot" class="issue-plot"><span class="axis-note">Issue position: liberal-coded ← 0 → conservative-coded</span></div><div id="issueCoverage" class="coverage"></div></div></div></div></section>

<section id="cases"><div class="section-head"><div class="kicker">Selected observations</div><h2>Examples and typical cases</h2><p>These cards include a high federal-baseline performer and an observation near each bloc median. They are entry points into the evidence, not a hand-selected proof of the result.</p></div><div id="caseStudies" class="cases"></div></section>

<section id="candidate-explorer"><div class="section-head"><div class="kicker">Caucus explorer</div><h2>Candidate similarity across all clustering dimensions</h2><p>Nearby points have similar observed issue records. The two display coordinates are a projection and do not represent individual ideological axes. Ellipses summarize the two groupings; they are not district geography or probability regions.</p></div><div class="panel"><div class="constellation-wrap"><div class="constellation-main"><svg id="constellation" viewBox="0 0 760 500" role="img" aria-label="Candidate similarity map"></svg><div class="key"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="prog"></i>Progressive-modern</span><span id="constellationCoverage"></span></div></div><aside id="candidateDetail" class="candidate-detail"><p>Select a point or table row to inspect a candidate-cycle.</p></aside></div><div class="table-tools"><label>Search candidates<input id="candidateSearch" type="search" placeholder="Name or district"></label></div><div class="table-wrap"><table><thead><tr><th>Candidate</th><th>Race</th><th>Bloc</th><th class="num">Quality residual</th><th class="num">Vs. federal</th><th class="num">Vs. president</th></tr></thead><tbody id="candidateRows"></tbody></table></div></div></section>

<section id="methods"><div class="section-head"><div class="kicker">Methods and limitations</div><h2>What the analysis can support</h2></div><div class="method"><h3>Cluster membership</h3><p>Candidate groupings use issue positions only. Candidate-quality residuals, election outcomes, incumbency, finance, demographics, district partisanship, and era are attached afterward and do not determine membership. The Democratic two-cluster solution is moderately stable, but candidates still lie on a continuum.</p></div><div class="method"><h3>Performance measures</h3><p>The candidate-quality residual is Direct CMO minus the externally estimated Southern structural expectation, including generic incumbency. It is candidate-oriented but remains a candidate-versus-opponent differential; it is neither Direct CMO nor the career-pooled quality index. Federal and presidential comparisons are raw margin differences and intentionally retain incumbency, fundraising, and other mechanisms through which ideological fit may support durable performance.</p></div><div class="method"><h3>Coverage</h3><p>Issue evidence is selective and varies by candidate, year, and topic. Shor–McCarty scores disproportionately cover officeholders. The post-2016 Democratic absolute-ideology regression has only five observations and is not estimated. Results describe historical associations and do not establish causal effects.</p></div><div class="method"><h3>Republican comparison</h3><p>The primary question here concerns Democratic survival during partisan realignment. Republican cluster assignments remain available in the underlying research output, but their discrete structure is less stable and is not presented as an equivalent caucus history on this page.</p></div></section></main><div id="tip" class="tip"></div><footer>Research and model by Jackson Hannan · <a href="cmo.html">CMO</a> · Updated August 23, 2026</footer><script>const DATA=__DATA__;
const $=s=>document.querySelector(s),tip=$('#tip');
const OUTCOMES={candidate_quality_residual:'Candidate quality residual',candidate_federal_overperformance:'Raw vs. federal baseline',candidate_presidential_overperformance:'Raw vs. previous president'};
const TRAD='Traditionalist-populist Democrats',PROG='Progressive-modern Democrats';
const COLORS={[TRAD]:'#651c2c',[PROG]:'#3b718f'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>v==null||!Number.isFinite(+v)?'—':`${+v>0?'+':''}${(+v).toFixed(1)}`;
const eraLabel=v=>({pre_2008:'Before 2008','2008_2014':'2008–2014',post_2016:'2016 and later'}[v]||v);
function hover(el,html){el.onmouseenter=e=>{tip.innerHTML=html;tip.style.display='block';moveTip(e)};el.onmousemove=moveTip;el.onmouseleave=()=>tip.style.display='none'}
function moveTip(e){tip.style.left=Math.min(innerWidth-305,e.clientX+13)+'px';tip.style.top=Math.min(innerHeight-150,e.clientY+13)+'px'}
function renderHeadline(){const o=$('#headlineOutcome').value,r=DATA.headlineBlocPerformance.find(x=>x.outcome===o);if(!r)return;$('#headline').innerHTML=`<div class="headline-card"><b>${fmt(r.traditionalist_mean)}</b><span>Traditionalist-populist mean</span><small>n=${r.traditionalist_n}; ±${(1.96*r.traditionalist_se).toFixed(1)} approximate 95% interval</small></div><div class="headline-card"><b style="color:var(--blue-dark)">${fmt(r.progressive_mean)}</b><span>Progressive-modern mean</span><small>n=${r.progressive_n}; ±${(1.96*r.progressive_se).toFixed(1)} approximate 95% interval</small></div><div class="headline-card"><b>${fmt(r.difference)}</b><span>Difference between bloc means</span><small>Descriptive difference; not an adjusted causal effect</small></div>`}
function renderTransition(){const cycles=[...new Set(DATA.democraticTransition.map(x=>x.cycle))].sort((a,b)=>a-b);$('#transitionChart').innerHTML=cycles.map(c=>{const rows=DATA.democraticTransition.filter(x=>x.cycle===c),total=rows.reduce((s,x)=>s+x.n,0);return `<div class="transition-row"><strong>${c}</strong><div class="stack">${[TRAD,PROG].map(label=>{const r=rows.find(x=>x.cluster_label===label),n=r?.n||0;return `<button style="width:${total?100*n/total:0}%;background:${COLORS[label]}" aria-label="${label}, ${n} of ${total}" title="${label}: ${n} of ${total}"></button>`}).join('')}</div><small>n=${total}</small></div>`}).join('')}
function renderProfile(){const rows=DATA.blocDifferences.slice(0,10);$('#profileChart').innerHTML=rows.map(r=>`<div class="profile-row"><label>${esc(r.label)}</label><div class="profile-track"><i style="left:${50+45*r.progressive}%;background:${COLORS[PROG]}" title="Progressive-modern ${r.progressive.toFixed(2)}"></i><i style="left:${50+45*r.traditionalist}%;background:${COLORS[TRAD]}" title="Traditionalist-populist ${r.traditionalist.toFixed(2)}"></i></div><output>${fmt(r.difference)}</output></div>`).join('')}
function jitter(id){let h=0;for(const c of id)h=(h*31+c.charCodeAt(0))>>>0;return ((h%1000)/999-.5)*56}
function renderDistribution(){const outcome=$('#distributionOutcome').value,era=$('#distributionEra').value,box=$('#performanceDistribution');box.querySelectorAll(':scope > :not(.axis-note)').forEach(x=>x.remove());const rows=DATA.cluster.members.filter(x=>x.party==='D'&&(era==='all'||x.era===era)&&x[outcome]!=null);const values=rows.map(x=>+x[outcome]),limit=Math.max(30,Math.ceil(Math.max(...values.map(Math.abs),20)/10)*10),left=v=>5+90*(v+limit)/(2*limit);const zero=document.createElement('i');zero.className='zero';zero.style.left=left(0)+'%';box.appendChild(zero);[TRAD,PROG].forEach((label,i)=>{const lane=74-i*43;const tag=document.createElement('span');tag.className='lane';tag.style.bottom=lane+'%';tag.textContent=label.replace(' Democrats','');box.appendChild(tag);const group=rows.filter(x=>x.cluster_label===label);group.forEach(d=>{const dot=document.createElement('button');dot.className='performance-dot';dot.style.background=COLORS[label];dot.style.left=left(d[outcome])+'%';dot.style.bottom=`calc(${lane}% + ${jitter(d.canonical_candidate_id)}px)`;hover(dot,`<b>${esc(d.canonical_name)}</b><br>${d.cycle} ${String(d.chamber).toUpperCase()} ${d.district}<br>${OUTCOMES[outcome]} ${fmt(d[outcome])}`);box.appendChild(dot)});if(group.length){const vals=group.map(x=>+x[outcome]),mean=vals.reduce((a,b)=>a+b,0)/vals.length,sd=Math.sqrt(vals.reduce((s,v)=>s+(v-mean)**2,0)/Math.max(1,vals.length-1)),se=sd/Math.sqrt(vals.length),lo=left(mean-1.96*se),hi=left(mean+1.96*se);const ci=document.createElement('i');ci.className='mean-ci';ci.style.left=lo+'%';ci.style.width=(hi-lo)+'%';ci.style.bottom=lane+'%';box.appendChild(ci);const mark=document.createElement('i');mark.className='mean-mark';mark.style.left=left(mean)+'%';mark.style.bottom=lane+'%';mark.title=`Mean ${fmt(mean)}, n=${vals.length}`;box.appendChild(mark)}})}
function renderEra(){const outcome='candidate_federal_overperformance',eras=['pre_2008','2008_2014','post_2016'];$('#eraEvidence').innerHTML=eras.map(era=>{const r=DATA.era.find(x=>x.sample===`D:${era}`&&x.outcome===outcome);const available=r&&r.coefficient!=null;return `<div class="era-card"><b>${available?fmt(r.coefficient):'Not estimated'}</b><span>${eraLabel(era)} · slope per SD rightward</span><p>${available?`95% CI ${fmt(r.ci_low)} to ${fmt(r.ci_high)}; n=${r.n}`:`Only ${r?.n||0} observed Democratic candidate-cycles with absolute ideology; insufficient for this specification.`}</p></div>`}).join('')}
function initIssues(){const preferred=['gun_access','civil_social_liberty','market_governance','welfare_generosity','abortion_access','racial_civil_rights'];const available=DATA.cluster.issues.slice().sort((a,b)=>(preferred.indexOf(a.key)<0?99:preferred.indexOf(a.key))-(preferred.indexOf(b.key)<0?99:preferred.indexOf(b.key))||a.label.localeCompare(b.label));$('#issueSelect').innerHTML=available.map(x=>`<option value="${x.key}">${esc(x.label)}</option>`).join('')}
function renderIssue(){const issue=$('#issueSelect').value,outcome=$('#issueOutcome').value,era=$('#issueEra').value,meta=DATA.issueMeta.find(x=>x.key===issue)||{label:issue,liberal:'Liberal-coded',conservative:'Conservative-coded',description:''},key='primitive_conservative_'+issue,box=$('#issuePlot');box.querySelectorAll('.performance-dot,.chart-empty').forEach(x=>x.remove());const rows=DATA.cluster.members.filter(x=>x.party==='D'&&(era==='all'||x.era===era)&&x[key]!=null&&x[outcome]!=null);$('#issueCopy').innerHTML=`<h3>${esc(meta.label)}</h3><p>${esc(meta.description)}</p><div class="poles"><span>${esc(meta.liberal)}</span><span>${esc(meta.conservative)}</span></div>`;if(!rows.length){box.insertAdjacentHTML('beforeend','<p class="chart-empty">No observations for this selection.</p>')}const vals=rows.map(x=>+x[outcome]),limit=Math.max(25,Math.ceil(Math.max(...vals.map(Math.abs),20)/10)*10);rows.forEach(d=>{const dot=document.createElement('button');dot.className='performance-dot';dot.style.background=COLORS[d.cluster_label];dot.style.left=(5+90*(+d[key]+1)/2)+'%';dot.style.bottom=(5+90*(+d[outcome]+limit)/(2*limit))+'%';hover(dot,`<b>${esc(d.canonical_name)}</b><br>${d.cycle} ${String(d.chamber).toUpperCase()} ${d.district}<br>${esc(meta.label)} ${fmt(d[key])}<br>${OUTCOMES[outcome]} ${fmt(d[outcome])}`);box.appendChild(dot)});const neg=rows.filter(x=>+x[key]<-.05).length,neutral=rows.filter(x=>Math.abs(+x[key])<=.05).length,pos=rows.filter(x=>+x[key]>.05).length;$('#issueCoverage').innerHTML=`<div><b>${rows.length}</b><span>Observed candidate-cycles</span></div><div><b>${neg} / ${neutral} / ${pos}</b><span>Liberal / neutral / conservative positions</span></div><div><b>${new Set(rows.map(x=>x.canonical_name)).size}</b><span>Distinct candidate names</span></div>`;const warning=$('#issueWarning'),thin=rows.length<12||neg===0||pos===0;warning.hidden=!thin;warning.innerHTML=thin?`<h3>Limited comparison</h3><p>${rows.length<12?'This selection has few observed candidate-cycles. ':''}${neg===0||pos===0?'The evidence does not contain observations on both ideological poles. ':''}Treat the pattern as descriptive coverage, not a clean estimate of issue effects.</p>`:''}
function renderCases(){const order={[TRAD]:0,[PROG]:1};$('#caseStudies').innerHTML=DATA.caseStudies.sort((a,b)=>order[a.cluster_label]-order[b.cluster_label]).map(d=>`<article class="case ${d.cluster_label===PROG?'progressive':''}"><div class="kicker">${esc(d.kind)}</div><h3>${esc(d.name)}</h3><div>${d.cycle} ${String(d.chamber).toUpperCase()} District ${d.district}<br>${esc(d.cluster_label)} · ${d.dimensions} observed issue dimensions</div><div class="metrics"><div><b>${fmt(d.candidate_quality_residual)}</b><span>Quality residual</span></div><div><b>${fmt(d.candidate_federal_overperformance)}</b><span>Vs. federal</span></div><div><b>${fmt(d.candidate_presidential_overperformance)}</b><span>Vs. president</span></div></div></article>`).join('')}
function ellipse(points){if(!points.length)return null;const mx=points.reduce((s,p)=>s+p.x,0)/points.length,my=points.reduce((s,p)=>s+p.y,0)/points.length;return{cx:mx,cy:my,rx:Math.max(42,Math.sqrt(points.reduce((s,p)=>s+(p.x-mx)**2,0)/points.length)*1.7),ry:Math.max(28,Math.sqrt(points.reduce((s,p)=>s+(p.y-my)**2,0)/points.length)*1.7)}}
let selected=null;function renderConstellation(){const svg=$('#constellation'),rows=DATA.cluster.members.filter(x=>x.party==='D'),point=d=>({x:380+d.constellation_x*310,y:250-d.constellation_y*205});svg.innerHTML='';[70,170,270,370,470,570,670].forEach(x=>svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="${x}" y1="30" x2="${x}" y2="470"/>`));[70,160,250,340,430].forEach(y=>svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="35" y1="${y}" x2="725" y2="${y}"/>`));[TRAD,PROG].forEach(label=>{const points=rows.filter(x=>x.cluster_label===label).map(point),e=ellipse(points);if(e)svg.insertAdjacentHTML('beforeend',`<ellipse class="envelope" cx="${e.cx}" cy="${e.cy}" rx="${e.rx}" ry="${e.ry}" fill="${COLORS[label]}" fill-opacity=".09" stroke="${COLORS[label]}"/>`)});rows.slice().sort((a,b)=>a.constellation_coverage-b.constellation_coverage).forEach(d=>{const p=point(d),circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('class','member'+(selected===d.canonical_candidate_id?' selected':''));circle.setAttribute('cx',p.x);circle.setAttribute('cy',p.y);circle.setAttribute('r',4+6*d.constellation_coverage);circle.setAttribute('fill',COLORS[d.cluster_label]);circle.setAttribute('opacity',.32+.65*d.constellation_coverage);circle.setAttribute('tabindex','0');hover(circle,`<b>${esc(d.canonical_name)}</b><br>${esc(d.cluster_label)}<br>${d.cycle} ${String(d.chamber).toUpperCase()} ${d.district}<br>${Math.round(d.constellation_coverage*100)}% clustering-dimension coverage`);circle.onclick=()=>selectCandidate(d);circle.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectCandidate(d)}};svg.appendChild(circle)});$('#constellationCoverage').textContent=`${rows.length} Democratic candidate-cycles · ${DATA.cluster.constellation.D.dimensions} dimensions`}
function selectCandidate(d){selected=d.canonical_candidate_id;const positions=DATA.cluster.issues.map(x=>({label:x.label,value:d['primitive_conservative_'+x.key]})).filter(x=>x.value!=null).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value)).slice(0,6);$('#candidateDetail').innerHTML=`<h3>${esc(d.canonical_name)}</h3><p>${d.cycle} ${String(d.chamber).toUpperCase()} District ${d.district}<br>${esc(d.cluster_label)}</p><div class="score">${fmt(d.candidate_quality_residual)}<span>Candidate quality residual</span></div><dl>${positions.map(x=>`<dt>${esc(x.label)}</dt><dd>${fmt(x.value)}</dd>`).join('')}</dl>`;renderConstellation();document.querySelector(`#candidateRows tr[data-id="${CSS.escape(d.canonical_candidate_id)}"]`)?.scrollIntoView({block:'nearest'})}
function renderRows(){const q=$('#candidateSearch').value.toLowerCase(),rows=DATA.cluster.members.filter(x=>x.party==='D'&&(!q||`${x.canonical_name} ${x.chamber} ${x.district}`.toLowerCase().includes(q))).sort((a,b)=>a.cycle-b.cycle||a.canonical_name.localeCompare(b.canonical_name));$('#candidateRows').innerHTML=rows.map(d=>`<tr data-id="${esc(d.canonical_candidate_id)}"><td>${esc(d.canonical_name)}</td><td>${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}</td><td>${d.cluster_label===TRAD?'Traditionalist-populist':'Progressive-modern'}</td><td class="num">${fmt(d.candidate_quality_residual)}</td><td class="num">${fmt(d.candidate_federal_overperformance)}</td><td class="num">${fmt(d.candidate_presidential_overperformance)}</td></tr>`).join('');document.querySelectorAll('#candidateRows tr').forEach(tr=>tr.onclick=()=>selectCandidate(DATA.cluster.members.find(x=>x.canonical_candidate_id===tr.dataset.id)))}
$('#headlineOutcome').onchange=renderHeadline;$('#distributionOutcome').onchange=renderDistribution;$('#distributionEra').onchange=renderDistribution;$('#issueSelect').onchange=renderIssue;$('#issueOutcome').onchange=renderIssue;$('#issueEra').onchange=renderIssue;$('#candidateSearch').oninput=renderRows;
initIssues();renderHeadline();renderTransition();renderProfile();renderDistribution();renderEra();renderIssue();renderCases();renderConstellation();renderRows();
</script></body></html>'''.replace("__DATA__", data)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
