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
const oc=t=>t.outcome==='target hit'?`<span class="b oc-t">Target hit ${pc(t.pl_pct)}</span>`:`<span class="b oc-s">Stop hit ${pc(t.pl_pct)}</span>`;
let D=null,CH=null,shown=200;
// tab switching (app.js already toggles button state and hides the other markets)
function show(on){root.hidden=!on;if(on){$('mkt-crypto').hidden=true;$('mkt-india').hidden=true;if(!D)load();}}
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{show(b.dataset.tab==='doji');if(b.dataset.tab==='doji'&&history.replaceState)history.replaceState(null,'','#doji')}));
if(location.hash==='#doji'){document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.tab==='doji'));show(true)}
const row=(cells)=>'<tr data-stk="'+esc(cells[0][1])+'">'+cells.map(([l,v])=>`<td data-l="${l}">${v}</td>`).join('')+'</tr>';
function sumTbl(S){const r=[];for(const p of ['2021-25','2026'])for(const s of ['ALL','BUY','SELL']){const x=S[p][s];r.push(`<tr><td data-l="Period"><b>${p==='2021-25'?'2021–2025':'2026'}</b></td><td data-l="Side">${s==='ALL'?'All':side(s)}</td><td data-l="Trades">${x.trades}</td><td data-l="Targets">${x.targets}</td><td data-l="Stops">${x.stops}</td><td data-l="Win rate">${x.win_rate??'–'}%</td><td data-l="Avg P/L">${pc(x.avg_pl)}</td><td data-l="Total">${pc(x.total_pl)}</td></tr>`)}return r.join('')}

