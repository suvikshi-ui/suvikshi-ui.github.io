"""Renko Doji scanner (separate from BrickFlow; imports tv_source read-only).
Universe: all NSE common stocks from TradingView's screener, liquidity-filtered (scanner/nse_all.json).
Bricks: TradingView daily Renko ATR14, source Close, wicks on (de-duplicated). HAB = javabgar HARSI (RSI 11/13/15/17) + its MA (EMA 13 of the mean RSI).
Doji: HAB body <=16% of range with wicks both sides. Next HAB candle: SELL if open==high, close<MA (entry below brick low);
BUY if open==low, close>MA (entry above brick high). Fill at level or open on gap; cancel after 20 trading days or opposite signal.
Exits 3% stop / 6% target, same day = stop.
Usage: python scanner/doji_scan.py trx/doji_data.json [--limit=N] [--workers=N]"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tv_source as TV
UNI = os.path.join(HERE, "nse_all.json")
MIN_MCAP, MIN_TURNOVER = 5e9, 1e7   # ₹500 Cr market cap, ₹1 Cr avg daily traded value (30d)
D = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")

def universe():
    b = {"columns": ["name", "description", "sector", "market_cap_basic", "average_volume_30d_calc", "close"],
         "filter": [{"left": "exchange", "operation": "equal", "right": "NSE"}, {"left": "type", "operation": "equal", "right": "stock"},
                    {"left": "is_primary", "operation": "equal", "right": True}],
         "range": [0, 6000], "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}}
    try:
        rq = urllib.request.Request(TV.SCANNER_URL, data=json.dumps(b).encode(), headers={"Content-Type": "application/json",
                                    "Origin": "https://www.tradingview.com", "User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(rq, timeout=40)); rows = d["data"]
        out = [{"symbol": r["d"][0], "tv_ticker": r["s"], "name": r["d"][1], "industry": r["d"][2] or "", "market_cap": r["d"][3]}
               for r in rows if r["s"].startswith("NSE:") and (r["d"][3] or 0) >= MIN_MCAP and (r["d"][4] or 0) * (r["d"][5] or 0) >= MIN_TURNOVER]
        if len(out) > 500:
            json.dump({"source": "TradingView screener (exchange NSE, type stock, primary listing)", "total_listed": len(rows),
                       "filter": "market cap >= ₹500 Cr and 30-day avg traded value >= ₹1 Cr", "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "symbols": out}, open(UNI, "w"), indent=0, ensure_ascii=False)
    except Exception as e: print("universe refresh failed, using cached:", e)
    return json.load(open(UNI))

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
            dl, err2, _ = TV._series(tk, False, n=1600)
            if err2 or not dl: raise RuntimeError(err2 or "no daily")
            return dedup(br), dl
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    raise RuntimeError(str(last))

r2 = lambda v: None if v is None else round(v, 2)
def analyse(sym, br, dl):
    bd = [D(x[0]) for x in br]; bo = [x[1] for x in br]; bh = [x[2] for x in br]; bl = [x[3] for x in br]; bc = [x[4] for x in br]
    O, H, L, C, MA = hab(bc); dd = [D(x[0]) for x in dl]
    sig = []; ndoji = 0
    for i in range(1, len(br) - 1):
        if O[i] is None or bd[i] < "2021": continue
        rg = H[i] - L[i]
        if rg <= 0: continue
        body = abs(C[i] - O[i]) / rg
        if not (body <= 0.16 and H[i] - max(O[i], C[i]) > 0 and min(O[i], C[i]) - L[i] > 0): continue
        ndoji += 1; j = i + 1; tol = max(0.05, 0.0001 * (H[j] - L[j]))
        if C[j] < O[j] and abs(H[j] - O[j]) < tol and C[j] < MA[j]: sig.append((j, -1, min(bo[j], bc[j]), i))
        elif C[j] > O[j] and abs(O[j] - L[j]) < tol and C[j] > MA[j]: sig.append((j, 1, max(bo[j], bc[j]), i))
    out = []
    for k, (j, sg, lv, i) in enumerate(sig):
        opp = [bd[s[0]] for s in sig[k+1:] if s[1] != sg]
        st = [z for z, d in enumerate(dd) if d > bd[j]]
        rec = {"stock": sym, "side": "BUY" if sg > 0 else "SELL", "doji_date": bd[i], "signal_date": bd[j], "level": r2(lv),
               "hab": [r2(O[j]), r2(H[j]), r2(L[j]), r2(C[j])], "hab_ma": r2(MA[j]), "doji_body_pct": round(abs(C[i]-O[i])/(H[i]-L[i])*100, 1)}
        z0 = st[0] if st else len(dl); e = None; z = z0; why = None
        for z in range(z0, min(z0 + 20, len(dl))):
            if opp and dd[z] >= opp[0]: why = "opposite signal"; break
            o, h, l = dl[z][1], dl[z][2], dl[z][3]
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
            if y > z and (h >= t_ if sg > 0 else l <= t_): res = (dd[y], t_, 6.0, "target hit"); break
        rec.update(entry_date=dd[z], entry=r2(e), stop=r2(s_), target=r2(t_))
        if res: rec.update(status="closed", outcome=res[3], exit_date=res[0], exit=r2(res[1]), pl_pct=res[2], days=y - z)
        else:
            last = dl[-1][4]; rec.update(status="open", days=len(dl) - 1 - z, last_price=r2(last), unreal_pct=round((last / e - 1) * 100 * sg, 2))
        out.append(rec)
    tail = [[bd[k], bo[k], bh[k], bl[k], bc[k], r2(O[k]), r2(H[k]), r2(L[k]), r2(C[k]), r2(MA[k])]
            for k in range(max(0, len(br) - 60), len(br))]
    return out, ndoji, tail, {"bricks": len(br), "last_brick": bd[-1], "last_price": dl[-1][4], "last_daily": dd[-1]}

def main():
    OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "trx/doji_data.json"
    opt = dict(a[2:].split("=", 1) for a in sys.argv if a.startswith("--") and "=" in a)
    t0 = time.time(); U = universe(); syms = [s["symbol"] for s in U["symbols"]][: int(opt.get("limit", 10**6))]
    W = int(opt.get("workers", 8)); res = {}; errs = {}
    with ThreadPoolExecutor(W) as ex:
        fs = {ex.submit(get, s): s for s in syms}
        for f in as_completed(fs):
            s = fs[f]
            try: res[s] = analyse(s, *f.result())
            except Exception as e: errs[s] = str(e)[:120]
    # retry failures once, slowly
    for s in list(errs):
        try: res[s] = analyse(s, *get(s, 2)); errs.pop(s)
        except Exception: time.sleep(1)
    per = lambda d: "2026" if d >= "2026" else "2021-25"
    T = [t for s in res for t in res[s][0]]; summ = {}
    for p in ("2021-25", "2026"):
        cl = [t for t in T if t["status"] == "closed" and per(t["signal_date"]) == p]; o = {}
        for side in ("ALL", "BUY", "SELL"):
            c = [t for t in cl if side == "ALL" or t["side"] == side]; w = sum(t["pl_pct"] > 0 for t in c); tot = sum(t["pl_pct"] for t in c)
            o[side] = {"trades": len(c), "targets": w, "stops": len(c) - w, "win_rate": round(w / len(c) * 100, 1) if c else None,
                       "avg_pl": round(tot / len(c), 2) if c else None, "total_pl": round(tot, 1)}
        summ[p] = o
    for p in ("2021-25", "2026"):
        summ[p]["qualified"] = sum(1 for t in T if per(t["signal_date"]) == p)
    stocks = {s: {"stats": res[s][3], "dojis": res[s][1], "signals": len(res[s][0]), "bricks": res[s][2]} for s in res}
    meta = {s["symbol"]: [s["name"], s["industry"]] for s in U["symbols"]}
    doc = {"strategy": "Renko Doji", "source": "TradingView (NSE daily Renko ATR 14, Close, wicks; daily candles)",
           "last_scan_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "scan_seconds": round(time.time() - t0),
           "universe": {"size": len(syms), "scanned": len(res), "failed": errs, "filter": U.get("filter"), "total_listed": U.get("total_listed")},
           "dojis_total": sum(res[s][1] for s in res), "summary": summ, "trades": T, "meta": meta,
           "stocks": {s: {k: v for k, v in stocks[s].items() if k != "bricks"} for s in stocks}}
    json.dump(doc, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    keep = {t["stock"] for t in T if t["status"] in ("pending", "open") or t["signal_date"] >= "2026"}
    json.dump({s: stocks[s]["bricks"] for s in sorted(keep)}, open(os.path.join(os.path.dirname(OUT) or ".", "doji_charts.json"), "w"), separators=(",", ":"))
    c = {k: sum(t["status"] == k for t in T) for k in ("pending", "open", "closed", "cancelled")}
    print(f"universe {len(syms)} scanned {len(res)} failed {len(errs)} in {doc['scan_seconds']}s; {c}; {json.dumps(summ)}")
if __name__ == "__main__": main()
