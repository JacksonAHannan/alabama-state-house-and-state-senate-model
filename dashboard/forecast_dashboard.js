(() => {
  "use strict";
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const params = new URLSearchParams(location.search);
  const PUBLIC_MODEL=DATA.meta.model;
  const STATEWIDE_VIEWBOX={x:0,y:0,width:650,height:710};
  const state = { chamber: params.get("chamber")||"house", model: params.get("model")||PUBLIC_MODEL, mode: params.get("mode")||"probability", selected: +(params.get("district")||0)||null, sort: "closeness", asc: true };
  const chamberName = c => c === "house" ? "State House" : "State Senate";
  const districtName = (c,d) => `${c === "house" ? "HD" : "SD"}-${d}`;
  const partyName = p => ({D:"Democratic",R:"Republican",I:"Independent"}[p] || p);
  const fmtMargin = v => v == null || Number.isNaN(+v) ? "—" : `${+v >= 0 ? "D+" : "R+"}${Math.abs(+v).toFixed(1)}`;
  const fmtMoney = (v,status) => {
    if (v != null) return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(v);
    if (status === "no_state_entry_zero_assumption_sensitivity_only") return "$0 state entry (assumption)";
    if (status === "unmatched") return "Not matched";
    return "Not available";
  };
  const mix = (a,b,t) => {
    const A=a.match(/\w\w/g).map(x=>parseInt(x,16)), B=b.match(/\w\w/g).map(x=>parseInt(x,16));
    return "#"+A.map((x,i)=>Math.round(x+(B[i]-x)*t).toString(16).padStart(2,"0")).join("");
  };
  const race = (c,d) => DATA[c].races.find(r => r.district === +d);
  const effectiveRating = r => r.status === "unopposed-major-party" ? `Unopposed ${r.demProbability === 1 ? "D" : "R"}` : r.rating;
  const competitive = r => r.status === "modeled" && r.demProbability >= .35 && r.demProbability <= .65;
  const intervalCrosses = r => r.low80 != null && r.low80 <= 0 && r.high80 >= 0;
  const leader = r => r.demProbability == null ? null : r.demProbability >= .5 ? "D" : "R";
  const variableLabels = {
    model_intercept_and_chamber:"Model intercept and chamber context",dem_incumbent_i:"Democratic incumbent",
    rep_incumbent_i:"Republican incumbent",finance_ratio_capped:"Fundraising ratio (capped)",
    ftm_finance_complete:"Both parties have matched finance records",open_seat:"Open seat",
    finance_x_open:"Fundraising × open seat",finance_x_dem_inc:"Fundraising × Democratic incumbent",
    finance_x_rep_inc:"Fundraising × Republican incumbent",nonwhite_share:"Nonwhite population share",
    white_college_share:"White college-graduate share",ramp_x_nonwhite:"Environment × nonwhite share",
    ramp_x_white_college:"Environment × white college share",prior_pres_swing_filled:"Previous presidential swing",
    trend_available:"Previous swing available",post2008:"After the 2008 realignment",
    post2016:"After the 2016 realignment",years_since_2008:"Years since 2008",years_since_2016:"Years since 2016"
  };
  const variableGroups={
    model_intercept_and_chamber:"Model context",dem_incumbent_i:"Incumbency",rep_incumbent_i:"Incumbency",
    finance_ratio_capped:"Fundraising",ftm_finance_complete:"Fundraising",open_seat:"Incumbency",
    finance_x_open:"Fundraising",finance_x_dem_inc:"Fundraising",finance_x_rep_inc:"Fundraising",
    nonwhite_share:"Demographics",white_college_share:"Demographics",ramp_x_nonwhite:"Demographics",
    ramp_x_white_college:"Demographics",prior_pres_swing_filled:"Presidential trend",trend_available:"Presidential trend",
    post2008:"Realignment and time",post2016:"Realignment and time",years_since_2008:"Realignment and time",years_since_2016:"Realignment and time"
  };
  const fmtEffect=v=>Math.abs(v)<.005?"<0.01":`${v>=0?"D+":"R+"}${Math.abs(v).toFixed(2)}`;
  function fmtValue(name,value){
    if(value==null) return "Missing; historical median used";
    if(["nonwhite_share","white_college_share"].includes(name)) return `${(100*value).toFixed(1)}%`;
    if(["dem_incumbent_i","rep_incumbent_i","ftm_finance_complete","open_seat","trend_available","post2008","post2016"].includes(name)) return +value?"Yes":"No";
    if(name==="finance_ratio_capped") return `${Math.exp(value).toFixed(2)}× D-to-R receipts`;
    if(name.startsWith("years_since_")) return `${Math.round(value)} years`;
    if(typeof value==="number") return Math.abs(value)>=10?value.toFixed(1):value.toFixed(3);
    return value;
  }
  const publicVersion=r=>r.models?.[PUBLIC_MODEL];
  const selectedVersion=r=>r.models?.[state.model];
  const contributionSteps=r=>(selectedVersion(r)?.steps||[]).map((s,i)=>({variable:DATA.contributionVariables[i],value:s[0],effect:s[1],runningMargin:s[2]}));
  const modelDelta=r=>selectedVersion(r)&&publicVersion(r)?selectedVersion(r).margin-publicVersion(r).margin:null;
  const winnerFor=m=>m==null?null:m>=0?"D":"R";
  const winnerDisagreement=r=>r.status==="modeled"&&new Set(Object.values(r.models).map(m=>winnerFor(m.margin))).size>1;
  const ratingDisagreement=r=>r.status==="modeled"&&new Set(Object.values(r.models).map(m=>ratingForProbability(m.demProbability))).size>1;
  function syncUrl(){
    const q=new URLSearchParams({model:state.model,chamber:state.chamber,mode:state.mode});
    if(state.selected) q.set("district",state.selected);
    history.replaceState(null,"",`${location.pathname}?${q}${location.hash}`);
  }

  function applyModel(){
    for(const c of ["house","senate"]){
      DATA[c].seatDistribution=DATA[c].modelSeatDistributions[state.model];
      for(const r of DATA[c].races){
        const m=r.models?.[state.model]; if(!m) continue;
        r.margin=m.margin; r.demProbability=m.demProbability; r.low80=m.low80; r.high80=m.high80; r.rating=ratingForProbability(m.demProbability);
      }
    }
    $("#workspace")?.setAttribute("aria-labelledby",`model-tab-${state.model}`);
  }
  const ratingForProbability=p=>{const lead=p>=.5?"D":"R",q=Math.max(p,1-p);return q<.55?"Toss-up":q<.70?`Lean ${lead}`:q<.90?`Likely ${lead}`:`Solid ${lead}`};
  const RATING_COLORS={"Solid D":"#397fb9","Likely D":"#70a3c8","Lean D":"#accadd","Toss-up":"#d7d0c7","Lean R":"#e4b0aa","Likely R":"#d77b74","Solid R":"#c94e4e"};
  const probabilityColor=p=>p<.20?"#c94e4e":p<.40?"#e4b0aa":p<.60?"#ebe5dc":p<.80?"#accadd":"#397fb9";

  function renderModelTabs(){
    $("#modelTabs").innerHTML=DATA.models.map((m,i)=>`<button role="tab" id="model-tab-${m.id}" data-model="${m.id}" aria-controls="workspace" tabindex="${m.id===state.model?0:-1}" aria-selected="${m.id===state.model}">${m.label}<small>${m.status}</small></button>`).join("");
    const m=DATA.models.find(x=>x.id===state.model);
    $("#modelDescription").innerHTML=`<b>${m.status}.</b> ${m.description}`;
    $("#modelScores").innerHTML=`<span><b>${m.meanMae.toFixed(2)}</b>All-cycle MAE</span><span><b>${m.recentMae.toFixed(2)}</b>2018–22 MAE</span><span><b>${m.latestMae.toFixed(2)}</b>2022 MAE</span>`;
    const tabs=$$('[data-model]');
    tabs.forEach((b,i)=>{b.addEventListener("click",()=>selectModel(b.dataset.model));b.addEventListener("keydown",e=>{if(!["ArrowLeft","ArrowRight","Home","End"].includes(e.key))return;e.preventDefault();let n=e.key==="Home"?0:e.key==="End"?tabs.length-1:(i+(e.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;tabs[n].focus();selectModel(tabs[n].dataset.model)})});
  }
  function selectModel(model){state.model=model;applyModel();syncUrl();renderAll();renderModelTabs()}

  function validatePayload(){
    const issues=[];
    for(const c of ["house","senate"]){
      if(!DATA[c] || !Array.isArray(DATA[c].races) || !Array.isArray(DATA[c].paths)) issues.push(`${c} payload missing`);
      else if(DATA[c].races.length !== (c === "house" ? 105 : 35)) issues.push(`${c} district count is invalid`);
    }
    if(issues.length) throw new Error(issues.join("; "));
  }

  function closestRace(c){
    return [...DATA[c].races].filter(r=>r.status==="modeled").sort((a,b)=>Math.abs(a.margin)-Math.abs(b.margin))[0];
  }

  function seatStats(c){
    const dist=DATA[c].seatDistribution;
    const mean=dist.reduce((s,x)=>s+x.demSeats*x.probability,0);
    const quantile=q=>{let s=0;for(const x of dist){s+=x.probability;if(s>=q)return x.demSeats}return dist.at(-1).demSeats};
    const mode=[...dist].sort((a,b)=>b.probability-a.probability)[0].demSeats;
    const total=c==="house"?105:35;
    const unknown=DATA[c].races.filter(r=>r.demProbability==null).length;
    const majority=Math.floor(total/2)+1,control=dist.filter(x=>x.demSeats>=majority).reduce((s,x)=>s+x.probability,0);
    const publicDist=DATA[c].modelSeatDistributions[PUBLIC_MODEL],publicMedian=(()=>{let s=0;for(const x of publicDist){s+=x.probability;if(s>=.5)return x.demSeats}})();
    return {mean,median:quantile(.5),low:quantile(.1),high:quantile(.9),mode,total,repMedian:total-quantile(.5)-unknown,competitive:DATA[c].races.filter(competitive).length,disagreements:DATA[c].races.filter(winnerDisagreement).length,unknown,control,publicMedian,majority};
  }

  function renderOverview(){
    $("#overviewGrid").innerHTML=["house","senate"].map(c=>{
      const s=seatStats(c), modeled=DATA[c].races.filter(r=>r.status==="modeled").length;
      return `<button class="overview-card" data-overview="${c}" aria-pressed="${state.chamber===c}">
        <div class="overview-title"><h2>${chamberName(c)}</h2><span>${s.total} seats</span></div>
        <div class="overview-stats">
          <div class="overview-stat"><b style="color:var(--blue)">${s.median}</b><span>Median Democratic seats</span></div>
          <div class="overview-stat"><b style="color:var(--red)">${s.repMedian}</b><span>Projected Republican seats${s.unknown?"*":""}</span></div>
          <div class="overview-stat range"><b>${s.low}–${s.high}</b><span>Democratic 80% range</span></div>
        </div>
        <div class="seatbar" aria-hidden="true"><div class="d" style="width:${100*s.median/s.total}%"></div><div class="u" style="width:${100*s.unknown/s.total}%"></div><div class="r" style="width:${100*(s.total-s.median-s.unknown)/s.total}%"></div><i class="majority-mark" style="left:${100*(Math.floor(s.total/2)+1)/s.total}%"></i></div>
        <div class="overview-foot">${modeled} D–R forecasts · ${s.competitive} competitive · ${s.disagreements} winner disagreements · ${s.control<.001?"<0.1":(100*s.control).toFixed(1)}% D-control chance${state.model!==PUBLIC_MODEL?` · ${s.median-s.publicMedian>=0?"+":""}${s.median-s.publicMedian} median D seats vs Basic`:""}${s.unknown?` · ${s.unknown} unmodeled`:""}</div>
      </button>`;
    }).join("");
    $$('[data-overview]').forEach(b=>b.addEventListener("click",()=>selectChamber(b.dataset.overview,true)));
  }

  function renderDistribution(){
    const dist=DATA[state.chamber].seatDistribution, max=Math.max(...dist.map(x=>x.probability)), mode=Math.max(...dist.map(x=>x.probability));
    $("#distribution").innerHTML=dist.map(x=>`<i class="${x.probability===mode?'mode':''}" style="height:${Math.max(2,52*x.probability/max)}px" title="${x.demSeats} Democratic seats: ${(100*x.probability).toFixed(1)}%"></i>`).join("");
    $("#distributionAxis").innerHTML=`<span>${dist[0].demSeats} D seats</span><span>${dist.at(-1).demSeats} D seats</span>`;
  }

  function renderChamberStrip(){
    const s=seatStats(state.chamber);
    $("#medianSeats").textContent=s.median;
    $("#seatRange").textContent=`${s.low}–${s.high}`;
    $("#chamberTitle").textContent=`Explore the ${chamberName(state.chamber)}`;
    $("#mapTitle").textContent=`Alabama ${chamberName(state.chamber)}`;
    renderDistribution();
  }

  function mapColor(r){
    if(r.demProbability==null) return "#aaa39a";
    if(r.status==="unopposed-major-party") return r.demProbability===1 ? "#397fb9" : "#c94e4e";
    if(state.mode==="rating") return RATING_COLORS[effectiveRating(r)]||"#aaa39a";
    if(state.mode==="probability") return probabilityColor(r.demProbability);
    const value=r.margin;
    const t=Math.min(1,Math.abs(value)/30);
    return value>=0?mix("#ebe5dc","#397fb9",t):mix("#ebe5dc","#c94e4e",t);
  }

  function legend(){
    const sw=(color,label,pattern="")=>`<i style="background:${color};${pattern}"></i>${label}`;
    if(state.mode==="rating") return [sw("#397fb9","Solid D"),sw("#70a3c8","Likely D"),sw("#accadd","Lean D"),sw("#d7d0c7","Toss-up"),sw("#e4b0aa","Lean R"),sw("#d77b74","Likely R"),sw("#c94e4e","Solid R"),sw("#aaa39a","Unmodeled","background-image:repeating-linear-gradient(45deg,#aaa 0 2px,#ddd 2px 4px)")].join("");
    if(state.mode==="margin") return [sw("#c94e4e","R+20"),sw("#e4b0aa","R+10"),sw("#ebe5dc","Even"),sw("#accadd","D+10"),sw("#397fb9","D+20"),sw("#aaa39a","Unmodeled")].join("");
    return [sw("#c94e4e","D chance <20%"),sw("#e4b0aa","20–40%"),sw("#ebe5dc","40–60%"),sw("#accadd","60–80%"),sw("#397fb9",">80%"),sw("#aaa39a","Unmodeled")].join("");
  }

  function tooltipText(r){
    const cand=r.candidates.map(c=>c.name).join(" vs. ")||"No candidates listed";
    const prob=r.demProbability==null?"Not modeled":`${Math.round(100*Math.max(r.demProbability,1-r.demProbability))}% ${partyName(leader(r))} win chance`;
    return `${districtName(state.chamber,r.district)} · ${effectiveRating(r)}\n${cand}\n${fmtMargin(r.margin)} · ${prob}`;
  }

  function renderMap(){
    const svg=$("#map"), races=DATA[state.chamber].races;
    svg.setAttribute("aria-label",`${chamberName(state.chamber)} district forecast map. Use Tab to move through districts and Enter to select.`);
    svg.innerHTML=DATA[state.chamber].paths.map(p=>{
      const r=races.find(x=>x.district===p.district), label=`${districtName(state.chamber,p.district)}, ${effectiveRating(r)}, ${fmtMargin(r.margin)}`;
      return `<path class="district ${state.selected===p.district?'selected':''} ${r.demProbability==null?'unmodeled':''}" data-district="${p.district}" fill="${mapColor(r)}" d="${p.path}" role="button" tabindex="0" aria-label="${label}"><title>${label}</title></path>`;
    }).join("");
    $$(".district").forEach(el=>{
      const select=()=>selectDistrict(+el.dataset.district,true);
      el.addEventListener("click",select);
      el.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();select()}});
      el.addEventListener("mousemove",e=>showTooltip(e,race(state.chamber,el.dataset.district)));
      el.addEventListener("mouseleave",hideTooltip);
    });
    updateMapViewport();
    $("#legend").innerHTML=legend();
  }

  function updateMapViewport(){
    const svg=$("#map");
    if(!state.selected){
      svg.setAttribute("viewBox",`${STATEWIDE_VIEWBOX.x} ${STATEWIDE_VIEWBOX.y} ${STATEWIDE_VIEWBOX.width} ${STATEWIDE_VIEWBOX.height}`);
      return;
    }
    const district=svg.querySelector(`.district[data-district="${state.selected}"]`);
    if(!district) return;
    const box=district.getBBox(), padding=Math.max(box.width,box.height)*.18+6;
    let x=box.x-padding, y=box.y-padding, width=box.width+2*padding, height=box.height+2*padding;
    const targetRatio=STATEWIDE_VIEWBOX.width/STATEWIDE_VIEWBOX.height, ratio=width/height;
    if(ratio>targetRatio){const expanded=width/targetRatio;y-=(expanded-height)/2;height=expanded}
    else{const expanded=height*targetRatio;x-=(expanded-width)/2;width=expanded}
    svg.setAttribute("viewBox",`${x} ${y} ${width} ${height}`);
  }

  function showTooltip(e,r){const t=$("#tooltip");t.style.display="block";t.style.left=Math.min(innerWidth-255,e.clientX+12)+"px";t.style.top=Math.min(innerHeight-90,e.clientY+12)+"px";t.textContent=tooltipText(r)}
  function hideTooltip(){ $("#tooltip").style.display="none"; }

  function candidateHtml(c){
    return `<div class="candidate"><i class="stripe ${c.party}" aria-hidden="true"></i><div><b>${c.name}</b><small>${partyName(c.party)}${c.incumbent?" · Incumbent":" · Non-incumbent"}</small></div><div class="finance-values"><small>${fmtMoney(c.raised,c.financeStatus)} raised<br>${fmtMoney(c.spent,c.financeStatus)} spent</small></div></div>`;
  }

  function uncertaintyHtml(r){
    const bound=Math.max(40,Math.ceil(Math.max(Math.abs(r.low80),Math.abs(r.high80))/10)*10), pct=v=>100*(v+bound)/(2*bound);
    return `<div class="uncertainty"><div class="uncertainty-title">Forecast margin and 80% predictive interval</div><div class="interval-chart" aria-label="Forecast ${fmtMargin(r.margin)}, middle 80 percent from ${fmtMargin(r.low80)} to ${fmtMargin(r.high80)}">
      <div class="interval-axis"></div><i class="interval-even" style="left:50%"></i>
      <span class="interval-band" style="left:${pct(r.low80)}%;width:${pct(r.high80)-pct(r.low80)}%"></span>
      <i class="interval-dot" style="left:${pct(r.margin)}%"></i>
      <span class="interval-end" style="left:${pct(r.low80)}%">${fmtMargin(r.low80)}</span><span class="interval-end" style="left:${pct(r.high80)}%">${fmtMargin(r.high80)}</span>
    </div><div class="interval-caption">The band is the middle 80% conditional predictive interval from the recent Southern calibration. Scale: R+${bound} to D+${bound}; the center line is an even race.</div></div>`;
  }

  function renderDetail(r){
    if(!r){
      $("#detail").innerHTML=`<div class="race-kicker">District explorer</div><div class="race-title">Select a district</div><p>Choose a district on the statewide map, from the district finder, or from the table below to zoom into its geography and open the race forecast.</p>`;
      return;
    }
    const lead=leader(r), leadProb=lead ? Math.max(r.demProbability,1-r.demProbability) : null;
    const bg=lead==="D"?"var(--blue)":lead==="R"?"var(--red)":"var(--gray)";
    const headline=r.status==="modeled"?`<div class="headline-call"><strong>${fmtMargin(r.margin)}</strong><span>${partyName(lead)} nominee favored · ${Math.round(100*leadProb)}% win probability</span></div>`:`<div class="headline-call"><strong>${effectiveRating(r)}</strong><span>${r.status==="unopposed-major-party"?"Single major-party nominee; independent contests are not modeled":"No two-party forecast available"}</span></div>`;
    const selectedModel=DATA.models.find(x=>x.id===state.model), steps=contributionSteps(r),pub=publicVersion(r),delta=modelDelta(r);
    const grouped=[];for(const s of steps){const name=variableGroups[s.variable]||"Other";let g=grouped.find(x=>x.name===name);if(!g){g={name,effect:0,items:[]};grouped.push(g)}g.effect+=s.effect;g.items.push(s)}
    let running=r.pollBaseline;const maxGroup=Math.max(1,...grouped.map(g=>Math.abs(g.effect)));
    const groupRows=grouped.map(g=>{running+=g.effect;return `<div class="metric contribution group"><span>${g.name}<small>${g.items.length} model term${g.items.length===1?"":"s"}</small><i class="effect-track" aria-hidden="true"><i class="${g.effect>=0?"d":"r"}" style="width:${100*Math.abs(g.effect)/maxGroup}%"></i></i></span><b>${fmtEffect(g.effect)}<small>→ ${fmtMargin(running)}</small></b></div>`}).join("");
    const technical=steps.map(s=>`<div class="metric contribution"><span>${variableLabels[s.variable]||s.variable}<small>${fmtValue(s.variable,s.value)}</small></span><b>${fmtEffect(s.effect)}<small>→ ${fmtMargin(s.runningMargin)}</small></b></div>`).join("");
    const compare=state.model===PUBLIC_MODEL?`<div class="comparison-call"><b>Basic model</b><span>Transparent default and guardrail for every richer specification.</span></div>`:`<div class="comparison-call ${winnerFor(r.margin)!==winnerFor(pub.margin)?"warning":""}"><b>${fmtEffect(delta)} vs Basic</b><span>Basic: ${fmtMargin(pub.margin)}${winnerFor(r.margin)!==winnerFor(pub.margin)?" · Models disagree on the favored party":""}</span></div>`;
    const financeComplete=r.candidates.filter(c=>["D","R"].includes(c.party)).every(c=>c.financeStatus==="observed");
    const model=r.status==="modeled"?`<div class="decomp"><h4>${selectedModel.label} forecast</h4>
      ${compare}<div class="data-badges"><span>${financeComplete?"Complete matched finance":"Incomplete finance data"}</span><span>${winnerDisagreement(r)?"Models disagree on winner":"Models agree on winner"}</span></div>
      <div class="metric"><span>2024 presidential margin</span><b>${fmtMargin(r.pres24)}</b></div>
      <div class="metric"><span>2026 environment change</span><b>${fmtEffect(r.environmentAdjustment)}</b></div>
      <div class="metric"><span>Basic forecast</span><b>${fmtMargin(r.pollBaseline)}</b></div>
      ${groupRows||'<div class="metric"><span>Additional model adjustment</span><b>None</b></div>'}
      <div class="metric total"><span>Selected model forecast</span><b>${fmtMargin(r.margin)}</b></div>
      ${steps.length?`<details class="technical-terms"><summary>Technical variable detail (${steps.length} terms)</summary>${technical}<small>These are exact sequential contribution estimates in the fixed order shown. For nonlinear models, changing the order can change individual attributions even though the final forecast is unchanged.</small></details>`:""}
      ${state.model===PUBLIC_MODEL?"":`<div class="scenario-box"><small>Fundamentals+ incorporates candidate and district information, but it did not beat Basic in the 2022 holdout and therefore remains experimental.</small></div>`}${uncertaintyHtml(r)}<div class="source-note"><b>Data provenance</b><span>Election baseline, polling, ACS demographics, regional context, certified candidates, candidate history, and Alabama finance filings. Dates and downloads appear in the source ledger below.</span></div></div>`:"";
    const ordered=[...DATA[state.chamber].races].filter(x=>x.status==="modeled").sort((a,b)=>Math.abs(a.margin)-Math.abs(b.margin)), pos=ordered.findIndex(x=>x.district===r.district);
    const prev=ordered[(pos-1+ordered.length)%ordered.length], next=ordered[(pos+1)%ordered.length];
    $("#detail").innerHTML=`<div class="race-kicker">2026 general election</div><div class="race-title">${chamberName(state.chamber)} District ${r.district}</div><button class="share-link small-button" id="shareRace">Copy link</button><span class="rating" style="background:${bg}">${effectiveRating(r)}</span>${headline}<div>${r.candidates.map(candidateHtml).join("")||"<p>No certified candidate listed.</p>"}</div>${model}<div class="race-nav"><button class="small-button" data-race-nav="${prev?.district||r.district}">← Closer race</button><button class="small-button" data-race-nav="${next?.district||r.district}">Next race →</button></div>`;
    $$('[data-race-nav]').forEach(b=>b.addEventListener("click",()=>selectDistrict(+b.dataset.raceNav,true)));
    $("#shareRace")?.addEventListener("click",async e=>{syncUrl();try{await navigator.clipboard.writeText(location.href);e.currentTarget.textContent="Link copied"}catch{e.currentTarget.textContent="Use address bar to copy"}});
  }

  function populateDistrictSelect(){
    $("#districtSelect").innerHTML=`<option value="">Statewide view</option>`+DATA[state.chamber].races.map(r=>`<option value="${r.district}">${districtName(state.chamber,r.district)} · ${effectiveRating(r)}</option>`).join("");
    $("#districtSelect").value=state.selected?String(state.selected):"";
  }

  function selectDistrict(d,scroll=false){
    state.selected=+d; syncUrl(); renderMap(); renderDetail(race(state.chamber,d)); renderTable(); $("#districtSelect").value=String(d);
    if(scroll && innerWidth<851) $("#detail").scrollIntoView({behavior:"smooth",block:"start"});
  }

  function clearDistrict(){
    state.selected=null;syncUrl();renderMap();renderDetail(null);renderTable();$("#districtSelect").value="";
  }

  function selectChamber(c,scroll=false){
    state.chamber=c;state.selected=null;syncUrl();
    $$('[data-chamber]').forEach(b=>b.setAttribute("aria-pressed",b.dataset.chamber===c));
    renderAll();
    if(scroll) $("#workspace").scrollIntoView({behavior:"smooth"});
  }

  function tableRows(){
    let rows=[...DATA[state.chamber].races], q=$("#search").value.trim().toLowerCase(), rating=$("#ratingFilter").value, scope=$("#scopeFilter").value;
    if(q) rows=rows.filter(r=>`${r.district} ${r.candidates.map(c=>c.name).join(" ")}`.toLowerCase().includes(q));
    if(rating!=="all") rows=rows.filter(r=>effectiveRating(r)===rating);
    if(scope==="competitive") rows=rows.filter(competitive);
    if(scope==="modeled") rows=rows.filter(r=>r.status==="modeled");
    if(scope==="open") rows=rows.filter(r=>!r.candidates.some(c=>c.incumbent));
    if(scope==="crosses") rows=rows.filter(intervalCrosses);
    if(scope==="winner-disagreement") rows=rows.filter(winnerDisagreement);
    if(scope==="rating-disagreement") rows=rows.filter(ratingDisagreement);
    const value=(r,k)=>k==="rating"?effectiveRating(r):k==="closeness"?(r.margin==null?999:Math.abs(r.margin)):r[k];
    rows.sort((a,b)=>{let x=value(a,state.sort),y=value(b,state.sort);x=x??-999;y=y??-999;return (x>y?1:x<y?-1:0)*(state.asc?1:-1)});
    return rows;
  }

  function renderTable(){
    const rows=tableRows();
    $("#rows").innerHTML=rows.map(r=>{const d=modelDelta(r),selected=selectedVersion(r),publicM=publicVersion(r);return `<tr data-district="${r.district}" tabindex="0" class="${state.selected===r.district?'selected':''}" aria-label="Open ${districtName(state.chamber,r.district)} details">
      <td>${districtName(state.chamber,r.district)}</td><td>${r.candidates.map(c=>`<span class="party-dot" style="background:${c.party==='D'?'var(--blue)':c.party==='R'?'var(--red)':'#766d61'}"></span>${c.name} (${c.party})`).join("<br>")||"—"}</td>
      <td>${effectiveRating(r)}${winnerDisagreement(r)?'<small class="disagreement">Winner disagreement</small>':ratingDisagreement(r)?'<small class="disagreement">Rating disagreement</small>':''}</td><td>${r.status==="unopposed-major-party"?"Unopposed":r.demProbability==null?"—":Math.round(100*r.demProbability)+"%"}</td><td>${fmtMargin(r.margin)}</td><td>${state.model===PUBLIC_MODEL?"Public":d==null?"—":fmtEffect(d)}</td><td>${r.low80==null?"—":`${fmtMargin(r.low80)} to ${fmtMargin(r.high80)}`}</td></tr>`}).join("");
    $$("#rows tr").forEach(tr=>{const open=()=>selectDistrict(+tr.dataset.district,true);tr.addEventListener("click",open);tr.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();open()}})});
    $("#rowCount").textContent=`${rows.length} districts shown for ${DATA.models.find(m=>m.id===state.model).label}`;
    $$('th button[data-sort]').forEach(b=>{const th=b.closest("th"),active=state.sort===b.dataset.sort;th.setAttribute("aria-sort",active?(state.asc?"ascending":"descending"):"none");b.querySelector("span").textContent=active?(state.asc?" ↑":" ↓"):""});
  }

  function downloadCsv(){
    const header=["selected_model","chamber","district","candidates","rating","dem_win_probability","forecast_margin","basic_model_margin","difference_from_basic","margin_80_low","margin_80_high","models_disagree_on_winner"];
    const esc=v=>`"${String(v??"").replaceAll('"','""')}"`;
    const body=DATA[state.chamber].races.map(r=>[state.model,state.chamber,r.district,r.candidates.map(c=>`${c.name} (${c.party})`).join("; "),effectiveRating(r),r.demProbability,r.margin,publicVersion(r)?.margin,modelDelta(r),r.low80,r.high80,winnerDisagreement(r)].map(esc).join(","));
    const blob=new Blob([[header.join(","),...body].join("\n")],{type:"text/csv"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=`alabama_2026_${state.chamber}_forecast.csv`;a.click();URL.revokeObjectURL(a.href);
  }

  function renderProvenance(){
    const el=$("#sourceLedger");if(!el)return;
    el.innerHTML=DATA.provenance.map(s=>`<article><b>${s.category}</b><span>${s.source}</span><small>Through ${s.asOf}</small><a href="${s.download}" download>Download supporting data</a></article>`).join("");
  }

  function renderAll(){
    renderOverview(); renderChamberStrip(); populateDistrictSelect(); renderMap(); renderDetail(race(state.chamber,state.selected)); renderTable();
  }

  function bind(){
    $$('[data-chamber]').forEach(b=>b.addEventListener("click",()=>selectChamber(b.dataset.chamber)));
    $$('[data-mode]').forEach(b=>b.addEventListener("click",()=>{state.mode=b.dataset.mode;syncUrl();$$('[data-mode]').forEach(x=>x.setAttribute("aria-pressed",x===b));renderMap()}));
    $("#districtSelect").addEventListener("change",e=>{if(e.target.value)selectDistrict(+e.target.value,true);else clearDistrict()});
    for(const id of ["search","ratingFilter","scopeFilter"]) $("#"+id).addEventListener(id==="search"?"input":"change",renderTable);
    $$('th button[data-sort]').forEach(b=>b.addEventListener("click",()=>{state.asc=state.sort===b.dataset.sort?!state.asc:true;state.sort=b.dataset.sort;renderTable()}));
    $("#download").addEventListener("click",downloadCsv);
  }

  try {
    validatePayload();
    if(!DATA.models.some(m=>m.id===state.model))state.model=PUBLIC_MODEL;
    if(!["house","senate"].includes(state.chamber))state.chamber="house";
    if(state.selected&&!race(state.chamber,state.selected))state.selected=null;
    $("#buildDate").textContent=DATA.meta.buildDate;
    $("#pollDate").textContent=DATA.meta.pollAsOf;
    $("#financeDate").textContent=DATA.meta.financeAsOf;
    $("#pollAge").textContent=`${DATA.meta.pollStalenessDays} days old`;
    if(DATA.meta.pollStalenessDays>21) $("#pollAge").classList.add("stale");
    applyModel(); bind(); renderModelTabs(); renderProvenance();renderAll();syncUrl();
  } catch(error) {
    document.body.innerHTML=`<main class="error"><h1>Dashboard data error</h1><p>${error.message}</p><p>Rebuild the forecast payload before publishing.</p></main>`;
    console.error(error);
  }
})();
