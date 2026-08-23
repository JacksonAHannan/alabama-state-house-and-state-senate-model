import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT=Path(__file__).resolve().parents[2]; CAL=ROOT/'data/processed/forecast_calibration'
def load(n): return pd.read_csv(CAL/n,low_memory=False)

def test_panel_and_pre_election_features_are_temporally_valid():
 p=load('robust_forecast_v1_panel.csv'); assert len(p)==1188; assert not p.duplicated(['state','year','chamber','district']).any()
 assert p.loc[p.year.eq(2024),'incumbency_model_ready'].sum()==323; assert p.loc[p.year.eq(2024)&~p.incumbency_model_ready.astype(bool),'incumbency_balance'].isna().all()
 assert p.loc[p.year.eq(2018),'prior_quality_available'].eq(0).all(); assert p.loc[p.prior_quality_available.eq(0),'prior_quality_differential'].eq(0).all()

def test_forward_predictions_and_selection():
 x=load('robust_forecast_v1_predictions.csv'); assert x.train_max_year.lt(x.year).all(); assert set(x.year)=={2020,2022,2024}
 r=load('robust_forecast_v1_ranking.csv'); assert r.selected.sum()==1; assert r.loc[r.selected,'model'].iloc[0]=='baseline'; assert not r.loc[r.model.ne('baseline'),'guardrail_pass'].any()

def test_probability_and_error_components():
 x=load('robust_forecast_v1_calibrated_predictions.csv'); assert len(x)==893; assert x.probability.between(0,1).all()
 m=json.loads((CAL/'robust_forecast_v1_manifest.json').read_text()); assert m['selected_probability']=={'family':'student_t','scale':5.75,'df':5.0}
 c=load('robust_forecast_v1_error_components.csv').iloc[0]; assert (c[['national_sd','state_sd','chamber_sd','district_sd']]>0).all(); assert c.district_sd<c.total_residual_sd

def test_manifest_declares_prospective_scenario_and_code_inputs():
 m=json.loads((CAL/'robust_forecast_v1_manifest.json').read_text()); paths={x['path'] for x in m['inputs']}; code={x['path'] for x in m['code_inputs']}
 required={
  'data/processed/war/2026_final_candidate_roster.csv',
  'data/processed/presidential/2026_district_presidential_features.csv',
  'data/processed/presidential/2022_district_presidential_features.csv',
  'data/processed/demographics/2026_sld_demographics.csv',
  'data/processed/war/2026_candidate_incumbency.csv',
  'data/processed/war/2026_poll_adjusted_baseline.csv',
  'data/processed/war/2026_state_candidate_finance_matches.csv',
  'data/processed/polling/votehub_silver_bplus_topline_environment.csv',
  'data/processed/polling/catalist_national_demographic_master.csv',
 }
 assert required<=paths
 assert {'scripts/run_robust_forecast_pipeline.py','scripts/run_forecast_experiment_tournament.py','scripts/fit_2026_prospective_model.py','scripts/build_southern_2024_incumbency.py'}<=code
 assert m['configuration']['seed']==20260822; assert m['configuration']['simulation_draws']==50000
 assert m['configuration']['forward_test_years']==[2020,2022,2024]
 assert m['configuration']['probability_grid']['student_t']['degrees_of_freedom']==[3,5,8]
 assert m['configuration']['selection_guardrails']['minimum_cycles_improved']==2
 assert m['status']=='validated_public_forecast'
 assert m['methodology_version']=='robust_forecast_v1_reconciled'
 assert set(m['configuration']['scenario_definitions'])=={'headline','environment_dem_favorable','environment_rep_favorable'}
 for item in [*m['inputs'],*m['code_inputs'],*m['outputs']]: assert len(item['sha256'])==64

def test_subgroups_finance_and_scenarios_are_explicit():
 g=load('robust_forecast_v1_subgroup_audit.csv'); assert set(g.dimension)=={'state','chamber','margin_band','incumbency_group','demographic_type'}; assert g.races.gt(0).all()
 f=load('robust_forecast_v1_finance_gate.csv').iloc[0]; assert not bool(f.eligible); assert f.coverage==0
 s=load('robust_forecast_v1_2026_scenarios.csv'); assert len(s)==144; assert set(s.scenario)=={'headline','environment_dem_favorable','environment_rep_favorable'}
 h=s[s.scenario.eq('headline')]; np.testing.assert_allclose(h.predicted_dem_margin,h.environment_baseline_margin)

def test_full_uncertainty_simulation_is_deterministic_and_normalized():
 d=load('robust_forecast_v1_2026_full_uncertainty.csv'); assert len(d)==48; assert d.draws.eq(50000).all(); assert d.full_uncertainty_dem_probability.between(0,1).all(); assert (d.margin_95_low<=d.margin_80_low).all(); assert (d.margin_95_high>=d.margin_80_high).all()
 seats=load('robust_forecast_v1_2026_modeled_seats.csv'); sums=seats.groupby('chamber').probability.sum(); np.testing.assert_allclose(sums,1,atol=1e-12)
