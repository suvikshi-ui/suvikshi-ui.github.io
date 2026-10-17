// Live renderer for the strategy scan. Data: data.json written by the scanner (GitHub Actions, every 5 min).
(function(){
const SOURCES=['data.json','https://raw.githubusercontent.com/suvikshi-ui/suvikshi-ui.github.io/main/trx/data.json'];
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const fd=d=>{if(!d)return '–';const [y,m,dd]=d.split('-');return (+dd)+' '+MON[+m-1]+' '+y};
const num=v=>{if(v===null||v===undefined||v==='')return '–';const n=+v;return Number(n.toPrecision(6)).toLocaleString('en-US',{maximumFractionDigits:10})};
const f4=v=>(+v).toFixed(4), f5=v=>(+v).toFixed(5), sg=v=>((+v)>=0?'+':'')+(+v).toFixed(5);
const short=c=>String(c).replace('BINGX:','');
const BC={'DARK GREEN':'dg','LIGHT GREEN':'lg','DARK RED':'dr','LIGHT RED':'lr','RED':'hr','GREEN':'hg'};
const tc=s=>s.toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());
const badge=s=>`<span class="b ${BC[s]||''}">${tc(s)}</span>`;
const todayUTC=()=>new Date().toISOString().slice(0,10);
const isForming=d=>d>=todayUTC(); // BingX daily candle closes 00:00 UTC = 05:30 IST
const stBadge=d=>isForming(d)?'<span class="b form" title="Daily candle not closed yet; the brick can still change">Forming (daily candle not closed)</span>':'<span class="b conf">Confirmed</span>';
const ist=iso=>{const d=new Date(iso);return d.toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true})+' IST'};
const key=m=>m.coin+'|'+m.date+'|'+m.side+'|'+m.brick_close;
let seen=null; try{seen=JSON.parse(localStorage.getItem('trxSeen')||'null')}catch(e){}
let newKeys=new Set(), lastScan=null;

