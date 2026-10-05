(() => {
  "use strict";
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const params = new URLSearchParams(location.search);
  const PUBLIC_MODEL=DATA.meta.model;
  const HIGHLIGHTS={all:()=>true,competitive:r=>competitive(r),close:r=>r.status==="modeled"&&Math.abs(r.margin)<10,open:r=>!r.candidates.some(c=>c.incumbent),trails:r=>trails(r)};
  const state = { highlight:"all", chamber: params.get("chamber")||"house", model: params.get("model")||PUBLIC_MODEL, mode: ["margin","result2022"].includes(params.get("mode"))?params.get("mode"):"probability", view: params.get("view")==="tiles"?"tiles":"map", selected: +(params.get("district")||0)||null, area: null, sort: "closeness", asc: true };
  let siteMap=null, mapChamber=null;
  const css=getComputedStyle(document.documentElement);
  const token=name=>css.getPropertyValue(name).trim();
  const chamberName = c => c === "house" ? "State House" : "State Senate";
  const chamberShort = c => c === "house" ? "House" : "Senate";
  const districtName = (c,d) => `${c === "house" ? "HD" : "SD"}-${d}`;
  const partyName = p => ({D:"Democratic",R:"Republican",I:"Independent"}[p] || p);
  const partyNoun = p => ({D:"Democrats",R:"Republicans"}[p] || p);
  const esc = v => String(v ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const fmtPct = v => v == null || Number.isNaN(+v) ? "—" : `${(100*+v).toFixed(1)}%`;
  const fmtNumber = v => v == null ? "—" : new Intl.NumberFormat("en-US").format(v);
  const fmtMargin = v => v == null || Number.isNaN(+v) ? "—" : `${+v >= 0 ? "D+" : "R+"}${Math.abs(+v).toFixed(1)}`;
  const fmtChance = p => p < .001 ? "<0.1%" : p > .999 ? ">99.9%" : `${(100*p).toFixed(1)}%`;
  const fmtMoney = (v,status) => {
    if (v != null) return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(v);
    if (status === "no_state_entry_zero_assumption_sensitivity_only") return "$0 state entry (assumption)";
    if (status === "unmatched") return "Not matched";
    return "Not available";
  };
  /* Natural frequencies read more reliably than bare percentages. */
  const inThousand = p => p > .999 ? "more than 999 in 1,000" : p < .001 ? "fewer than 1 in 1,000" : p >= .99 || p <= .01 ? `${Math.round(p*1000)} in 1,000` : p >= .9 || p <= .1 ? `${Math.round(p*100)} in 100` : `${Math.round(p*10)} in 10`;
  const race = (c,d) => DATA[c].races.find(r => r.district === +d);
  const effectiveRating = r => r.status === "unopposed-major-party" ? `Unopposed ${r.demProbability === 1 ? "D" : "R"}` : r.rating;
  const competitive = r => r.status === "modeled" && r.demProbability >= .35 && r.demProbability <= .65;
  const intervalCrosses = r => r.low80 != null && r.low80 <= 0 && r.high80 >= 0;
  const leader = r => r.demProbability == null ? null : r.demProbability >= .5 ? "D" : "R";
  const incumbentParty = r => r.candidates.find(c=>c.incumbent&&["D","R"].includes(c.party))?.party||null;
  const trails = r => r.status==="modeled" && incumbentParty(r) && leader(r)!==incumbentParty(r);
  const fmtEffect=v=>Math.abs(v)<.005?"<0.01":`${v>=0?"D+":"R+"}${Math.abs(v).toFixed(2)}`;
  const publicVersion=r=>r.models?.[PUBLIC_MODEL];
  const selectedVersion=r=>r.models?.[state.model];
  const modelDelta=r=>selectedVersion(r)&&publicVersion(r)?selectedVersion(r).margin-publicVersion(r).margin:null;
  const winnerFor=m=>m==null?null:m>=0?"D":"R";
  const winnerDisagreement=r=>r.status==="modeled"&&new Set(Object.values(r.models).map(m=>winnerFor(m.margin))).size>1;
  const ratingDisagreement=r=>r.status==="modeled"&&new Set(Object.values(r.models).map(m=>ratingForProbability(m.demProbability))).size>1;
  const ratingForProbability=p=>{const lead=p>=.5?"D":"R",q=Math.max(p,1-p);return q<.60?"Toss-up":q<.80?`Lean ${lead}`:q<.95?`Likely ${lead}`:q<.98?`Very likely ${lead}`:`Solid ${lead}`};
  const RATING_COLORS={"Solid D":token("--rating-solid-d"),"Very likely D":token("--rating-very-likely-d"),"Likely D":token("--rating-likely-d"),"Lean D":token("--rating-lean-d"),"Toss-up":token("--rating-tossup"),"Lean R":token("--rating-lean-r"),"Likely R":token("--rating-likely-r"),"Very likely R":token("--rating-very-likely-r"),"Solid R":token("--rating-solid-r"),"Unopposed D":token("--rating-solid-d"),"Unopposed R":token("--rating-solid-r")};
  const NONE=token("--rating-none");
  const probabilityColor=p=>RATING_COLORS[ratingForProbability(p)];
  /* Printed cut-offs: the leading party's win chance, with no gaps between bands. */
  const RATING_BANDS=[["Solid D","98% or more"],["Very likely D","95–98%"],["Likely D","80–95%"],["Lean D","60–80%"],["Toss-up","under 60% for either party"],["Lean R","60–80%"],["Likely R","80–95%"],["Very likely R","95–98%"],["Solid R","98% or more"]];
  const MARGIN_BANDS=[[20,"Solid D","D+20 or more"],[10,"Very likely D","D+10 to D+20"],[5,"Likely D","D+5 to D+10"],[2,"Lean D","D+2 to D+5"],[-2,"Toss-up","within 2 points"],[-5,"Lean R","R+2 to R+5"],[-10,"Likely R","R+5 to R+10"],[-20,"Very likely R","R+10 to R+20"],[-Infinity,"Solid R","R+20 or more"]];
  const marginColor=m=>{for(const [floor,key] of MARGIN_BANDS){if(m>=floor)return RATING_COLORS[key]}return RATING_COLORS["Solid R"]};

  function syncUrl(){
    const q=new URLSearchParams({model:state.model,chamber:state.chamber,mode:state.mode,view:state.view});
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

  function renderModelTabs(){
    $("#modelTabs").innerHTML=DATA.models.map(m=>`<button role="tab" id="model-tab-${m.id}" data-model="${m.id}" aria-controls="workspace" tabindex="${m.id===state.model?0:-1}" aria-selected="${m.id===state.model}">${m.label}<small>${m.status}</small></button>`).join("");
    const m=DATA.models.find(x=>x.id===state.model);
    $("#modelDescription").innerHTML=`<b>${m.status}.</b> ${m.description}`;
    const tabs=$$('[data-model]');
    tabs.forEach((b,i)=>{b.addEventListener("click",()=>selectModel(b.dataset.model));b.addEventListener("keydown",e=>{if(!["ArrowLeft","ArrowRight","Home","End"].includes(e.key))return;e.preventDefault();let n=e.key==="Home"?0:e.key==="End"?tabs.length-1:(i+(e.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;selectModel(tabs[n].dataset.model);requestAnimationFrame(()=>document.querySelector(`[data-model="${state.model}"]`)?.focus())})});
  }
  function selectModel(model){state.model=model;applyModel();syncUrl();renderAll();renderModelTabs()}

  function validatePayload(){
    const issues=[];
    for(const c of ["house","senate"]){
      if(!DATA[c] || !Array.isArray(DATA[c].races) || !DATA[c].geometry?.districts) issues.push(`${c} payload missing`);
      else if(DATA[c].races.length !== (c === "house" ? 105 : 35)) issues.push(`${c} district count is invalid`);
    }
    if(issues.length) throw new Error(issues.join("; "));
  }

  function seatStats(c){
    const dist=DATA[c].seatDistribution;
    const mean=dist.reduce((s,x)=>s+x.demSeats*x.probability,0);
    const quantile=q=>{let s=0;for(const x of dist){s+=x.probability;if(s>=q)return x.demSeats}return dist.at(-1).demSeats};
    const total=c==="house"?105:35;
    const unknown=DATA[c].races.filter(r=>r.demProbability==null).length;
    const majority=Math.floor(total/2)+1,control=dist.filter(x=>x.demSeats>=majority).reduce((s,x)=>s+x.probability,0);
    const median=quantile(.5);
    return {mean,median,low:quantile(.1),high:quantile(.9),total,repMedian:total-median-unknown,competitive:DATA[c].races.filter(competitive).length,disagreements:DATA[c].races.filter(winnerDisagreement).length,unknown,control,majority};
  }
  const rangeText=s=>s.low===s.high?`${s.low}`:`${s.low}–${s.high}`;
  const panelWidth=()=>Math.max(260,Math.min(560,($("#detail")?.clientWidth||480)-44));

  /* One tab stop per collection: arrow keys move, Enter or Space opens. */
  function rove(items,{onSelect,onHover}){
    if(!items.length)return;
    items.forEach((item,i)=>{
      item.tabIndex=i===0?0:-1;
      item.addEventListener("keydown",e=>{
        const moves={ArrowRight:1,ArrowDown:1,ArrowLeft:-1,ArrowUp:-1};
        if(e.key in moves||e.key==="Home"||e.key==="End"){
          e.preventDefault();
          const n=e.key==="Home"?0:e.key==="End"?items.length-1:(i+moves[e.key]+items.length)%items.length;
          items.forEach(x=>x.tabIndex=-1);items[n].tabIndex=0;items[n].focus();onHover?.(items[n]);
        } else if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(item)}
      });
      item.addEventListener("click",()=>onSelect(item));
      item.addEventListener("pointerenter",()=>onHover?.(item));
      item.addEventListener("pointerleave",()=>onHover?.(null));
      item.addEventListener("blur",()=>onHover?.(null));
    });
  }

  function stripOrder(c){
    const rank=r=>r.demProbability==null?-1:r.demProbability;
    return [...DATA[c].races].sort((a,b)=>rank(b)-rank(a)||a.district-b.district);
  }

  function renderTopline(){
    $("#topline").innerHTML=["house","senate"].map(c=>{
      const s=seatStats(c), rControl=1-s.control;
      const favorite=s.control>=.5?"D":"R", odds=favorite==="D"?s.control:rControl;
      const order=stripOrder(c), counts={};
      for(const r of order){const k=effectiveRating(r)||"Not modeled";counts[k]=(counts[k]||0)+1}
      const countOrder=["Unopposed D","Solid D","Very likely D","Likely D","Lean D","Toss-up","Lean R","Likely R","Very likely R","Solid R","Unopposed R"];
      const short=s.majority-s.median;
      return `<article class="chamber-card ${state.chamber===c?'is-active':''}" aria-labelledby="card-${c}">
        <header><h2 id="card-${c}">${chamberName(c)}</h2><span>${s.total} seats · ${s.majority} for a majority</span></header>
        <p class="verdict"><b>${partyNoun(favorite)} control the ${chamberShort(c)}</b> in ${inThousand(odds)} simulations (${fmtChance(odds)}). The Democratic median is ${s.median} seats${short>0?`, ${short} short of a majority`:""}.</p>
        <dl class="chamber-stats"><div class="d"><dt>Median Democratic seats</dt><dd>${s.median}</dd></div><div class="r"><dt>Projected Republican seats${s.unknown?"*":""}</dt><dd>${s.repMedian}</dd></div><div><dt>Democratic seats in 80% of simulations</dt><dd>${rangeText(s)}</dd></div></dl>
        <div class="strip-wrap"><div class="seat-strip" role="group" aria-label="${chamberName(c)} seats ordered from most Democratic to most Republican">${order.map(r=>`<button data-strip-district="${r.district}" data-strip-chamber="${c}" class="${trails(r)?'trails':''}" style="background-color:${seatColor(r)}" title="${districtName(c,r.district)} · ${esc(effectiveRating(r))}${r.status==="modeled"?` · ${fmtMargin(r.margin)} · ${Math.round(100*r.demProbability)}% D`:""}" aria-label="${districtName(c,r.district)}, ${esc(effectiveRating(r))}${r.status==="modeled"?`, ${Math.round(100*r.demProbability)} percent Democratic chance`:""}${trails(r)?", incumbent's party trails":""}"></button>`).join("")}</div>
          <i class="strip-mark majority" style="left:${100*s.majority/s.total}%"><span>${s.majority} for majority</span></i>
          <i class="strip-mark median" style="left:${100*s.median/s.total}%"><span>D median ${s.median}</span></i>
          <div class="strip-ends" aria-hidden="true"><span>← Most Democratic</span><span>Most Republican →</span></div></div>
        <ul class="rating-counts" aria-label="Seats by rating">${countOrder.filter(k=>counts[k]).map(k=>`<li><i style="background:${RATING_COLORS[k]}"></i>${k} <b>${counts[k]}</b></li>`).join("")}${order.some(trails)?`<li><i class="hatch-swatch" style="background-color:${RATING_COLORS["Toss-up"]}"></i>Hatched: incumbent's party trails</li>`:""}</ul>
        <button class="explore" data-overview="${c}" aria-pressed="${state.chamber===c}">Explore the ${chamberShort(c)} map</button>
      </article>`;
    }).join("");
    $$('[data-overview]').forEach(b=>b.addEventListener("click",()=>selectChamber(b.dataset.overview,true)));
    for(const c of ["house","senate"]){
      rove($$(`[data-strip-chamber="${c}"]`),{
        onSelect:b=>{if(state.chamber!==c)selectChamber(c);selectDistrict(+b.dataset.stripDistrict,true)},
        onHover:b=>{if(state.chamber===c)linkHover(b?+b.dataset.stripDistrict:null,"strip")},
      });
    }
  }
  function seatColor(r){
    if(r.demProbability==null) return NONE;
    if(r.status==="unopposed-major-party") return r.demProbability===1 ? RATING_COLORS["Solid D"] : RATING_COLORS["Solid R"];
    return probabilityColor(r.demProbability);
  }

  function renderChamberHead(){
    $("#chamberTitle").textContent=`Explore the ${chamberName(state.chamber)}`;
    $("#mapTitle").textContent=`Alabama ${chamberName(state.chamber)} map`;
    $$('[data-chamber]').forEach(b=>b.setAttribute("aria-pressed",b.dataset.chamber===state.chamber));
    $("#mapScope").textContent=state.selected?`${districtName(state.chamber,state.selected)} selected. Close the district panel to return to the statewide view.`:state.view==="tiles"?"Tiles give every district one equal square, placed near its real location, because each district holds about the same number of people.":"Districts are drawn at their true size, so large rural districts dominate the picture. Switch to Tiles to give every district equal space.";
  }

  /* District map */
  /* 2022 result, shown only where the 2026 district is the 2022 district (plan-equivalence audit). */
  const prior2022=r=>{const p=r.profile?.priorResult;return p&&p.samePlan?p:null};
  function priorColor(r){
    const p=prior2022(r);
    if(!p||!p.winner) return NONE;
    return p.margin==null?RATING_COLORS[p.winner==="D"?"Solid D":"Solid R"]:marginColor(p.margin);
  }
  function priorText(r){
    const p=r.profile?.priorResult;
    if(!p) return "No 2022 result on record";
    if(!p.samePlan) return "Lines changed since 2022; no comparable result";
    const names=[p.demCandidate&&`${esc(p.demCandidate)} (D)`,p.repCandidate&&`${esc(p.repCandidate)} (R)`].filter(Boolean).join(" vs. ");
    return p.margin==null?`2022: ${names||partyName(p.winner)}, unopposed by the other major party`:`2022: ${names}, ${fmtMargin(p.margin)}`;
  }
  function mapColor(r){
    if(state.mode==="result2022") return priorColor(r);
    if(r.demProbability==null) return NONE;
    if(r.status==="unopposed-major-party") return r.demProbability===1 ? RATING_COLORS["Solid D"] : RATING_COLORS["Solid R"];
    if(state.mode==="probability") return probabilityColor(r.demProbability);
    return marginColor(r.margin);
  }
  function tooltipHtml(r){
    if(state.mode==="result2022") return `<b>${districtName(state.chamber,r.district)}</b>${priorText(r)}${r.profile?.priorResult?.planNote?"<br><small>Lines match 2022 while the reinstated 2021 Senate map governs 2026</small>":""}`;
    const cand=r.candidates.map(c=>`${esc(c.name)} (${c.party})`).join(" vs. ")||"No candidates listed";
    const prob=r.status!=="modeled"?esc(effectiveRating(r)):`${fmtMargin(r.margin)} · ${Math.round(100*Math.max(r.demProbability,1-r.demProbability))}% ${partyName(leader(r))} win chance`;
    return `<b>${districtName(state.chamber,r.district)} · ${esc(effectiveRating(r))}</b>${cand}<br>${prob}${trails(r)?"<br><small>Incumbent's party trails</small>":""}`;
  }
  function accessibleName(r){
    if(state.mode==="result2022") return `${chamberName(state.chamber)} District ${r.district}, ${priorText(r)}`;
    return `${chamberName(state.chamber)} District ${r.district}, ${effectiveRating(r)}${r.status==="modeled"?`, ${fmtMargin(r.margin)}, ${Math.round(100*r.demProbability)} percent Democratic chance`:""}${trails(r)?", incumbent's party trails":""}`;
  }
  function renderMap(){
    const c=state.chamber;
    if(mapChamber!==c||!siteMap){
      mapChamber=c;
      siteMap=SiteMap.create($("#map"),{
        geometry:DATA[c].geometry, context:DATA.context,
        label:`Interactive Alabama ${chamberName(c)} district forecast map`,
        fill:id=>mapColor(race(c,id)), hatch:id=>state.mode==="result2022"?prior2022(race(c,id))?.margin===null:trails(race(c,id)), dashed:id=>state.mode!=="result2022"&&race(c,id).demProbability==null,
        name:id=>accessibleName(race(c,id)), describe:id=>tooltipHtml(race(c,id)),
        muted:id=>!HIGHLIGHTS[state.highlight](race(c,id)),
        onSelect:id=>selectDistrict(+id,true), onHover:id=>linkHover(id?+id:null,"map"),
      });
      siteMap.setView(state.view);
      renderPresets();
    }
    siteMap.refresh();
    updateMapViewport();
    renderLegend();
  }
  function updateMapViewport(){
    if(!siteMap)return;
    if(state.selected) siteMap.select(String(state.selected));
    else {siteMap.select(null,{zoom:!state.area});if(state.area)siteMap.focusArea(state.area)}
  }
  function renderPresets(){
    const metros=(DATA.context.metros||[]).map(m=>m.name);
    $("#presets").innerHTML=["Statewide",...metros].map(n=>`<button data-area="${n}" aria-pressed="${(state.area||"Statewide")===n}">${n}</button>`).join("");
    $$('[data-area]').forEach(b=>b.addEventListener("click",()=>{
      state.area=b.dataset.area==="Statewide"?null:b.dataset.area;
      $$('[data-area]').forEach(x=>x.setAttribute("aria-pressed",x===b));
      if(state.selected){state.selected=null;syncUrl();renderDetail(null);renderTable();renderChamberHead()}
      siteMap.select(null,{zoom:false});
      siteMap.focusArea(state.area);
    }));
  }
  function renderLegend(){
    const sw=(color,label,note="",extra="")=>`<li><i style="background:${color};${extra}"></i><span>${label}${note?` <small>${note}</small>`:""}</span></li>`;
    const bands=state.mode==="probability"?RATING_BANDS.map(([k,n])=>sw(RATING_COLORS[k],k,n)):MARGIN_BANDS.map(([,k,n])=>sw(RATING_COLORS[k],n));
    if(state.mode==="result2022"){
      const races=DATA[state.chamber].races, changed=races.filter(r=>r.profile?.priorResult&&!r.profile.priorResult.samePlan).length, conditional=races.some(r=>r.profile?.priorResult?.planNote);
      const split=`linear-gradient(90deg,${RATING_COLORS["Solid D"]} 50%,${RATING_COLORS["Solid R"]} 50%)`;
      $("#legend").innerHTML=`<ul class="legend-scale">${bands.join("")}${sw(split,"Unopposed by the other major party","hatched, in the winner's Solid color","background-image:repeating-linear-gradient(45deg,#fff 0 1.6px,transparent 1.6px 5px),"+split)}${changed?sw(NONE,"Lines changed since 2022","no comparable result"):""}</ul><p class="legend-note">2022 general-election margins. Every district shown in color has exactly the same blocks as its 2022 district${changed?"; districts in gray changed":""}.${conditional?" Senate 25 and 26 match while the reinstated 2021 Senate map governs 2026.":""} <a href="data/alabama_2022_2026_plan_equivalence.csv">District match audit</a></p>`;
      return;
    }
    $("#legend").innerHTML=`<ul class="legend-scale">${bands.join("")}${sw(`linear-gradient(90deg,${RATING_COLORS["Solid D"]} 50%,${RATING_COLORS["Solid R"]} 50%)`,"Unopposed","shown in that party's Solid color")}${sw(RATING_COLORS["Toss-up"],"Incumbent's party trails","hatched","background-image:repeating-linear-gradient(45deg,#fff 0 1.6px,transparent 1.6px 5px)")}</ul>`;
  }

  /* Linked hover across strip, map, swarm and table. */
  function linkHover(d,source){
    if(source!=="map") siteMap?.highlight(d==null?null:String(d));
    $$(`[data-strip-chamber="${state.chamber}"]`).forEach(b=>b.classList.toggle("is-hover",+b.dataset.stripDistrict===d));
    $$("#beeswarm circle").forEach(x=>x.classList.toggle("is-hover",+x.dataset.district===d));
    $$("#rows tr").forEach(tr=>tr.classList.toggle("is-hover",+tr.dataset.district===d));
  }

  /* Chamber overview shown when no district is open */
  function unitHistogram(c){
    const dist=DATA[c].seatDistribution.filter(x=>x.probability>0), s=seatStats(c);
    const raw=dist.map(x=>x.probability*100), counts=raw.map(Math.floor);
    let left=100-counts.reduce((a,b)=>a+b,0);
    raw.map((v,i)=>[v-Math.floor(v),i]).sort((a,b)=>b[0]-a[0]).forEach(([,i])=>{if(left>0){counts[i]++;left--}});
    const cols=dist.map((x,i)=>({seats:x.demSeats,n:counts[i],p:x.probability})).filter(x=>x.n>0);
    const W=panelWidth(), colW=Math.min(64,W/Math.max(cols.length,1)), sq=Math.max(3,Math.min(10,(colW-8)/5)), gap=1.2, rows=Math.max(...cols.map(x=>Math.ceil(x.n/5)),1);
    const H=rows*(sq+gap)+46, x0=(W-colW*cols.length)/2;
    const body=cols.map((col,ci)=>{
      const left=x0+ci*colW+(colW-5*(sq+gap))/2, inRange=col.seats>=s.low&&col.seats<=s.high, isMedian=col.seats===s.median;
      const squares=Array.from({length:col.n},(_,k)=>`<rect class="sq" x="${(left+(k%5)*(sq+gap)).toFixed(1)}" y="${(H-34-(Math.floor(k/5)+1)*(sq+gap)).toFixed(1)}" width="${sq.toFixed(1)}" height="${sq.toFixed(1)}" fill="${isMedian?token("--rating-solid-d"):inRange?token("--rating-likely-d"):token("--rating-lean-d")}"/>`).join("");
      return `${squares}<text x="${(x0+ci*colW+colW/2).toFixed(1)}" y="${H-20}" text-anchor="middle" font-size="11" font-weight="${isMedian?700:400}" fill="var(--ink)">${col.seats}</text>${col.p>=.05?`<text x="${(x0+ci*colW+colW/2).toFixed(1)}" y="${(H-38-Math.ceil(col.n/5)*(sq+gap)).toFixed(1)}" text-anchor="middle" font-size="11" fill="var(--muted)">${Math.round(100*col.p)}%</text>`:""}`;
    }).join("");
    return `<figure class="chart unit-hist"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${chamberName(c)}: Democrats win ${rangeText(s)} seats in 80% of simulations; median ${s.median}; ${s.majority} needed for a majority">${body}<text x="${W/2}" y="${H-4}" text-anchor="middle" font-size="11" fill="var(--muted)">Democratic seats · ${s.majority} needed for a majority${s.high<s.majority?" (off this scale)":""}</text></svg><figcaption class="chart-note">Each square is 1 in 100 simulated outcomes${state.model===PUBLIC_MODEL?" from the 50,000 correlated simulations":" for this scenario"}. The darkest column is the median; mid-blue columns are inside the 80% range and the palest are outside it.</figcaption></figure>`;
  }
  function pathForParty(party){
    const rows=DATA[state.chamber].races, total=state.chamber==="house"?105:35, majority=Math.floor(total/2)+1;
    const fixed=rows.filter(r=>r.status==="unopposed-major-party"&&leader(r)===party).length;
    const modeled=rows.filter(r=>r.status==="modeled").sort((a,b)=>party==="D"?b.demProbability-a.demProbability:a.demProbability-b.demProbability);
    const needed=Math.max(0,majority-fixed), tipping=needed>0&&needed<=modeled.length?modeled[needed-1]:null;
    const near=tipping?modeled.slice(Math.max(0,needed-3),Math.min(modeled.length,needed+2)):[];
    return {party,fixed,needed,tipping,near,majority,modeledCount:modeled.length};
  }
  function renderMajorityPath(){
    const el=$("#majorityPath"); if(!el)return;
    const stats=seatStats(state.chamber), d=pathForParty("D"), r=pathForParty("R");
    const route=x=>`<article class="party-path ${x.party}"><strong>${fmtChance(x.party==="D"?stats.control:1-stats.control)}</strong><b>${partyName(x.party)} path</b><p>${x.fixed} ${x.fixed===1?"seat":"seats"} with no opponent; ${x.needed} modeled ${x.needed===1?"win":"wins"} needed${x.tipping?`. The route reaches the threshold at ${districtName(state.chamber,x.tipping.district)} (${Math.round(100*(x.party==="D"?x.tipping.demProbability:1-x.tipping.demProbability))}% ${x.party} chance).`:x.needed>x.modeledCount?`. Only ${x.modeledCount} two-party races are modeled, so a majority is out of reach without uncontested seats.`:"."}</p>${x.near.length?`<div class="path-races" role="group" aria-label="Races around the ${partyName(x.party)} majority threshold">${x.near.map(q=>`<button data-jump-district="${q.district}" class="${q===x.tipping?'tipping':''}">${districtName(state.chamber,q.district)} ${Math.round(100*(x.party==="D"?q.demProbability:1-q.demProbability))}%</button>`).join("")}</div>`:""}</article>`;
    el.innerHTML=`<div class="path-grid">${route(d)}${route(r)}</div><p class="panel-note">The marked race is the threshold seat in each party's probability-ranked route, not a claim that every easier seat will vote the same way.</p>`;
  }
  function renderRaceWatch(){
    const el=$("#raceWatch"); if(!el)return;
    const modeled=DATA[state.chamber].races.filter(r=>r.status==="modeled");
    const byCloseness=list=>[...list].sort((a,b)=>Math.abs(a.demProbability-.5)-Math.abs(b.demProbability-.5));
    const group=(title,list,empty)=>`<div class="watch-group"><b>${title}</b>${list.length?list.map(q=>`<button data-jump-district="${q.district}">${districtName(state.chamber,q.district)} <small>${esc(effectiveRating(q))}</small><strong>${fmtMargin(q.margin)}</strong></button>`).join(""):`<p>${empty}</p>`}</div>`;
    el.innerHTML=`<div class="watch-grid">${group("Closest races",byCloseness(modeled).slice(0,4),"No modeled races")}${group("Closest open seats",byCloseness(modeled.filter(r=>r.profile?.openSeat)).slice(0,3),"No modeled open seats")}${group("Incumbent's party trailing",byCloseness(modeled.filter(trails)).slice(0,3),"No incumbent's party currently trails")}</div>`;
  }
  function bindDistrictJumps(scope=document){
    scope.querySelectorAll('[data-jump-district]').forEach(button=>button.addEventListener("click",()=>selectDistrict(+button.dataset.jumpDistrict,true)));
  }
  function overviewHtml(){
    return `<div class="overview"><div class="panel-kicker">${chamberName(state.chamber)} at a glance</div><h3>Select a district</h3><p class="section-note">Choose a district on the map, the seat strip, the search box or the table to open its forecast.</p>
      <div class="overview-block"><h4>Simulated seat outcomes</h4>${unitHistogram(state.chamber)}</div>
      <div class="overview-block"><h4>Path to a majority</h4><div id="majorityPath"></div></div>
      <div class="overview-block"><h4>Seats to watch</h4><div id="raceWatch"></div></div></div>`;
  }

  /* District detail */
  function outcomeDots(r){
    const m=selectedVersion(r), offsets=DATA.meta.outcomeOffsets;
    const values=offsets.map(o=>m.margin+o), bound=Math.max(30,Math.ceil(Math.max(...values.map(Math.abs),Math.abs(m.low80),Math.abs(m.high80))/10)*10);
    const W=panelWidth(), x=v=>20+(W-40)*(v+bound)/(2*bound), bin=2, stacks={}, R=Math.min(3.4,(W-40)/(bound*2/bin)/2.2);
    const dots=values.map(v=>{const b=Math.floor(v/bin);stacks[b]=(stacks[b]||0)+1;return {v,b,k:stacks[b]-1}});
    const tallest=Math.max(...Object.values(stacks)), base=26+tallest*(2*R+.6), H=base+40;
    const dWins=values.filter(v=>v>0).length;
    const ticks=[-bound,-bound/2,0,bound/2,bound].map(v=>`<text x="${x(v).toFixed(1)}" y="${base+17}" text-anchor="middle" font-size="11" fill="var(--muted)">${v===0?"Even":fmtMargin(v).replace(".0","")}</text>`).join("");
    return `<figure class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${dWins} of 100 equally likely outcomes are Democratic wins; middle 80 percent from ${fmtMargin(m.low80)} to ${fmtMargin(m.high80)}">
      <line class="even-line" x1="${x(0)}" x2="${x(0)}" y1="14" y2="${base+4}"/>
      ${dots.map(d=>`<circle class="dot ${d.v>0?"D":"R"}" cx="${(x((d.b+.5)*bin)).toFixed(1)}" cy="${(base-R-d.k*(2*R+.6)).toFixed(1)}" r="${R}"/>`).join("")}
      <line x1="${x(m.low80)}" x2="${x(m.high80)}" y1="${base+5}" y2="${base+5}" stroke="var(--ink)" stroke-width="2"/><line x1="${x(m.low80)}" x2="${x(m.low80)}" y1="${base+1}" y2="${base+9}" stroke="var(--ink)"/><line x1="${x(m.high80)}" x2="${x(m.high80)}" y1="${base+1}" y2="${base+9}" stroke="var(--ink)"/>
      ${ticks}
      <text x="${x(0)-6}" y="10" text-anchor="end" font-size="11" font-weight="700" fill="var(--rep)">R wins ${100-dWins}</text><text x="${x(0)+6}" y="10" font-size="11" font-weight="700" fill="var(--dem)">D wins ${dWins}</text>
    </svg><figcaption class="chart-note">Each dot is one of 100 equally likely outcomes from the forecast's Student-t error (${DATA.meta.probability.scale.toFixed(2)}-point scale). The bracket marks the middle 80%.</figcaption></figure>`;
  }
  function componentComparisonHtml(r){
    if(r.status!=="modeled")return "";
    const selected=selectedVersion(r), raw=selected.steps, last=raw.length-1;
    /* In a scenario view the baseline already contains the polling shift and the final step only
       restates it. Draw the baseline without the shift so every bar adds to the line above. */
    const shift=Math.abs(raw[last][2]-raw[last-1][2])<1e-9?raw[last][1]:0;
    const steps=raw.map((s,i)=>i===0?[s[0]-shift,s[1]-shift,s[2]-shift]:i<last?[s[0],s[1],s[2]-shift]:s);
    const runs=steps.map(s=>s[2]), lo=Math.min(0,...runs,selected.low80), hi=Math.max(0,...runs,selected.high80);
    const pad=(hi-lo)*.08+1, a=lo-pad, b=hi+pad, W=panelWidth(), L=Math.min(160,W*.4), x=v=>L+(W-L-10)*(v-a)/(b-a), rowH=26;
    const rows=steps.map((step,i)=>{
      const from=i===0?0:steps[i-1][2], to=step[2], cls=i===0?"base":step[1]>=0?"D":"R", y=i*rowH+6;
      let lx=Math.max(x(from),x(to))+4; if(Math.abs(lx-x(0))<16) lx=x(0)+6;
      return `<text x="0" y="${y+13}" font-size="11" fill="var(--ink)">${esc(DATA.contributionVariables[i])}</text><rect class="wf-bar ${cls}" x="${Math.min(x(from),x(to)).toFixed(1)}" y="${y+3}" width="${Math.max(1.5,Math.abs(x(to)-x(from))).toFixed(1)}" height="${rowH-10}"/><text x="${Math.min(W-2,lx).toFixed(1)}" y="${y+13}" font-size="11" fill="var(--muted)" text-anchor="${lx>W-46?"end":"start"}">${i?fmtEffect(step[1]):fmtMargin(to)}</text>`;
    }).join("");
    const yF=steps.length*rowH+6;
    const final=`<text x="0" y="${yF+13}" font-size="11" font-weight="700" fill="var(--ink)">Forecast margin</text><line x1="${x(selected.low80)}" x2="${x(selected.high80)}" y1="${yF+9}" y2="${yF+9}" stroke="var(--ink)" stroke-width="2"/><circle cx="${x(selected.margin)}" cy="${yF+9}" r="5" fill="${selected.margin>=0?token("--dem"):token("--rep")}"/>${x(selected.high80)+52<W?`<text x="${x(selected.high80)+6}" y="${yF+13}" font-size="11" font-weight="700" fill="var(--ink)">${fmtMargin(selected.margin)}</text>`:x(selected.low80)-52>L?`<text x="${x(selected.low80)-6}" y="${yF+13}" font-size="11" font-weight="700" fill="var(--ink)" text-anchor="end">${fmtMargin(selected.margin)}</text>`:`<text x="${x(selected.margin)}" y="${yF-1}" font-size="11" font-weight="700" fill="var(--ink)" text-anchor="middle">${fmtMargin(selected.margin)}</text>`}`;
    const H=yF+26;
    const scenarios=DATA.models.map(model=>{const m=r.models[model.id];return `<div class="scenario-result ${model.id===state.model?'selected':''}"><span>${model.label}</span><b>${fmtMargin(m.margin)}</b><small>${Math.round(100*m.demProbability)}% D chance</small></div>`}).join("");
    return `<section class="component-comparison"><h4>Forecast components</h4><figure class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Forecast components from ${fmtMargin(steps[0][2])} to ${fmtMargin(selected.margin)}"><line class="even-line" x1="${x(0)}" x2="${x(0)}" y1="0" y2="${H}" stroke-dasharray="2 2"/>${rows}${final}</svg><figcaption class="chart-note">Each bar moves the Democratic margin from the line above${state.model===PUBLIC_MODEL?"":"; in this scenario the polling shift is drawn as its own final bar"}. The structural steps come from the post-2016 WAR model; carried-forward candidate WAR applies only where a nominee has a matched prior Alabama race; the scenario tabs change only national polling error.</figcaption></figure><div class="scenario-results">${scenarios}</div></section>`;
  }
  function candidateHistoryHtml(c){
    if(!c.warHistory?.length)return "";
    const max=Math.max(5,...c.warHistory.map(x=>Math.abs(x.war)));
    return `<details class="candidate-history"><summary>${esc(c.name)}: Alabama WAR history (${c.warHistory.length} race${c.warHistory.length===1?"":"s"})</summary><p>Retrospective race residuals. The forecast carries part of this nominee's most recent matched result forward; the amount used here is the carried-forward step in Forecast components.</p><div class="career-timeline">${c.warHistory.map(x=>`<div class="career-row"><span>${x.cycle}<small>${districtName(x.chamber,x.district)}${x.incumbent?" · incumbent":""}</small></span><i class="career-scale"><i class="zero"></i><i class="career-bar ${x.war>=0?'D':'R'}" style="left:${x.war>=0?50:50-45*Math.abs(x.war)/max}%;width:${45*Math.abs(x.war)/max}%"></i></i><b>${fmtEffect(x.war)}</b></div>`).join("")}</div></details>`;
  }
  function candidateHtml(c){
    return `<div class="candidate"><i class="stripe ${c.party}" aria-hidden="true"></i><div><b>${esc(c.name)}</b><small>${partyName(c.party)}${c.incumbent?" · Incumbent":" · Non-incumbent"}</small></div><div class="finance-values">${fmtMoney(c.raised,c.financeStatus)} raised<br>${fmtMoney(c.spent,c.financeStatus)} spent<br>not used by forecast</div></div>${candidateHistoryHtml(c)}`;
  }
  function profileHtml(r){
    const p=r.profile||{}, prior=p.priorResult;
    const priorText=!prior?"Not available":prior.margin==null?"No two-party margin":fmtMargin(prior.margin);
    const region=p.regions?.length?p.regions.map(x=>`${x.name} ${fmtPct(x.share)}`).join("; "):"Not available";
    const priorDetail=prior?([prior.demCandidate,prior.repCandidate].filter(Boolean).length?[prior.demCandidate,prior.repCandidate].filter(Boolean).map(esc).join(" vs. "):`D ${fmtNumber(prior.demVotes)} · R ${fmtNumber(prior.repVotes)}`):"";
    return `<section class="district-profile"><h4>District profile</h4><div class="profile-grid"><div><span>2024 presidential margin</span><b>${fmtMargin(r.pres24)}</b></div><div><span>2022 legislative result</span><b>${priorText}</b><small>${priorDetail}</small></div><div><span>Seat status</span><b>${p.openSeat?"Open seat":"Incumbent running"}</b></div><div><span>Black CVAP</span><b>${fmtPct(p.blackCvapShare)}</b></div><div><span>White non-Hispanic CVAP</span><b>${fmtPct(p.whiteCvapShare)}</b></div><div><span>College graduate share</span><b>${fmtPct(p.collegeShare)}</b></div><div><span>White college graduate share</span><b>${fmtPct(p.whiteCollegeShare)}</b></div><div class="profile-wide"><span>Regional composition</span><b>${region}</b></div></div><p class="profile-note">Demographics are district estimates, not individual voting behavior. Regional shares describe the district's geographic composition.</p></section>`;
  }
  function renderDetail(r){
    const el=$("#detail");
    if(!r){
      el.classList.remove("is-open");
      el.innerHTML=overviewHtml();
      renderMajorityPath(); renderRaceWatch(); bindDistrictJumps(el);
      return;
    }
    el.classList.add("is-open");
    const lead=leader(r), leadProb=lead?Math.max(r.demProbability,1-r.demProbability):null, rating=effectiveRating(r);
    const call=r.status==="modeled"?`<p class="call"><strong>${fmtMargin(r.margin)}</strong>${partyName(lead)} nominee favored in ${Math.round(100*leadProb)} of 100 outcomes.</p>`:`<p class="call"><strong>${esc(rating)}</strong>${r.status==="unopposed-major-party"?"Single major-party nominee; independent contests are not modeled.":"No two-party forecast available."}</p>`;
    const modeled=r.status==="modeled"?`<h4>Range of outcomes</h4>${outcomeDots(r)}${componentComparisonHtml(r)}`:"";
    const ordered=[...DATA[state.chamber].races].filter(x=>x.status==="modeled").sort((a,b)=>Math.abs(a.margin)-Math.abs(b.margin)), pos=ordered.findIndex(x=>x.district===r.district);
    const prev=pos>-1?ordered[(pos-1+ordered.length)%ordered.length]:ordered[0], next=pos>-1?ordered[(pos+1)%ordered.length]:ordered[0];
    el.innerHTML=`<div class="detail-top"><div><div class="panel-kicker">2026 general election</div><h3>${chamberName(state.chamber)} District ${r.district}</h3></div><button class="close-detail" id="closeDistrict" aria-label="Close district and return to statewide map">×</button></div>
      <span class="chip rating-chip"><i style="background:${seatColor(r)}"></i>${esc(rating)}</span>${trails(r)?' <span class="chip" style="border-color:var(--ink)">Incumbent\'s party trails</span>':""}
      ${call}<div class="detail-actions"><button class="small-button" id="shareRace">Copy link</button></div>
      <h4>Candidates</h4><div>${r.candidates.map(candidateHtml).join("")||"<p>No certified candidate listed.</p>"}</div>${modeled}${profileHtml(r)}
      <div class="race-nav"><button class="small-button" data-race-nav="${prev?.district||r.district}">← Closer race</button><button class="small-button" data-race-nav="${next?.district||r.district}">Next race →</button></div>`;
    el.querySelectorAll('[data-race-nav]').forEach(b=>b.addEventListener("click",()=>selectDistrict(+b.dataset.raceNav,true)));
    $("#shareRace")?.addEventListener("click",async e=>{syncUrl();try{await navigator.clipboard.writeText(location.href);e.currentTarget.textContent="Link copied"}catch{e.currentTarget.textContent="Use address bar to copy"}});
    $("#closeDistrict")?.addEventListener("click",()=>clearDistrict(true));
  }

  /* Where the competitive seats sit: one dot per modeled race on the margin axis. */
  function renderBeeswarm(){
    const races=DATA[state.chamber].races.filter(r=>r.status==="modeled");
    const W=Math.max(320,($("#beeswarm").clientWidth||1000)-36), B=30, narrow=W<600, Rr=narrow?6:9, x=v=>(narrow?24:40)+(W-(narrow?48:80))*(Math.max(-B,Math.min(B,v))+B)/(2*B);
    const placed=[], dots=[...races].sort((a,b)=>Math.abs(a.margin)-Math.abs(b.margin)).map(r=>{
      const cx=x(r.margin); let k=0, cy=0;
      for(;;k++){cy=(k%2?1:-1)*Math.ceil(k/2)*(2*Rr+1);if(!placed.some(p=>Math.abs(p.cx-cx)<2*Rr+1&&Math.abs(p.cy-cy)<2*Rr+1))break}
      const d={r,cx,cy};placed.push(d);return d;
    });
    const span=Math.max(...placed.map(p=>Math.abs(p.cy)),Rr)+Rr+6, mid=span+24, H=2*span+64;
    const ticks=(narrow?[-30,-15,0,15,30]:[-30,-20,-10,0,10,20,30]).map(v=>`<line x1="${x(v)}" x2="${x(v)}" y1="22" y2="${H-26}" stroke="${v?'var(--rule-soft)':'var(--ink)'}"/><text x="${x(v)}" y="${H-10}" text-anchor="${narrow&&Math.abs(v)===B?(v<0?"start":"end"):"middle"}" font-size="12" fill="var(--muted)">${v===0?"Even":v<0?`R+${-v}`:`D+${v}`}${Math.abs(v)===B?(narrow?"+":" or more"):""}</text>`).join("");
    const close=races.filter(r=>Math.abs(r.margin)<5).length;
    $("#closestNote").textContent=`${races.length} ${chamberName(state.chamber)} races have both a Democrat and a Republican; ${close} ${close===1?"is":"are"} within 5 points in the ${DATA.models.find(m=>m.id===state.model).label.toLowerCase()} view. Ringed dots mark seats where the incumbent's party trails.`;
    $("#beeswarm").innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Modeled ${chamberName(state.chamber)} races by forecast margin"><rect class="band" x="${x(-5)}" y="20" width="${x(5)-x(-5)}" height="${H-46}"/><text x="${x(0)}" y="14" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ink)">Within 5 points</text><text x="${narrow?0:40}" y="14" font-size="12" font-weight="700" fill="var(--rep)">← ${narrow?"R":"Republican"} favored</text><text x="${narrow?W:W-40}" y="14" text-anchor="end" font-size="12" font-weight="700" fill="var(--dem)">${narrow?"D":"Democratic"} favored →</text>${ticks}
      ${dots.map(d=>`<circle data-district="${d.r.district}" class="${trails(d.r)?'trails':''}" role="button" aria-label="${esc(accessibleName(d.r))}" cx="${d.cx.toFixed(1)}" cy="${(mid+d.cy).toFixed(1)}" r="${Rr}" fill="${probabilityColor(d.r.demProbability)}"><title>${districtName(state.chamber,d.r.district)} ${fmtMargin(d.r.margin)}</title></circle>`).join("")}</svg>`;
    rove($$("#beeswarm circle"),{onSelect:c=>selectDistrict(+c.dataset.district,true),onHover:c=>linkHover(c?+c.dataset.district:null,"swarm")});
  }


  /* Seats won at each regular general election since 1994, with the 2026 forecast range. */
  function renderHistory(){
    const el=$("#history"), H=DATA.seatHistory; if(!el||!H){if(el)el.hidden=true;return}
    el.hidden=false;
    const avail=Math.max(300,(el.clientWidth||1100)-36), chartW=Math.round(innerWidth>760?(avail-18)/2:avail);
    const chart=c=>{
      const rows=H.chambers[c], s=seatStats(c), total=rows[0].seats, majority=Math.floor(total/2)+1;
      const W=chartW, Ht=230, top=18, base=190, colW=(W-110)/(rows.length+1), y=v=>base-(base-top)*v/total;
      const bars=rows.map((r,i)=>{const x=40+i*colW+colW*.18, w=colW*.64, dTop=y(r.D), uTop=y(r.D+r.unknown), oTop=y(r.D+r.unknown+r.other);
        const flag=r.reconciliation==="match"?"":"†";
        return `<g><rect x="${x.toFixed(1)}" y="${dTop.toFixed(1)}" width="${w.toFixed(1)}" height="${(base-dTop).toFixed(1)}" fill="var(--dem)"/>${r.unknown?`<rect x="${x.toFixed(1)}" y="${uTop.toFixed(1)}" width="${w.toFixed(1)}" height="${(dTop-uTop).toFixed(1)}" fill="var(--rating-none)"/><rect x="${x.toFixed(1)}" y="${uTop.toFixed(1)}" width="${w.toFixed(1)}" height="${(dTop-uTop).toFixed(1)}" fill="url(#hist-hatch-${c})"/>`:""}${r.other?`<rect x="${x.toFixed(1)}" y="${oTop.toFixed(1)}" width="${w.toFixed(1)}" height="${(uTop-oTop).toFixed(1)}" fill="var(--ind)"/>`:""}<rect x="${x.toFixed(1)}" y="${top}" width="${w.toFixed(1)}" height="${(oTop-top).toFixed(1)}" fill="var(--rep)"/><text x="${(x+w/2).toFixed(1)}" y="${(base-4).toFixed(1)}" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">${r.D}</text><text x="${(x+w/2).toFixed(1)}" y="${base+14}" text-anchor="middle" font-size="11" fill="var(--ink)">${r.cycle}${flag}</text><title>${r.cycle}: ${r.D} Democratic, ${r.R} Republican${r.other?`, ${r.other} other`:""}${r.unknown?`, ${r.unknown} unknown`:""} seats won</title></g>`}).join("");
      const fx=40+rows.length*colW+colW*.18, fw=colW*.64;
      const forecast=`<g><rect x="${fx.toFixed(1)}" y="${y(s.median).toFixed(1)}" width="${fw.toFixed(1)}" height="${(base-y(s.median)).toFixed(1)}" fill="var(--rating-likely-d)"/><rect x="${fx.toFixed(1)}" y="${top}" width="${fw.toFixed(1)}" height="${(y(s.median)-top).toFixed(1)}" fill="var(--rating-likely-r)"/><line x1="${(fx+fw/2).toFixed(1)}" x2="${(fx+fw/2).toFixed(1)}" y1="${y(s.high).toFixed(1)}" y2="${y(s.low).toFixed(1)}" stroke="var(--ink)" stroke-width="2"/><text x="${(fx+fw/2).toFixed(1)}" y="${(base-4).toFixed(1)}" text-anchor="middle" font-size="11" font-weight="700" fill="var(--ink)">${s.median}</text><text x="${(fx+fw/2).toFixed(1)}" y="${base+14}" text-anchor="middle" font-size="11" font-weight="700" fill="var(--ink)">2026</text><text x="${(fx+fw/2).toFixed(1)}" y="${base+27}" text-anchor="middle" font-size="11" fill="var(--muted)">forecast</text></g>`;
      return `<figure class="chart"><figcaption><b>${chamberName(c)}</b></figcaption><svg viewBox="0 0 ${W} ${Ht}" role="img" aria-label="${chamberName(c)} seats won by party, ${rows[0].cycle} to ${rows.at(-1).cycle}, and the 2026 Democratic median of ${s.median}"><defs><pattern id="hist-hatch-${c}" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)"><rect width="1.6" height="5" fill="#fff"/></pattern></defs>${bars}${forecast}<line x1="34" x2="${W-78}" y1="${y(majority).toFixed(1)}" y2="${y(majority).toFixed(1)}" stroke="var(--ink)" stroke-dasharray="4 3"/><text x="${W-72}" y="${(y(majority)-3).toFixed(1)}" font-size="11" font-weight="700" fill="var(--ink)">Majority</text><text x="${W-72}" y="${(y(majority)+11).toFixed(1)}" font-size="11" fill="var(--ink)">${majority} seats</text></svg></figure>`;
    };
    const flagged=["house","senate"].some(c=>H.chambers[c].some(r=>r.reconciliation!=="match"));
    el.innerHTML=`<div class="kicker">Context</div><h2 id="historyTitle">Seats won since 1994</h2><p class="section-note">Democratic seats (blue, labeled) and Republican seats won at each regular general election, with this forecast's Democratic median and 80% range for 2026. Gray hatched seats have no confirmed winner party. These are general-election results, not chamber composition after special elections or party switches.</p><div class="section-panel history-grid">${chart("house")}${chart("senate")}</div><p class="chart-note">${flagged?`† No independent reference matches this total exactly; see the <a href="${H.reconciliation}">reconciliation file</a>. `:""}Source: warehouse final-stage results, run ${esc(H.runId)}. <a href="${H.download}">Download seat counts</a></p>`;
  }

  /* Seats by shared polling miss: simulations grouped by the environment error every district shares. */
  const sideBySide=el=>{const avail=Math.max(300,(el.clientWidth||1100)-36);return Math.round(innerWidth>760?(avail-18)/2:avail)};
  const missLabel=v=>v===0?"Even":v<0?`R+${-v}`:`D+${v}`;
  function binQuantiles(rows){
    rows.sort((a,b)=>a[1]-b[1]);
    const n=rows.reduce((s,r)=>s+r[2],0), q=p=>{let s=0;for(const r of rows){s+=r[2];if(s>=p*n)return r[1]}return rows.at(-1)[1]};
    return {n,low:q(.1),median:q(.5),high:q(.9)};
  }
  function renderEnvironment(){
    const el=$("#environment"), J=DATA.environmentJoint; if(!el||!J){if(el)el.hidden=true;return}
    el.hidden=false;
    const chartW=sideBySide(el);
    const chart=c=>{
      const groups=new Map();
      for(const r of J.chambers[c]){if(!groups.has(r[0]))groups.set(r[0],[]);groups.get(r[0]).push(r)}
      const bins=[...groups.entries()].map(([env,rows])=>({env,...binQuantiles(rows)})).filter(b=>b.n>=J.draws*.005).sort((a,b)=>a.env-b.env);
      const total=c==="house"?105:35, majority=Math.floor(total/2)+1, s=seatStats(c), w=J.binWidth;
      const W=chartW, H=262, L=34, R=14, top=14, base=190, lo=bins[0].env, hi=bins.at(-1).env+w;
      const x=v=>L+(W-L-R)*(v-lo)/(hi-lo), mid=b=>b.env+w/2;
      const yMin=Math.max(0,Math.min(...bins.map(b=>b.low),majority)-2), yMax=Math.min(total,Math.max(...bins.map(b=>b.high),majority)+2);
      const y=v=>base-(base-top)*(v-yMin)/(yMax-yMin);
      const band=bins.map(b=>`${x(mid(b)).toFixed(1)},${y(b.high).toFixed(1)}`).concat(bins.slice().reverse().map(b=>`${x(mid(b)).toFixed(1)},${y(b.low).toFixed(1)}`)).join(" ");
      const line=bins.map(b=>`${x(mid(b)).toFixed(1)},${y(b.median).toFixed(1)}`).join(" ");
      const most=Math.max(...bins.map(b=>b.n));
      const bars=bins.map(b=>{const h=24*b.n/most;return `<rect x="${(x(b.env)+.5).toFixed(1)}" y="${(base+28-h).toFixed(1)}" width="${Math.max(1,x(b.env+w)-x(b.env)-1).toFixed(1)}" height="${h.toFixed(1)}" fill="var(--rule)"/>`}).join("");
      const step=hi-lo>24?10:5, ticks=[];for(let t=Math.ceil(lo/step)*step;t<=hi;t+=step)ticks.push(t);
      const yStep=total>60?10:5, yTicks=[];for(let t=Math.ceil(yMin/yStep)*yStep;t<=yMax;t+=yStep)yTicks.push(t);
      const flip=bins.find(b=>b.median>=majority);
      const finding=flip?(flip.env<=0?`The median simulation is already a Democratic majority at today's polling.`:`The median simulation becomes a Democratic majority only when the shared miss reaches ${missLabel(flip.env)} or more.`):`No simulated environment, even a large Democratic miss, makes a Democratic majority the median outcome.`;
      return `<figure class="chart"><figcaption><b>${chamberName(c)}</b> <small>${finding}</small></figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${chamberName(c)}: Democratic seats by shared polling miss. At today's polling the median is ${s.median} seats; ${majority} are needed for a majority. ${finding}">
        ${yTicks.map(t=>`<line x1="${L}" x2="${W-R}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" stroke="var(--rule-soft)"/><text x="${L-6}" y="${(y(t)+4).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--muted)">${t}</text>`).join("")}
        <polygon points="${band}" fill="var(--rating-lean-d)" opacity=".55"/><polyline points="${line}" fill="none" stroke="var(--dem)" stroke-width="2.5"/>
        <line x1="${L}" x2="${W-R}" y1="${y(majority).toFixed(1)}" y2="${y(majority).toFixed(1)}" stroke="var(--ink)" stroke-dasharray="4 3"/><text x="${W-R}" y="${(y(majority)-5).toFixed(1)}" text-anchor="end" font-size="11" font-weight="700" fill="var(--ink)">Majority ${majority}</text>
        <line x1="${x(0).toFixed(1)}" x2="${x(0).toFixed(1)}" y1="${top}" y2="${base+28}" stroke="var(--ink)" stroke-width="1.2"/><text x="${(x(0)+5).toFixed(1)}" y="${(Math.abs(y(majority)-(top+10))<14?y(majority)+16:top+10).toFixed(1)}" font-size="11" font-weight="700" fill="var(--ink)">Today's polls</text>
        ${bars}${ticks.map(t=>`<text x="${x(t).toFixed(1)}" y="${base+44}" text-anchor="middle" font-size="11" fill="var(--muted)">${missLabel(t)}</text>`).join("")}
        <text x="${((L+W-R)/2).toFixed(1)}" y="${H-4}" text-anchor="middle" font-size="11" fill="var(--ink-2)">Shared polling miss in every district (gray bars: share of simulations)</text></svg></figure>`;
    };
    el.innerHTML=`<div class="kicker">Uncertainty</div><h2 id="environmentTitle">If the polls are off</h2><p class="section-note">Every simulation moves all districts together by a shared statewide error, then adds district noise. Grouping the ${J.draws.toLocaleString("en-US")} simulations by that shared miss shows the Democratic seat count it produces: the line is the median, the band the middle 80%.</p><div class="section-panel history-grid">${chart("house")}${chart("senate")}</div>`;
  }

  /* Polling replay: today's candidates and model under each week's polling average. */
  function renderTrend(){
    const el=$("#trend"), T=DATA.pollingReplay; if(!el||!T||T.rows.length<2){if(el)el.hidden=true;return}
    el.hidden=false;
    const chartW=sideBySide(el), rows=T.rows.map(r=>({...r,t:Date.parse(r.asOf+"T00:00:00Z")}));
    const t0=rows[0].t, t1=rows.at(-1).t, fmtDay=t=>new Date(t).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric",timeZone:"UTC"});
    const chart=c=>{
      const total=c==="house"?105:35, majority=Math.floor(total/2)+1, pts=rows.map(r=>({t:r.t,...r.chambers[c]}));
      const W=chartW, H=232, L=34, R=58, top=14, base=196;
      const yMin=Math.max(0,Math.min(...pts.map(p=>p.low),majority)-2), yMax=Math.min(total,Math.max(...pts.map(p=>p.high),majority)+2);
      const x=t=>L+(W-L-R)*(t-t0)/Math.max(1,t1-t0), y=v=>base-(base-top)*(v-yMin)/(yMax-yMin);
      const band=pts.map(p=>`${x(p.t).toFixed(1)},${y(p.high).toFixed(1)}`).concat(pts.slice().reverse().map(p=>`${x(p.t).toFixed(1)},${y(p.low).toFixed(1)}`)).join(" ");
      const line=pts.map(p=>`${x(p.t).toFixed(1)},${y(p.median).toFixed(1)}`).join(" "), last=pts.at(-1), first=pts[0];
      const yStep=total>60?10:5, yTicks=[];for(let t=Math.ceil(yMin/yStep)*yStep;t<=yMax;t+=yStep)yTicks.push(t);
      const months=[];{const d=new Date(t0);d.setUTCDate(1);d.setUTCMonth(d.getUTCMonth()+1);for(;d.getTime()<=t1;d.setUTCMonth(d.getUTCMonth()+(t1-t0>200*864e5?3:1)))months.push(d.getTime())}
      return `<figure class="chart"><figcaption><b>${chamberName(c)}</b></figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${chamberName(c)}: median Democratic seats moved from ${first.median} on ${fmtDay(first.t)} to ${last.median} on ${fmtDay(last.t)} under each week's polling average; ${majority} needed for a majority.">
        ${yTicks.map(t=>`<line x1="${L}" x2="${W-R}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" stroke="var(--rule-soft)"/><text x="${L-6}" y="${(y(t)+4).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--muted)">${t}</text>`).join("")}
        <polygon points="${band}" fill="var(--rating-lean-d)" opacity=".55"/><polyline points="${line}" fill="none" stroke="var(--dem)" stroke-width="2.5"/>
        <line x1="${L}" x2="${W-R}" y1="${y(majority).toFixed(1)}" y2="${y(majority).toFixed(1)}" stroke="var(--ink)" stroke-dasharray="4 3"/><text x="${L+4}" y="${(y(majority)-5).toFixed(1)}" font-size="11" font-weight="700" fill="var(--ink)">Majority ${majority}</text>
        <circle cx="${x(last.t).toFixed(1)}" cy="${y(last.median).toFixed(1)}" r="4" fill="var(--dem)"/><text x="${(x(last.t)+7).toFixed(1)}" y="${(y(last.median)+4).toFixed(1)}" font-size="12" font-weight="700" fill="var(--ink)">${last.median}</text>
        ${months.map(m=>`<text x="${x(m).toFixed(1)}" y="${base+18}" text-anchor="middle" font-size="11" fill="var(--muted)">${new Date(m).toLocaleDateString("en-US",{month:"short",timeZone:"UTC"})}${new Date(m).getUTCMonth()===0?` ${new Date(m).getUTCFullYear()}`:""}</text>`).join("")}</svg></figure>`;
    };
    const gb=rows.map(r=>r.genericBallot);
    el.innerHTML=`<div class="kicker">Polling replay</div><h2 id="trendTitle">How the outlook moves with the polls</h2><p class="section-note">Today's candidates and model, re-run with the Silver Bulletin generic-ballot average as it stood each week from ${fmtDay(t0)} to ${fmtDay(t1)} (generic ballot ${fmtMargin(Math.min(...gb))} to ${fmtMargin(Math.max(...gb))}). Line: median Democratic seats; band: middle 80%. This is not a record of past forecasts: ${T.limitations.map(s=>esc(s.charAt(0).toLowerCase()+s.slice(1).replace(/\.$/,""))).join("; ")}.</p><div class="section-panel history-grid">${chart("house")}${chart("senate")}</div>`;
  }

  /* Table */
  function tableRows(){
    let rows=[...DATA[state.chamber].races], q=$("#search").value.trim().toLowerCase(), rating=$("#ratingFilter").value, scope=$("#scopeFilter").value;
    if(q) rows=rows.filter(r=>`${r.district} ${districtName(state.chamber,r.district).toLowerCase()} ${r.candidates.map(c=>c.name).join(" ")}`.toLowerCase().includes(q));
    if(rating!=="all") rows=rows.filter(r=>effectiveRating(r)===rating);
    if(scope==="competitive") rows=rows.filter(competitive);
    if(scope==="modeled") rows=rows.filter(r=>r.status==="modeled");
    if(scope==="open") rows=rows.filter(r=>!r.candidates.some(c=>c.incumbent));
    if(scope==="crosses") rows=rows.filter(intervalCrosses);
    if(scope==="trails") rows=rows.filter(trails);
    if(scope==="winner-disagreement") rows=rows.filter(winnerDisagreement);
    if(scope==="rating-disagreement") rows=rows.filter(ratingDisagreement);
    const value=(r,k)=>k==="rating"?effectiveRating(r):k==="closeness"?(r.margin==null?999:Math.abs(r.margin)):r[k];
    rows.sort((a,b)=>{let x=value(a,state.sort),y=value(b,state.sort);x=x??-999;y=y??-999;return (x>y?1:x<y?-1:0)*(state.asc?1:-1)});
    return rows;
  }
  function marginCell(r){
    if(r.margin==null) return r.status==="unopposed-major-party"?"Unopposed":"—";
    const B=40, x=v=>4+112*(Math.max(-B,Math.min(B,v))+B)/(2*B);
    return `<div class="margin-cell"><svg viewBox="0 0 120 16" aria-hidden="true"><line x1="4" x2="116" y1="8" y2="8" stroke="var(--rule-soft)"/><line x1="60" x2="60" y1="2" y2="14" stroke="var(--ink)"/><line x1="${x(r.low80).toFixed(1)}" x2="${x(r.high80).toFixed(1)}" y1="8" y2="8" stroke="var(--ink-2)" stroke-width="2"/><circle cx="${x(r.margin).toFixed(1)}" cy="8" r="4" fill="${r.margin>=0?token("--dem"):token("--rep")}"/></svg><span>${fmtMargin(r.margin)}</span></div>`;
  }
  function renderTable(){
    const rows=tableRows(), isHeadline=state.model===PUBLIC_MODEL;
    $("table").classList.toggle("hide-delta",isHeadline);
    $("#rows").innerHTML=rows.map(r=>{const d=modelDelta(r),rating=effectiveRating(r);return `<tr data-district="${r.district}" tabindex="0" class="${state.selected===r.district?'selected':''}" aria-label="Open ${districtName(state.chamber,r.district)} details">
      <td>${districtName(state.chamber,r.district)}</td><td>${r.candidates.map(c=>`<span class="party-dot" style="background:${c.party==='D'?'var(--dem)':c.party==='R'?'var(--rep)':'var(--ind)'}"></span>${esc(c.name)} (${c.party})`).join("<br>")||"—"}</td>
      <td><span class="chip"><i style="background:${seatColor(r)}"></i>${esc(rating)}</span>${winnerDisagreement(r)?'<small class="disagreement">Winner disagreement</small>':ratingDisagreement(r)?'<small class="disagreement">Rating disagreement</small>':''}</td>
      <td>${r.status==="unopposed-major-party"?"Unopposed":r.demProbability==null?"—":`<div class="prob-cell"><span class="prob-bar" aria-hidden="true"><i style="width:${(100*r.demProbability).toFixed(1)}%"></i></span><span>${Math.round(100*r.demProbability)}%</span></div>`}</td>
      <td>${marginCell(r)}</td><td class="delta-col">${isHeadline?"—":d==null?"—":fmtEffect(d)}</td></tr>`}).join("");
    $$("#rows tr").forEach(tr=>{const open=()=>selectDistrict(+tr.dataset.district,true);tr.addEventListener("click",open);tr.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();open()}});tr.addEventListener("pointerenter",()=>linkHover(+tr.dataset.district,"table"));tr.addEventListener("pointerleave",()=>linkHover(null,"table"))});
    $("#rowCount").textContent=`${rows.length} districts shown for ${DATA.models.find(m=>m.id===state.model).label}`;
    $$('th button[data-sort]').forEach(b=>{const th=b.closest("th"),active=state.sort===b.dataset.sort;th.setAttribute("aria-sort",active?(state.asc?"ascending":"descending"):"none");b.querySelector("span").textContent=active?(state.asc?" ↑":" ↓"):""});
  }
  function downloadCsv(){
    const header=["selected_view","chamber","district","candidates","rating","dem_win_probability","forecast_margin","headline_margin","difference_from_headline","margin_80_low","margin_80_high","views_disagree_on_winner","incumbent_party_trails"];
    const cell=v=>`"${String(v??"").replaceAll('"','""')}"`;
    const body=DATA[state.chamber].races.map(r=>[state.model,state.chamber,r.district,r.candidates.map(c=>`${c.name} (${c.party})`).join("; "),effectiveRating(r),r.demProbability,r.margin,publicVersion(r)?.margin,modelDelta(r),r.low80,r.high80,winnerDisagreement(r),trails(r)].map(cell).join(","));
    const blob=new Blob([[header.join(","),...body].join("\n")],{type:"text/csv"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=`alabama_2026_${state.chamber}_forecast.csv`;a.click();URL.revokeObjectURL(a.href);
  }
  function renderProvenance(){
    const el=$("#sourceLedger");if(!el)return;
    el.innerHTML=DATA.provenance.map(s=>`<article><b>${esc(s.category)}</b><span>${esc(s.source)}</span><small>Through ${esc(s.asOf)}</small><a href="${s.download}" download>Download supporting data</a></article>`).join("");
  }

  /* Search: districts, candidates, and the cities in each district's regional profile. */
  let finderActive=-1, finderMatches=[];
  function finderIndex(){
    return DATA[state.chamber].races.map(r=>({r,text:`${districtName(state.chamber,r.district)} district ${r.district} ${r.candidates.map(c=>c.name).join(" ")} ${(r.profile?.regions||[]).map(x=>x.name).join(" ")}`.toLowerCase()}));
  }
  function renderFinder(){
    const input=$("#districtSearch"), list=$("#districtOptions"), q=input.value.trim().toLowerCase();
    finderMatches=q?finderIndex().filter(x=>q.split(/\s+/).every(t=>x.text.includes(t))).slice(0,8).map(x=>x.r):[];
    finderActive=finderMatches.length?0:-1;
    list.innerHTML=finderMatches.map((r,i)=>`<li role="option" id="finder-${i}" data-district="${r.district}" aria-selected="${i===finderActive}">${districtName(state.chamber,r.district)} · ${esc(effectiveRating(r))}<small>${r.candidates.map(c=>esc(c.name)).join(" vs. ")}${(r.profile?.regions||[]).length?` · ${r.profile.regions.map(x=>esc(x.name)).join(", ")}`:""}</small></li>`).join("")||(q?`<li role="option" aria-disabled="true">No ${chamberName(state.chamber)} district matches</li>`:"");
    list.hidden=!q; input.setAttribute("aria-expanded",String(Boolean(q)));
    input.setAttribute("aria-activedescendant",finderActive>=0?`finder-${finderActive}`:"");
    list.querySelectorAll("[data-district]").forEach(li=>li.addEventListener("mousedown",e=>{e.preventDefault();chooseFinder(+li.dataset.district)}));
  }
  function chooseFinder(d){const input=$("#districtSearch");input.value="";$("#districtOptions").hidden=true;input.setAttribute("aria-expanded","false");selectDistrict(d,true)}
  function bindFinder(){
    const input=$("#districtSearch");
    input.addEventListener("input",renderFinder);
    input.addEventListener("keydown",e=>{
      if(e.key==="ArrowDown"||e.key==="ArrowUp"){if(!finderMatches.length)return;e.preventDefault();finderActive=(finderActive+(e.key==="ArrowDown"?1:-1)+finderMatches.length)%finderMatches.length;$$("#districtOptions [role=option]").forEach((li,i)=>li.setAttribute("aria-selected",i===finderActive));input.setAttribute("aria-activedescendant",`finder-${finderActive}`)}
      else if(e.key==="Enter"&&finderActive>=0){e.preventDefault();chooseFinder(finderMatches[finderActive].district)}
      else if(e.key==="Escape"){input.value="";renderFinder()}
    });
    input.addEventListener("blur",()=>setTimeout(()=>{$("#districtOptions").hidden=true;input.setAttribute("aria-expanded","false")},120));
  }

  let selectionOrigin=null;
  function selectDistrict(d,scroll=false){
    const from=document.activeElement;
    selectionOrigin=from?.closest?.("#rows")?"row":from?.closest?.("#map")?"map":from?.closest?.("[data-strip-chamber]")?"strip":from?.closest?.("#beeswarm")?"swarm":null;
    state.selected=+d; state.area=null; syncUrl();
    $$('[data-area]').forEach(x=>x.setAttribute("aria-pressed",x.dataset.area==="Statewide"));
    renderChamberHead(); updateMapViewport(); renderDetail(race(state.chamber,d)); renderTable();
    if(scroll){
      if(innerWidth<761){$("#closeDistrict")?.focus({preventScroll:true})}
      else{
        $("#workspace").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
        if(selectionOrigin!=="map") $("#closeDistrict")?.focus({preventScroll:true});
      }
    }
  }
  function clearDistrict(returnFocus=false){
    const was=state.selected;
    state.selected=null;syncUrl();renderChamberHead();updateMapViewport();renderDetail(null);renderTable();
    if(!returnFocus||!was) return;
    /* Return focus to the control the reader came from. */
    const target=selectionOrigin==="row"?document.querySelector(`#rows tr[data-district="${was}"]`)
      :selectionOrigin==="strip"?document.querySelector(`[data-strip-chamber="${state.chamber}"][data-strip-district="${was}"]`)
      :selectionOrigin==="swarm"?document.querySelector(`#beeswarm circle[data-district="${was}"]`)
      :document.querySelector('#map [tabindex="0"]');
    target?.focus({preventScroll:selectionOrigin==="row"&&innerWidth<761});
  }
  function selectChamber(c,scroll=false){
    state.chamber=c;state.selected=null;state.area=null;syncUrl();
    renderAll();
    if(scroll) $("#workspace").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});
  }
  function renderAll(){
    renderTopline(); renderChamberHead(); renderMap(); renderDetail(race(state.chamber,state.selected)); renderBeeswarm(); renderTrend(); renderEnvironment(); renderHistory(); renderTable();
  }

  function bind(){
    $$('[data-chamber]').forEach(b=>b.addEventListener("click",()=>selectChamber(b.dataset.chamber)));
    $$('[data-mode]').forEach(b=>b.addEventListener("click",()=>{state.mode=b.dataset.mode;syncUrl();$$('[data-mode]').forEach(x=>x.setAttribute("aria-pressed",x===b));renderMap()}));
    $$('[data-view]').forEach(b=>b.addEventListener("click",()=>{state.view=b.dataset.view;syncUrl();$$('[data-view]').forEach(x=>x.setAttribute("aria-pressed",x===b));siteMap.setView(state.view);renderChamberHead()}));
    $$('[data-mode]').forEach(x=>x.setAttribute("aria-pressed",x.dataset.mode===state.mode));
    $$('[data-view]').forEach(x=>x.setAttribute("aria-pressed",x.dataset.view===state.view));
    for(const id of ["search","ratingFilter","scopeFilter"]) $("#"+id).addEventListener(id==="search"?"input":"change",renderTable);
    $$('th button[data-sort]').forEach(b=>b.addEventListener("click",()=>{state.asc=state.sort===b.dataset.sort?!state.asc:true;state.sort=b.dataset.sort;renderTable()}));
    $("#download").addEventListener("click",downloadCsv);
    $("#highlight").addEventListener("change",e=>{state.highlight=e.target.value;siteMap?.refresh()});
    document.addEventListener("keydown",e=>{if(e.key==="Escape"&&state.selected&&!e.target.closest?.("#districtSearch"))clearDistrict(true)});
    bindFinder();
    let resizeTimer=null,lastWidth=innerWidth;
    addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(innerWidth===lastWidth)return;lastWidth=innerWidth;renderBeeswarm();renderTrend();renderEnvironment();renderHistory();renderDetail(race(state.chamber,state.selected))},200)});
  }

  try {
    validatePayload();
    if(!DATA.models.some(m=>m.id===state.model))state.model=PUBLIC_MODEL;
    if(!["house","senate"].includes(state.chamber))state.chamber="house";
    if(state.selected&&!race(state.chamber,state.selected))state.selected=null;
    $("#buildDate").textContent=DATA.meta.buildDate;
    $("#pollDate").textContent=DATA.meta.pollAsOf;
    $("#buildId").textContent=DATA.meta.version;
    $("#pollAge").textContent=`${DATA.meta.pollStalenessDays} days old`;
    if(DATA.meta.pollStalenessDays>21) $("#pollAge").classList.add("stale");
    applyModel(); bind(); renderModelTabs(); renderProvenance(); renderAll(); syncUrl();
  } catch(error) {
    document.body.innerHTML=`<main class="error"><h1>Dashboard data error</h1><p>${esc(error.message)}</p><p>Rebuild the forecast payload before publishing.</p></main>`;
    console.error(error);
  }
})();
