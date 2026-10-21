"""Renko Doji scanner (separate from BrickFlow; imports tv_source read-only).
Universe: Nifty 100 only (scanner/nifty100.json, TradingView NSE:CNX100 constituents).
Bricks: TradingView daily Renko ATR14, source Close, wicks on (de-duplicated). HAB = javabgar HARSI (RSI 11/13/15/17). No MA filter.
Doji: HAB body <=16% of range with wicks both sides. Live rule (DOJI_RUN_MODE=any): hard CM_EMA 11 filter (brick close > EMA11 for BUY, < for SELL, equal blocks); run of >=2 same-colour HAB candles; opposite signal cancels pending / closes open at next open; 0.1% cost. Old rule (DOJI_RUN_MODE=fixed):
SELL: 4-8 green HAB candles, doji, next HAB red with open==high -> entry on break below brick low; cancelled if a BUY doji setup completes in the run.
BUY: 3-5 red HAB candles, doji, next HAB green with open==low -> entry on break above brick high; cancelled if a SELL doji setup completes in the run.
Fill at level or open on gap; cancelled if no break within 20 trading days. Exits 3% stop / 6% target, same day = stop.
Usage: python scanner/doji_scan.py trx/doji_data.json [--limit=N] [--workers=N]"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tv_source as TV
UNI = os.path.join(HERE, "nifty100.json")
RUN_MODE = os.environ.get("DOJI_RUN_MODE", "any")   # "any": run of >= RUN_MIN same-colour HAB candles (live rule); "fixed": old 4-8 green / 3-5 red
RUN_MIN = 2; COST = 0.1   # % per round trip
D = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")

def universe():
    """Nifty 100 only (scanner/nifty100.json, TradingView CNX100 constituents; read-only here)."""
    d = json.load(open(UNI))
    return {"symbols": [{"symbol": c["symbol"], "name": c.get("name", ""), "industry": c.get("industry", c.get("sector", ""))} for c in d["constituents"]], "filter": "Nifty 100 constituents (TradingView NSE:CNX100)",
            "total_listed": len(d["constituents"])}

def rsi(x, L):
    out = [None] * len(x); g = l = 0
    for i in range(1, len(x)):
        d = x[i] - x[i-1]; up = max(d, 0); dn = max(-d, 0)
        if i <= L:
            g += up / L; l += dn / L
            if i < L: continue
        else: g = (g * (L-1) + up) / L; l = (l * (L-1) + dn) / L
        out[i] = 100 if l == 0 else 100 - 100 / (1 + g / l)
    return out

def hab(c):
    rs = [rsi(c, L) for L in (11, 13, 15, 17)]; n = len(c)
    O1 = [None]*n; C1 = [None]*n; O2 = [None]*n; C2 = [None]*n; H2 = [None]*n; L2 = [None]*n; MA = [None]*n; e = None
    for i in range(n):
        v = [r[i] for r in rs]
        if None in v: continue
        m = sum(v) / 4; e = m if e is None else (2/14) * m + (12/14) * e; MA[i] = e
        h, cc, o, l = sorted(v, reverse=True)
        C1[i] = (o+h+l+cc)/4; O1[i] = (o+cc)/2 if O1[i-1] is None else (O1[i-1]+C1[i-1])/2
        H1 = max(h, O1[i], C1[i]); L1 = min(l, O1[i], C1[i])
        C2[i] = (O1[i]+H1+L1+C1[i])/4; O2[i] = (O1[i]+C1[i])/2 if O2[i-1] is None else (O2[i-1]+C2[i-1])/2
        H2[i] = max(H1, O2[i], C2[i]); L2[i] = min(L1, O2[i], C2[i])
    return O2, H2, L2, C2, MA

def dedup(br):
    """TradingView sometimes sends the whole brick history twice: keep only the first strictly time-ordered run."""
    for k in range(1, len(br)):
        if br[k][0] <= br[k-1][0]: return br[:k]
    return br

def get(sym, tries=3):
    tk = TV.tv_symbol(sym); last = None
    for a in range(tries):
        try:
            br, err, _ = TV._series(tk, True)
            if err or not br: raise RuntimeError(err or "no bricks")
            dl, err2, _ = TV._series(tk, False, n=1500)
            if err2 or not dl: raise RuntimeError(err2 or "no daily")
            return dedup(br), dl
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    raise RuntimeError(str(last))

def ema(x, L=11):
    """CM_EMA TrendBars line: EMA(L) of Renko brick closes (seeded with the SMA of the first L closes)."""
    out = [None] * len(x); k = 2 / (L + 1)
    for i in range(L - 1, len(x)):
        out[i] = sum(x[:L]) / L if i == L - 1 else k * x[i] + (1 - k) * out[i - 1]
    return out

r2 = lambda v: None if v is None else round(v, 2)
def analyse(sym, br, dl):
    bd = [D(x[0]) for x in br]; bo = [x[1] for x in br]; bh = [x[2] for x in br]; bl = [x[3] for x in br]; bc = [x[4] for x in br]
    O, H, L, C, MA = hab(bc); dd = [D(x[0]) for x in dl]
    sig = []; ndoji = 0
    tl = lambda m: max(0.05, 0.0001 * (H[m] - L[m]))
    def isdoji(m):
        if m < 0 or O[m] is None: return False
        r = H[m] - L[m]
        return r > 0 and abs(C[m] - O[m]) / r <= 0.16 and H[m] - max(O[m], C[m]) > 0 and min(O[m], C[m]) - L[m] > 0
    fol = lambda n, side: isdoji(n - 1) and ((C[n] < O[n] and abs(H[n] - O[n]) < tl(n)) if side < 0 else (C[n] > O[n] and abs(O[n] - L[n]) < tl(n)))
    for i in range(9, len(br) - 1):
        j = i + 1
        if O[i] is None or bd[j] < "2021" or not isdoji(i): continue
        ndoji += 1
        for sg, rmin, rmax in (((-1, 4, 8), (1, 3, 5)) if RUN_MODE == "fixed" else ((-1, RUN_MIN, 10**6), (1, RUN_MIN, 10**6))):
            if not fol(j, sg): continue
            run = 0; k = i - 1
            while k >= 0 and O[k] is not None and ((C[k] > O[k]) if sg < 0 else (C[k] < O[k])): run += 1; k -= 1
            if not rmin <= run <= rmax: continue
            if RUN_MODE == "fixed" and any(fol(n, -sg) for n in range(i - run, i)): continue   # opposite setup inside the run cancels
            sig.append((j, sg, min(bo[j], bc[j]) if sg < 0 else max(bo[j], bc[j]), i, run))
    VI = ema(bc, 11); out = []; keep_sig = []
    for (j, sg, lv, i, run) in sig:   # hard CM_EMA 11 filter: BUY needs brick close > EMA11, SELL close < EMA11 (equal blocks both)
        m = j
        while m + 1 < len(br) and bd[m + 1] == bd[j]: m += 1   # latest brick on the signal day
        e1 = VI[m]
        ok = e1 is not None and (bc[m] > e1 if sg > 0 else bc[m] < e1)
        if ok: keep_sig.append((j, sg, lv, i, run))
        else: out.append({"stock": sym, "side": "BUY" if sg > 0 else "SELL", "doji_date": bd[i], "signal_date": bd[j], "level": r2(lv), "run": run, "run_start": bd[i - run],
                          "doji_body_pct": round(abs(C[i]-O[i])/(H[i]-L[i])*100, 1), "hab": [r2(O[j]), r2(H[j]), r2(L[j]), r2(C[j])], "status": "skipped", "reason": "CM_EMA 11",
                          "close": bc[m], "ema11": r2(e1)})
    sig = keep_sig
    for k, (j, sg, lv, i, run) in enumerate(sig):
        opp = [bd[s[0]] for s in sig[k+1:] if s[1] != sg and bd[s[0]] > bd[j]]
        st = [z for z, d in enumerate(dd) if d > bd[j]]
        rec = {"stock": sym, "side": "BUY" if sg > 0 else "SELL", "doji_date": bd[i], "signal_date": bd[j], "level": r2(lv),
               "hab": [r2(O[j]), r2(H[j]), r2(L[j]), r2(C[j])], "hab_ma": r2(MA[j]), "doji_body_pct": round(abs(C[i]-O[i])/(H[i]-L[i])*100, 1), "run": run, "run_start": bd[i - run]}
        z0 = st[0] if st else len(dl); e = None; z = z0; why = None
        for z in range(z0, min(z0 + 20, len(dl))):
            o, h, l = dl[z][1], dl[z][2], dl[z][3]
            if opp and dd[z] > opp[0]: why = "opposite signal " + opp[0]; break
            if sg < 0 and l < lv: e = min(o, lv); break
            if sg > 0 and h > lv: e = max(o, lv); break
        if e is None:
            waited = min(len(dl), z0 + 20) - z0
            if why is None and waited < 20: rec.update(status="pending", days_waiting=waited, expires_after=20 - waited)
            else: rec.update(status="cancelled", reason=why or "no break in 20 trading days")
            out.append(rec); continue
        s_ = e * (1 - .03 * sg); t_ = e * (1 + .06 * sg); res = None
        for y in range(z, len(dl)):
            h, l = dl[y][2], dl[y][3]
            if (l <= s_ if sg > 0 else h >= s_): res = (dd[y], s_, -3.0, "stop hit"); break
            if opp and dd[y] > opp[0] and y > z: res = (dd[y], dl[y][1], round((dl[y][1] / e - 1) * 100 * sg, 2), "opposite signal"); break
            if y > z and (h >= t_ if sg > 0 else l <= t_): res = (dd[y], t_, 6.0, "target hit"); break
        rec.update(entry_date=dd[z], entry=r2(e), stop=r2(s_), target=r2(t_))
        if res: rec.update(status="closed", outcome=res[3], exit_date=res[0], exit=r2(res[1]), pl_gross=res[2], pl_pct=round(res[2] - COST, 2), days=y - z)
        else:
            last = dl[-1][4]; rec.update(status="open", days=len(dl) - 1 - z, last_price=r2(last), unreal_pct=round((last / e - 1) * 100 * sg, 2), opposite_pending=opp[0] if opp else None)
        out.append(rec)
    tail = [[bd[k], bo[k], bh[k], bl[k], bc[k], r2(O[k]), r2(H[k]), r2(L[k]), r2(C[k]), r2(MA[k]), r2(VI[k])]
            for k in range(max(0, len(br) - 60), len(br))]
    return out, ndoji, tail, {"bricks": len(br), "last_brick": bd[-1], "last_price": dl[-1][4], "last_daily": dd[-1]}

def main():
    OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "trx/doji_data.json"
    opt = dict(a[2:].split("=", 1) for a in sys.argv if a.startswith("--") and "=" in a)
    t0 = time.time(); U = universe(); syms = [s["symbol"] for s in U["symbols"]][: int(opt.get("limit", 10**6))]
    W = int(opt.get("workers", 6)); DL = float(opt.get("deadline", 1500)); res = {}; errs = {}; stale = []
    # incremental cache: previous output; stocks not refreshed before the deadline keep their previous results
    try: PREV = json.load(open(OUT)); PT = {}; [PT.setdefault(t["stock"], []).append(t) for t in PREV.get("trades", [])]
    except Exception: PREV, PT = {}, {}
    try: PCH = json.load(open(os.path.join(os.path.dirname(OUT) or ".", "doji_charts.json")))
    except Exception: PCH = {}
    def job(s):
        if time.time() - t0 > DL: raise TimeoutError("deadline")
        return get(s)
    ex = ThreadPoolExecutor(W); fs = {ex.submit(job, s): s for s in syms}; done = 0
    for f in as_completed(fs):
        s = fs[f]; done += 1
        try: res[s] = analyse(s, *f.result())
        except TimeoutError: pass
        except Exception as e: errs[s] = str(e)[:120]
        if done % 100 == 0: print(f"{done}/{len(syms)} done, {len(errs)} errors, {time.time()-t0:.0f}s", flush=True)
    ex.shutdown()
    for s in syms:
        if s not in res and s in PREV.get("stocks", {}):
            st0 = PREV["stocks"][s]; res[s] = (PT.get(s, []), st0["dojis"], PCH.get(s, []), st0["stats"]); stale.append(s); errs.pop(s, None)
    per = lambda d: "2026" if d >= "2026" else "2021-25"
    T = [t for s in res for t in res[s][0]]; summ = {}
    for p in ("2021-25", "2026"):
        cl = [t for t in T if t["status"] == "closed" and per(t["signal_date"]) == p]; o = {}
        for side in ("ALL", "BUY", "SELL"):
            c = [t for t in cl if side == "ALL" or t["side"] == side]; w = sum(t["pl_pct"] > 0 for t in c); tot = sum(t["pl_pct"] for t in c)
            o[side] = {"trades": len(c), "targets": w, "stops": sum(t["outcome"] == "stop hit" for t in c), "flips": sum(t["outcome"] == "opposite signal" for t in c), "losses": len(c) - w, "win_rate": round(w / len(c) * 100, 1) if c else None,
                       "avg_pl": round(tot / len(c), 2) if c else None, "total_pl": round(tot, 1)}
        summ[p] = o
    for p in ("2021-25", "2026"):
        summ[p]["qualified"] = sum(1 for t in T if per(t["signal_date"]) == p and t["status"] != "skipped"); summ[p]["skipped_ema"] = sum(1 for t in T if per(t["signal_date"]) == p and t["status"] == "skipped")
    stocks = {s: {"stats": res[s][3], "dojis": res[s][1], "signals": len(res[s][0]), "bricks": res[s][2]} for s in res}
    meta = {s["symbol"]: [s["name"], s["industry"]] for s in U["symbols"]}
    doc = {"strategy": "Renko Doji", "rule": {"run_mode": RUN_MODE, "run_min": RUN_MIN, "ema_filter": "CM_EMA TrendBars EMA 11 on brick closes; BUY close > EMA, SELL close < EMA, equal blocks both", "cost_pct": COST, "stop_pct": 3, "target_pct": 6}, "source": "TradingView (NSE daily Renko ATR 14, Close, wicks; daily candles)",
           "last_scan_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "scan_seconds": round(time.time() - t0),
           "universe": {"size": len(syms), "scanned": len(res), "failed": errs, "kept_from_previous_scan": len(stale), "filter": U.get("filter"), "total_listed": U.get("total_listed")},
           "dojis_total": sum(res[s][1] for s in res), "summary": summ, "trades": T, "meta": meta,
           "stocks": {s: {k: v for k, v in stocks[s].items() if k != "bricks"} for s in stocks}}
    json.dump(doc, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    keep = set(stocks)   # charts for every scanned Nifty 100 stock (loaded only when a pop-up opens)
    json.dump({s: stocks[s]["bricks"] for s in sorted(keep)}, open(os.path.join(os.path.dirname(OUT) or ".", "doji_charts.json"), "w"), separators=(",", ":"))
    c = {k: sum(t["status"] == k for t in T) for k in ("pending", "open", "closed", "cancelled", "skipped")}
    print(f"universe {len(syms)} scanned {len(res)} failed {len(errs)} in {doc['scan_seconds']}s; {c}; {json.dumps(summ)}")
if __name__ == "__main__": main()
