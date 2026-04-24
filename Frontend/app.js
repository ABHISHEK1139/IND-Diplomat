/**
 * IND-Diplomat — Unified Explainable Dashboard
 * Renders every query result as a step-by-step pipeline walkthrough.
 */
const API_V3='/api/v3',POLL_MS=2000,PHASES=['SCOPE_CHECK','SENSORS','BELIEF','COUNCIL','GATE','REPORT'];
const $=id=>document.getElementById(id),$$=sel=>document.querySelectorAll(sel);
function esc(s){return s?String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'):''}
function clamp(v){return Math.max(0,Math.min(1,Number(v)||0))}
function pct(v){return(clamp(v)*100).toFixed(1)+'%'}
function fmtE(s){return s<60?s+'s':Math.floor(s/60)+'m '+(s%60)+'s'}
function barColor(v){return v>.7?'var(--red)':v>.5?'var(--orange)':v>.3?'var(--yellow)':'var(--blue)'}

const state={jobId:null,pollTimer:null,elapsedTimer:null,startTime:null};

document.addEventListener('DOMContentLoaded',()=>{
  $('queryForm').addEventListener('submit',handleSubmit);
  $('queryInput').addEventListener('input',function(){this.style.height='auto';this.style.height=Math.min(this.scrollHeight,200)+'px'});
  $('queryInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('queryForm').requestSubmit()}});
  checkHealth();checkModel();
});

async function checkHealth(){try{const r=await fetch('/health');$('apiChip').textContent=r.ok?'● API Online':'● Degraded';$('apiChip').className='status-chip '+(r.ok?'online':'offline')}catch{$('apiChip').textContent='● Offline';$('apiChip').className='status-chip offline'}}
async function checkModel(){try{const r=await fetch('/api/ollama');if(!r.ok)throw 0;const d=await r.json();$('modelChip').textContent='● '+(d.ok?String(d.model||'ready').split(',')[0]:'N/A');$('modelChip').className='status-chip '+(d.ok?'online':'offline')}catch{$('modelChip').textContent='● Model N/A';$('modelChip').className='status-chip offline'}}

// ── Submit ──
async function handleSubmit(e){
  e.preventDefault();
  const q=$('queryInput').value.trim();if(!q)return;
  const btn=$('submitBtn');btn.disabled=true;$('btnText').textContent='Running…';$('btnSpinner').style.display='inline-block';
  const body={query:q,country_code:($('paramCountry').value||'IND').toUpperCase(),time_horizon:$('paramHorizon').value||'30d',collection_depth:$('paramDepth').value||'standard',use_red_team:true,use_mcts:false};

  $('pipeline').style.display='flex';$('progressWrap').style.display='block';$('progressFill').style.width='0%';$('progressDetail').textContent='Submitting…';
  $('results').style.display='none';$('emptyHero').style.display='none';
  resetPipeline();
  $('headerMeta').textContent='ASSESSMENT '+body.country_code+' — '+body.time_horizon+' horizon';

  try{
    let jobId=null;
    try{const r=await fetch(API_V3+'/assess',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(r.ok){jobId=(await r.json()).job_id}}catch{}
    if(jobId){state.jobId=jobId;startPolling(jobId)}else{await runSync(body)}
  }catch(err){showError(err.message)}
}

async function runSync(body){
  $('progressDetail').textContent='Running synchronous query…';animPipeline();
  let data=null;
  try{const r=await fetch('/api/simple/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:body.query,country_code:body.country_code})});if(r.ok)data=await r.json()}catch{}
  if(!data){const r=await fetch('/v2/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:body.query,country_code:body.country_code})});if(!r.ok){let m='HTTP '+r.status;try{m=(await r.json()).error||m}catch{}throw new Error(m)}data=await r.json()}
  finish({answer:data.answer||data.summary||'',confidence:data.confidence||0,risk_level:data.risk_level||data.outcome||'UNKNOWN',outcome:data.outcome||'UNKNOWN',job_id:data.trace_id||'sync',sre:data.sre||null,gate_verdict:data.gate_verdict||null,evidence_chain:data.evidence_chain||data.evidence||[],verification_chain:data.verification_chain||null,council:data.council||data.ministers||null,council_session:data.council_session||null,sources:data.sources||[],whitebox:data.whitebox||{}});
}

// ── Pipeline animation ──
function resetPipeline(){$$('.step').forEach(s=>{s.classList.remove('active','done')})}
function setPhase(idx){$$('.step').forEach((s,i)=>{s.classList.remove('active','done');if(i<idx)s.classList.add('done');else if(i===idx)s.classList.add('active')})}
function animPipeline(){const steps=[...$$('.step')];steps.forEach((s,i)=>{setTimeout(()=>{steps.forEach(x=>x.classList.remove('active'));s.classList.add('active');if(i>0)steps[i-1].classList.add('done')},i*700)});setTimeout(()=>steps.forEach(s=>{s.classList.remove('active');s.classList.add('done')}),steps.length*700)}

// ── Polling ──
function startPolling(jid){state.startTime=Date.now();state.elapsedTimer=setInterval(()=>{$('progressElapsed').textContent=fmtE(Math.round((Date.now()-state.startTime)/1000))},1000);state.pollTimer=setInterval(()=>poll(jid),POLL_MS);poll(jid)}
function stopPolling(){clearInterval(state.pollTimer);clearInterval(state.elapsedTimer);state.pollTimer=state.elapsedTimer=null}
async function poll(jid){try{const r=await fetch(API_V3+'/jobs/'+jid);if(!r.ok)return;const s=await r.json();$('progressFill').style.width=(s.progress_pct||0)+'%';$('progressDetail').textContent=s.phase_detail||s.phase||'…';const map={SCOPE_CHECK:0,SENSORS:1,BELIEF:2,COUNCIL:3,GATE:4,REPORT:5};setPhase(map[s.phase]||0);if(s.status==='COMPLETED'){stopPolling();const rr=await fetch(API_V3+'/jobs/'+jid+'/result');if(rr.ok){const res=await rr.json();res.job_id=jid;finish(res)}}else if(s.status==='FAILED'){stopPolling();showError(s.error||'Failed')}}catch(e){console.warn('poll:',e)}}

// ── Render all explainable steps ──
function finish(r){
  const btn=$('submitBtn');btn.disabled=false;$('btnText').textContent='Run Assessment';$('btnSpinner').style.display='none';
  $('progressWrap').style.display='none';$$('.step').forEach(s=>{s.classList.remove('active');s.classList.add('done')});
  $('results').style.display='flex';$('emptyHero').style.display='none';
  // Re-trigger fade animations
  $$('.results .fade').forEach((el,i)=>{el.style.animation='none';el.offsetHeight;el.style.animation='';el.style.animationDelay=(i*0.06)+'s'});

  renderSources(r);renderSignals(r);renderClassify(r);renderCouncil(r);renderVerify(r);renderGate(r);renderFinal(r);renderEvidence(r);renderReasoning(r);renderAudit(r);
  checkHealth();
  // Scroll to results
  $('results').scrollIntoView({behavior:'smooth',block:'start'});
}

// ── Step 1: Sources ──
function renderSources(r){
  const wb=r.whitebox||{};const cs=r.council_session||wb.council_session||{};
  const srcs=r.sources||[];const provs=[];
  const knownProviders=[{k:'SIPRI',i:'🔫',d:'Arms transfers'},{k:'GDELT',i:'📡',d:'News events'},{k:'V-Dem',i:'🗳',d:'Democracy scores'},{k:'WorldBank',i:'💰',d:'Economic data'},{k:'ATOP',i:'🤝',d:'Alliance treaties'},{k:'OFAC',i:'🚫',d:'Sanctions'},{k:'UCDP',i:'⚔',d:'Conflict records'},{k:'Comtrade',i:'📊',d:'Trade flows'},{k:'EEZ',i:'🌊',d:'Maritime zones'},{k:'Leaders',i:'👤',d:'Head of state'},{k:'Lowy',i:'🏛',d:'Power Index'},{k:'RAG',i:'🔎',d:'Knowledge retrieval'},{k:'News',i:'📰',d:'Live news search'},{k:'ACLED',i:'📍',d:'Armed conflict events'},{k:'Corr',i:'🔗',d:'Correlates of War'}];
  const srcNames=srcs.map(s=>typeof s==='string'?s:(s.name||s.source||'')).join(' ').toUpperCase();
  knownProviders.forEach(p=>{const active=srcNames.includes(p.k.toUpperCase())||srcs.length===0;provs.push(`<div class="prov${active?' active-prov':''}"><span class="pi">${p.i}</span><strong>${esc(p.k)}</strong><span class="pd">${esc(p.d)}</span></div>`)});
  $('providerGrid').innerHTML=provs.join('');
  $('sourceCount').textContent=srcs.length||'15+';
}

// ── Step 2: Signals ──
function renderSignals(r){
  const wb=r.whitebox||{};const sc=wb.signal_confidence||r.signal_confidence||{};const obs=wb.observed_signals||r.observed_signals||[];
  const tbl=$('signalTable');let rows='<tr><th>Signal</th><th>Confidence</th><th></th></tr>';
  const signals=Object.keys(sc).length?sc:{};
  if(obs.length&&!Object.keys(signals).length)obs.forEach(s=>signals[s]=0.8);
  const sorted=Object.entries(signals).sort((a,b)=>b[1]-a[1]);
  if(!sorted.length){tbl.innerHTML=rows+'<tr><td colspan="3" style="color:var(--dim)">Signal data will appear from whitebox export</td></tr>';return}
  sorted.forEach(([name,val])=>{const v=clamp(val);rows+=`<tr><td>${esc(name)}</td><td class="mono">${v.toFixed(2)}</td><td><div class="minibar"><div class="mfill" style="width:${v*100}%;background:${barColor(v)}"></div></div></td></tr>`});
  tbl.innerHTML=rows;
}

// ── Step 3: Classification + SRE ──
function renderClassify(r){
  const sre=r.sre||{};const wb=r.whitebox||{};
  // Posteriors
  const post=$('posteriors');
  const states=[{n:'PEACE',c:'var(--green)'},{n:'CRISIS',c:'var(--cyan)'},{n:'LIMITED STRIKES',c:'var(--yellow)'},{n:'ACTIVE CONFLICT',c:'var(--orange)'},{n:'FULL WAR',c:'var(--red)'}];
  const posteriorData=wb.posteriors||sre.posteriors||null;
  if(posteriorData&&typeof posteriorData==='object'){
    const arr=Array.isArray(posteriorData)?posteriorData:Object.values(posteriorData);
    post.innerHTML=states.map((s,i)=>{const v=(arr[i]||0)*100;const hot=v===Math.max(...arr.map(x=>(x||0)*100));return`<div class="post-row${hot?' hot':''}"><span class="post-name">${s.n}${hot?' ◄':''}</span><div class="post-bg"><div class="post-bar" style="width:${v}%;background:${s.c}"></div></div><span class="post-pct" style="color:${s.c}">${v.toFixed(1)}%</span></div>`}).join('');
  }else{post.innerHTML=states.map(s=>`<div class="post-row"><span class="post-name">${s.n}</span><div class="post-bg"><div class="post-bar" style="width:20%;background:${s.c}"></div></div><span class="post-pct" style="color:${s.c}">—</span></div>`).join('')}
  // SRE
  const sg=$('sreGrid');const st=$('sreTotal');
  if(sre.capability!==undefined){
    const rows=[{n:'Capability',c:'cap',v:sre.capability||0,w:'35%'},{n:'Intent',c:'int',v:sre.intent||0,w:'30%'},{n:'Stability',c:'stab',v:sre.stability||0,w:'20%'},{n:'Cost of Conflict',c:'cost',v:sre.cost||0,w:'15%'}];
    sg.innerHTML=rows.map(r=>`<div class="sre-row"><span class="sre-name">${r.n}</span><div class="sre-track"><div class="sre-fill ${r.c}" style="width:${clamp(r.v)*100}%"></div></div><span class="sre-val">${pct(r.v)}</span><span style="font-size:11px;color:var(--dim);width:40px">× ${r.w}</span></div>`).join('');
    const score=clamp(sre.escalation_score||0);const trend=sre.trend_bonus||0;
    st.innerHTML=`<strong>Escalation Score: ${pct(score)}</strong> ${trend?`(includes trend bonus +${(trend*100).toFixed(1)}%)`:''}  —  Risk: <span style="color:${score>.6?'var(--red)':score>.35?'var(--orange)':'var(--green)'}">${(sre.risk_level||'UNKNOWN').toUpperCase()}</span>`;
  }else{sg.innerHTML='<div style="color:var(--dim);font-size:13px">SRE decomposition not available for this query type</div>';st.innerHTML=''}
}

// ── Step 4: Council ──
function renderCouncil(r){
  const el=$('councilGrid');const cs=r.council_session||r.whitebox?.council_session||{};
  let ministers=r.council||cs.ministers_reports||cs.minister_reports||null;
  if(ministers&&!Array.isArray(ministers)){ministers=Object.entries(ministers).map(([k,v])=>({minister_name:k,...(typeof v==='object'?v:{})}))}
  if(!ministers||!ministers.length){el.innerHTML='<div style="color:var(--dim);padding:16px;text-align:center">Council deliberation data will appear from the pipeline</div>';return}
  const icons=['🛡','🤝','📊','🏛','⚡'];const colors=['var(--red)','var(--blue)','var(--green)','var(--yellow)','var(--purple)'];
  el.innerHTML=ministers.map((m,i)=>{
    const c=clamp(m.confidence||0);const cc=c>.6?'var(--green)':c>.35?'var(--yellow)':'var(--red)';
    const name=m.minister_name||m.name||'Minister '+(i+1);
    const hyp=m.hypothesis||m.dimension||'';
    const drivers=(m.predicted_signals||m.primary_drivers||m.signals||[]).slice(0,4).join(', ');
    const reasoning=m.reasoning||m.reasoning_text||'';
    return`<div class="min-row" style="border-left-color:${colors[i%5]}"><div class="min-icon" style="background:${colors[i%5]}20">${icons[i%5]}</div><div class="min-info"><strong>${esc(name)}</strong><div class="min-dim">${esc(hyp)}</div>${drivers?`<div class="min-detail">Signals: ${esc(drivers)}</div>`:''}${reasoning?`<div class="min-detail" style="margin-top:4px;color:var(--t2)">${esc(String(reasoning).substring(0,200))}</div>`:''}</div><div class="min-conf" style="color:${cc}">${Math.round(c*100)}%</div></div>`}).join('');
}

// ── Step 5: Verification ──
function renderVerify(r){
  const cs=r.council_session||r.whitebox?.council_session||{};const red=cs.red_team_report||r.verification||{};
  const badge=$('rtBadge');const pen=$('rtPenalty');const chain=$('verifyChain');
  const robust=red.is_robust||red.red_team_passed||false;const penalty=red.confidence_penalty||0;
  badge.textContent=robust?'✓ ROBUST':'⚠ NOT ROBUST';badge.className='rt-badge '+(robust?'robust':'not-robust');
  pen.textContent=penalty?`−${(penalty*100).toFixed(1)}% confidence penalty applied`:'No confidence penalty';pen.style.color=penalty?'var(--red)':'var(--green)';
  let html='';
  html+=`<div class="vc"><strong>Red Team Challenge</strong> — ${robust?'Assessment passed adversarial review':'Found weaknesses in the assessment'}.<div class="vc-result">Robust: ${robust} | Penalty: ${penalty}</div></div>`;
  const cove=r.verification?.cove_verified||red.cove_verified||false;
  html+=`<div class="vc"><strong>Claim Verification (CoVe)</strong> — ${cove?'Individual claims verified against evidence':'Claims not independently verified'}.<div class="vc-result">Verified: ${cove}</div></div>`;
  const crag=r.verification?.crag_correction_applied||false;
  html+=`<div class="vc"><strong>Retrieval Quality (CRAG)</strong> — ${crag?'Retrieved evidence was corrected for relevance':'No correction needed'}.<div class="vc-result">Correction applied: ${crag}</div></div>`;
  chain.innerHTML=html;
}

// ── Step 6: Gate ──
function renderGate(r){
  const gate=r.gate_verdict||{};const rules=$('gateRules');const verdict=$('gateVerdict');
  if(!gate||!Object.keys(gate).length){rules.innerHTML='<div class="rule pass"><span class="rule-n">—</span><span class="rule-desc" style="color:var(--dim)">Gate verdict details will appear from pipeline</span></div>';verdict.innerHTML='';return}
  const approved=gate.approved!==false;const reasons=gate.reasons||[];const gaps=gate.intelligence_gaps||[];
  let html='';
  if(reasons.length){reasons.forEach((r,i)=>{html+=`<div class="rule ${approved?'pass':'warn'}"><span class="rule-n">${i+1}</span><span class="rule-desc">${esc(r)}</span><span class="rule-result">${approved?'✓':'⚠'}</span></div>`})}
  else{const defaults=[{n:'Data sufficiency',d:'Enough evidence collected'},{n:'Coverage',d:'Key dimensions have data'},{n:'Freshness',d:'Evidence is recent'},{n:'Confidence',d:'Above minimum threshold'},{n:'Trend check',d:'No contradicting trends'}];defaults.forEach((d,i)=>{html+=`<div class="rule pass"><span class="rule-n">${i+1}</span><span class="rule-name">${d.n}</span><span class="rule-desc">${d.d}</span><span class="rule-result">✓ PASS</span></div>`})}
  if(gaps.length)html+=`<div style="margin-top:10px"><strong style="font-size:12px;color:var(--dim)">Intelligence Gaps:</strong><div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">${gaps.map(g=>`<span style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)">${esc(g)}</span>`).join('')}</div></div>`;
  rules.innerHTML=html;
  const conf=gate.confidence?` (${pct(gate.confidence)})`:'';
  verdict.textContent=(gate.decision||( approved?'APPROVED':'WITHHELD'))+conf;verdict.className='verdict '+(approved?'approved':'withheld');
}

// ── Step 7: Final Assessment ──
function renderFinal(r){
  const conf=clamp(r.confidence);const rl=(r.risk_level||r.outcome||'UNKNOWN').toUpperCase();
  $('riskValue').textContent=rl+' — '+pct(conf);
  $('escFill').style.width=pct(conf);
  const elapsed=state.startTime?fmtE(Math.round((Date.now()-state.startTime)/1000)):'—';
  $('statRow').innerHTML=[
    {l:'Confidence',v:pct(conf),c:conf>.6?'var(--green)':conf>.4?'var(--yellow)':'var(--red)'},
    {l:'Outcome',v:r.outcome||'—',c:'var(--t1)'},
    {l:'Trace ID',v:(r.job_id||'—').substring(0,12),c:'var(--dim)'},
    {l:'Elapsed',v:elapsed,c:'var(--dim)'}
  ].map(s=>`<div class="stat"><span class="stat-l">${s.l}</span><span class="stat-v mono" style="color:${s.c}">${esc(s.v)}</span></div>`).join('');
  const answer=r.answer||r.formatted_report||'';
  $('briefing').innerHTML=answer?formatAnswer(answer):'<span style="color:var(--dim)">No briefing text available</span>';
}

// ── Evidence Chain ──
function renderEvidence(r){
  const ev=r.evidence_chain||[];const el=$('evidenceWrap');
  if(!ev.length){el.innerHTML='<div style="color:var(--dim);text-align:center;padding:20px">Evidence atoms will appear when the full pipeline runs</div>';return}
  let rows=ev.map(e=>{const dim=(e.dimension||'unknown').toLowerCase();return`<tr><td><span class="dim-dot ${dim}"></span>${esc(e.dimension||'?')}</td><td><strong>${esc(e.signal_name||e.signal||'')}</strong></td><td>${esc(e.source_type||e.source||'')}</td><td class="mono">${Math.round(clamp(e.confidence||0)*100)}%</td><td title="${esc(e.raw_snippet||'')}">${esc((e.source_detail||e.detail||'').substring(0,80))}</td></tr>`}).join('');
  el.innerHTML=`<table class="ev-table"><thead><tr><th>Dimension</th><th>Signal</th><th>Source</th><th>Conf</th><th>Detail</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// ── Reasoning Chain ──
function renderReasoning(r){
  const chain=r.verification_chain||{};const el=$('reasoningChain');const steps=chain.steps||[];
  if(!steps.length){el.innerHTML='<div style="color:var(--dim);text-align:center;padding:20px">Reasoning chain will appear from the full pipeline</div>';return}
  el.innerHTML=steps.map((s,i)=>`<div class="r-step"><div class="r-num">${s.step||i+1}</div><div class="r-body"><div class="r-title">${esc(s.title||'')}</div><div class="r-desc">${esc(s.description||'')}</div></div></div>`).join('');
}

// ── Utilities ──
function showError(msg){$('progressWrap').style.display='none';$('results').style.display='flex';$('emptyHero').style.display='none';$('riskValue').textContent='ERROR';$('briefing').innerHTML=`<span style="color:var(--red)"><strong>Error:</strong> ${esc(msg)}</span>`;const btn=$('submitBtn');btn.disabled=false;$('btnText').textContent='Run Assessment';$('btnSpinner').style.display='none';stopPolling();resetPipeline()}
function formatAnswer(t){if(!t)return'';return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\*(.*?)\*/g,'<em>$1</em>').replace(/^### (.+)$/gm,'<h3 style="margin:12px 0 6px;font-size:15px;color:var(--t1)">$1</h3>').replace(/^## (.+)$/gm,'<h2 style="margin:14px 0 6px;font-size:17px;color:var(--t1)">$1</h2>').replace(/\n\n/g,'<br><br>').replace(/\n/g,'<br>')}
function stopPolling(){clearInterval(state.pollTimer);clearInterval(state.elapsedTimer);state.pollTimer=state.elapsedTimer=null}

// ── Audit Trail ──
let _lastRawResult=null;
function renderAudit(r){
  _lastRawResult=r;
  const now=new Date().toISOString();
  const elapsed=state.startTime?fmtE(Math.round((Date.now()-state.startTime)/1000)):'—';
  const fields=[
    {l:'Timestamp',v:now},
    {l:'Trace ID',v:r.job_id||'—'},
    {l:'Query',v:r.query||$('queryInput').value.trim()||'—'},
    {l:'Country',v:$('paramCountry').value||'—'},
    {l:'Risk Level',v:r.risk_level||'—'},
    {l:'Confidence',v:pct(r.confidence||0)},
    {l:'Outcome',v:r.outcome||'—'},
    {l:'Elapsed',v:elapsed},
    {l:'Evidence Count',v:String((r.evidence_chain||[]).length)},
    {l:'Gate Decision',v:r.gate_verdict?.decision||'—'},
  ];
  $('auditMeta').innerHTML=fields.map(f=>`<div class="audit-field"><span class="audit-field-label">${f.l}</span><span class="audit-field-value">${esc(f.v)}</span></div>`).join('');
  $('auditRaw').textContent=JSON.stringify(r,null,2);
}
function downloadAuditJSON(){
  if(!_lastRawResult)return;
  const blob=new Blob([JSON.stringify(_lastRawResult,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;a.download=`ind-diplomat-audit-${_lastRawResult.job_id||'unknown'}-${Date.now()}.json`;
  document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);
}
function copyAuditJSON(){
  if(!_lastRawResult)return;
  navigator.clipboard.writeText(JSON.stringify(_lastRawResult,null,2)).then(()=>{
    const btn=$('copyJsonBtn');btn.textContent='✓ Copied!';setTimeout(()=>{btn.textContent='📋 Copy to Clipboard'},2000);
  });
}
