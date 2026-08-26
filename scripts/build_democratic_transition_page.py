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
CURRENT_QUALITY = ROOT / "data" / "processed" / "war" / "cmo_v5_candidates.csv"
PREFIX = "primitive_conservative_"
PROGRESSIVE = "Progressive-modern Democrats"
TRADITIONALIST = "Traditionalist-populist Democrats"
BRIDGE = "Bridge-coalition Democrats"


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


def _within_context_bloc_contrast(frame: pd.DataFrame, outcome: str) -> dict:
    """Estimate the traditionalist-minus-progressive contrast within election context.

    The fixed effects prevent the historically earlier composition of the
    traditionalist bloc from being mistaken for a candidate-bloc effect. Only
    cycle/chamber cells containing both Democratic blocs identify the result.
    Standard errors are clustered by resolved person identity so repeat
    candidate appearances do not count as independent evidence.
    """
    rows = frame[
        frame.party.eq("D")
        & frame.cluster_label.isin([PROGRESSIVE, TRADITIONALIST])
        & frame[outcome].notna()
    ].copy()
    rows["traditionalist_i"] = rows.cluster_label.eq(TRADITIONALIST).astype(float)
    rows["stratum"] = rows.cycle.astype(str) + "-" + rows.chamber.astype(str)
    overlap = rows.groupby("stratum").traditionalist_i.nunique()
    rows = rows[rows.stratum.isin(overlap[overlap.eq(2)].index)].copy()
    if rows.empty:
        raise ValueError(f"No within-cycle-and-chamber support for {outcome}")

    fixed_effects = pd.get_dummies(rows.stratum, drop_first=True, dtype=float)
    design = np.column_stack([
        np.ones(len(rows)), rows.traditionalist_i.to_numpy(), fixed_effects.to_numpy()
    ])
    response = rows[outcome].to_numpy(dtype=float)
    bread = np.linalg.pinv(design.T @ design)
    coefficients = bread @ design.T @ response
    residuals = response - design @ coefficients

    identities = rows.person_id.where(
        rows.person_id.notna() & rows.person_id.astype(str).str.strip().ne(""),
        rows.canonical_candidate_id,
    ).astype(str)
    meat = np.zeros((design.shape[1], design.shape[1]))
    identity_array = identities.to_numpy()
    for identity in identities.unique():
        index = np.flatnonzero(identity_array == identity)
        score = design[index].T @ residuals[index]
        meat += np.outer(score, score)
    people = int(identities.nunique())
    rank = int(np.linalg.matrix_rank(design))
    if people <= 1 or len(rows) <= rank:
        raise ValueError(f"Insufficient clustered support for {outcome}")
    finite_sample = (people / (people - 1)) * ((len(rows) - 1) / (len(rows) - rank))
    covariance = finite_sample * bread @ meat @ bread
    standard_error = float(np.sqrt(max(0.0, covariance[1, 1])))
    difference = float(coefficients[1])
    return {
        "outcome": outcome,
        "difference": difference,
        "standard_error": standard_error,
        "ci_low": difference - 1.96 * standard_error,
        "ci_high": difference + 1.96 * standard_error,
        "n": int(len(rows)),
        "people": people,
        "strata": int(rows.stratum.nunique()),
        "method": "cycle_chamber_fixed_effects_person_clustered_se",
    }


@lru_cache(maxsize=1)
def payload() -> dict:
    """Combine validated regression and cluster outputs without changing either analysis."""
    ideology = ideology_payload()
    clusters = deepcopy(cluster_payload())
    members = pd.DataFrame(clusters["members"])
    quality = pd.read_csv(
        CURRENT_QUALITY,
        usecols=["canonical_candidate_id", "candidate_quality_index"],
    )
    if quality.canonical_candidate_id.duplicated().any():
        raise ValueError("Current candidate-quality output has duplicate candidate IDs")
    members = (members.drop(columns=["candidate_quality_residual", "candidate_quality_index"], errors="ignore")
               .merge(quality, on="canonical_candidate_id", how="left", validate="one_to_one"))
    if members.candidate_quality_index.isna().any():
        missing = members.loc[members.candidate_quality_index.isna(), "canonical_candidate_id"].tolist()
        raise ValueError(f"Cluster members missing current Candidate Quality Index: {missing[:5]}")

    profiles = pd.DataFrame(clusters["profiles"])
    performance = pd.DataFrame(clusters["performance"])
    performance = performance[~performance.outcome.eq("candidate_cmo")].copy()
    quality_performance = (members.groupby(
        ["party", "cluster_id", "cluster_label"], as_index=False
    ).candidate_quality_index.agg(["count", "mean", "median", "std"]).reset_index())
    quality_performance = quality_performance.rename(
        columns={"count": "n", "std": "sd"}
    )
    quality_performance["standard_error"] = (
        quality_performance.sd / np.sqrt(quality_performance.n)
    )
    quality_performance["outcome"] = "candidate_quality_index"
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
        bloc = democrats[democrats.cluster_label.eq(label)].copy()
        subset = bloc[
            bloc.candidate_federal_overperformance.notna()
            & bloc.candidate_quality_index.notna()
        ].copy()
        if subset.empty or bloc.candidate_quality_index.notna().sum() == 0:
            continue
        # The performance case is defined on the federal comparison. The
        # representative case is independently defined on current CQI
        # quality so its label and displayed headline value refer to the same
        # quantity. Restrict the card candidate to rows with a federal value,
        # but compare it with the median of the full quality-scored bloc.
        quality_median = bloc.candidate_quality_index.median()
        upper_decile = subset.candidate_federal_overperformance.quantile(0.90)
        picks = [(subset.candidate_federal_overperformance - upper_decile).abs().idxmin(),
                 (subset.candidate_quality_index - quality_median).abs().idxmin()]
        for kind, index in zip((
            "Upper-decile federal performance",
            "Near bloc median CQI",
        ), picks):
            row = subset.loc[index]
            case_rows.append({
                "kind": kind, "canonical_candidate_id": row.canonical_candidate_id,
                "name": row.canonical_name, "cycle": int(row.cycle), "chamber": row.chamber,
                "district": int(row.district), "cluster_label": label,
                "candidate_quality_index": row.candidate_quality_index,
                "candidate_federal_overperformance": row.candidate_federal_overperformance,
                "candidate_presidential_overperformance": row.candidate_presidential_overperformance,
                "dimensions": int(row.cluster_dimensions_observed),
            })

    headline = [
        _within_context_bloc_contrast(democrats, outcome)
        for outcome in (
            "candidate_quality_index",
            "candidate_federal_overperformance",
            "candidate_presidential_overperformance",
        )
    ]

    # The discrete issue clusters and continuous Shor–McCarty scale are
    # different measurements. Quantify their empirical connection so the
    # public page never presents a per-SD slope as though it were a bloc mean
    # difference.
    shor = pd.DataFrame(ideology["shorPoints"])[
        ["canonical_candidate_id", "absolute_conservatism_z"]
    ].drop_duplicates("canonical_candidate_id")
    measured = democrats.merge(
        shor, on="canonical_candidate_id", how="left", validate="one_to_one"
    )
    era_estimates = pd.DataFrame(ideology["era"])
    measurement_comparison = []
    for era in ("pre_2008", "2008_2014"):
        covered = measured[
            measured.era.eq(era) & measured.absolute_conservatism_z.notna()
        ]
        means = covered.groupby("cluster_label").absolute_conservatism_z.mean()
        estimate = era_estimates[
            era_estimates["sample"].eq(f"D:{era}")
            & era_estimates["outcome"].eq("candidate_quality_index")
            & era_estimates["term"].eq("absolute_conservatism_z")
        ]
        if not {PROGRESSIVE, TRADITIONALIST}.issubset(means.index) or len(estimate) != 1:
            continue
        slope = float(estimate.iloc[0].coefficient)
        separation = float(means[TRADITIONALIST] - means[PROGRESSIVE])
        observed = _within_context_bloc_contrast(
            democrats[democrats.era.eq(era)], "candidate_quality_index"
        )
        measurement_comparison.append({
            "era": era,
            "shor_cqi_per_sd": slope,
            "cluster_shor_separation_sd": separation,
            "shor_implied_cluster_cqi_gap": slope * separation,
            "observed_issue_cluster_cqi_gap": observed["difference"],
            "shor_cluster_covered": int(len(covered)),
            "issue_cluster_comparison_n": observed["n"],
        })

    ideology["cluster"] = clusters
    ideology["democraticTransition"] = _records(transition)
    ideology["blocDifferences"] = differences
    ideology["headlineBlocPerformance"] = headline
    ideology["measurementComparison"] = measurement_comparison
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
        "blocDifferences", "headlineBlocPerformance", "measurementComparison",
        "caseStudies",
    )}
    public["era"] = [
        row for row in complete["era"]
        if row.get("outcome") == "candidate_quality_index"
    ]
    public["cluster"] = {
        key: complete["cluster"][key]
        for key in ("members", "issues", "constellation")
    }
    data = json.dumps(public, separators=(",", ":"), allow_nan=False)
    return r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Historical Democratic ideology and electoral performance in Alabama"><link rel="icon" href="data:,"><title>Democratic ideology and performance · Jackson Hannan</title><style>
