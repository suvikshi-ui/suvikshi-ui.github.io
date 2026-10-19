// BrickFlow · Indian Stock Market (Nifty 100) renderer. Data: india/data.json written by the scanner (NSE data only).
(function(){
const BASE='india/';
const SOURCES=[BASE+'data.json','https://raw.githubusercontent.com/suvikshi-ui/suvikshi-ui.github.io/main/trx/india/data.json'];
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const fd=d=>{if(!d)return '–';const [y,m,dd]=d.split('-');return (+dd)+' '+MON[+m-1]+' '+y};
const num=v=>{if(v===null||v===undefined||v==='')return '–';return (+v).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})};
const short=c=>String(c).replace('NSE:','');
const BC={'DARK GREEN':'dg','LIGHT GREEN':'lg','DARK RED':'dr','LIGHT RED':'lr','RED':'hr','GREEN':'hg'};
const tc=s=>String(s).toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());
const badge=s=>s?`<span class="b ${BC[s]||''}">${tc(s)}</span>`:'–';
const istNow=()=>{const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(new Date());const g=t=>p.find(x=>x.type===t).value;return {d:`${g('year')}-${g('month')}-${g('day')}`,hm:(+g('hour'))*60+(+g('minute'))}};
// NSE cash market closes 15:30 IST; a brick dated today is still forming before that
const isForming=d=>{const n=istNow();return d>n.d||(d===n.d&&n.hm<930)};
const stBadge=d=>isForming(d)?'<span class="b form" title="Today\'s NSE session has not closed yet; the brick can still change">Forming (session open)</span>':'<span class="b conf">Confirmed</span>';
const ist=iso=>new Date(iso).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true})+' IST';
const key=m=>m.coin+'|'+m.date+'|'+m.side+'|'+m.brick_close;
let seen=null; try{seen=JSON.parse(localStorage.getItem('bfSeenIN')||'null')}catch(e){}
let newKeys=new Set(), lastScan=null, DATA=null;
// Follow-through tag (label only; every setup stays visible)
const sgn=v=>v===null||v===undefined?'–':((+v)>0?'+':'')+(+v).toFixed(2)+'%';
const hasFT=m=>typeof m.strong==='boolean';
const ftBadge=m=>!hasFT(m)?'':(m.strong?'<span class="b strong" title="Meets the follow-through rule on the setup day (see the note above)">Strong</span>':'<span class="b noft" title="Does not meet the follow-through rule on the setup day (see the note above)">No follow-through</span>');
const ftInfo=m=>!hasFT(m)?'–':`gap ${sgn(m.gap_pct)} · ${m.bricks_that_day} brick${m.bricks_that_day===1?'':'s'} that day`;
let strongOnly=false;
const cap='Chart drawn by BrickFlow from NSE data (charting.nseindia.com daily OHLC reconciled to the NSE bhavcopy; daily Renko ATR14).';

