// Renko Doji tab (separate from BrickFlow). Data: doji_data.json + doji_charts.json written by scanner/doji_scan.py (TradingView only).
(function(){
const $=id=>document.getElementById(id), root=$('mkt-doji'); if(!root)return;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>'&'+({'&':'amp','<':'lt','>':'gt','"':'quot'}[c])+';');
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const fd=d=>{if(!d)return '–';const [y,m,dd]=d.split('-');return (+dd)+' '+MON[+m-1]+' '+y};
const num=v=>v==null?'–':(+v).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
const pc=v=>v==null?'–':((+v)>0?'+':'')+(+v).toFixed(2)+'%';
const ist=iso=>new Date(iso).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true})+' IST';
const side=s=>`<span class="b sig ${s.toLowerCase()}">${s}</span>`;
const oc=t=>t.outcome==='target hit'?`<span class="b oc-t">Target hit ${pc(t.pl_pct)}</span>`:t.outcome==='opposite signal'?`<span class="b ${t.pl_pct>0?'oc-t':'oc-s'}">Closed by opposite signal ${pc(t.pl_pct)}</span>`:`<span class="b oc-s">Stop hit ${pc(t.pl_pct)}</span>`;
let D=null,CH=null,shown=200;
// tab switching (app.js already toggles button state and hides the other markets)
function show(on){root.hidden=!on;if(on){$('mkt-crypto').hidden=true;$('mkt-india').hidden=true;if(!D)load();}}
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{show(b.dataset.tab==='doji');if(b.dataset.tab==='doji'&&history.replaceState)history.replaceState(null,'','#doji')}));
if(location.hash==='#doji'){document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.tab==='doji'));show(true)}
const row=(cells)=>'<tr data-stk="'+esc(cells[0][1])+'">'+cells.map(([l,v])=>`<td data-l="${l}">${v}</td>`).join('')+'</tr>';
function sumTbl(S){const r=[];for(const p of ['2021-25','2026'])for(const s of ['ALL','BUY','SELL']){const x=S[p][s];r.push(`<tr><td data-l="Period"><b>${p==='2021-25'?'2021–2025':'2026'}</b></td><td data-l="Side">${s==='ALL'?'All':side(s)}</td><td data-l="Trades">${x.trades}</td><td data-l="Targets">${x.targets}</td><td data-l="Stops">${x.stops}</td><td data-l="Win rate">${x.win_rate??'–'}%</td><td data-l="Avg P/L">${pc(x.avg_pl)}</td><td data-l="Total">${pc(x.total_pl)}</td></tr>`)}return r.join('')}