function chart(br,flips){
  if(!br||!br.length)return '';
  const W=1000,H=380,pl=52,pr=14,pt=16,pb=46,n=br.length;
  let lo=Math.min(...br.map(b=>Math.min(b[1],b[2])))-0.0055, hi=Math.max(...br.map(b=>Math.max(b[1],b[2])))+0.0055;
  const bw=(W-pl-pr)/n, y=v=>pt+(hi-v)/(hi-lo)*(H-pt-pb);
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="TRX daily Renko bricks with signal markers" xmlns="http://www.w3.org/2000/svg">`;
  for(let k=Math.ceil(lo/0.011);k*0.011<=hi;k++){const v=k*0.011,yy=y(v);s+=`<line x1="${pl}" x2="${W-pr}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}" class="grid"/><text x="${pl-6}" y="${(yy+4).toFixed(1)}" class="ax" text-anchor="end">${v.toFixed(3)}</text>`}
  const fm={};(flips||[]).forEach(f=>fm[f.date+'|'+f.brick_close]=f);
  br.forEach((b,j)=>{const [d,o,c]=b,x=pl+j*bw,top=y(Math.max(o,c)),bot=y(Math.min(o,c));
    s+=`<rect x="${(x+1).toFixed(1)}" y="${top.toFixed(1)}" width="${(bw-2).toFixed(1)}" height="${(bot-top).toFixed(1)}" class="${c>o?'up':'dn'}"><title>${d}  ${f4(o)} → ${f4(c)}</title></rect>`;
    if(j===0||br[j-1][0].slice(0,7)!==d.slice(0,7)){s+=`<text x="${(x+bw/2).toFixed(1)}" y="${H-pb+16}" class="ax" text-anchor="middle">${MON[+d.slice(5,7)-1]}</text>`;if(j===0||d.slice(5,7)==='01')s+=`<text x="${(x+bw/2).toFixed(1)}" y="${H-pb+30}" class="ax" text-anchor="middle">${d.slice(0,4)}</text>`}
    const f=fm[d+'|'+c]; if(f){const cx=x+bw/2;
      if(f.match){if(f.side==='SELL'){const yy=bot+6;s+=`<polygon points="${cx-7},${yy} ${cx+7},${yy} ${cx},${yy+12}" class="msell"><title>SELL setup ${d} close ${f4(c)}</title></polygon>`}
        else{const yy=top-6;s+=`<polygon points="${cx-7},${yy} ${cx+7},${yy} ${cx},${yy-12}" class="mbuy"><title>BUY setup ${d} close ${f4(c)}</title></polygon>`}}
      else{const yy=f.side==='SELL'?bot+8:top-8;s+=`<circle cx="${cx}" cy="${yy}" r="3.5" class="mfail"><title>Failed ${f.side} flip ${d}</title></circle>`}}});
  return s+'</svg>';
}

function renderTRX(d){
  const t=d.trx||{}, flips=t.flips||[], br=t.bricks||[];
  const ms=flips.filter(f=>f.match), fl=flips.filter(f=>!f.match);
  const nb=ms.filter(m=>m.side==='BUY').length, ns=ms.filter(m=>m.side==='SELL').length;
  const last=br[br.length-1]; const lastFlip=last&&ms.find(m=>m.date===last[0]&&m.brick_close===last[2]);
  if(last){$('winTo').textContent=fd(last[0]);$('chartTo').textContent=fd(last[0])}
  $('trxCards').innerHTML=`<div class="card"><div class="k">Sell setups</div><div class="v s">${ns}</div></div>
<div class="card"><div class="k">Buy setups</div><div class="v bu">${nb}</div></div>
<div class="card"><div class="k">Renko flips checked</div><div class="v">${flips.length}</div></div>
<div class="card"><div class="k">Bricks in window</div><div class="v">${br.length}</div></div>
<div class="card"><div class="k">Latest brick</div><div class="v" style="font-size:18px">${last?fd(last[0]):'–'}<br><small>${last?(last[2]>last[1]?'green':'red')+' · '+f4(last[2])+(lastFlip?' · '+lastFlip.side+' setup':'')+(isForming(last[0])?' · forming':''):''}</small></div></div>`;
  $('trxChart').innerHTML=chart(br,flips);
  $('trxM').innerHTML=ms.slice().reverse().map((r,i)=>`<tr class="click ${newKeys.has(key(r))?'isnew':''}" data-key="${esc(key(r))}"><td data-l="#">${ms.length-i}</td><td data-l="Date"><b>${fd(r.date)}</b>${last&&r.date===last[0]?' <small>(latest brick)</small>':''} ${newKeys.has(key(r))?'<span class="b new">NEW</span>':''}</td><td data-l="Signal"><span class="b ${r.side.toLowerCase()}">${r.side}</span> ${stBadge(r.date)}</td><td data-l="Brick close">${f4(r.brick_close)}</td><td data-l="Hull Suite 55">${badge(r.hull_color)} ${f5(r.mhull)} <small>(2 back ${f5(r.shull)})</small></td><td data-l="Histogram before → after">${badge(r.state_before)} ${sg(r.hist_before)} → ${badge(r.state_after)} ${sg(r.hist_after)}</td></tr>`).join('')||'<tr><td colspan="6" class="pending">No setups yet.</td></tr>';
  $('trxF').innerHTML=fl.map(r=>{const why=[];if(!r.hull_ok)why.push(`Hull Suite ${r.hull_color.toLowerCase()} (needed ${r.side==='BUY'?'green':'red'})`);if(!r.macd_ok)why.push(`histogram ${r.state_before.toLowerCase()} → ${r.state_after.toLowerCase()}`);
    return `<tr><td data-l="Date">${fd(r.date)}</td><td data-l="Flip"><span class="b ${r.side==='BUY'?'buyo':'sello'}">${r.side}</span> ${r.side==='BUY'?'red→green':'green→red'}</td><td data-l="Close">${f4(r.brick_close)}</td><td data-l="Hull">${badge(r.hull_color)} ${f5(r.mhull)}</td><td data-l="Histogram">${badge(r.state_before)} → ${badge(r.state_after)}</td><td data-l="Why it failed">${why.join('; ')}</td></tr>`}).join('');
  const rg=flips.filter(f=>f.side==='BUY'), rgRed=rg.filter(f=>!f.hull_ok);
  $('trxFnote').innerHTML=nb?'':`<small>${rg.length===rgRed.length&&rg.length?`All ${rg.length} red→green flips in 2026 came while Hull Suite was still red, so there were no BUY setups.`:''}</small>`;
}

function renderCoins(d){
  const S=d.summary||[], M=(d.matches||[]).filter(m=>m.date>='2026-01-01').slice().sort((a,b)=>a.date<b.date?1:a.date>b.date?-1:a.coin.localeCompare(b.coin));
  const few=S.filter(s=>String(s.status).startsWith('too little')), part=S.filter(s=>String(s.status).startsWith('partial'));
  const nb=M.filter(m=>m.side==='BUY').length, ns=M.filter(m=>m.side==='SELL').length;
  const ord=S.slice().sort((a,b)=>(String(a.status).startsWith('too little')-String(b.status).startsWith('too little'))||((b.buys||0)+(b.sells||0)-(a.buys||0)-(a.sells||0))||a.coin.localeCompare(b.coin));
  const rows=ord.map(s=>{const st=String(s.status),sc=st.startsWith('too little')||st.startsWith('fetch');let b;
    if(st==='ok')b='<span class="b hg">Full</span>';else if(st.startsWith('partial')){const m=st.match(/from (\d{4}-\d\d-\d\d)/);b=`<span class="b lr">Partial</span> <small>scored from ${m?fd(m[1]):'?'}</small>`}
    else if(st.startsWith('fetch'))b='<span class="b" style="border:1px solid #CBD5E1;color:#64748B">Fetch error</span>';else b='<span class="b" style="border:1px solid #CBD5E1;color:#64748B">Too little history</span>';
    return `<tr class="${s.chart_latest?'click':''}" ${s.chart_latest?`data-coin="${esc(s.coin)}"`:''}><td data-l="Coin"><b>${esc(short(s.coin))}</b>${s.chart_latest?' <span class="lnk">chart</span>':''}</td><td data-l="Data">${b}</td><td data-l="Box">${num(s.box_size)}</td><td data-l="Bricks 2026">${s.bricks_in_window??'–'}</td><td data-l="Flips">${s.flips??'–'}</td>
<td data-l="BUY">${sc?'–':(s.buys?`<b style="color:#059669">${s.buys}</b>`:0)}</td><td data-l="SELL">${sc?'–':(s.sells?`<b style="color:#DC2626">${s.sells}</b>`:0)}</td>
<td data-l="Latest brick">${fd(s.latest_brick_date)} ${s.latest_brick_color?(s.latest_brick_color==='RED'?"<span class='b dr'>red</span>":"<span class='b dg'>green</span>"):''} ${num(s.latest_close)}${s.latest_brick_date&&isForming(s.latest_brick_date)?' <small>(forming)</small>':''}</td></tr>`}).join('');
  const mrows=M.map(m=>{const nw=newKeys.has(key(m));return `<tr class="${nw?'isnew':''}"><td data-l="Date"><b>${fd(m.date)}</b> ${nw?'<span class="b new">NEW</span>':''}</td><td data-l="Coin">${esc(short(m.coin))}</td><td data-l="Signal"><span class="b ${m.side.toLowerCase()}">${m.side}</span></td><td data-l="Status">${stBadge(m.date)}</td>
<td data-l="Brick close">${num(m.brick_close)}</td><td data-l="Hull Suite 55">${badge(m.hull_color)} ${num(m.mhull)}</td><td data-l="Histogram before → after">${badge(m.state_before)} → ${badge(m.state_after)}</td></tr>`}).join('');
  const errs=Object.keys(d.fetch_errors||{});
  $('c-summary').innerHTML=`<section id="coins"><h2>Crypto summary · all watchlist coins (${S.length})</h2>
<p><small>The same strategy runs on every coin in the TradingView "Crypto currency" watchlist (BingX symbols, daily Renko ATR(14), Hull Suite 55, MACD 12/26/9). Window: 1 Jan 2026 to the latest brick. Data: TradingView. Updated live, newest first.</small></p>
<div class="cards"><div class="card"><div class="k">Coins scanned</div><div class="v">${S.length}</div></div>
<div class="card"><div class="k">BUY setups</div><div class="v bu">${nb}</div></div>
<div class="card"><div class="k">SELL setups</div><div class="v s">${ns}</div></div>
<div class="card"><div class="k">Too little history</div><div class="v">${few.length}</div></div></div>
<div class="note" style="background:#F0FDFA;border-color:#99F6E4;color:#134E4A;margin-bottom:12px">${few.length} coins had too little history to score (Hull/MACD need about 60 bricks to warm up): ${few.map(s=>short(s.coin)).join(', ')}. ${part.length} coins have <b>partial history</b>, so they were scored only from the date shown: ${part.map(s=>short(s.coin)).join(', ')}.${errs.length?` Last scan could not fetch: ${errs.map(short).join(', ')}.`:''}
<br><small>"Forming" means the setup is on a daily candle that hasn't closed yet (BingX's daily candle closes at 05:30 IST), so the brick can still change. "Confirmed" means the candle has closed.</small></div>
<h3>Per-coin summary</h3><div class="tw"><table class="rtable"><thead><tr><th>Coin</th><th>Data</th><th>Box</th><th>Bricks 2026</th><th>Flips</th><th>BUY</th><th>SELL</th><th>Latest brick</th></tr></thead><tbody>${rows}</tbody></table></div>
<p><small>All ${M.length} setups (${nb} BUY / ${ns} SELL) are listed at the top of the page, under Active trading setups and All other 2026 setups.</small></p></section>`;
}

let DATA=null;
function renderTop(d){
  DATA=d;
  const M=(d.matches||[]).slice().sort((a,b)=>a.date<b.date?1:a.date>b.date?-1:a.coin.localeCompare(b.coin));
  const act=M.filter(m=>m.active), oth=M.filter(m=>!m.active);
  $('c-active').innerHTML=act.length?act.map(m=>{const nw=newKeys.has(key(m)),s=m.side==='SELL';
    return `<div class="ac ${s?'sellc':'buyc'}" data-key="${esc(key(m))}" tabindex="0" role="button">