:root{--ink:#25191d;--muted:#6d6064;--line:#bcaeb2;--paper:#fff;--blue:#b9d9ec;--blue-dark:#3b718f;--ox:#651c2c;--ox-dark:#42101b;--pale:#eef7fb;--gold:#ae7b26;--green:#2f6f56}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--blue);color:var(--ink);font:15px/1.55 Arial,Helvetica,sans-serif}header,footer{background:var(--ox);color:#fff}.mast,.shell{width:min(1180px,calc(100% - 40px));margin:auto}.mast{display:flex;justify-content:space-between;align-items:center;gap:22px;padding:18px 0}.brand{font:bold 23px Georgia,serif}.tag,.eyebrow,.kicker{font:bold 10px Arial,sans-serif;letter-spacing:1.1px;text-transform:uppercase}.tag{color:#eadde1;margin-top:3px}.nav{display:flex;gap:16px;flex-wrap:wrap}.nav a,footer a{color:#fff;text-decoration:none;font-size:11px}.nav a[aria-current=page]{border-bottom:2px solid #fff;padding-bottom:3px}.shell{background:var(--paper);padding:52px clamp(18px,4vw,52px) 90px;border-left:1px solid #9ebaca;border-right:1px solid #9ebaca}.hero{max-width:880px}.eyebrow{color:var(--ox)}h1{font:bold clamp(39px,6vw,70px)/1.02 Georgia,serif;letter-spacing:-2px;margin:10px 0 19px}.dek{font:20px/1.55 Georgia,serif;margin:0}.thesis{margin:28px 0 36px;border:1px solid var(--ox);border-left:8px solid var(--ox);padding:18px 20px;background:#fff9fa;font:16px/1.6 Georgia,serif}.contents{display:flex;gap:8px;flex-wrap:wrap;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:11px 0;margin-bottom:60px}.contents a{color:var(--ox);text-decoration:none;font:bold 10px Arial;padding:5px 8px;background:#f8f3f4}section{margin:74px 0;scroll-margin-top:20px}.section-head{max-width:820px;margin-bottom:25px}.section-head h2{font:bold 33px/1.1 Georgia,serif;margin:7px 0 10px}.section-head p{margin:0;color:#4d4246}.panel{border:1px solid var(--line);background:#fff}.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap;padding:13px 15px;border-bottom:1px solid var(--line);background:#f8f4f5}.controls label{font:bold 9px Arial;text-transform:uppercase;letter-spacing:.7px;color:var(--muted)}select,input{display:block;margin-top:4px;border:1px solid #9c8c91;background:#fff;padding:8px 30px 8px 9px;color:var(--ink)}.headline-grid{display:grid;grid-template-columns:1fr 1fr 1fr}.headline-card{padding:22px;border-right:1px solid var(--line)}.headline-card:last-child{border:0}.headline-card b{display:block;font:bold 32px Georgia;color:var(--ox)}.headline-card span{display:block;font-size:11px;color:var(--muted)}.headline-card small{display:block;margin-top:10px}.key{display:flex;gap:18px;flex-wrap:wrap;font-size:11px;color:var(--muted);margin:10px 0}.key i{display:inline-block;width:11px;height:11px;margin-right:5px;vertical-align:-1px}.trad{background:var(--ox)}.prog{background:var(--blue-dark)}.transition{padding:18px}.transition-row{display:grid;grid-template-columns:58px 1fr 58px;gap:10px;align-items:center;padding:8px 0;border-top:1px solid #e2d9dc}.transition-row:first-child{border:0}.stack{height:27px;display:flex;border:1px solid #9e8d92}.stack button{height:100%;border:0;min-width:2px;cursor:pointer}.stack button:hover,.stack button:focus{filter:brightness(1.2);outline:2px solid var(--ink);z-index:2}.transition-row strong{font-size:12px}.transition-row small{text-align:right;color:var(--muted)}.profile-chart{padding:16px}.profile-row{display:grid;grid-template-columns:190px 1fr 70px;gap:12px;align-items:center;padding:10px 0;border-top:1px solid #e2d9dc}.profile-row:first-child{border:0}.profile-row label{font-size:12px}.profile-track{position:relative;height:24px;background:linear-gradient(90deg,#dcecf5,#fff 49.5%,#f0dce1)}.profile-track:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #8e7c82}.profile-track i{position:absolute;top:5px;width:13px;height:13px;border-radius:50%;transform:translateX(-50%);border:2px solid #fff}.profile-row output{text-align:right;font:bold 12px Arial}.distribution{height:390px;position:relative;margin:20px 32px 50px 112px;border-left:1px solid var(--line);border-bottom:1px solid var(--line);background:repeating-linear-gradient(to right,transparent 0,transparent calc(20% - 1px),#eee 20%)}.distribution .lane{position:absolute;left:-105px;width:100px;font-size:10px;text-align:right;transform:translateY(50%)}.distribution .zero{position:absolute;top:0;bottom:0;width:1px;background:#7b6c71}.performance-dot{position:absolute;border:1px solid #fff;box-shadow:0 0 0 1px #57484d;width:9px;height:9px;border-radius:50%;transform:translate(-50%,50%);cursor:pointer;opacity:.7}.mean-mark{position:absolute;width:4px;height:34px;transform:translate(-50%,50%);background:var(--ink)}.mean-ci{position:absolute;height:3px;transform:translateY(50%);background:var(--ink)}.axis-note{position:absolute;bottom:-32px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted);white-space:nowrap}.era-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line)}.era-card{background:#fff;padding:18px}.era-card b{font:bold 29px Georgia,serif;display:block}.era-card span{font-size:11px;color:var(--muted)}.era-card p{font-size:12px;margin:10px 0 0}.issue-layout{display:grid;grid-template-columns:280px 1fr}.issue-copy{padding:20px;background:#f7f2f4;border-right:1px solid var(--line)}.issue-copy h3{font:bold 23px Georgia;margin:0 0 8px}.issue-copy p{font-size:12px}.poles{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding-top:10px;font:bold 9px Arial;text-transform:uppercase;color:var(--muted)}.issue-plot{height:390px;position:relative;margin:20px 25px 50px 70px;border-left:1px solid var(--line);border-bottom:1px solid var(--line);background:linear-gradient(90deg,#e4f1f8,#fff 49.5%,#f3e1e5)}.issue-plot:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #8e7c82}.coverage{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border-top:1px solid var(--line)}.coverage div{background:#fff;padding:12px}.coverage b{display:block;font-size:19px}.coverage span{font-size:9px;color:var(--muted)}.cases{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.case{border-top:5px solid var(--ox);background:#fff;border-left:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:17px}.case.progressive{border-top-color:var(--blue-dark)}.case h3{font:bold 20px Georgia;margin:4px 0}.case .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:15px}.case .metrics div{background:#f5f1f2;padding:9px}.case .metrics b{display:block}.constellation-wrap{display:grid;grid-template-columns:minmax(0,1fr) 310px}.constellation-main{padding:16px;border-right:1px solid var(--line)}#constellation{display:block;width:100%;height:auto;background:#f7fbfd;border:1px solid var(--line)}#constellation .grid{stroke:#dae3e7}#constellation .envelope{stroke-width:2;stroke-dasharray:5 4}#constellation .member{stroke:#fff;stroke-width:1.5;cursor:pointer}#constellation .member.selected{stroke:var(--ink);stroke-width:3}.candidate-detail{padding:20px}.candidate-detail h3{font:bold 24px Georgia;margin:0}.candidate-detail .score{font:bold 36px Georgia;color:var(--ox);margin:18px 0}.candidate-detail .score span{display:block;font:9px Arial;text-transform:uppercase;color:var(--muted)}.candidate-detail dl{font-size:11px}.candidate-detail dt{float:left;clear:left;color:var(--muted)}.candidate-detail dd{text-align:right;border-bottom:1px solid #e2d9dc;padding:4px 0}.table-tools{padding:14px;border-top:1px solid var(--line)}.table-wrap{max-height:390px;overflow:auto;border-top:1px solid var(--line)}table{border-collapse:collapse;width:100%;font-size:11px}th{position:sticky;top:0;background:var(--ox);color:#fff;text-align:left;padding:8px}td{padding:8px;border-top:1px solid #e2d9dc}tbody tr{cursor:pointer}tbody tr:hover{background:var(--pale)}.num{text-align:right}.method{border-left:6px solid var(--ox);background:#f8f3f4;padding:18px 20px;margin:12px 0}.method h3{font:bold 18px Georgia;margin:0 0 7px}.method p{margin:0;font-size:12px}.tip{position:fixed;display:none;z-index:20;pointer-events:none;max-width:290px;background:var(--ox-dark);color:#fff;padding:10px 12px;font-size:11px;box-shadow:0 8px 22px #0004}footer{padding:25px max(20px,calc((100vw - 1140px)/2));font-size:11px}@media(max-width:780px){.mast{align-items:flex-start;flex-direction:column}.headline-grid,.era-grid{grid-template-columns:1fr}.headline-card{border-right:0;border-bottom:1px solid var(--line)}.profile-row{grid-template-columns:125px 1fr 55px}.issue-layout,.constellation-wrap{grid-template-columns:1fr}.issue-copy,.constellation-main{border-right:0;border-bottom:1px solid var(--line)}.cases{grid-template-columns:1fr}}@media(max-width:520px){.mast,.shell{width:100%}.mast{padding:15px}.shell{padding:36px 14px 65px;border:0}h1{font-size:39px}.transition-row{grid-template-columns:45px 1fr 42px}.profile-row{grid-template-columns:1fr 50px}.profile-track{grid-column:1/-1}.distribution{height:330px;margin-left:78px}.case .metrics{grid-template-columns:1fr}.nav{gap:9px}}
</style><style>.headline-comparison{padding:10px 20px 20px}.headline-row{display:grid;grid-template-columns:220px minmax(260px,1fr) 190px;gap:18px;align-items:center;padding:17px 0;border-top:1px solid var(--line)}.headline-row:first-child{border-top:0}.headline-row h3{font:bold 14px Georgia;margin:0}.headline-track{position:relative;height:34px;background:linear-gradient(90deg,#f5e8eb,#fff 50%,#e5f1f7)}.headline-track:after,.forest-track:after{content:"";position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #776a6e}.headline-ci{position:absolute;top:15px;height:3px;transform:translateX(0)}.headline-point{position:absolute;top:10px;width:13px;height:13px;border:2px solid #fff;border-radius:50%;transform:translateX(-50%);box-shadow:0 0 0 1px #4f4246}.headline-values{font-size:10px;color:var(--muted)}.headline-values b{display:block;font-size:13px;color:var(--ink)}.transition-axis{display:grid;grid-template-columns:58px 1fr 58px;gap:10px;font-size:9px;color:var(--muted)}.transition-axis div{display:flex;justify-content:space-between}.transition-row.thin{background:#fff8e8}.sample-note{margin:10px 0 0;font-size:10px;color:#73530c}.era-forest{padding:12px 20px}.forest-row{display:grid;grid-template-columns:150px minmax(220px,1fr) 175px;gap:14px;align-items:center;padding:15px 0;border-top:1px solid var(--line)}.forest-row:first-child{border:0}.forest-track{position:relative;height:28px;background:#f7f2f4}.forest-ci{position:absolute;top:13px;height:3px;background:var(--ox)}.forest-point{position:absolute;top:8px;width:13px;height:13px;border-radius:50%;background:var(--ox);border:2px solid #fff;box-shadow:0 0 0 1px var(--ox);transform:translateX(-50%)}.forest-value{font-size:10px;color:var(--muted)}.forest-value b{display:block;font-size:12px;color:var(--ink)}.selection-detail{min-height:48px;border-top:1px solid var(--line);padding:11px 15px;background:#fbf8f9;font-size:11px}.selection-detail b{font-family:Georgia,serif}.contents-mobile{display:none;margin:0 0 36px;border:1px solid var(--line);background:#fff}.contents-mobile summary{padding:12px;font-weight:bold;color:var(--ox);cursor:pointer}.contents-mobile .contents{margin:0;border:0;padding:0 10px 12px}.performance-dot:focus-visible,#constellation .member:focus-visible{outline:3px solid var(--gold);outline-offset:3px}.candidate-detail{min-height:250px}#candidateRows tr:focus{outline:2px solid var(--blue-dark);outline-offset:-2px;background:var(--pale)}@media(max-width:780px){.headline-row,.forest-row{grid-template-columns:1fr}.headline-values,.forest-value{display:grid;grid-template-columns:1fr 1fr;gap:8px}.contents{display:none}.contents-mobile{display:block}.contents-mobile .contents{display:flex}.hero{max-width:none}.thesis{margin-bottom:24px}}@media(max-width:520px){.headline-comparison,.era-forest{padding:8px 12px 15px}.headline-track,.forest-track{min-width:0}.selection-detail{font-size:10px}}</style></head><body><header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative elections</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">CMO</a><a href="ideology-performance.html" aria-current="page">Ideology &amp; caucuses</a><a href="cmo-methodology.html">Methodology</a></nav></div></header><main class="shell"><div class="hero"><div class="eyebrow">Historical Democratic ideology and performance</div><h1>Alabama Democratic blocs, 1998–2022</h1><p class="dek">This page compares two groupings found in the available issue-position records and measures how their candidates performed on the Candidate Quality Index, against same-cycle federal results, and against the previous presidential result.</p><div class="thesis"><b>Result:</b> the traditionalist-populist bloc ran substantially farther ahead of federal and presidential baselines than the progressive-modern bloc. The association is strongest in the pre-2008 data. It is descriptive evidence of a durable coalition, not proof that any one issue caused the advantage.</div></div><nav class="contents" aria-label="On this page"><a href="#performance">Bloc performance</a><a href="#transition">Transition</a><a href="#positions">Bloc positions</a><a href="#time">Change over time</a><a href="#issues">Issue evidence</a><a href="#cases">Candidates</a><a href="#candidate-explorer">Caucus map</a><a href="#methods">Methods</a></nav><details class="contents-mobile"><summary>On this page</summary><nav class="contents" aria-label="On this page"><a href="#performance">Bloc performance</a><a href="#transition">Transition</a><a href="#positions">Bloc positions</a><a href="#time">Change over time</a><a href="#issues">Issue evidence</a><a href="#cases">Candidates</a><a href="#candidate-explorer">Caucus map</a><a href="#methods">Methods</a></nav></details>

<section id="performance"><div class="section-head"><div class="kicker">Issue-cluster measurement</div><h2>CQI difference between issue-based blocs</h2><p>This is a binary comparison between candidates assigned to the traditionalist-populist and progressive-modern clusters from their issue records. Its unit is <b>CQI points between clusters</b>. Positive values and rightward positions mean the traditionalist-populist bloc performed better. Election performance was not used to assign candidates to a bloc.</p></div><div class="panel"><div id="headline" class="headline-comparison" aria-live="polite"></div><div class="method headline-method"><b>Issue-cluster comparison set:</b> only cycle-and-chamber cells containing both blocs. Lines show approximate 95% intervals with repeat appearances clustered by candidate identity. These are descriptive adjusted contrasts, not causal effects.</div></div><div class="measurement-explainer"><h3>Do not compare the cluster difference directly with the Shor–McCarty slope</h3><div class="measure-definitions"><div><b>Issue-cluster contrast</b><span>Binary group membership derived from multidimensional issue records.</span><strong>Unit: CQI points between clusters</strong></div><div><b>Shor–McCarty slope</b><span>Continuous nationally comparable ideology score.</span><strong>Unit: CQI points per one ideology standard deviation</strong></div></div><div id="measurementBridge" class="measurement-bridge panel"></div></div></section>

<section id="transition"><div class="section-head"><div class="kicker">Composition</div><h2>The observed caucus changed over time</h2><p>Each bar shows the share of Democratic candidate-cycles assigned to each bloc in that election year. Coverage reflects candidates with enough issue evidence to enter the cluster analysis.</p></div><div class="panel"><div id="transitionChart" class="transition"></div></div></section>

<section id="positions"><div class="section-head"><div class="kicker">Issue profile</div><h2>Where the endpoint blocs differed most</h2><p>Dots compare the traditionalist-populist and progressive-modern endpoint means on conservative-oriented issue axes. The bridge coalition is displayed in the transition and candidate map but is not folded into either endpoint. Positive values indicate the conservative-coded pole named in the issue explorer; negative values indicate the opposite pole.</p></div><div class="panel"><div class="key" style="padding:12px 16px 0"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="bridge"></i>Bridge coalition</span><span><i class="prog"></i>Progressive-modern</span></div><div id="profileChart" class="profile-chart"></div></div></section>

<section><div class="section-head"><div class="kicker">Candidate distribution</div><h2>The bloc result is not only a difference in averages</h2><p>Candidate-cycles remain visible behind each bloc mean and approximate 95% interval. Use the era filter to inspect how much of the evidence comes from different political periods.</p></div><div class="panel"><div class="controls"><label>Measure<select id="distributionOutcome"><option value="candidate_federal_overperformance">Raw vs. federal baseline</option><option value="candidate_presidential_overperformance">Raw vs. previous president</option><option value="candidate_quality_index">Candidate Quality Index (CQI)</option></select></label><label>Era<select id="distributionEra"><option value="all">All eras</option><option value="pre_2008">Before 2008</option><option value="2008_2014">2008–2014</option><option value="post_2016">2016 and later</option></select></label></div><div id="performanceDistribution" class="distribution"><span class="axis-note">Candidate-oriented margin points →</span></div><div id="distributionDetail" class="selection-detail" aria-live="polite">Select a candidate point for its race, bloc, and performance value.</div></div></section>

<section id="time"><div class="section-head"><div class="kicker">Shor–McCarty continuous measurement</div><h2>CQI slope by absolute ideology and era</h2><p>Each row estimates the change in Candidate Quality Index associated with a one-standard-deviation move toward the conservative end of the nationally comparable Shor–McCarty scale. Its unit is <b>CQI points per one Shor–McCarty standard deviation</b>, not CQI points between issue clusters. Positive and rightward estimates mean that more conservative Democrats had higher CQI; negative and leftward estimates mean the reverse.</p></div><div id="eraEvidence" class="era-forest panel"></div></section>

<section id="issues"><div class="section-head"><div class="kicker">Issue explorer</div><h2>Candidate evidence by issue</h2><p>Use this view to inspect individual observations, evidence balance, and performance. Sparse or one-sided issue records should not be read as clean causal comparisons.</p></div><div class="panel"><div class="controls"><label>Issue<select id="issueSelect"></select></label><label>Measure<select id="issueOutcome"><option value="candidate_federal_overperformance">Raw vs. federal baseline</option><option value="candidate_presidential_overperformance">Raw vs. previous president</option><option value="candidate_quality_index">Candidate Quality Index (CQI)</option></select></label><label>Era<select id="issueEra"><option value="all">All eras</option><option value="pre_2008">Before 2008</option><option value="2008_2014">2008–2014</option><option value="post_2016">2016 and later</option></select></label></div><div id="issueWarning" class="method" hidden></div><div class="issue-layout"><aside id="issueCopy" class="issue-copy"></aside><div><div id="issuePlot" class="issue-plot"><span class="axis-note">Issue position: liberal-coded ← 0 → conservative-coded</span></div><div id="issuePointDetail" class="selection-detail" aria-live="polite">Select a candidate point for the underlying issue and performance values.</div><div id="issueCoverage" class="coverage"></div></div></div></div></section>

<section id="cases"><div class="section-head"><div class="kicker">Selected observations</div><h2>Examples and typical cases</h2><p>These cards include a high federal-baseline performer and the eligible observation nearest each bloc's median CQI. They are entry points into the evidence, not a hand-selected proof of the result.</p></div><div id="caseStudies" class="cases"></div></section>

<section id="candidate-explorer"><div class="section-head"><div class="kicker">Caucus explorer</div><h2>Candidate similarity across all clustering dimensions</h2><p>Nearby points have similar observed issue records. The two display coordinates are a projection and do not represent individual ideological axes. Ellipses summarize three descriptive Democratic regions; they are not district geography, formal caucus boundaries, or probability regions.</p></div><div class="panel"><div class="constellation-wrap"><div class="constellation-main"><svg id="constellation" viewBox="0 0 760 500" role="img" aria-label="Candidate similarity map"></svg><div class="key"><span><i class="trad"></i>Traditionalist-populist</span><span><i class="bridge"></i>Bridge coalition</span><span><i class="prog"></i>Progressive-modern</span><span id="constellationCoverage"></span></div></div><aside id="candidateDetail" class="candidate-detail"><p>Select a point or table row to inspect a candidate-cycle.</p></aside></div><div class="table-tools"><label>Search candidates<input id="candidateSearch" type="search" placeholder="Name or district"></label></div><div class="table-wrap"><table><thead><tr><th>Candidate</th><th>Race</th><th>Bloc</th><th class="num">CQI</th><th class="num">Vs. federal</th><th class="num">Vs. president</th></tr></thead><tbody id="candidateRows"></tbody></table></div></div></section>

<section id="methods"><div class="section-head"><div class="kicker">Methods and limitations</div><h2>What the analysis can support</h2></div><div class="method"><h3>Two ideology measurements</h3><p><b>Issue-cluster contrasts</b> compare binary group assignments derived from the multidimensional issue evidence and are reported in outcome points between clusters. <b>Shor–McCarty slopes</b> use a continuous nationally comparable ideology score and are reported in outcome points per one standard deviation. Neither number is an average of the other. Their samples also differ because Shor–McCarty primarily covers legislators while the issue evidence has its own coverage requirements.</p></div><div class="method"><h3>Cluster membership</h3><p>Candidate groupings use issue positions only. CQI, election outcomes, incumbency, finance, demographics, district partisanship, and era are attached afterward and do not determine membership. The Democratic two-cluster solution is moderately stable, but candidates still lie on a continuum.</p></div><div class="method"><h3>Performance measures</h3><p>The Candidate Quality Index estimates the repeatable candidate component of cycle-centered CMO across a candidate's observed race and opponent network. It is partially pooled toward zero and is retrospective; it is not Direct CMO or the post-2016-invalid Southern structural residual. Federal and presidential comparisons are raw margin differences and intentionally retain incumbency, fundraising, and other mechanisms through which ideological fit may support durable performance.</p></div><div class="method"><h3>Coverage</h3><p>Issue evidence is selective and varies by candidate, year, and topic. Shor–McCarty scores disproportionately cover officeholders. The post-2016 Democratic absolute-ideology regression has only five observations and is not estimated. The modern bloc comparison contains four traditionalist and twenty progressive candidate-cycles and remains descriptive. Results do not establish causal effects.</p></div><div class="method"><h3>Republican comparison</h3><p>The primary question here concerns Democratic survival during partisan realignment. Republican cluster assignments remain available in the underlying research output, but their discrete structure is less stable and is not presented as an equivalent caucus history on this page.</p></div></section></main><div id="tip" class="tip"></div><footer>Research and model by Jackson Hannan · <a href="cmo.html">CMO</a> · Updated August 24, 2026</footer><script>const DATA=__DATA__;
const $=s=>document.querySelector(s),tip=$('#tip');
const OUTCOMES={candidate_quality_index:'Candidate Quality Index (CQI)',candidate_federal_overperformance:'Raw vs. federal baseline',candidate_presidential_overperformance:'Raw vs. previous president'};
const TRAD='Traditionalist-populist Democrats',BRIDGE='Bridge-coalition Democrats',PROG='Progressive-modern Democrats',DEMOCRATIC_BLOCS=[TRAD,BRIDGE,PROG];
const COLORS={[TRAD]:'#651c2c',[BRIDGE]:'#ae7b26',[PROG]:'#3b718f'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>v==null||!Number.isFinite(+v)?'—':`${+v>0?'+':''}${(+v).toFixed(1)}`;
const eraLabel=v=>({pre_2008:'Before 2008','2008_2014':'2008–2014',post_2016:'2016 and later'}[v]||v);
function hover(el,html){const label=html.replace(/<br\s*\/?>/gi,', ').replace(/<[^>]+>/g,'').replace(/&middot;|Â·/g,' - ');el.setAttribute('aria-label',label);el.onmouseenter=e=>{tip.innerHTML=html;tip.style.display='block';moveTip(e)};el.onfocus=()=>{tip.style.display='none'};el.onmousemove=moveTip;el.onmouseleave=()=>tip.style.display='none'}
function moveTip(e){tip.style.left=Math.min(innerWidth-305,e.clientX+13)+'px';tip.style.top=Math.min(innerHeight-150,e.clientY+13)+'px'}
function renderTransition(){const cycles=[...new Set(DATA.democraticTransition.map(x=>x.cycle))].sort((a,b)=>a-b);$('#transitionChart').innerHTML=cycles.map(c=>{const rows=DATA.democraticTransition.filter(x=>x.cycle===c),total=rows.reduce((s,x)=>s+x.n,0);return `<div class="transition-row"><strong>${c}</strong><div class="stack">${[TRAD,PROG].map(label=>{const r=rows.find(x=>x.cluster_label===label),n=r?.n||0;return `<button style="width:${total?100*n/total:0}%;background:${COLORS[label]}" aria-label="${label}, ${n} of ${total}" title="${label}: ${n} of ${total}"></button>`}).join('')}</div><small>n=${total}</small></div>`}).join('')}
function renderProfile(){const rows=DATA.blocDifferences.slice(0,10);$('#profileChart').innerHTML=rows.map(r=>`<div class="profile-row"><label>${esc(r.label)}</label><div class="profile-track"><i style="left:${50+45*r.progressive}%;background:${COLORS[PROG]}" title="Progressive-modern ${r.progressive.toFixed(2)}"></i><i style="left:${50+45*r.traditionalist}%;background:${COLORS[TRAD]}" title="Traditionalist-populist ${r.traditionalist.toFixed(2)}"></i></div><output>${fmt(r.difference)}</output></div>`).join('')}
function jitter(id){let h=0;for(const c of id)h=(h*31+c.charCodeAt(0))>>>0;return ((h%1000)/999-.5)*56}
function renderDistribution(){const outcome=$('#distributionOutcome').value,era=$('#distributionEra').value,box=$('#performanceDistribution');box.querySelectorAll(':scope > :not(.axis-note)').forEach(x=>x.remove());const rows=DATA.cluster.members.filter(x=>x.party==='D'&&(era==='all'||x.era===era)&&x[outcome]!=null);const values=rows.map(x=>+x[outcome]),limit=Math.max(30,Math.ceil(Math.max(...values.map(Math.abs),20)/10)*10),left=v=>5+90*(v+limit)/(2*limit);const zero=document.createElement('i');zero.className='zero';zero.style.left=left(0)+'%';box.appendChild(zero);DEMOCRATIC_BLOCS.forEach((label,i)=>{const lane=78-i*28;const tag=document.createElement('span');tag.className='lane';tag.style.bottom=lane+'%';tag.textContent=label.replace(' Democrats','');box.appendChild(tag);const group=rows.filter(x=>x.cluster_label===label);group.forEach(d=>{const dot=document.createElement('button');dot.className='performance-dot';dot.style.background=COLORS[label];dot.style.left=left(d[outcome])+'%';dot.style.bottom=`calc(${lane}% + ${jitter(d.canonical_candidate_id)}px)`;hover(dot,`<b>${esc(d.canonical_name)}</b><br>${d.cycle} ${String(d.chamber).toUpperCase()} ${d.district}<br>${OUTCOMES[outcome]} ${fmt(d[outcome])}`);box.appendChild(dot)});if(group.length){const vals=group.map(x=>+x[outcome]),mean=vals.reduce((a,b)=>a+b,0)/vals.length,sd=Math.sqrt(vals.reduce((s,v)=>s+(v-mean)**2,0)/Math.max(1,vals.length-1)),se=sd/Math.sqrt(vals.length),lo=left(mean-1.96*se),hi=left(mean+1.96*se);const ci=document.createElement('i');ci.className='mean-ci';ci.style.left=lo+'%';ci.style.width=(hi-lo)+'%';ci.style.bottom=lane+'%';box.appendChild(ci);const mark=document.createElement('i');mark.className='mean-mark';mark.style.left=left(mean)+'%';mark.style.bottom=lane+'%';mark.title=`Mean ${fmt(mean)}, n=${vals.length}`;box.appendChild(mark)}})}
function renderEra(){const outcome='candidate_quality_index',eras=['pre_2008','2008_2014','post_2016'];$('#eraEvidence').innerHTML=eras.map(era=>{const r=DATA.era.find(x=>x.sample===`D:${era}`&&x.outcome===outcome);const available=r&&r.coefficient!=null;return `<div class="era-card"><b>${available?fmt(r.coefficient):'Not estimated'}</b><span>${eraLabel(era)} · CQI per 1 SD more conservative</span><p>${available?`95% CI ${fmt(r.ci_low)} to ${fmt(r.ci_high)}; n=${r.n}`:`Only ${r?.n||0} observed Democratic candidate-cycles with absolute ideology; insufficient for this specification.`}</p></div>`}).join('')}
function initIssues(){const preferred=['gun_access','civil_social_liberty','market_governance','welfare_generosity','abortion_access','racial_civil_rights'];const available=DATA.cluster.issues.slice().sort((a,b)=>(preferred.indexOf(a.key)<0?99:preferred.indexOf(a.key))-(preferred.indexOf(b.key)<0?99:preferred.indexOf(b.key))||a.label.localeCompare(b.label));$('#issueSelect').innerHTML=available.map(x=>`<option value="${x.key}">${esc(x.label)}</option>`).join('')}
function renderIssue(){const issue=$('#issueSelect').value,outcome=$('#issueOutcome').value,era=$('#issueEra').value,meta=DATA.issueMeta.find(x=>x.key===issue)||{label:issue,liberal:'Liberal-coded',conservative:'Conservative-coded',description:''},key='primitive_conservative_'+issue,box=$('#issuePlot');box.querySelectorAll('.performance-dot,.chart-empty').forEach(x=>x.remove());const rows=DATA.cluster.members.filter(x=>x.party==='D'&&(era==='all'||x.era===era)&&x[key]!=null&&x[outcome]!=null);$('#issueCopy').innerHTML=`<h3>${esc(meta.label)}</h3><p>${esc(meta.description)}</p><div class="poles"><span>${esc(meta.liberal)}</span><span>${esc(meta.conservative)}</span></div>`;if(!rows.length){box.insertAdjacentHTML('beforeend','<p class="chart-empty">No observations for this selection.</p>')}const vals=rows.map(x=>+x[outcome]),limit=Math.max(25,Math.ceil(Math.max(...vals.map(Math.abs),20)/10)*10);rows.forEach(d=>{const dot=document.createElement('button');dot.className='performance-dot';dot.style.background=COLORS[d.cluster_label];dot.style.left=(5+90*(+d[key]+1)/2)+'%';dot.style.bottom=(5+90*(+d[outcome]+limit)/(2*limit))+'%';hover(dot,`<b>${esc(d.canonical_name)}</b><br>${d.cycle} ${String(d.chamber).toUpperCase()} ${d.district}<br>${esc(meta.label)} ${fmt(d[key])}<br>${OUTCOMES[outcome]} ${fmt(d[outcome])}`);box.appendChild(dot)});const neg=rows.filter(x=>+x[key]<-.05).length,neutral=rows.filter(x=>Math.abs(+x[key])<=.05).length,pos=rows.filter(x=>+x[key]>.05).length;$('#issueCoverage').innerHTML=`<div><b>${rows.length}</b><span>Observed candidate-cycles</span></div><div><b>${neg} / ${neutral} / ${pos}</b><span>Liberal / neutral / conservative positions</span></div><div><b>${new Set(rows.map(x=>x.canonical_name)).size}</b><span>Distinct candidate names</span></div>`;const warning=$('#issueWarning'),thin=rows.length<12||neg===0||pos===0;warning.hidden=!thin;warning.innerHTML=thin?`<h3>Limited comparison</h3><p>${rows.length<12?'This selection has few observed candidate-cycles. ':''}${neg===0||pos===0?'The evidence does not contain observations on both ideological poles. ':''}Treat the pattern as descriptive coverage, not a clean estimate of issue effects.</p>`:''}
function renderCases(){const order={[TRAD]:0,[PROG]:1};$('#caseStudies').innerHTML=DATA.caseStudies.sort((a,b)=>order[a.cluster_label]-order[b.cluster_label]).map(d=>`<article class="case ${d.cluster_label===PROG?'progressive':''}"><div class="kicker">${esc(d.kind)}</div><h3>${esc(d.name)}</h3><div>${d.cycle} ${String(d.chamber).toUpperCase()} District ${d.district}<br>${esc(d.cluster_label)} · ${d.dimensions} observed issue dimensions</div><div class="metrics"><div><b>${fmt(d.candidate_quality_index)}</b><span>CQI</span></div><div><b>${fmt(d.candidate_federal_overperformance)}</b><span>Vs. federal</span></div><div><b>${fmt(d.candidate_presidential_overperformance)}</b><span>Vs. president</span></div></div></article>`).join('')}
function ellipse(points){if(!points.length)return null;const mx=points.reduce((s,p)=>s+p.x,0)/points.length,my=points.reduce((s,p)=>s+p.y,0)/points.length;return{cx:mx,cy:my,rx:Math.max(42,Math.sqrt(points.reduce((s,p)=>s+(p.x-mx)**2,0)/points.length)*1.7),ry:Math.max(28,Math.sqrt(points.reduce((s,p)=>s+(p.y-my)**2,0)/points.length)*1.7)}}
let selected=null;function renderConstellation(){const svg=$('#constellation'),rows=DATA.cluster.members.filter(x=>x.party==='D'),point=d=>({x:380+d.constellation_x*310,y:250-d.constellation_y*205});svg.innerHTML='';[70,170,270,370,470,570,670].forEach(x=>svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="${x}" y1="30" x2="${x}" y2="470"/>`));[70,160,250,340,430].forEach(y=>svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="35" y1="${y}" x2="725" y2="${y}"/>`));DEMOCRATIC_BLOCS.forEach(label=>{const points=rows.filter(x=>x.cluster_label===label).map(point),e=ellipse(points);if(e)svg.insertAdjacentHTML('beforeend',`<ellipse class="envelope" cx="${e.cx}" cy="${e.cy}" rx="${e.rx}" ry="${e.ry}" fill="${COLORS[label]}" fill-opacity=".09" stroke="${COLORS[label]}"/>`)});rows.slice().sort((a,b)=>a.constellation_coverage-b.constellation_coverage).forEach(d=>{const p=point(d),circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('class','member'+(selected===d.canonical_candidate_id?' selected':''));circle.setAttribute('cx',p.x);circle.setAttribute('cy',p.y);circle.setAttribute('r',4+6*d.constellation_coverage);circle.setAttribute('fill',COLORS[d.cluster_label]);circle.setAttribute('opacity',.32+.65*d.constellation_coverage);circle.setAttribute('tabindex','0');hover(circle,`<b>${esc(d.canonical_name)}</b><br>${esc(d.cluster_label)}<br>${d.cycle} ${String(d.chamber).toUpperCase()} ${d.district}<br>${Math.round(d.constellation_coverage*100)}% clustering-dimension coverage`);circle.onclick=()=>selectCandidate(d);circle.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectCandidate(d)}};svg.appendChild(circle)});$('#constellationCoverage').textContent=`${rows.length} Democratic candidate-cycles · ${DATA.cluster.constellation.D.dimensions} dimensions`}
function selectCandidate(d){selected=d.canonical_candidate_id;const positions=DATA.cluster.issues.map(x=>({label:x.label,value:d['primitive_conservative_'+x.key]})).filter(x=>x.value!=null).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value)).slice(0,6);$('#candidateDetail').innerHTML=`<h3>${esc(d.canonical_name)}</h3><p>${d.cycle} ${String(d.chamber).toUpperCase()} District ${d.district}<br>${esc(d.cluster_label)}</p><div class="score">${fmt(d.candidate_quality_index)}<span>Candidate Quality Index (CQI)</span></div><dl>${positions.map(x=>`<dt>${esc(x.label)}</dt><dd>${fmt(x.value)}</dd>`).join('')}</dl>`;renderConstellation();document.querySelector(`#candidateRows tr[data-id="${CSS.escape(d.canonical_candidate_id)}"]`)?.scrollIntoView({block:'nearest'})}
function renderRows(){const q=$('#candidateSearch').value.toLowerCase(),rows=DATA.cluster.members.filter(x=>x.party==='D'&&(!q||`${x.canonical_name} ${x.chamber} ${x.district}`.toLowerCase().includes(q))).sort((a,b)=>a.cycle-b.cycle||a.canonical_name.localeCompare(b.canonical_name));$('#candidateRows').innerHTML=rows.map(d=>`<tr data-id="${esc(d.canonical_candidate_id)}"><td>${esc(d.canonical_name)}</td><td>${d.cycle} ${String(d.chamber).toUpperCase()}-${d.district}</td><td>${esc(d.cluster_label.replace(' Democrats',''))}</td><td class="num">${fmt(d.candidate_quality_index)}</td><td class="num">${fmt(d.candidate_federal_overperformance)}</td><td class="num">${fmt(d.candidate_presidential_overperformance)}</td></tr>`).join('');document.querySelectorAll('#candidateRows tr').forEach(tr=>tr.onclick=()=>selectCandidate(DATA.cluster.members.find(x=>x.canonical_candidate_id===tr.dataset.id)))}
function renderMeasurementBridge(){const rows=DATA.measurementComparison;$('#measurementBridge').innerHTML=`<div class="measurement-row measurement-head"><b>Era</b><b>Shor–McCarty slope</b><b>Cluster separation</b><b>Implied cluster gap</b><b>Observed cluster gap</b></div>`+rows.map(r=>`<div class="measurement-row"><b>${eraLabel(r.era)}</b><span>${fmt(r.shor_cqi_per_sd)} CQI per SD</span><span>${r.cluster_shor_separation_sd.toFixed(2)} SD</span><span>${fmt(r.shor_implied_cluster_cqi_gap)} CQI</span><span>${fmt(r.observed_issue_cluster_cqi_gap)} CQI</span></div>`).join('')+`<p>Conversion: Shor–McCarty slope × observed distance between the two issue clusters = implied CQI gap. Coverage differs across the two measurements; the comparison is descriptive. Post-2016 Shor–McCarty coverage is insufficient for this conversion.</p>`}
function renderHeadline(){const rows=DATA.headlineBlocPerformance,all=rows.flatMap(r=>[r.ci_low,r.ci_high]).filter(Number.isFinite),limit=Math.max(10,Math.ceil(Math.max(...all.map(Math.abs))/5)*5),left=v=>5+90*(v+limit)/(2*limit),axis=`<div class="headline-axis"><span>Measure</span><div><span>Progressive-modern advantage</span><span>No difference</span><span>Traditionalist-populist advantage</span></div><span>Adjusted issue-cluster contrast</span></div>`;$('#headline').innerHTML=axis+rows.map(r=>{const leader=r.difference>=0?'Traditionalist-populist':'Progressive-modern',pointColor=r.difference>=0?COLORS[TRAD]:COLORS[PROG];return `<div class="headline-row"><h3>${esc(OUTCOMES[r.outcome])}</h3><div class="headline-track" role="img" aria-label="${esc(OUTCOMES[r.outcome])}: ${leader} advantage ${Math.abs(r.difference).toFixed(1)} CQI points between issue clusters, approximate 95 percent interval ${fmt(r.ci_low)} to ${fmt(r.ci_high)}"><i class="headline-ci" style="left:${left(r.ci_low)}%;width:${left(r.ci_high)-left(r.ci_low)}%;background:${pointColor}"></i><i class="headline-point" style="left:${left(r.difference)}%;background:${pointColor}"></i></div><div class="headline-values"><b>${leader} +${Math.abs(r.difference).toFixed(1)}</b><span>Signed issue-cluster difference ${fmt(r.difference)}; 95% interval ${fmt(r.ci_low)} to ${fmt(r.ci_high)}</span><small>Unit: outcome points between issue clusters · n=${r.n}; ${r.strata} cycle/chamber cells</small></div></div>`}).join('')}
function renderTransition(){const cycles=[...new Set(DATA.democraticTransition.map(x=>x.cycle))].sort((a,b)=>a-b),thin=[];$('#transitionChart').innerHTML=`<div class="transition-axis"><span></span><div><span>0%</span><span>50%</span><span>100%</span></div><span>sample</span></div>`+cycles.map(c=>{const rows=DATA.democraticTransition.filter(x=>x.cycle===c),total=rows.reduce((s,x)=>s+x.n,0);if(total<10)thin.push(`${c} (n=${total})`);return `<div class="transition-row ${total<10?'thin':''}"><strong>${c}</strong><div class="stack">${DEMOCRATIC_BLOCS.map(label=>{const r=rows.find(x=>x.cluster_label===label),n=r?.n||0;return `<button style="width:${total?100*n/total:0}%;background:${COLORS[label]}" aria-label="${label}, ${n} of ${total}" title="${label}: ${n} of ${total}"></button>`}).join('')}</div><small>n=${total}</small></div>`}).join('')+(thin.length?`<p class="sample-note">Low-coverage cycles: ${thin.join(', ')}. Their shares are descriptive and should not be read as stable caucus estimates.</p>`:'')}
function renderEra(){const outcome='candidate_quality_index',eras=['pre_2008','2008_2014','post_2016'],rows=eras.map(era=>({era,r:DATA.era.find(x=>x.sample===`D:${era}`&&x.outcome===outcome)})),bounds=rows.flatMap(x=>[x.r?.ci_low,x.r?.ci_high]).filter(Number.isFinite),limit=Math.max(5,Math.ceil(Math.max(...bounds.map(Math.abs),1)/2)*2),left=v=>5+90*(v+limit)/(2*limit);$('#eraEvidence').innerHTML=`<div class="forest-axis"><span>Era</span><div><span>More conservative associated with lower CQI</span><span>No association</span><span>More conservative associated with higher CQI</span></div><span>Estimate</span></div>`+rows.map(({era,r})=>{const available=r&&r.coefficient!=null;return `<div class="forest-row"><b>${eraLabel(era)}</b><div class="forest-track">${available?`<i class="forest-ci" style="left:${left(r.ci_low)}%;width:${left(r.ci_high)-left(r.ci_low)}%"></i><i class="forest-point" style="left:${left(r.coefficient)}%"></i>`:''}</div><div class="forest-value">${available?`<b>${fmt(r.coefficient)} CQI per 1 SD more conservative</b>95% CI ${fmt(r.ci_low)} to ${fmt(r.ci_high)}; n=${r.n}`:`<b>Not estimated</b>Only ${r?.n||0} observed candidate-cycles.`}</div></div>`}).join('')}
function labelInteractivePoints(){document.querySelectorAll('.performance-dot').forEach((dot,i)=>{const issue=dot.closest('#issuePlot'),context=issue?'issue-position chart':'candidate-performance chart';if(!dot.getAttribute('aria-label'))dot.setAttribute('aria-label',`Candidate observation ${i+1} in ${context}`);dot.type='button';dot.onclick=()=>{const target=$(issue?'#issuePointDetail':'#distributionDetail');if(target)target.textContent=dot.getAttribute('aria-label')}});document.querySelectorAll('#constellation .member').forEach((dot,i)=>{if(!dot.getAttribute('aria-label'))dot.setAttribute('aria-label',`Candidate observation ${i+1} in caucus similarity map`);dot.setAttribute('role','button')})}
function enableCandidateRows(){document.querySelectorAll('#candidateRows tr').forEach(tr=>{tr.tabIndex=0;tr.setAttribute('aria-label',`Open candidate details for ${tr.cells[0]?.textContent||'candidate'}`);tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();tr.click()}}})}
$('#distributionOutcome').onchange=()=>{renderDistribution();labelInteractivePoints()};$('#distributionEra').onchange=()=>{renderDistribution();labelInteractivePoints()};$('#issueSelect').onchange=()=>{renderIssue();labelInteractivePoints()};$('#issueOutcome').onchange=()=>{renderIssue();labelInteractivePoints()};$('#issueEra').onchange=()=>{renderIssue();labelInteractivePoints()};$('#candidateSearch').oninput=()=>{renderRows();enableCandidateRows()};
initIssues();renderHeadline();renderMeasurementBridge();renderTransition();renderProfile();renderDistribution();renderEra();renderIssue();renderCases();renderConstellation();renderRows();labelInteractivePoints();enableCandidateRows();
</script></body></html>'''.replace("__DATA__", data)


_build_unresponsive = build


def build() -> str:
    """Add headline and small-screen rules to the generated analysis page."""
    page = _build_unresponsive()
    page = page.replace(
        ".trad{background:var(--ox)}.prog{background:var(--blue-dark)}",
        ".trad{background:var(--ox)}.bridge{background:var(--gold)}.prog{background:var(--blue-dark)}",
    )
    page = page.replace(
        "This page compares two groupings found in the available issue-position records and measures how their candidates performed on the Candidate Quality Index, against same-cycle federal results, and against the previous presidential result.",
        "This page compares three groupings found in the available issue-position records and measures how their candidates performed on the Candidate Quality Index, against same-cycle federal results, and against the previous presidential result. The headline contrast compares the traditionalist and progressive endpoints; the bridge coalition remains separate.",
    )
    # The base template retains one superseded transition renderer for backward
    # compatibility; make both definitions use the current three-group fit.
    page = page.replace("${[TRAD,PROG].map(label=>", "${DEMOCRATIC_BLOCS.map(label=>")
    supplemental_css = (
        "<style>"
        ".headline-axis{display:grid;grid-template-columns:220px minmax(260px,1fr) 190px;"
        "gap:18px;padding:7px 0 10px;font-size:9px;color:var(--muted)}"
        ".headline-axis>div{display:flex;justify-content:space-between}"
        ".headline-axis>span:last-child{text-align:right}"
        ".headline-track,.forest-track{background:linear-gradient(90deg,#e5f1f7 0%,#fff 50%,#f5e8eb 100%)}"
        ".headline-values{display:flex;flex-direction:column;gap:1px}"
        ".headline-values small{color:var(--muted)}"
        ".headline-method{margin:0 20px 20px}"
        ".measurement-explainer{margin-top:22px}.measurement-explainer h3{font:bold 21px Georgia,serif;margin:0 0 12px}"
        ".measure-definitions{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line)}"
        ".measure-definitions>div{display:flex;flex-direction:column;gap:5px;background:#fff;padding:14px 16px}"
        ".measure-definitions span{font-size:11px;color:var(--muted)}.measure-definitions strong{font-size:11px;color:var(--ox)}"
        ".measurement-bridge{margin-top:10px;padding:10px 16px}.measurement-row{display:grid;grid-template-columns:1.05fr 1.35fr 1.1fr 1.2fr 1.2fr;gap:10px;padding:10px 0;border-top:1px solid #e2d9dc;font-size:11px}"
        ".measurement-row:first-child{border:0}.measurement-head{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}"
        ".measurement-bridge p{margin:10px 0 2px;padding-top:10px;border-top:1px solid var(--line);font-size:11px;color:var(--muted)}"
        ".forest-axis{display:grid;grid-template-columns:150px minmax(220px,1fr) 175px;"
        "gap:14px;padding:7px 0 10px;font-size:9px;color:var(--muted)}"
        ".forest-axis>div{display:flex;justify-content:space-between;gap:12px;text-align:center}"
        ".forest-axis>span:last-child{text-align:right}"
        "@media(max-width:780px){.headline-axis,.forest-axis{display:none}.headline-method{margin:0 12px 15px}.measure-definitions{grid-template-columns:1fr}.measurement-row{grid-template-columns:1fr 1fr}.measurement-head{display:none}.measurement-row span:before{display:block;font-size:8px;color:var(--muted)}}"
        "@media(max-width:520px){"
        ".distribution{margin-left:14px;margin-right:14px}"
        ".distribution .lane{left:6px;width:auto;max-width:calc(100% - 12px);"
        "padding:2px 4px;background:rgba(255,255,255,.88);text-align:left;z-index:3}"
        "}</style>"
    )
    return page.replace("</head>", supplemental_css + "</head>", 1)


# The maintained page was rebuilt around the current three-group clustering
# contract.  Keep this module as the stable entry point used by the site build
# and older tooling, but route every public call to the clean implementation.
try:
    from scripts.build_democratic_transition_page_v2 import (
        OUTPUT as _CURRENT_OUTPUT,
        build as _current_build,
        main as _current_main,
        payload as _current_payload,
    )
except ModuleNotFoundError:
    from build_democratic_transition_page_v2 import (
        OUTPUT as _CURRENT_OUTPUT,
        build as _current_build,
        main as _current_main,
        payload as _current_payload,
    )

OUTPUT = _CURRENT_OUTPUT
build = _current_build
payload = _current_payload


def main() -> None:
    _current_main()


if __name__ == "__main__":
    main()