function header(){const h=root.querySelector('h2.mh');if(h)h.textContent='Renko Doji (Nifty 100)';const n=root.querySelector('.note');if(n)n.innerHTML='<b>Rules.</b> Nifty 100 only. Daily TradingView Renko (ATR 14, Close, wicks), HAB RSI 11/13/15/17, no MA filter. <b>SELL</b>: a run of 2 or more green HAB candles, doji, then red open = high; entry below that brick\'s low. <b>BUY</b>: a run of 2 or more red HAB candles, doji, then green open = low; entry above that brick\'s high. <b>CM_EMA 11 filter (hard)</b>: CM_EMA 11 = ChrisMoody CM_EMA TrendBars, EMA length 11 of Renko brick closes, read on the latest brick on or before the signal day. A BUY is taken only if that brick\'s close is strictly above the EMA (green); a SELL only if it is strictly below (red); a close equal to the EMA blocks both. Filtered signals show as Skipped: CM_EMA 11. An opposite (taken) signal cancels a pending one and closes an open trade at the next open. 3% stop, 6% target (1:2), 0.1% cost per trade; a day touching both counts as a stop. Separate from BrickFlow.'}
header();
function details(){
  const T=D.trades,np=T.filter(t=>t.status==='pending').length,no=T.filter(t=>t.status==='open').length;
  const tb=(h,rows)=>`<div class="tw"><table class="rtable"><thead><tr>${h.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((c,i)=>`<td data-l="${h[i]}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const H=['Test','Period','Trades','Win rate','Avg per trade','Total'];
  let el=$('d-details'); if(!el){el=document.createElement('section');el.id='d-details';root.querySelector('.note').after(el)}
  el.innerHTML=`<h2>Setup details</h2>
<div class="note" style="background:#F0FDFA;border-color:#99F6E4;color:#134E4A;margin-bottom:14px"><b>1. Rules (continuation-run version, no MA filter).</b>
<ul><li>Universe: Nifty 100 stocks only (TradingView NSE:CNX100 constituents).</li>
<li>Chart: TradingView daily Renko (ATR 14, source Close, wicks on). Each brick is one bar.</li>
<li>HAB RSI: javabgar "HARSI – Heikin Ashi RSI" with RSI lengths 11/13/15/17, drawn as candles on the bricks (levels 30/50/70). The amber MA line on the charts is for reference only; it is not a filter.</li>
<li><b>Doji</b>: a HAB candle whose body is 16% of its range or less, with wicks on both sides.</li>
<li><b>SELL</b>: a run of consecutive green HAB candles (any length, 2 or more), then a doji, then a red HAB candle with open = high (no upper wick). Entry when the daily price breaks below that brick's low.</li>
<li><b>BUY</b>: the mirror. A run of 2 or more red HAB candles, then a doji, then a green HAB candle with open = low (no lower wick). Entry when the price breaks above that brick's high.</li>
<li><b>CM_EMA 11 filter (hard)</b>: ChrisMoody's CM_EMA TrendBars, EMA length 11 of the Renko brick closes, using the latest brick on or before the signal day. BUY only when the brick close is strictly above the EMA (green); SELL only when strictly below (red); a close equal to the EMA blocks both. Filtered signals are listed as <b>Skipped: CM_EMA 11</b> and are not traded.</li>
<li><b>Opposite signal</b>: a new opposite signal cancels a pending one, and closes an open trade at the next day's open (flip).</li>
<li>Fill at the level, or at the open on a gap. A pending signal is cancelled if there is no break within 20 trading days.</li>
<li>Exits: 3% stop loss and 6% target (1:2). A day that touches both counts as a stop. Results are net of a 0.1% cost per trade.</li></ul></div>
<h3>2. Backtest results, Nifty 100 (this scan)</h3>
${tb(['Period','Side','Trades','Targets','Stops','Win rate','Avg P/L','Total'],['2021-25','2026'].flatMap(p=>['ALL','BUY','SELL'].map(s=>{const x=D.summary[p][s];return [p==='2021-25'?'2021–25':'2026',s==='ALL'?'All':side(s),x.trades,x.targets,x.stops,(x.win_rate??'–')+'%',pc(x.avg_pl),pc(x.total_pl)]})))}
<p><small>Previous rule (4–8 green / 3–5 red runs, before 0.1% costs), 2021–25: 90 trades, +45%; 2026: 23 trades, −6%. Most entries fill at the next day's open (gap through the level).</small></p>
<h3>3. Past test (not used now): MA version without runs, Nifty 100</h3>
${tb(['Version','Period','Trades','Targets / Stops','Win rate','Avg per trade','Total'],[['Doji + HAB MA filter','2021–25','285','105 / 180','36.8%','+0.32%','+90%'],['Doji + HAB MA filter','2026','70 (4 open)','28 / 38','42.4%','+0.82%','+54%']])}
<p><small>Skipped by the CM_EMA 11 filter: ${D.summary['2021-25'].skipped_ema??0} (2021–25) · ${D.summary['2026'].skipped_ema??0} (2026).</small></p><h3>4. Right now</h3><p><b>${np} pending</b> (waiting for the break) · <b>${no} open</b> trades · last scan ${ist(D.last_scan_utc)}.</p>`;
}
function render(){
  details(); const T=D.trades, U=D.universe;
  $('d-info').innerHTML=`Last scan: <b>${ist(D.last_scan_utc)}</b> · ${U.scanned} of ${U.size} Nifty 100 stocks scanned in ${D.scan_seconds}s · Universe: ${esc(U.filter)} · Source: ${esc(D.source)}`;
  const P=T.filter(t=>t.status==='pending').sort((a,b)=>b.signal_date.localeCompare(a.signal_date)), O=T.filter(t=>t.status==='open').sort((a,b)=>b.entry_date.localeCompare(a.entry_date));
  const C=T.filter(t=>t.status==='closed').sort((a,b)=>b.exit_date.localeCompare(a.exit_date)||a.stock.localeCompare(b.stock));
  $('d-cnt').textContent=`${P.length} pending · ${O.length} open · ${C.length} closed (2021 onwards) · ${D.dojis_total} doji candles found, ${T.length} qualified with the follow-up candle (${T.filter(t=>t.status==='skipped').length} skipped: CM_EMA 11)`;
  $('d-pend').innerHTML=P.length?P.map(t=>`<div class="ac ${t.side==='SELL'?'sellc':'buyc'}" data-stk="${esc(t.stock)}" tabindex="0" role="button"><div class="top"><span class="coin">${esc(t.stock)}</span><span>${side(t.side)} <span class="b form">Waiting for break</span></span></div><div class="px">${t.side==='BUY'?'Above':'Below'} ₹${num(t.level)}</div><div class="row"><span>Doji brick</span><span>${fd(t.doji_date)} (body ${t.doji_body_pct}%)</span></div><div class="row"><span>Signal brick</span><span><b>${fd(t.signal_date)}</b></span></div><div class="row"><span>Run before doji</span><span>${t.run} ${t.side==='SELL'?'green':'red'} HAB candles</span></div><div class="row"><span>HAB O/H/L/C</span><span>${t.hab.join(' / ')}</span></div><div class="row"><span>Waiting</span><span>${t.days_waiting} trading days (cancels after ${t.expires_after} more)</span></div></div>`).join(''):'<div class="pending">No pending signals right now.</div>';
  $('d-open').innerHTML=O.length?O.map(t=>`<div class="ac ${t.side==='SELL'?'sellc':'buyc'}" data-stk="${esc(t.stock)}" tabindex="0" role="button"><div class="top"><span class="coin">${esc(t.stock)}</span><span>${side(t.side)} <span class="b oc-o">Open</span></span></div><div class="px">₹${num(t.entry)}</div><div class="row"><span>Entry</span><span><b>${fd(t.entry_date)}</b> at ₹${num(t.entry)}</span></div><div class="row"><span>Exits (1:2)</span><span>Stop ${num(t.stop)} · Target ${num(t.target)}</span></div><div class="row"><span>Days in trade</span><span>${t.days}</span></div><div class="row"><span>Last price</span><span>₹${num(t.last_price)} (${pc(t.unreal_pct)})</span></div><div class="row"><span>Doji → signal</span><span>${fd(t.doji_date)} → ${fd(t.signal_date)} (${t.run} ${t.side==='SELL'?'green':'red'} run)</span></div>${t.opposite_pending?`<div class="row"><span>Opposite signal</span><span>${fd(t.opposite_pending)}: closes at next open</span></div>`:''}</div>`).join(''):'<div class="pending">No open trades right now.</div>';
  $('d-sum').innerHTML=sumTbl(D.summary);
  const cl=()=>$('d-closed').innerHTML=C.slice(0,shown).map(t=>row([['Stock',esc(t.stock)],['Signal',side(t.side)],['Doji → signal',fd(t.doji_date)+' → '+fd(t.signal_date)],['Entry',fd(t.entry_date)+' · ₹'+num(t.entry)],['Stop · Target',num(t.stop)+' · '+num(t.target)],['Exit',fd(t.exit_date)+' · ₹'+num(t.exit)],['Days',t.days],['Outcome',oc(t)]])).join('')+(C.length>shown?`<tr><td colspan="8"><button id="d-more" class="tab">Show more (${C.length-shown} left)</button></td></tr>`:'');
  cl(); root.addEventListener('click',e=>{if(e.target.id==='d-more'){shown+=300;cl()}});
  // per-stock rows
  const by={};T.forEach(t=>{(by[t.stock]=by[t.stock]||[]).push(t)});
  const st=Object.keys(by).map(s=>{const c=by[s].filter(t=>t.status==='closed'),w=c.filter(t=>t.pl_pct>0).length,tot=c.reduce((a,t)=>a+t.pl_pct,0);return {s,n:by[s].length,c:c.length,w,tot,p:by[s].filter(t=>t.status==='pending').length,o:by[s].filter(t=>t.status==='open').length,d:D.stocks[s]?.dojis??0,last:by[s].map(t=>t.signal_date).sort().pop()}}).sort((a,b)=>(b.p+b.o)-(a.p+a.o)||b.last.localeCompare(a.last));
  const fl=()=>{const q=($('d-q').value||'').toUpperCase();$('d-stk').innerHTML=st.filter(x=>!q||x.s.includes(q)).slice(0,q?500:150).map(x=>row([['Stock','<b>'+esc(x.s)+'</b> <small>'+esc((D.meta[x.s]||[])[0]||'')+'</small>'],['Dojis',x.d],['Signals',x.n],['Pending · Open',x.p+' · '+x.o],['Closed',x.c],['Win rate',x.c?Math.round(x.w/x.c*100)+'%':'–'],['Total P/L',pc(x.tot)],['Last signal',fd(x.last)]])).join('')};
  $('d-q').addEventListener('input',fl);fl();
  root.querySelectorAll('[data-stk]').forEach(()=>{});
}
root.addEventListener('click',e=>{const el=e.target.closest('[data-stk]');if(el&&el.dataset.stk)chart(el.dataset.stk)});
async function chart(s){
  if(!CH){try{CH=await (await fetch('doji_charts.json',{cache:'no-store'})).json()}catch(e){CH={}}}
  const B=CH[s]; if(!B){return}
  // trade markers: each date maps to the last brick on or before that day; dates before the chart window can't be placed
  const bi=d=>{if(!d||d<B[0][0])return -1;let k=-1;for(let q=0;q<B.length;q++){if(B[q][0]<=d)k=q;else break}return k};
  const MK=[],LN=[];let unpl=0;
  D.trades.filter(t=>t.stock===s&&(t.status==='open'||t.status==='closed')).forEach(t=>{const e=bi(t.entry_date);if(e<0){unpl++;return}
    MK.push({k:e,p:t.entry,ty:t.side,lb:(t.side==='BUY'?'BUY ':'SELL ')+fd(t.entry_date)+' ₹'+num(t.entry)});
    if(t.status==='closed'){const x=bi(t.exit_date);if(x>=0)MK.push({k:x,p:t.exit,ty:t.outcome==='target hit'?'TGT':t.outcome==='stop hit'?'SL':'EXIT',lb:(t.outcome==='target hit'?'TGT ':t.outcome==='stop hit'?'SL ':'Exit ')+fd(t.exit_date)+' ₹'+num(t.exit)})}
    else LN.push({k:e,st:t.stop,tg:t.target})});
  const m=$('d-modal');m.hidden=false;$('d-mt').textContent=s+' · Renko (ATR 14, Close) + HAB RSI (11/13/15/17) · last '+B.length+' bricks';
  const cv=$('d-cv'),W=cv.width=Math.min(1000,innerWidth-60),H=cv.height=460,x=cv.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,W,H);
  const n=B.length,bw=(W-60)/n,ph=270,hy=290,hh=160;
  const lo=Math.min(...B.map(b=>b[3]),...MK.map(m=>m.p),...LN.flatMap(l=>[l.st,l.tg]),...B.map(b=>b[10]).filter(v=>v!=null)),hi=Math.max(...B.map(b=>b[2]),...MK.map(m=>m.p),...LN.flatMap(l=>[l.st,l.tg]),...B.map(b=>b[10]).filter(v=>v!=null)),py=v=>10+(hi-v)/(hi-lo||1)*(ph-20);
  const hv=B.flatMap(b=>[b[6],b[7],b[9]]).filter(v=>v!=null),hl=Math.min(30,...hv),hH=Math.max(70,...hv),qy=v=>hy+(hH-v)/(hH-hl)*hh;
  x.font='10px sans-serif';
  [30,50,70].forEach(v=>{x.strokeStyle='#ccc';x.setLineDash([3,3]);x.beginPath();x.moveTo(0,qy(v));x.lineTo(W-60,qy(v));x.stroke();x.setLineDash([]);x.fillStyle='#666';x.fillText(v,W-55,qy(v)+3)});
  [lo,(lo+hi)/2,hi].forEach(v=>{x.fillStyle='#666';x.fillText(num(v),W-55,py(v)+3)});
  B.forEach((b,i)=>{const cx=i*bw+bw/2,up=b[4]>b[1];x.strokeStyle=x.fillStyle=up?'#16a34a':'#dc2626';
    x.beginPath();x.moveTo(cx,py(b[2]));x.lineTo(cx,py(b[3]));x.stroke();x.fillRect(i*bw+1,py(Math.max(b[1],b[4])),bw-2,Math.max(1,Math.abs(py(b[1])-py(b[4]))));
    if(b[5]!=null){const u=b[8]>b[5];x.strokeStyle=x.fillStyle=u?'#16a34a':'#dc2626';x.beginPath();x.moveTo(cx,qy(b[6]));x.lineTo(cx,qy(b[7]));x.stroke();x.fillRect(i*bw+1,qy(Math.max(b[5],b[8])),bw-2,Math.max(1,Math.abs(qy(b[5])-qy(b[8]))))}
    if(i%Math.ceil(n/8)===0){x.fillStyle='#666';x.fillText(fd(b[0]),i*bw,H-4)}});
  // CM_EMA 11 (ChrisMoody CM_EMA TrendBars) on the Renko price panel: green while brick close > EMA, red while below, grey when equal
  x.lineWidth=2;B.forEach((b,i)=>{const p=B[i-1];if(!p||p[10]==null||b[10]==null)return;x.strokeStyle=b[4]>b[10]?'#16a34a':b[4]<b[10]?'#dc2626':'#6b7280';x.beginPath();x.moveTo((i-1)*bw+bw/2,py(p[10]));x.lineTo(i*bw+bw/2,py(b[10]));x.stroke()});
  x.lineWidth=1;x.font='11px sans-serif';x.fillStyle='#16a34a';x.fillRect(8,8,14,3);x.fillStyle='#dc2626';x.fillRect(22,8,14,3);x.fillStyle='#111';x.fillText('CM_EMA 11'+(B.some(b=>b[10]!=null)?'':' – not enough bricks yet'),42,13);x.font='10px sans-serif';
  x.strokeStyle='#d97706';x.lineWidth=1.5;x.beginPath();B.forEach((b,i)=>{if(b[9]!=null)(i?x.lineTo:x.moveTo).call(x,i*bw+bw/2,qy(b[9]))});x.stroke();x.lineWidth=1;
  // draw trade markers + open-trade dashed stop/target lines (visual only)
  LN.forEach(l=>{[[l.st,'#dc2626','SL '+num(l.st)],[l.tg,'#16a34a','TGT '+num(l.tg)]].forEach(([v,c,t])=>{x.strokeStyle=c;x.setLineDash([5,4]);x.beginPath();x.moveTo(l.k*bw,py(v));x.lineTo(W-60,py(v));x.stroke();x.setLineDash([]);x.fillStyle=c;x.fillText(t,W-58,py(v)-2)})});
  MK.forEach((m,q)=>{const cx=m.k*bw+bw/2,y=py(m.p),dy=(q%3)*11;x.lineWidth=2;
    if(m.ty==='BUY'){x.fillStyle='#15803d';x.beginPath();x.moveTo(cx,y);x.lineTo(cx-6,y+10);x.lineTo(cx+6,y+10);x.fill();x.fillText(m.lb,Math.min(cx-20,W-170),y+21+dy)}
    else if(m.ty==='SELL'){x.fillStyle='#b91c1c';x.beginPath();x.moveTo(cx,y);x.lineTo(cx-6,y-10);x.lineTo(cx+6,y-10);x.fill();x.fillText(m.lb,Math.min(cx-20,W-170),y-13-dy)}
    else if(m.ty==='SL'){x.strokeStyle='#dc2626';x.beginPath();x.moveTo(cx-5,y-5);x.lineTo(cx+5,y+5);x.moveTo(cx+5,y-5);x.lineTo(cx-5,y+5);x.stroke();x.fillStyle='#dc2626';x.fillText(m.lb,Math.min(cx+7,W-170),y+4+dy)}
    else {x.strokeStyle='#16a34a';x.beginPath();x.moveTo(cx-5,y);x.lineTo(cx-1,y+5);x.lineTo(cx+6,y-6);x.stroke();x.fillStyle='#16a34a';x.fillText(m.lb,Math.min(cx+7,W-170),y+4+dy)}
    x.lineWidth=1});
  // legend
  {let lx=8,ly=26;x.font='10px sans-serif';[['▲ BUY entry','#15803d'],['▼ SELL entry','#b91c1c'],['✕ SL hit','#dc2626'],['✓ TGT hit','#16a34a'],['- - open trade SL / TGT','#6b7280']].forEach(([t,c])=>{x.fillStyle=c;x.fillText(t,lx,ly);lx+=x.measureText(t).width+12})}
  const tr=D.trades.filter(t=>t.stock===s).slice(-8);$('d-mc').innerHTML=(unpl?`${unpl} older trade(s) fall before this chart's ${B.length}-brick window and are not marked. `:'')+'CM_EMA 11 line on the Renko panel: green when the brick close is above the EMA, red below (entry filter). HAB MA line in amber (reference only). Signals: '+tr.map(t=>`${t.side} ${fd(t.signal_date)} (${t.status==='closed'?t.outcome+' '+pc(t.pl_pct):t.status==='cancelled'?'cancelled: '+(t.reason||''):t.status==='skipped'?'<span class="b oc-s">Skipped: CM_EMA 11</span>':t.status})`).join(' · ');
}
$('d-mx').addEventListener('click',()=>$('d-modal').hidden=true);
function load(){fetch('doji_data.json',{cache:'no-store'}).then(r=>r.json()).then(d=>{D=d;render()}).catch(e=>{$('d-info').textContent='Renko Doji data not available yet ('+e.message+').'})}
})();