<div class="top"><span class="coin">${esc(short(m.coin))}</span><span><span class="b sig ${m.side.toLowerCase()}">${m.side}</span> ${nw?'<span class="b new">NEW</span>':''}</span></div>
<div class="px">${num(m.brick_close)}</div>
<div class="row"><span>Setup brick</span><span><b>${fd(m.date)}</b></span></div>
<div class="row"><span>Status</span><span>${stBadge(m.date)}</span></div>
<div class="row"><span>Hull Suite 55</span><span>${badge(m.hull_color)} ${num(m.mhull)}</span></div>
<div class="row"><span>Histogram</span><span>${badge(m.state_before)} → ${badge(m.state_after)}</span></div>
<div class="row"><span>Bricks since</span><span>${m.bricks_since===0?'setup is the latest brick':'+'+m.bricks_since+' in the same direction'}</span></div>
<div class="vw">View chart ›</div></div>`}).join(''):'<div class="pending">No active setups right now.</div>';
  $('c-other').innerHTML=oth.map(m=>{const nw=newKeys.has(key(m));return `<tr class="click ${nw?'isnew':''}" data-key="${esc(key(m))}"><td data-l="Date"><b>${fd(m.date)}</b> ${nw?'<span class="b new">NEW</span>':''}</td><td data-l="Coin">${esc(short(m.coin))}</td><td data-l="Signal"><span class="b ${m.side.toLowerCase()}">${m.side}</span></td><td data-l="Status">${stBadge(m.date)}</td><td data-l="Close">${num(m.brick_close)}</td><td data-l="Hull Suite 55">${badge(m.hull_color)} ${num(m.mhull)}</td><td data-l="Histogram before → after">${badge(m.state_before)} → ${badge(m.state_after)}</td><td data-l=""><span class="lnk">chart ›</span></td></tr>`}).join('')||'<tr><td colspan="8" class="pending">None.</td></tr>';
}
// ---- Modal (single in-page chart view) ----
function openModal(views,title){
  const tabs=$('mTabs'); $('mTitle').innerHTML=title; tabs.innerHTML='';
  const show=i=>{const v=views[i];$('mImg').src=v.src;$('mImg').alt=v.label;$('mCap').textContent=v.cap;[...tabs.children].forEach((b,j)=>b.classList.toggle('on',j===i))};
  views.forEach((v,i)=>{const b=document.createElement('button');b.textContent=v.label;b.onclick=()=>show(i);tabs.appendChild(b)});
  tabs.style.display=views.length>1?'flex':'none'; show(0); $('modal').hidden=false; document.body.style.overflow='hidden';
  // optional real TradingView screenshot slot: shots/<SYMBOL>_<date>_<side>.png
  views.filter(v=>v.shot).forEach(v=>{const im=new Image();im.onload=()=>{const b=document.createElement('button');b.textContent='TradingView screenshot';b.onclick=()=>{$('mImg').src=v.shot;$('mCap').textContent='Screenshot from the TradingView app.';[...tabs.children].forEach(x=>x.classList.remove('on'));b.classList.add('on')};tabs.appendChild(b);tabs.style.display='flex'};im.src=v.shot});
}
function closeModal(){$('modal').hidden=true;document.body.style.overflow=''}
const capFor=c=>`Chart rendered from TradingView data (${c}, daily Renko ATR14).`;
function openSetup(k){
  if(!DATA)return; const m=(DATA.matches||[]).find(x=>key(x)===k); if(!m)return;
  const s=(DATA.summary||[]).find(x=>x.coin===m.coin)||{}; const v=[];
  const bust='?v='+encodeURIComponent(DATA.last_change_utc||'');
  if(m.chart)v.push({label:'Setup chart',src:m.chart+bust,cap:capFor(m.coin),shot:'shots/'+m.coin.replace(':','_')+'_'+m.date+'_'+m.side+'.png'});
  if(s.chart_latest)v.push({label:'Latest chart',src:s.chart_latest+bust,cap:capFor(m.coin)});
  if(!v.length)return;
  openModal(v,`${esc(short(m.coin))} · <span class="b ${m.side.toLowerCase()}">${m.side}</span> ${fd(m.date)} · close ${num(m.brick_close)} · ${stBadge(m.date)}`);
}
function openCoin(c){
  if(!DATA)return; const s=(DATA.summary||[]).find(x=>x.coin===c); if(!s||!s.chart_latest)return;
  openModal([{label:'Latest chart',src:s.chart_latest+'?v='+encodeURIComponent(DATA.last_change_utc||''),cap:capFor(c)}],`${esc(short(c))} · latest bricks`);
}
document.addEventListener('click',e=>{
  if(e.target.id==='modal'||e.target.id==='mClose'){closeModal();return}
  const k=e.target.closest('[data-key]'); if(k){openSetup(k.getAttribute('data-key'));return}
  const c=e.target.closest('[data-coin]'); if(c){openCoin(c.getAttribute('data-coin'))}
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();if(e.key==='Enter'&&e.target.classList&&e.target.classList.contains('ac'))openSetup(e.target.getAttribute('data-key'))});

function setLive(){
  if(!lastScan)return;
  $('lastScan').textContent=ist(lastScan);
  const age=(Date.now()-new Date(lastScan))/60000, el=$('live');
  if(age>45){el.classList.add('stale');$('liveNote').textContent=`The last scan was ${Math.round(age)} min ago. GitHub's scheduler can be delayed, so the next one may be late.`}
  else{el.classList.remove('stale');$('liveNote').textContent='Auto-scan every 15 minutes on TradingView data. This page checks for new data every 60 seconds.'}
}