function details(){
  const T=D.trades,np=T.filter(t=>t.status==='pending').length,no=T.filter(t=>t.status==='open').length;
  const tb=(h,rows)=>`<div class="tw"><table class="rtable"><thead><tr>${h.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((c,i)=>`<td data-l="${h[i]}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const H=['Test','Period','Trades','Win rate','Avg per trade','Total'];
  let el=$('d-details'); if(!el){el=document.createElement('section');el.id='d-details';root.querySelector('.note').after(el)}
  el.innerHTML=`<h2>Setup details</h2>
<div class="note" style="background:#F0FDFA;border-color:#99F6E4;color:#134E4A;margin-bottom:14px"><b>1. Rules.</b>
<ul><li>Chart: TradingView daily Renko (ATR 14, source Close, wicks on). Each brick is one bar.</li>
<li>HAB RSI: javabgar "HARSI – Heikin Ashi RSI" with RSI lengths 11/13/15/17, drawn as candles on the bricks (levels 30/50/70).</li>
<li>HAB MA filter: the 13 EMA of the average RSI line.</li>
<li><b>Doji</b>: a HAB candle whose body is 16% of its range or less, with wicks on both sides.</li>
<li><b>SELL</b>: the next HAB candle has open = high (no upper wick) and HAB is below its MA. Entry when the daily price breaks below that brick's low.</li>
<li><b>BUY</b>: the mirror. The next HAB candle has open = low (no lower wick) and HAB is above its MA. Entry when the price breaks above that brick's high.</li>
<li>Exits: 3% stop loss and 6% target (1:2). A day that touches both counts as a stop. A pending signal is cancelled after 20 trading days or on an opposite signal.</li></ul></div>
<h3>2. Earlier tests (corrected data, 3% stop / 6% target)</h3>
${tb(H,[['Strong baseline','2021–25','242','–','−0.02%','–'],['Strong baseline','2026','64','–','+0.29%','–'],['Strong buy + HAB MA','2021–25','137','38.0%','+0.42%','+57%'],['Strong buy + HAB MA','2026','31','45.2%','+1.06%','+33%']])}
<h3>3. Nifty 100: doji pattern with and without the HAB MA filter</h3>
${tb(['Version','Period','Trades','Targets / Stops','Win rate','Avg per trade','Total'],[['No filter','2021–25','407','–','34.9%','+0.14%','+57%'],['No filter','2026','110','–','36.9%','+0.32%','+33%'],['With MA filter','2021–25','285','105 / 180','36.8%','+0.32%','+90%'],['With MA filter','2026','70 (4 open)','28 / 38','42.4%','+0.82%','+54%']])}
<h3>4. All NSE stocks (${D.universe.scanned} stocks, with MA filter)</h3>
${tb(['Period','Side','Trades','Targets','Stops','Win rate','Avg P/L','Total'],['2021-25','2026'].flatMap(p=>['ALL','BUY','SELL'].map(s=>{const x=D.summary[p][s];return [p==='2021-25'?'2021–25':'2026',s==='ALL'?'All':side(s),x.trades,x.targets,x.stops,(x.win_rate??'–')+'%',pc(x.avg_pl),pc(x.total_pl)]})))}
<p><small>Across all NSE stocks the pattern is roughly break-even: sells are profitable, buys are losing.</small></p>
<h3>5. Right now</h3><p><b>${np} pending</b> (waiting for the break) · <b>${no} open</b> trades · last scan ${ist(D.last_scan_utc)}.</p>
<h3>6. Example: ICICI Bank</h3>
<p>Doji HAB candle on <b>8 Sep 2026</b>; the follow-up candle on <b>15 Sep 2026</b> had open = high. Without the filter this gave a SELL entry on 16 Sep at ₹1,359.0, stopped out on 19 Oct (−3%). With the HAB MA filter this sell is filtered out; the filter left 1 ICICI trade per period (2021–25 and 2026), and both hit the target.</p>`;
}
function render(){
  details(); const T=D.trades, U=D.universe;
  $('d-info').innerHTML=`Last scan: <b>${ist(D.last_scan_utc)}</b> · ${U.scanned} of ${U.size} NSE stocks scanned in ${Math.round(D.scan_seconds/60)} min · Universe: TradingView screener, NSE common stocks (${U.total_listed} listed), filter ${esc(U.filter)} · Source: ${esc(D.source)}`;
  const P=T.filter(t=>t.status==='pending').sort((a,b)=>b.signal_date.localeCompare(a.signal_date)), O=T.filter(t=>t.status==='open').sort((a,b)=>b.entry_date.localeCompare(a.entry_date));
  const C=T.filter(t=>t.status==='closed').sort((a,b)=>b.exit_date.localeCompare(a.exit_date)||a.stock.localeCompare(b.stock));
  $('d-cnt').textContent=`${P.length} pending · ${O.length} open · ${C.length} closed (2021 onwards) · ${D.dojis_total} doji candles found, ${T.length} qualified with the follow-up candle`;
  $('d-pend').innerHTML=P.length?P.map(t=>`<div class="ac ${t.side==='SELL'?'sellc':'buyc'}" data-stk="${esc(t.stock)}" tabindex="0" role="button"><div class="top"><span class="coin">${esc(t.stock)}</span><span>${side(t.side)} <span class="b form">Waiting for break</span></span></div><div class="px">${t.side==='BUY'?'Above':'Below'} ₹${num(t.level)}</div><div class="row"><span>Doji brick</span><span>${fd(t.doji_date)} (body ${t.doji_body_pct}%)</span></div><div class="row"><span>Signal brick</span><span><b>${fd(t.signal_date)}</b></span></div><div class="row"><span>HAB O/H/L/C · MA</span><span>${t.hab.join(' / ')} · ${t.hab_ma}</span></div><div class="row"><span>Waiting</span><span>${t.days_waiting} trading days (cancels after ${t.expires_after} more)</span></div></div>`).join(''):'<div class="pending">No pending signals right now.</div>';
  $('d-open').innerHTML=O.length?O.map(t=>`<div class="ac ${t.side==='SELL'?'sellc':'buyc'}" data-stk="${esc(t.stock)}" tabindex="0" role="button"><div class="top"><span class="coin">${esc(t.stock)}</span><span>${side(t.side)} <span class="b oc-o">Open</span></span></div><div class="px">₹${num(t.entry)}</div><div class="row"><span>Entry</span><span><b>${fd(t.entry_date)}</b> at ₹${num(t.entry)}</span></div><div class="row"><span>Exits (1:2)</span><span>Stop ${num(t.stop)} · Target ${num(t.target)}</span></div><div class="row"><span>Days in trade</span><span>${t.days}</span></div><div class="row"><span>Last price</span><span>₹${num(t.last_price)} (${pc(t.unreal_pct)})</span></div><div class="row"><span>Doji → signal</span><span>${fd(t.doji_date)} → ${fd(t.signal_date)}</span></div></div>`).join(''):'<div class="pending">No open trades right now.</div>';
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
  const m=$('d-modal');m.hidden=false;$('d-mt').textContent=s+' · Renko (ATR 14, Close) + HAB RSI (11/13/15/17) with MA · last '+B.length+' bricks';
  const cv=$('d-cv'),W=cv.width=Math.min(1000,innerWidth-60),H=cv.height=460,x=cv.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,W,H);
  const n=B.length,bw=(W-60)/n,ph=270,hy=290,hh=160;
  const lo=Math.min(...B.map(b=>b[3])),hi=Math.max(...B.map(b=>b[2])),py=v=>10+(hi-v)/(hi-lo||1)*(ph-20);
  const hv=B.flatMap(b=>[b[6],b[7],b[9]]).filter(v=>v!=null),hl=Math.min(30,...hv),hH=Math.max(70,...hv),qy=v=>hy+(hH-v)/(hH-hl)*hh;
  x.font='10px sans-serif';
  [30,50,70].forEach(v=>{x.strokeStyle='#ccc';x.setLineDash([3,3]);x.beginPath();x.moveTo(0,qy(v));x.lineTo(W-60,qy(v));x.stroke();x.setLineDash([]);x.fillStyle='#666';x.fillText(v,W-55,qy(v)+3)});
  [lo,(lo+hi)/2,hi].forEach(v=>{x.fillStyle='#666';x.fillText(num(v),W-55,py(v)+3)});
  B.forEach((b,i)=>{const cx=i*bw+bw/2,up=b[4]>b[1];x.strokeStyle=x.fillStyle=up?'#16a34a':'#dc2626';
    x.beginPath();x.moveTo(cx,py(b[2]));x.lineTo(cx,py(b[3]));x.stroke();x.fillRect(i*bw+1,py(Math.max(b[1],b[4])),bw-2,Math.max(1,Math.abs(py(b[1])-py(b[4]))));
    if(b[5]!=null){const u=b[8]>b[5];x.strokeStyle=x.fillStyle=u?'#16a34a':'#dc2626';x.beginPath();x.moveTo(cx,qy(b[6]));x.lineTo(cx,qy(b[7]));x.stroke();x.fillRect(i*bw+1,qy(Math.max(b[5],b[8])),bw-2,Math.max(1,Math.abs(qy(b[5])-qy(b[8]))))}
    if(i%Math.ceil(n/8)===0){x.fillStyle='#666';x.fillText(fd(b[0]),i*bw,H-4)}});
  x.strokeStyle='#d97706';x.lineWidth=1.5;x.beginPath();B.forEach((b,i)=>{if(b[9]!=null)(i?x.lineTo:x.moveTo).call(x,i*bw+bw/2,qy(b[9]))});x.stroke();x.lineWidth=1;
  const tr=D.trades.filter(t=>t.stock===s).slice(-6);$('d-mc').innerHTML='HAB MA line in amber. Signals: '+tr.map(t=>`${t.side} ${fd(t.signal_date)} (${t.status==='closed'?t.outcome:t.status})`).join(' · ');
}
$('d-mx').addEventListener('click',()=>$('d-modal').hidden=true);
function load(){fetch('doji_data.json',{cache:'no-store'}).then(r=>r.json()).then(d=>{D=d;render()}).catch(e=>{$('d-info').textContent='Renko Doji data not available yet ('+e.message+').'})}
})();