function render(d){
  DATA=d;
  $('i-pending').hidden=true; $('i-live').hidden=false;
  $('i-src').textContent=d.source||'NSE'; $('i-lastScan').textContent=ist(d.last_scan_utc);
  const S=d.summary||[], M=(d.matches||[]).filter(m=>m.date>='2026-01-01').slice().sort((a,b)=>a.date<b.date?1:a.date>b.date?-1:a.coin.localeCompare(b.coin));
  const act=M.filter(m=>m.active), oth=M.filter(m=>!m.active);
  const vis=L=>strongOnly?L.filter(m=>m.strong):L;
  const sr=d.strong_rule||{}, nst=L=>L.filter(m=>m.strong).length;
  const ftn=$('i-ftNote'); if(ftn){ftn.hidden=!M.some(hasFT); const t=$('i-ftRule'), md=String(sr.mode||'or').toLowerCase(), gp=`open gapped at least ${sr.gap_pct??0.5}% in the setup's direction versus the prior NSE close`; if(t)t.textContent=md==='gap_single'?`${gp}, on a day when only one Renko brick formed. Days with 2 or more bricks are not tagged Strong, because in the 2021–2025 re-check those setups failed more often`:`${gp} ${md==='and'?'and':'or'} ${sr.min_bricks??2}+ Renko bricks formed that day`}
  const nb=M.filter(m=>m.side==='BUY').length, ns=M.filter(m=>m.side==='SELL').length;
  // data-quality note
  const ig=d.integrity||{}, su=ig.summary||{}, ex=Object.keys(ig.excluded||{}), wl=su.warn_list||{};
  const pc=(a,b)=>b?(100*a/b).toFixed(2)+'%':'–';
  $('i-dq').innerHTML=`<b>Data quality.</b> Prices come only from NSE: daily OHLC from charting.nseindia.com (history from 2021, back-adjusted for splits, bonuses and rights). Every session is reconciled to the official NSE bhavcopy. Before publishing, an integrity gate checked all ${su.stocks||100} stocks${ig.generated_ist?' ('+esc(ig.generated_ist)+')':''}: <b>${su.pass??'–'} pass, ${su.warn??'–'} flagged, ${su.fail??'–'} excluded</b>. ${su.bhav_sessions_checked?`${Number(su.bhav_sessions_checked).toLocaleString('en-IN')} stock-sessions were compared with the bhavcopy, and ${su.corrected_to_bhavcopy} incomplete chart rows (mostly 5–13 Feb 2026) were replaced with the official values. ${su.unresolved} rows are unresolved.`:''} ${su.tv_days_2026?`As an independent cross-check, TradingView agrees on ${pc(su.tv_ohlc_match,su.tv_days_2026)} of 2026 stock-days.`:''} Zero-volume, OHLC-inconsistent or non-positive rows: 0.
${Object.keys(wl).length?`<br><small><b>Flagged (still scanned):</b> ${Object.entries(wl).map(([k,v])=>`${esc(k)} (${esc(v)})`).join('; ')}. The large single-day moves were checked against the bhavcopy and are real. Demergers (e.g. SIEMENS Apr 2025, TMPV Oct 2025, VEDL Apr 2026) are not back-adjusted by NSE, so they show as real price gaps in the bricks.</small>`:''}
${ex.length?`<br><small><b>Excluded:</b> ${ex.map(esc).join(', ')}.</small>`:''}`;
  const card=m=>{const nw=newKeys.has(key(m)),s=m.side==='SELL';return `<div class="ac ${s?'sellc':'buyc'}" data-ikey="${esc(key(m))}" tabindex="0" role="button">
<div class="top"><span class="coin">${esc(short(m.coin))}</span><span><span class="b sig ${m.side.toLowerCase()}">${m.side}</span> ${ftBadge(m)} ${nw?'<span class="b new">NEW</span>':''}</span></div>
<div class="px">₹${num(m.brick_close)}</div>
<div class="row"><span>Setup brick</span><span><b>${fd(m.date)}</b></span></div>
<div class="row"><span>Status</span><span>${stBadge(m.date)}</span></div>
<div class="row"><span>Hull Suite 55</span><span>${badge(m.hull_color)} ${num(m.mhull)}</span></div>
<div class="row"><span>Histogram</span><span>${badge(m.state_before)} → ${badge(m.state_after)}</span></div>
<div class="row"><span>Follow-through</span><span>${ftInfo(m)}</span></div>
<div class="row"><span>Bricks since</span><span>${m.bricks_since===0?'setup is the latest brick':'+'+m.bricks_since+' in the same direction'}</span></div>
<div class="vw">View chart ›</div></div>`};
  $('i-active').innerHTML=vis(act).length?vis(act).map(card).join(''):'<div class="pending">No active setups right now.</div>';
  $('i-other').innerHTML=vis(oth).map(m=>{const nw=newKeys.has(key(m));return `<tr class="click ${nw?'isnew':''}" data-ikey="${esc(key(m))}"><td data-l="Date"><b>${fd(m.date)}</b> ${nw?'<span class="b new">NEW</span>':''}</td><td data-l="Stock">${esc(short(m.coin))}</td><td data-l="Signal"><span class="b ${m.side.toLowerCase()}">${m.side}</span> ${ftBadge(m)}</td><td data-l="Follow-through"><small>${ftInfo(m)}</small></td><td data-l="Status">${stBadge(m.date)}</td><td data-l="Close">${num(m.brick_close)}</td><td data-l="Hull Suite 55">${badge(m.hull_color)} ${num(m.mhull)}</td><td data-l="Histogram before → after">${badge(m.state_before)} → ${badge(m.state_after)}</td><td data-l=""><span class="lnk">chart ›</span></td></tr>`}).join('')||'<tr><td colspan="9" class="pending">None.</td></tr>';
  const few=S.filter(s=>String(s.status).startsWith('too little')), part=S.filter(s=>String(s.status).startsWith('partial')), errs=Object.keys(d.fetch_errors||{});
  const ord=S.slice().sort((a,b)=>(String(a.status).startsWith('too little')-String(b.status).startsWith('too little'))||((b.buys||0)+(b.sells||0)-(a.buys||0)-(a.sells||0))||a.coin.localeCompare(b.coin));
    const rows=ord.map(s=>{const st=String(s.status),sc=!(st==='ok'||st.startsWith('partial'));let b;
    if(st==='ok')b='<span class="b hg">Full</span>';else if(st.startsWith('partial')){const m=st.match(/from (\d{4}-\d\d-\d\d)/);b=`<span class="b lr">Partial</span> <small>scored from ${m?fd(m[1]):'?'}</small>`}
    else if(st.startsWith('excluded'))b='<span class="b" style="border:1px solid #FCA5A5;color:#B91C1C">Excluded</span>';
    else if(st.startsWith('fetch'))b='<span class="b" style="border:1px solid #CBD5E1;color:#64748B">Fetch error</span>';else b='<span class="b" style="border:1px solid #CBD5E1;color:#64748B">Too little history</span>';
    const g=(short(s.coin) in wl)?' <span class="b" style="border:1px solid #FDE68A;color:#B45309" title="'+esc(wl[short(s.coin)]||'')+'">flagged</span>':'';
    return `<tr class="${s.chart_latest?'click':''}" ${s.chart_latest?`data-istock="${esc(s.coin)}"`:''}><td data-l="Stock"><b>${esc(short(s.coin))}</b>${s.chart_latest?' <span class="lnk">chart</span>':''}</td><td data-l="Data">${b}${g}</td><td data-l="Box (₹)">${num(s.box_size)}</td><td data-l="Bricks 2026">${s.bricks_in_window??'–'}</td><td data-l="Flips">${s.flips??'–'}</td>
<td data-l="BUY">${sc?'–':(s.buys?`<b style="color:#059669">${s.buys}</b>`:0)}</td><td data-l="SELL">${sc?'–':(s.sells?`<b style="color:#DC2626">${s.sells}</b>`:0)}</td>
<td data-l="Latest brick">${fd(s.latest_brick_date)} ${s.latest_brick_color?(s.latest_brick_color==='RED'?"<span class='b dr'>red</span>":"<span class='b dg'>green</span>"):''} ${num(s.latest_close)}${s.latest_brick_date&&isForming(s.latest_brick_date)?' <small>(forming)</small>':''}</td></tr>`}).join('');
  $('i-summary').innerHTML=`<section><h2>Nifty 100 summary (${S.length} stocks)</h2>
<p><small>The same BrickFlow rules on every Nifty 100 stock (NSE EQ series). BrickFlow builds the Renko itself from NSE daily data: traditional, close-based, box = latest daily ATR(14) rounded to ₹0.05, with wicks. Hull Suite 55 and MACD 12/26/9 run on brick closes. Window: 1 Jan 2026 to the latest brick.</small></p>
<div class="cards"><div class="card"><div class="k">Stocks scanned</div><div class="v">${S.length}</div></div>
<div class="card"><div class="k">BUY setups</div><div class="v bu">${nb}</div></div>
<div class="card"><div class="k">SELL setups</div><div class="v s">${ns}</div></div>
<div class="card"><div class="k">Active now</div><div class="v">${act.length}</div></div>
${M.some(hasFT)?`<div class="card"><div class="k">Strong setups</div><div class="v">${nst(M)} <small>of ${M.length}</small></div><small>${M.length-nst(M)} no follow-through</small></div>
<div class="card"><div class="k">Active · strong</div><div class="v">${nst(act)} <small>of ${act.length}</small></div><small>${act.length-nst(act)} no follow-through</small></div>`:''}
<div class="card"><div class="k">Not scorable</div><div class="v">${few.length}</div></div></div>
<div class="note" style="background:#F0FDFA;border-color:#99F6E4;color:#134E4A;margin-bottom:12px">${few.length} stocks are <b>not scorable</b> because their history is too short (Hull/MACD need about 60 bricks to warm up): ${few.map(s=>short(s.coin)).join(', ')||'none'}. ${part.length} stocks have <b>partial history</b>, so they were scored only from the date shown: ${part.map(s=>short(s.coin)).join(', ')||'none'}.${errs.length?` Last scan could not fetch: ${errs.map(short).join(', ')}.`:''}
<br><small>"Forming" means the setup is on today's daily bar and the NSE session (closes 15:30 IST) hasn't ended yet, so the brick can still change. "Confirmed" means the session has closed.</small></div>
<h3>Per-stock summary</h3><div class="tw"><table class="rtable"><thead><tr><th>Stock</th><th>Data</th><th>Box (₹)</th><th>Bricks 2026</th><th>Flips</th><th>BUY</th><th>SELL</th><th>Latest brick</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}
function openModal(views,title){
  const tabs=$('mTabs'); $('mTitle').innerHTML=title; tabs.innerHTML='';
  const show=i=>{const v=views[i];$('mImg').src=v.src;$('mImg').alt=v.label;$('mCap').textContent=v.cap;[...tabs.children].forEach((b,j)=>b.classList.toggle('on',j===i))};
  views.forEach((v,i)=>{const b=document.createElement('button');b.textContent=v.label;b.onclick=()=>show(i);tabs.appendChild(b)});
  tabs.style.display=views.length>1?'flex':'none'; show(0); $('modal').hidden=false; document.body.style.overflow='hidden';
}
function openSetup(k){
  if(!DATA)return; const m=(DATA.matches||[]).find(x=>key(x)===k); if(!m)return;
  const s=(DATA.summary||[]).find(x=>x.coin===m.coin)||{}, bust='?v='+encodeURIComponent(DATA.last_change_utc||''), v=[];
  if(m.chart)v.push({label:'Setup chart',src:BASE+m.chart+bust,cap});
  if(s.chart_latest)v.push({label:'Latest chart',src:BASE+s.chart_latest+bust,cap});
  if(v.length)openModal(v,`${esc(short(m.coin))} · <span class="b ${m.side.toLowerCase()}">${m.side}</span> ${fd(m.date)} · close ₹${num(m.brick_close)} · ${stBadge(m.date)}${hasFT(m)?` · ${ftBadge(m)} <small>${ftInfo(m)}</small>`:''}`);
}
function openStock(c){
  if(!DATA)return; const s=(DATA.summary||[]).find(x=>x.coin===c); if(!s||!s.chart_latest)return;
  openModal([{label:'Latest chart',src:BASE+s.chart_latest+'?v='+encodeURIComponent(DATA.last_change_utc||''),cap}],`${esc(short(c))} · latest bricks`);
}
document.addEventListener('click',e=>{const k=e.target.closest('[data-ikey]');if(k){openSetup(k.getAttribute('data-ikey'));return}
  const c=e.target.closest('[data-istock]');if(c)openStock(c.getAttribute('data-istock'))});
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.dataset&&e.target.dataset.ikey)openSetup(e.target.dataset.ikey)});

async function load(force){
  const ts=Date.now();
  const got=await Promise.all(SOURCES.map(u=>fetch(u+'?t='+ts,{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)));
  const d=got.filter(Boolean).sort((a,b)=>(b.last_scan_utc||'').localeCompare(a.last_scan_utc||''))[0];
  if(!d)return;
  if(!force&&lastScan&&d.last_scan_utc<=lastScan){$('i-lastScan').textContent=ist(lastScan);return}
  const keys=(d.matches||[]).map(key);
  if(seen)keys.forEach(k=>{if(!seen.includes(k))newKeys.add(k)});
  seen=Array.from(new Set([...(seen||[]),...keys])); try{localStorage.setItem('bfSeenIN',JSON.stringify(seen))}catch(e){}
  lastScan=d.last_scan_utc;
  try{render(d)}catch(e){console.error(e)}
  if(!window._ihash&&location.hash.startsWith('#iopen=')){window._ihash=1;openSetup(decodeURIComponent(location.hash.slice(7)))}
}
window.bfIndia=()=>load(true);
{const so=$('i-strongOnly'); if(so)so.onchange=()=>{strongOnly=so.checked; if(DATA)try{render(DATA)}catch(e){console.error(e)}}}
load(); setInterval(()=>load(),60000);

// per-stock brick drilldown
let FULL=null, LIMIT=150; const sel=$('i-sel');
const nv=v=>v===null||v===undefined?'–':(+v).toLocaleString('en-IN',{maximumFractionDigits:4});
function drill(){
  if(!FULL)return; const sym=sel.value, rows=(FULL.coins[sym]||[]).slice().reverse(), C=FULL.columns, ix=k=>C.indexOf(k);
  $('i-csv').href=BASE+'data/coins/'+sym.replace(':','_')+'.csv';
  $('i-info').textContent=rows.length+' bricks'+(rows.length>LIMIT?` (showing newest ${LIMIT})`:'');
  const body=rows.slice(0,LIMIT).map(r=>`<tr><td data-l="Date">${fd(r[ix('brick_date')])}${r[ix('forming')]?' <small>(forming)</small>':''}${r[ix('flip')]?' <span class="b '+(r[ix('brick_color')]==='GREEN'?'buyo':'sello')+'">flip</span>':''}</td>
<td data-l="Brick">${r[ix('brick_color')]==='GREEN'?"<span class='b dg'>green</span>":"<span class='b dr'>red</span>"}</td><td data-l="Open">${nv(r[ix('open')])}</td><td data-l="High">${nv(r[ix('high')])}</td><td data-l="Low">${nv(r[ix('low')])}</td><td data-l="Close"><b>${nv(r[ix('close')])}</b></td>
<td data-l="Hull">${badge(r[ix('hull_color')])} ${nv(r[ix('mhull')])} <small>/ ${nv(r[ix('shull')])}</small></td><td data-l="MACD">${nv(r[ix('macd')])}</td><td data-l="Signal">${nv(r[ix('signal')])}</td><td data-l="Histogram">${badge(r[ix('hist_color')])} ${nv(r[ix('histogram')])}</td></tr>`).join('');
  $('i-tbl').innerHTML=`<table class="rtable"><thead><tr><th>Date</th><th>Brick</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Hull (MHULL / SHULL)</th><th>MACD</th><th>Signal</th><th>Histogram</th></tr></thead><tbody>${body}</tbody></table>`+(rows.length>LIMIT?`<div class="pending"><a href="#" id="i-more" style="color:#0D9488">Show all ${rows.length}</a></div>`:'');
  const m=$('i-more'); if(m)m.onclick=e=>{e.preventDefault();LIMIT=1e9;drill()};
}
async function loadFull(){
  try{const r=await fetch(BASE+'data/all_bricks.json?t='+Math.floor(Date.now()/300000),{cache:'no-store'});if(!r.ok)throw 0;FULL=await r.json()}catch(e){return}
  const cur=sel.value, syms=Object.keys(FULL.coins);
  sel.innerHTML=syms.map(s=>`<option value="${s}">${short(s)}</option>`).join('');
  sel.value=syms.includes(cur)?cur:(syms.includes('NSE:RELIANCE')?'NSE:RELIANCE':syms[0]); drill();
}
if(sel){sel.onchange=()=>{LIMIT=150;drill()};const al=$('i-allLink');if(al)al.href=BASE+'data/all_bricks.json';loadFull();setInterval(loadFull,300000)}
})();