async function load(){
  const ts=Date.now();
  const got=await Promise.all(SOURCES.map(u=>fetch(u+(u.includes('?')?'&':'?')+'t='+ts,{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)));
  const d=got.filter(Boolean).sort((a,b)=>(b.last_scan_utc||'').localeCompare(a.last_scan_utc||''))[0];
  if(!d)return;
  if(lastScan&&d.last_scan_utc<=lastScan){setLive();return}
  const keys=(d.matches||[]).map(key);
  if(seen){keys.forEach(k=>{if(!seen.includes(k))newKeys.add(k)})}
  seen=Array.from(new Set([...(seen||[]),...keys]));
  try{localStorage.setItem('trxSeen',JSON.stringify(seen))}catch(e){}
  lastScan=d.last_scan_utc;
  $('lastUpd').textContent=ist(d.last_change_utc||d.last_scan_utc);
  try{renderTRX(d)}catch(e){console.error(e)}
  try{renderCoins(d)}catch(e){console.error(e)}
  try{renderTop(d)}catch(e){console.error(e)}
  if(!window._hashDone&&location.hash.startsWith('#open=')){window._hashDone=1;openSetup(decodeURIComponent(location.hash.slice(6)))}
  setLive();
}
load(); setInterval(load,60000); setInterval(setLive,30000);
})();
// ---- Per-coin brick drilldown (lazy-loads data/all_bricks.json) ----
(function(){
const $=id=>document.getElementById(id);
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const fd=d=>{const [y,m,dd]=d.split('-');return (+dd)+' '+MON[+m-1]+' '+y};
const nv=v=>v===null||v===undefined?'–':Number((+v).toPrecision(6)).toLocaleString('en-US',{maximumFractionDigits:10});
const BC={'DARK GREEN':'dg','LIGHT GREEN':'lg','DARK RED':'dr','LIGHT RED':'lr','RED':'hr','GREEN':'hg'};
const bd=s=>s?`<span class="b ${BC[s]||''}">${s.toLowerCase().replace(/\b\w/g,c=>c.toUpperCase())}</span>`:'–';
let FULL=null, LIMIT=150;
const sel=$('c-sel'); if(!sel)return;
function render(){
  const sym=sel.value, rows=(FULL.coins[sym]||[]).slice().reverse(), C=FULL.columns, ix=k=>C.indexOf(k);
  $('c-csv').href='data/coins/'+sym.replace(':','_')+'.csv';
  $('c-info').textContent=rows.length+' bricks'+(rows.length>LIMIT?` (showing newest ${LIMIT})`:'');
  const body=rows.slice(0,LIMIT).map(r=>`<tr><td data-l="Date">${fd(r[ix('brick_date')])}${r[ix('forming')]?' <small>(forming)</small>':''}${r[ix('flip')]?' <span class="b '+(r[ix('brick_color')]==='GREEN'?'buyo':'sello')+'">flip</span>':''}</td>
<td data-l="Brick">${r[ix('brick_color')]==='GREEN'?"<span class='b dg'>green</span>":"<span class='b dr'>red</span>"}</td><td data-l="Open">${nv(r[ix('open')])}</td><td data-l="High">${nv(r[ix('high')])}</td><td data-l="Low">${nv(r[ix('low')])}</td><td data-l="Close"><b>${nv(r[ix('close')])}</b></td>
<td data-l="Hull">${bd(r[ix('hull_color')])} ${nv(r[ix('mhull')])} <small>/ ${nv(r[ix('shull')])}</small></td><td data-l="MACD">${nv(r[ix('macd')])}</td><td data-l="Signal">${nv(r[ix('signal')])}</td><td data-l="Histogram">${bd(r[ix('hist_color')])} ${nv(r[ix('histogram')])}</td></tr>`).join('');
  $('c-tbl').innerHTML=`<table class="rtable"><thead><tr><th>Date</th><th>Brick</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Hull (MHULL / SHULL)</th><th>MACD</th><th>Signal</th><th>Histogram</th></tr></thead><tbody>${body}</tbody></table>`+(rows.length>LIMIT?`<div class="pending"><a href="#" id="c-more" style="color:#5b8def">Show all ${rows.length}</a></div>`:'');
  const m=$('c-more'); if(m)m.onclick=e=>{e.preventDefault();LIMIT=1e9;render()};
}
async function loadFull(){
  try{const r=await fetch('data/all_bricks.json?t='+Math.floor(Date.now()/300000),{cache:'no-store'});if(!r.ok)throw 0;FULL=await r.json()}
  catch(e){$('c-tbl').innerHTML='<div class="pending">The brick dataset isn\'t available yet.</div>';return}
  const cur=sel.value, syms=Object.keys(FULL.coins);
  sel.innerHTML=syms.map(s=>`<option value="${s}">${s.replace('BINGX:','')}</option>`).join('');
  sel.value=syms.includes(cur)?cur:(syms.includes('BINGX:TRXUSDT.P')?'BINGX:TRXUSDT.P':syms[0]);
  render();
}
sel.onchange=()=>{LIMIT=150;render()};
loadFull(); setInterval(loadFull,300000);
})();

// ---- Tabs + India pending list ----
(function(){
const $=id=>document.getElementById(id);
function setTab(k){document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.tab===k));
  $('mkt-crypto').hidden=k!=='crypto';$('mkt-india').hidden=k!=='india';
  const lm=$('liveMkt');if(lm)lm.textContent=k==='india'?'Crypto':'Crypto';
  if(history.replaceState&&!location.hash.startsWith('#open='))history.replaceState(null,'',k==='india'?'#india':'#crypto');}
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>setTab(b.dataset.tab)));
if(location.hash==='#india')setTab('india');
const al=$('c-allLink');if(al)al.href='data/all_bricks.json';
fetch('../scanner/nifty100.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{if(!d)return;
  $('i-listInfo').textContent=`Nifty 100 constituents (${d.count} stocks, official NSE Indices list, retrieved ${d.retrieved_ist}). This is a constituent list, not market data.`;
  $('i-list').innerHTML=d.constituents.map(c=>`<span class="chip" title="${c.name} · ${c.industry}">${c.symbol}</span>`).join('');}).catch(()=>{});
})();
