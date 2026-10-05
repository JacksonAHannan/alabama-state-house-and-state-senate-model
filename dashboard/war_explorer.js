let active=null,origin=null,highlight=0,sortKey='war',sortDir=-1,selected=null,selectedParty=null,mapMode='absolute',view='map',area=null,baselineChoices={},playTimer=null,siteMap=null,mapSection=null;
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const fmt=n=>(n>0?'+':'')+Number(n).toFixed(1),fmtMaybe=n=>n==null?'Unavailable':fmt(n),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const css=getComputedStyle(document.documentElement),token=n=>css.getPropertyValue(n).trim();
const reduceMotion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
const panelWidth=()=>Math.max(260,Math.min(560,($('#detail')?.clientWidth||480)-40));
/* Remember where a selection came from so closing it returns focus there. */
function noteOrigin(){const a=document.activeElement;origin=a?.closest?.('#rows')?'row':a?.closest?.('#map')?'map':a?.closest?.('.swarm')?'swarm':null}
function restoreFocus(district,section){const target=origin==='row'?document.querySelector(`#rows tr[data-section="${section}"][data-district="${district}"]`):origin==='swarm'?document.querySelector(`.swarm circle[data-district="${district}"]`):document.querySelector('#map [tabindex="0"]');target?.focus({preventScroll:origin!=='map'&&innerWidth<761})}
/* WAR is a residual, so it gets its own purple–orange scale, never the party red and blue. */
const WAR_STOPS=[[-30,'--war-r3'],[-15,'--war-r2'],[-5,'--war-r1'],[0,'--war-0'],[5,'--war-d1'],[15,'--war-d2'],[30,'--war-d3']].map(([v,n])=>[v,token(n)]);
function mix(a,b,t){const A=a.match(/\w\w/g).map(x=>parseInt(x,16)),B=b.match(/\w\w/g).map(x=>parseInt(x,16));return '#'+A.map((x,i)=>Math.round(x+(B[i]-x)*t).toString(16).padStart(2,'0')).join('')}
function warColor(v){if(v==null||!Number.isFinite(Number(v)))return token('--war-none');const x=Math.max(-30,Math.min(30,Number(v)));for(let i=1;i<WAR_STOPS.length;i++){const[v1,c1]=WAR_STOPS[i-1],[v2,c2]=WAR_STOPS[i];if(x<=v2)return mix(c1,c2,(x-v1)/(v2-v1))}return WAR_STOPS.at(-1)[1]}
/* Election records sometimes print names in capitals; display them in title case. */
function displayName(s){const text=String(s??'');if(/[a-z]/.test(text))return text;return text.toLowerCase().replace(/(^|[\s\-'’.])([a-z])/g,(m,p,c)=>p+c.toUpperCase()).replace(/\bMc([a-z])/g,(m,c)=>'Mc'+c.toUpperCase()).replace(/\b(Ii|Iii|Iv)\b/g,m=>m.toUpperCase())}
const SECTIONS=Object.keys(DATA).sort((a,b)=>DATA[a].cycle-DATA[b].cycle||DATA[a].chamber.localeCompare(DATA[b].chamber));
const CYCLES=[...new Set(SECTIONS.map(k=>DATA[k].cycle))].sort((a,b)=>a-b);
const keyFor=(cycle,chamber)=>`${cycle}-${chamber}`,chamberLabel=c=>c==='house'?'House':'Senate';
const allCandidates=()=>Object.entries(DATA).flatMap(([section,d])=>d.candidates.map(x=>({...x,section,cycle:d.cycle,chamber:d.chamber})));
const MODE_CONFIG={absolute:{label:'Alabama WAR',description:'Alabama WAR, residual margin points',headline:'Alabama WAR'},governor:{label:'Vs. governor',description:'Raw overperformance vs. governor (a benchmark, not WAR)',headline:'Raw overperformance vs. governor'},presidential:{label:'Vs. previous president',description:'Raw overperformance vs. previous presidential margin (a benchmark, not WAR)',headline:'Raw overperformance vs. previous presidential margin'}};
function modeConfig(){return MODE_CONFIG[mapMode]||MODE_CONFIG.absolute}
function mapMetric(d,district){if(mapMode==='absolute')return d.demWar[district];if(mapMode==='governor')return d.rawVsGovernor[district];return d.rawVsPresidential[district]}
function candidateMetric(x){if(!x)return null;if(mapMode==='absolute')return x.war;const value=mapMetric(DATA[active],x.district);return value==null?null:(x.party==='D'?Number(value):-Number(value))}
function currentSelectedCandidate(){if(selected==null)return null;const d=DATA[active];return d.candidates.find(c=>c.district===Number(selected)&&(!selectedParty||c.party===selectedParty))||d.winners[selected]||null}
function mapValueText(value){const side=value>=0?'Democratic':'Republican',amount=Math.abs(value).toFixed(1);return mapMode==='absolute'?`${side} WAR advantage: ${amount} points`:`${side} overperformance: ${amount} points`}
function median(values){const v=values.filter(x=>x!=null&&Number.isFinite(+x)).map(Number).sort((a,b)=>a-b);if(!v.length)return null;const m=Math.floor(v.length/2);return v.length%2?v[m]:(v[m-1]+v[m])/2}

function syncUrl(){const d=DATA[active],q=new URLSearchParams({cycle:d.cycle,chamber:d.chamber,mode:mapMode,view});if(selected)q.set('district',selected);history.replaceState(null,'',`${location.pathname}?${q}${location.hash}`)}
function readUrl(){const q=new URLSearchParams(location.search),cycle=+q.get('cycle'),chamber=q.get('chamber')==='senate'?'senate':'house';active=DATA[keyFor(cycle,chamber)]?keyFor(cycle,chamber):keyFor(2022,'house');if(MODE_CONFIG[q.get('mode')])mapMode=q.get('mode');view=q.get('view')==='tiles'?'tiles':'map';const d=+q.get('district');if(d&&DATA[active].winners[d]){selected=d;selectedParty=DATA[active].winners[d].party}}

/* Controls: chamber, election timeline with play, and the per-cycle median strip */
function renderControls(){
  const d=DATA[active],i=CYCLES.indexOf(d.cycle);
  $$('[data-chamber]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.chamber===d.chamber));
  const range=$('#cycleRange');range.max=CYCLES.length-1;range.value=i;range.setAttribute('aria-valuetext',`${d.cycle} election`);
  $('#cycleTicks').innerHTML=CYCLES.map(c=>c===d.cycle?`<b>${c}</b>`:`<span>${c}</span>`).join('');
  $$('[data-map-mode]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.mapMode===mapMode));
  $$('[data-view]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.view===view));
  renderDrift();
}
function renderDrift(){
  const chamber=DATA[active].chamber,values=CYCLES.map(c=>median(Object.values(DATA[keyFor(c,chamber)].demWar))),cap=Math.max(10,...values.map(v=>Math.abs(v||0)));
  $('#drift').innerHTML=`<div class="drift-cols" role="group" aria-label="Median race WAR by election, ${chamberLabel(chamber)}">${values.map((v,i)=>{const h=v==null?0:26*Math.abs(v)/cap,on=CYCLES[i]===DATA[active].cycle;return `<button class="drift-col${on?' is-on':''}" data-cycle="${CYCLES[i]}" aria-pressed="${on}" aria-label="${CYCLES[i]}: median race WAR ${v==null?'unavailable':fmt(v)}"><i style="height:${Math.max(1,h).toFixed(1)}px;${v>=0?'bottom':'top'}:50%;background:${warColor(v)}"></i><span style="${v>=0?'bottom':'top'}:calc(50% + ${(h+2).toFixed(1)}px)">${v==null?'':fmt(v)}</span></button>`}).join('')}</div><p class="note">Median race WAR in each election (Democratic-oriented). Early cycles sit far from zero because every cycle is scored against the fixed 2018–24 reference model.</p>`;
  $$('#drift [data-cycle]').forEach(r=>r.addEventListener('click',()=>setCycle(+r.dataset.cycle)));
}
function setCycle(cycle){const key=keyFor(cycle,DATA[active].chamber);if(!DATA[key])return;active=key;selected=null;selectedParty=null;render()}
function setChamber(chamber){const key=keyFor(DATA[active].cycle,chamber);if(!DATA[key])return;active=key;selected=null;selectedParty=null;area=null;render()}
function togglePlay(){
  const b=$('#play');
  if(playTimer){clearInterval(playTimer);playTimer=null;b.setAttribute('aria-pressed','false');b.setAttribute('aria-label','Play elections in order');b.textContent='▶';return}
  b.setAttribute('aria-pressed','true');b.setAttribute('aria-label','Pause');b.textContent='❚❚';
  if(DATA[active].cycle===CYCLES.at(-1))setCycle(CYCLES[0]);
  playTimer=setInterval(()=>{const i=CYCLES.indexOf(DATA[active].cycle);if(i>=CYCLES.length-1){togglePlay();return}setCycle(CYCLES[i+1])},reduceMotion()?2400:1600);
}

/* Map */
function tooltip(d,district){const x=d.winners[district],raw=mapMetric(d,district),status=d.districtStatus[String(district)]||'No contested D–R race on record';return x&&raw!=null?`<b>District ${district}</b>${esc(modeConfig().label)}: ${mapValueText(raw)}<br>Won by ${esc(displayName(x.candidate))} (${x.party})`:`<b>District ${district}</b>${esc(x?'Selected benchmark unavailable':status)}`}
function accessibleName(d,district){const x=d.winners[district],raw=mapMetric(d,district);return x&&raw!=null?`District ${district}, ${mapValueText(raw)}, won by ${displayName(x.candidate)}`:`District ${district}, ${d.districtStatus[String(district)]||'no contested D–R race on record'}`}
function renderMap(){
  const d=DATA[active];
  $('#map-title').textContent=`${d.cycle} Alabama ${chamberLabel(d.chamber)}`;
  $('#map-sub').textContent=modeConfig().description;
  $('#vintage').textContent=`Boundaries: ${d.mapVintage}`;
  if(mapSection!==active){
    mapSection=active;
    siteMap=SiteMap.create($('#map'),{geometry:GEOMETRY[d.plan],context:CONTEXT,label:`${d.cycle} Alabama ${chamberLabel(d.chamber)} WAR map`,
      fill:id=>warColor(mapMetric(DATA[active],+id)),name:id=>accessibleName(DATA[active],+id),
      muted:id=>{const v=mapMetric(DATA[active],+id);return highlight>0&&(v==null||Math.abs(v)<highlight)},describe:id=>tooltip(DATA[active],+id),
      onSelect:id=>{noteOrigin();const x=DATA[active].winners[+id];selected=+id;selectedParty=x?x.party:null;render(true)},onHover:id=>linkHover(id?+id:null)});
    siteMap.setView(view);renderPresets();
  }
  siteMap.refresh();
  if(selected)siteMap.select(String(selected));else{siteMap.select(null,{zoom:!area});if(area)siteMap.focusArea(area)}
  renderLegend();
}
function renderPresets(){
  $('#presets').innerHTML=['Statewide',...(CONTEXT.metros||[]).map(m=>m.name)].map(n=>`<button data-area="${n}" aria-pressed="${(area||'Statewide')===n}">${n}</button>`).join('');
  $$('[data-area]').forEach(b=>b.addEventListener('click',()=>{area=b.dataset.area==='Statewide'?null:b.dataset.area;$$('[data-area]').forEach(x=>x.setAttribute('aria-pressed',x===b));selected=null;selectedParty=null;detail(null);siteMap.select(null,{zoom:false});siteMap.focusArea(area);syncUrl()}));
}
function renderLegend(){
  const ramp=WAR_STOPS.map(([,c])=>`<i style="background:${c}"></i>`).join('');
  const what=mapMode==='absolute'?'ran ahead of the reference model':'ran ahead of the benchmark';
  $('#legend').innerHTML=`<div class="legend-ends"><span>← Republican ${what}</span><span>Democrat ${what} →</span></div><div class="legend-ramp">${ramp}</div><div class="legend-ticks"><span>R+30</span><span>R+15</span><span>R+5</span><span>Even</span><span>D+5</span><span>D+15</span><span>D+30</span></div><div class="none"><i></i>No contested D–R race or benchmark unavailable (not zero)</div>`;
}
function linkHover(district){siteMap?.highlight(district==null?null:String(district));$$('.swarm circle').forEach(c=>c.classList.toggle('is-hover',+c.dataset.district===district));$$('#rows tr').forEach(tr=>tr.classList.toggle('is-hover',tr.dataset.section===active&&+tr.dataset.district===district))}

/* Cycle overview shown when no race is open */
function overview(){
  const d=DATA[active],races=Object.entries(d.winners).map(([district,x])=>({district:+district,x,v:mapMetric(d,+district)})).filter(r=>r.v!=null);
  const W=panelWidth(),B=40,R=W<400?4.5:5.5,X=v=>20+(W-40)*(Math.max(-B,Math.min(B,v))+B)/(2*B),placed=[];
  const dots=races.sort((a,b)=>Math.abs(a.v)-Math.abs(b.v)).map(r=>{const cx=X(r.v);let k=0,cy=0;for(;;k++){cy=(k%2?1:-1)*Math.ceil(k/2)*(2*R+.8);if(!placed.some(p=>Math.abs(p.cx-cx)<2*R+.8&&Math.abs(p.cy-cy)<2*R+.8))break}const p={...r,cx,cy};placed.push(p);return p});
  const span=Math.max(R,...placed.map(p=>Math.abs(p.cy)))+R+4,mid=span+22,H=2*span+48;
  const ticks=[-40,-20,0,20,40].map(v=>`<line x1="${X(v)}" x2="${X(v)}" y1="18" y2="${H-22}" stroke="${v?'var(--rule-soft)':'var(--ink)'}"/><text x="${X(v)}" y="${H-8}" text-anchor="middle" font-size="11" fill="var(--muted)">${v===0?'Even':v<0?`R+${-v}`:`D+${v}`}${Math.abs(v)===B?'+':''}</text>`).join('');
  const med=median(races.map(r=>r.v)),top=d.summary;
  return `<div class="panel-kicker">${d.cycle} ${chamberLabel(d.chamber)} at a glance</div><h3>Select a district</h3><p class="note">Choose a district on the map, a dot below, or a row in the table.</p>
    <div class="overview-stats"><div><b>${races.length}</b><span>Contested D–R districts</span></div><div><b>${med==null?'—':fmt(med)}</b><span>Median ${mapMode==='absolute'?'race WAR':'benchmark gap'} (D-oriented)</span></div><div><b>${esc(displayName(top.top))}</b><span>Top WAR winner</span></div></div>
    <h4>Every contested race</h4><figure class="swarm"><svg viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc(modeConfig().label)} for every contested ${d.cycle} ${chamberLabel(d.chamber)} race"><text x="0" y="11" font-size="11" font-weight="700" fill="var(--war-r3)">← ${W<400?'R':'Republican'} ran ahead</text><text x="${W}" y="11" text-anchor="end" font-size="11" font-weight="700" fill="var(--war-d3)">${W<400?'D':'Democrat'} ran ahead →</text>${ticks}${dots.map(p=>`<circle data-district="${p.district}" role="button" aria-label="${esc(accessibleName(d,p.district))}" cx="${p.cx.toFixed(1)}" cy="${(mid+p.cy).toFixed(1)}" r="${R}" fill="${warColor(p.v)}"><title>District ${p.district}: ${fmt(p.v)}</title></circle>`).join('')}</svg><figcaption class="note">One dot per contested race, placed by its Democratic-oriented ${mapMode==='absolute'?'WAR':'benchmark gap'}. The Republican candidate's score is the exact negative.</figcaption></figure>`;
}
function rove(items,onSelect){items.forEach((el,i)=>{el.tabIndex=i===0?0:-1;el.addEventListener('click',()=>onSelect(el));el.addEventListener('pointerenter',()=>linkHover(+el.dataset.district));el.addEventListener('pointerleave',()=>linkHover(null));el.addEventListener('keydown',e=>{const moves={ArrowRight:1,ArrowDown:1,ArrowLeft:-1,ArrowUp:-1};if(e.key in moves){e.preventDefault();const n=items[(i+moves[e.key]+items.length)%items.length];items.forEach(x=>x.tabIndex=-1);n.tabIndex=0;n.focus();linkHover(+n.dataset.district)}else if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(el)}})})}

/* Race detail */
function baselineOptions(x){const raw=DATA[active].baselines[String(x.district)]||[];return raw.filter(o=>o.available!==false).sort((a,b)=>{const rank=o=>o.label==='Governor'?0:o.kind==='office'?1:o.kind==='composite'?2:3;return rank(a)-rank(b)||a.label.localeCompare(b.label)})}
function setBaseline(district,index){baselineChoices[active+'-'+district]=index;detail(currentSelectedCandidate()||DATA[active].winners[district])}
function baselineContext(x,total){const options=baselineOptions(x);if(!options.length)return '';const key=active+'-'+x.district,index=Math.min(baselineChoices[key]??0,options.length-1),o=options[index],margin=o.demMargin,leader=margin>=0?'D':'R',demShare=(100+margin)/2,repShare=100-demShare,isObserved=o.kind==='office',boxTotal=isObserved?Number(o.demVotes)+Number(o.repVotes):total,demVotes=isObserved?Number(o.demVotes):Math.round(boxTotal*demShare/100),repVotes=isObserved?Number(o.repVotes):Math.round(boxTotal*repShare/100),gap=Math.abs(Math.round(demVotes-repVotes)),tabs=options.map((v,i)=>`<button class="${i===index?'active':''}" aria-pressed="${i===index}" onclick="setBaseline(${x.district},${i})">${esc(v.label)}</button>`).join(''),subtitle=isObserved?'District-level two-party office result':'Margin normalized to legislative two-party turnout',note=isObserved?'Votes are the allocated district result for this statewide office.':'Vote totals are implied from the selected margin at the legislative race’s observed turnout.';return `<div class="baseline-context"><div class="baseline-title">District top-of-ticket context</div><div class="baseline-tabs">${tabs}</div><div class="baseline-wikibox"><div class="baseline-wikibox-head">${esc(o.label)}</div><div class="baseline-wikibox-sub">${subtitle}</div><table><thead><tr><th aria-label="Party color"></th><th>Candidate</th><th>Party</th><th class="num">Votes</th><th class="num">Share</th></tr></thead><tbody><tr class="${leader==='D'?'leader':''}"><td class="party-cell D"></td><td>${esc(o.demName)}</td><td>D${leader==='D'?' <span class="check">✓</span>':''}</td><td class="num">${Math.round(demVotes).toLocaleString()}</td><td class="num">${demShare.toFixed(1)}%</td></tr><tr class="${leader==='R'?'leader':''}"><td class="party-cell R"></td><td>${esc(o.repName)}</td><td>R${leader==='R'?' <span class="check">✓</span>':''}</td><td class="num">${Math.round(repVotes).toLocaleString()}</td><td class="num">${repShare.toFixed(1)}%</td></tr></tbody></table><div class="baseline-wikibox-foot"><div><b>${Math.round(boxTotal).toLocaleString()}</b> two-party votes</div><div>Margin: <b>${leader}+${Math.abs(margin).toFixed(1)}</b> · ${gap.toLocaleString()} votes</div></div><div class="baseline-wikibox-note">${note}</div></div><div class="source-credit">Source: Alabama Secretary of State official returns; district allocation and composite calculations by this project.</div></div>`}
function raceBox(x){const d=DATA[active],race=d.candidates.filter(c=>c.district===x.district).sort((a,b)=>b.votes-a.votes),total=race.reduce((s,c)=>s+c.votes,0),actualGap=race.length>1?race[0].votes-race[1].votes:total,actualMargin=100*actualGap/total,dem=race.find(c=>c.party==='D'),expectedDem=dem?dem.expectedMargin:0,expectedLeader=expectedDem>=0?'Democratic':'Republican',expectedGap=Math.round(total*Math.abs(expectedDem)/100),rows=race.map(c=>{const expectedShare=(100+c.expectedMargin)/2,expectedVotes=Math.round(total*expectedShare/100);return `<tr class="${c.winner?'winner-row':''}"><td class="party-cell ${c.party}"></td><td class="candidate-col">${esc(displayName(c.candidate))} ${c.party}${c.incumbent?' <small>(inc.)</small>':''}${c.winner?' <span class="check" aria-label="Winner">✓</span>':''}</td><td class="num">${c.votes.toLocaleString()}</td><td class="num">${(100*c.votes/total).toFixed(1)}%</td><td class="num expected">${expectedVotes.toLocaleString()}</td><td class="num expected">${expectedShare.toFixed(1)}%</td></tr>`}).join('');return `<div class="racebox"><div class="racebox-head">${d.cycle} Alabama ${chamberLabel(d.chamber)} District ${x.district}</div><div class="racebox-sub">General election · actual versus ticket baseline</div><div class="racebox-table"><table><thead><tr><th rowspan="2" aria-label="Party color"></th><th rowspan="2">Candidate</th><th colspan="2" class="group-head">Actual</th><th colspan="2" class="group-head">Ticket baseline</th></tr><tr><th class="num">Votes</th><th class="num">Share</th><th class="num">Votes</th><th class="num">Share</th></tr></thead><tbody>${rows}</tbody></table></div><div class="racebox-comparison"><div><span>Actual margin</span><b>${race[0].party==='D'?'Democratic':'Republican'} +${actualMargin.toFixed(1)} pts · ${actualGap.toLocaleString()} votes</b></div><div><span>Ticket baseline margin</span><b>${expectedLeader} +${Math.abs(expectedDem).toFixed(1)} pts · ${expectedGap.toLocaleString()} votes</b></div><div><span>Two-party turnout</span><b>${total.toLocaleString()} votes</b></div></div><div class="source-credit">Actual votes: Alabama Secretary of State. Candidate-name display may use archived Wikipedia pages only as a secondary cross-check; official totals control.</div>${baselineContext(x,total)}</div>`}
/* Raw gap minus the structural expectation equals WAR, drawn as three bars on one axis. */
function waterfall(x){
  if(x.rawGap==null||x.predictedStructuralGap==null)return '';
  const steps=[['Raw legislative-minus-ticket gap',0,x.rawGap],['Minus the structural expectation',x.rawGap,x.rawGap-x.predictedStructuralGap],['WAR',0,x.war]];
  const values=steps.flat().filter(v=>typeof v==='number'),lo=Math.min(0,...values),hi=Math.max(0,...values),pad=(hi-lo)*.1+1,a=lo-pad,b=hi+pad,W=panelWidth(),L=Math.min(200,W*.45),X=v=>L+(W-L-46)*(v-a)/(b-a),sign=x.party==='D'?1:-1;
  return `<h4>How the score is built</h4><figure class="waterfall"><svg viewBox="0 0 ${W} ${steps.length*28+12}" role="img" aria-label="Raw gap ${fmt(x.rawGap)}, structural expectation ${fmt(x.predictedStructuralGap)}, WAR ${fmt(x.war)}"><line x1="${X(0)}" x2="${X(0)}" y1="0" y2="${steps.length*28+12}" stroke="var(--ink)" stroke-dasharray="2 2"/>${steps.map(([label,from,to],i)=>{const y=i*28+6,v=to-from;return `<text x="0" y="${y+14}" font-size="11" ${i===2?'font-weight="700"':''} fill="var(--ink)">${label}</text><rect x="${Math.min(X(from),X(to)).toFixed(1)}" y="${y+4}" width="${Math.max(1.5,Math.abs(X(to)-X(from))).toFixed(1)}" height="16" fill="${warColor(sign*(i===1?-x.predictedStructuralGap:to-from)>=0?18:-18)}"/><text x="${(Math.max(X(from),X(to))+4).toFixed(1)}" y="${y+16}" font-size="11" fill="var(--muted)">${i===1?fmt(-x.predictedStructuralGap):fmt(to)}</text>`}).join('')}</svg><figcaption class="note">Candidate-oriented margin points. Purple bars help the Democrat's side of the race, orange bars the Republican's.</figcaption></figure>`;
}
function detail(x){
  const box=$('#detail');
  if(!x&&selected!=null){
    const d=DATA[active];box.classList.add('is-open');
    box.innerHTML=`<button class="close-detail" id="closeDetail" aria-label="Close and return to the cycle overview">×</button><div class="panel-kicker">${d.cycle} ${chamberLabel(d.chamber)} · District ${selected}</div><h3>No WAR score</h3><div class="warning"><b>No contested D–R race on record.</b> ${esc(d.districtStatus[String(selected)]||'This district has no strict contested Democratic-versus-Republican general election in this cycle.')} Missing WAR is not zero.</div>`;
    $('#closeDetail').addEventListener('click',()=>{const was=selected;selected=null;selectedParty=null;render();restoreFocus(was,active)});
    return;
  }
  if(!x){box.classList.remove('is-open');box.innerHTML=overview();rove($$('.swarm circle'),c=>{origin='swarm';const district=+c.dataset.district,w=DATA[active].winners[district];selected=district;selectedParty=w?w.party:null;render(true)});return}
  box.classList.add('is-open');
  const history=allCandidates().filter(c=>c.personId&&c.personId===x.personId).sort((a,b)=>a.cycle-b.cycle),scope=x.scoringScope==='post2016_southern_model_backcast'?'Fixed 2018-24 reference model':'Published same-cycle residual',historyHtml=history.length>1?`<div class="decomp"><div class="decomp-title">Resolved election history</div>${history.map(c=>`<div class="stat"><span>${c.cycle} ${c.chamber} ${c.district}</span><b>WAR ${fmt(c.war)}</b></div>`).join('')}</div>`:'';
  box.innerHTML=`<button class="close-detail" id="closeDetail" aria-label="Close race and return to the cycle overview">×</button><div class="panel-kicker">${DATA[active].cycle} ${chamberLabel(DATA[active].chamber)} · District ${x.district}</div><h3>${esc(displayName(x.candidate))}</h3><div class="party ${x.party}">${x.party==='D'?'Democratic':'Republican'}${x.incumbent?' · Incumbent':''}${x.winner?' · Won':''}</div><div class="war-number" style="color:${warColor((x.party==='D'?1:-1)*Math.sign(x.war)*20)}">${fmt(x.war)}</div><div class="war-label">Alabama WAR · ${x.percentile.toFixed(0)}th percentile of this election</div><div class="distribution" aria-hidden="true"><i style="left:${x.percentile}%"></i><div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div>${waterfall(x)}${raceBox(x)}<div class="decomp"><div class="decomp-title">Residual decomposition</div><div class="stat"><span>Raw legislative-minus-ticket gap</span><b>${fmt(x.rawGap)}</b></div><div class="stat"><span>Fitted structural expectation</span><b>${fmt(x.predictedStructuralGap)}</b></div><div class="stat"><span>Lag component</span><b>${fmt(x.lagComponent)}</b></div><div class="stat"><span>Scoring method</span><b>${scope}</b></div><div class="stat"><span>Lag context</span><b>${x.lagContextAvailable?'Observed':'Unavailable; zero-valued model encoding'}</b></div></div><div class="decomp"><div class="decomp-title">Source quality</div><div class="quality-grid"><div><span>Baseline method</span><b>${esc(x.baselineMethod||'Unavailable')}</b></div><div><span>Identity linkage</span><b>${esc(x.identityStatus)}</b></div><div><span>Previous president</span><b>${fmtMaybe(x.priorPres)}</b></div><div><span>Votes</span><b>${x.votes.toLocaleString()}</b></div></div></div>${historyHtml}<div class="explain">${x.war>=0?'This candidate finished ahead of':'This candidate finished behind'} the fitted structural expectation by <b>${Math.abs(x.war).toFixed(1)} margin points</b>. ${x.scoringScope==='post2016_southern_model_backcast'?'This is a backward application of a model trained only on post-2016 Southern races.':'This is the published modern same-cycle residual.'}</div>`;
  $('#closeDetail').addEventListener('click',()=>{const was=selected;selected=null;selectedParty=null;render();restoreFocus(was,active)});
}

/* Table */
function warCell(x){const v=x.war,B=40,X=t=>45+43*Math.max(-B,Math.min(B,t))/B,dem=(x.party==='D'?1:-1)*v;return `<div class="war-cell"><b>${fmt(v)}</b><svg viewBox="0 0 90 12" aria-hidden="true"><line x1="45" x2="45" y1="0" y2="12" stroke="var(--ink)"/><rect x="${Math.min(45,X(v)).toFixed(1)}" y="2" width="${Math.abs(X(v)-45).toFixed(1)}" height="8" fill="${warColor(dem>=0?18:-18)}"/></svg></div>`}
function renderRows(){const d=DATA[active],scope=$('#scope-filter').value,q=$('#candidate-search').value.toLowerCase(),party=$('#party-filter').value,outcome=$('#outcome-filter').value,source=scope==='all'?allCandidates():d.candidates.map(x=>({...x,section:active,cycle:d.cycle,chamber:d.chamber})),rows=source.filter(x=>(party==='all'||x.party===party)&&(outcome==='all'||(outcome==='winner'&&x.winner)||(outcome==='incumbent'&&x.incumbent))&&(!q||displayName(x.candidate).toLowerCase().includes(q)||String(x.district)===q||String(x.cycle)===q||`${x.chamber} ${x.district}`.includes(q))).sort((a,b)=>{let A=a[sortKey],B=b[sortKey];return(typeof A==='string'?A.localeCompare(B):(A??-9999)-(B??-9999))*sortDir});$('#rows').innerHTML=rows.map(x=>`<tr tabindex="0" data-section="${x.section}" data-district="${x.district}" data-party="${x.party}"><td>${x.cycle} ${x.chamber==='house'?'H':'S'}</td><td>${x.district}</td><td class="cand"><i class="party-dot ${x.party}"></i>${esc(displayName(x.candidate))}${x.winner?' <small>✓<span class="sr-only"> winner</span></small>':''}</td><td class="num">${warCell(x)}</td><td class="num">${fmt(x.rawGap)}</td><td class="num">${fmt(x.predictedStructuralGap)}</td><td class="num">${fmt(x.lagComponent)}</td><td>${x.scoringScope==='post2016_southern_model_backcast'?'Fixed 2018-24 reference':'Published same-cycle'}</td><td class="num">${fmt(x.cycleTopTicket)}</td><td class="num">${fmt(x.margin)}</td><td class="num">${x.votes.toLocaleString()}</td></tr>`).join('');$$('#rows tr').forEach(row=>{row.onclick=()=>selectCandidate(row.dataset.section,row.dataset.district,row.dataset.party);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.onclick()}};row.onpointerenter=()=>{if(row.dataset.section===active)linkHover(+row.dataset.district)};row.onpointerleave=()=>linkHover(null)});$$('th[data-sort]').forEach(th=>th.setAttribute('aria-sort',th.dataset.sort===sortKey?(sortDir>0?'ascending':'descending'):'none'))}
function selectCandidate(section,district,party){noteOrigin();active=section;selected=Number(district);selectedParty=party;render(true)}

function render(scroll=false){
  renderControls();renderMap();detail(currentSelectedCandidate());renderRows();syncUrl();
  if(scroll&&selected){if(innerWidth<761)$('#closeDetail')?.focus({preventScroll:true});else{$('#explorer').scrollIntoView({behavior:reduceMotion()?'auto':'smooth',block:'start'});if(origin!=='map')$('#closeDetail')?.focus({preventScroll:true})}}
}
function bind(){
  $$('[data-chamber]').forEach(b=>b.addEventListener('click',()=>setChamber(b.dataset.chamber)));
  $('#cycleRange').addEventListener('input',e=>setCycle(CYCLES[+e.target.value]));
  $('#play').addEventListener('click',togglePlay);
  $('#highlight').addEventListener('change',e=>{highlight=+e.target.value;siteMap?.refresh()});
  $$('[data-map-mode]').forEach(b=>b.addEventListener('click',()=>{mapMode=b.dataset.mapMode;render()}));
  $$('[data-view]').forEach(b=>b.addEventListener('click',()=>{view=b.dataset.view;siteMap.setView(view);renderControls();syncUrl()}));
  $$('th[data-sort]').forEach(th=>{th.tabIndex=0;const go=()=>{const k=th.dataset.sort;sortDir=sortKey===k?-sortDir:(k==='candidate'?1:-1);sortKey=k;renderRows()};th.onclick=go;th.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}}});
  ['candidate-search','scope-filter','party-filter','outcome-filter'].forEach(id=>$('#'+id).oninput=renderRows);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&selected){const was=selected;selected=null;selectedParty=null;render();restoreFocus(was,active)}});
  let resizeTimer=null,lastWidth=innerWidth;
  addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(innerWidth===lastWidth)return;lastWidth=innerWidth;detail(currentSelectedCandidate())},200)});
}
readUrl();bind();render();
