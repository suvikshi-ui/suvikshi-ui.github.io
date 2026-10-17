"""Live Renko + Hull Suite 55 + MACD 12/26/9 strategy scan (signal only, no trades/alerts).
Data: TradingView public chart feed (anonymous), BingX symbols, daily Renko ATR(14), wicks on.
Writes trx/data.json. Usage: python scanner/scan.py [out_path]"""
import json, math, random, string, re, sys, time, os
from collections import Counter
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "trx", "data.json")
SYMS = json.load(open(os.path.join(HERE, "symbols.json")))
START = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
D = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")

def rs(n=12): return "".join(random.choice(string.ascii_lowercase) for _ in range(n))
def frame(m, p):
    s = json.dumps({"m": m, "p": p}, separators=(",", ":")); return f"~m~{len(s)}~m~{s}"

def fetch(symbol, ver="40"):
    ws = websocket.create_connection("wss://data.tradingview.com/socket.io/websocket?from=chart%2F&type=chart",
                                     header=["Origin: https://www.tradingview.com"], timeout=30)
    cs = "cs_" + rs()
    sym = {"symbol": {"symbol": symbol, "adjustment": "splits"}, "type": f"BarSetRenko@tv-prostudies-{ver}!",
           "inputs": {"source": "close", "sources": "Close", "boxSize": 1, "style": "ATR", "atrLength": 14, "wicks": True}}
    for m, p in [("set_auth_token", ["unauthorized_user_token"]), ("chart_create_session", [cs, ""]),
                 ("resolve_symbol", [cs, "sds_sym_1", "=" + json.dumps(sym)]),
                 ("create_series", [cs, "sds_1", "s1", "sds_sym_1", "1D", 5000, ""])]:
        ws.send(frame(m, p))
    bars, err, t0 = [], None, time.time()
    while time.time() - t0 < 40:
        try: raw = ws.recv()
        except Exception as e: err = "recv " + str(e); break
        for part in re.split(r"~m~\d+~m~", raw):
            if not part: continue
            if part.startswith("~h~"): ws.send(f"~m~{len(part)}~m~{part}"); continue
            try: j = json.loads(part)
            except Exception: continue
            m = str(j.get("m"))
            if m in ("timescale_update", "du"):
                for b in j["p"][1].get("sds_1", {}).get("s", []): bars.append(b["v"])
            if m in ("symbol_error", "critical_error", "series_error"): err = m; t0 = 0
            if m == "series_completed": t0 = 0
    try: ws.close()
    except Exception: pass
    return bars, err

def fetch_retry(s):
    last = None
    for a in range(5):
        try:
            b, e = fetch(s)
            if b: return s, b, None
            last = e
        except Exception as ex: last = str(ex)[:200]
        time.sleep((8 if "429" in str(last) else 2) * (a + 1) + random.random() * 3)
    return s, [], last or "no data"

def wma(x, L):
    out = [None] * len(x)
    for i in range(L - 1, len(x)):
        seg = x[i - L + 1:i + 1]
        if None in seg: continue
        out[i] = sum((k + 1) * seg[k] for k in range(L)) / (L * (L + 1) / 2)
    return out
def hma(x, L=55):
    a = wma(x, L // 2); b = wma(x, L)
    return wma([(2 * a[i] - b[i]) if a[i] is not None and b[i] is not None else None for i in range(len(x))], round(math.sqrt(L)))
def ema(x, L):
    out = [None] * len(x); a = 2 / (L + 1); s = None
    for i, v in enumerate(x):
        if i == L - 1: s = sum(x[:L]) / L
        elif i >= L: s = a * v + (1 - a) * s
        out[i] = s
    return out
def state(h, p):
    if h >= 0: return "DARK GREEN" if h > p else "LIGHT GREEN"
    return "DARK RED" if h < p else "LIGHT RED"
def rnd(v): return float(f"{v:.6g}") if isinstance(v, float) else v

def analyse(s, B, today):
    bj = [i for i in range(1, len(B)) if B[i][0] < B[i - 1][0]]
    if bj: B = B[bj[-1]:]
    n = len(B); rec = {"coin": s}
    if n == 0: rec["status"] = "fetch error / no data"; return rec, [], [], [], []
    t = [b[0] for b in B]; o = [b[1] for b in B]; c = [b[4] for b in B]
    box = Counter(round(abs(c[i] - o[i]), 12) for i in range(n)).most_common(1)[0][0]
    H = hma(c); e12 = ema(c, 12); e26 = ema(c, 26)
    macd = [e12[i] - e26[i] if e26[i] is not None else None for i in range(n)]
    sig = [None] * n; vals = [(i, v) for i, v in enumerate(macd) if v is not None]; sv = None
    for k, (i, v) in enumerate(vals):
        if k == 8: sv = sum(v2 for _, v2 in vals[:9]) / 9
        elif k > 8: sv = 0.2 * v + 0.8 * sv
        if k >= 8: sig[i] = sv
    hist = [macd[i] - sig[i] if sig[i] is not None else None for i in range(n)]
    col = lambda i: "G" if c[i] > o[i] else "R"
    ib = [i for i in range(n) if t[i] >= START]
    fv = next((i for i in range(n) if H[i] is not None and i >= 2 and H[i - 2] is not None and hist[i - 1] is not None and hist[i] is not None), None)
    flips = buys = sells = skipped = 0; matches = []; allflips = []
    for i in ib:
        if i < 1 or col(i) == col(i - 1): continue
        flips += 1
        if fv is None or i < fv or H[i - 2] is None or hist[i - 1] is None or hist[i - 2] is None:
            skipped += 1; continue
        hc = "GREEN" if H[i] > H[i - 2] else "RED"
        b, a = state(hist[i - 1], hist[i - 2]), state(hist[i], hist[i - 1])
        if col(i) == "R":
            side = "SELL"; hok = hc == "RED"; mok = (b, a) in [("DARK GREEN", "LIGHT GREEN"), ("LIGHT RED", "DARK RED")]
        else:
            side = "BUY"; hok = hc == "GREEN"; mok = (b, a) in [("DARK RED", "LIGHT RED"), ("LIGHT GREEN", "DARK GREEN")]
        d = D(t[i])
        r = {k: rnd(v) for k, v in dict(coin=s, date=d, side=side, brick_open=o[i], brick_close=c[i], box_size=box, hull_color=hc,
              mhull=H[i], shull=H[i - 2], hist_before=hist[i - 1], state_before=b, hist_after=hist[i], state_after=a,
              hull_ok=hok, macd_ok=mok, match=hok and mok, status="FORMING" if d >= today else "CONFIRMED").items()}
        allflips.append(r)
        if r["match"]:
            matches.append(r); buys += side == "BUY"; sells += side == "SELL"
    if fv is None: st = "too little history: Hull/MACD never warm (needs ~60 bricks)"
    elif not ib: st = "no bricks in 2026"
    elif fv <= ib[0]: st = "ok"
    else: st = "partial: Hull/MACD warm only from " + D(t[fv])
    if n >= 5000: st += " | feed capped at 5000 bricks, history truncated"
    rec.update({k: rnd(v) for k, v in dict(status=st, box_size=box, total_bricks=n, history_from=D(t[0]), bricks_in_window=len(ib),
                flips=flips, unscored_flips=skipped, buys=buys, sells=sells, latest_brick_date=D(t[-1]),
                latest_brick_color="GREEN" if col(n - 1) == "G" else "RED", latest_close=c[-1],
                latest_brick_forming=D(t[-1]) >= today,
                indicators_valid_from=D(t[fv]) if fv is not None else None).items()})
    bricks = [[D(t[i]), rnd(o[i]), rnd(c[i])] for i in ib]
    full = []
    for i in ib:
        hcol = None if (H[i] is None or i < 2 or H[i - 2] is None) else ("GREEN" if H[i] > H[i - 2] else "RED")
        hs = None if (hist[i] is None or i < 1 or hist[i - 1] is None) else state(hist[i], hist[i - 1])
        full.append([D(t[i]), rnd(o[i]), rnd(B[i][2]), rnd(B[i][3]), rnd(c[i]), "GREEN" if col(i) == "G" else "RED",
                     rnd(H[i]), rnd(H[i - 2]) if i >= 2 else None, hcol, rnd(macd[i]), rnd(sig[i]), rnd(hist[i]), hs,
                     i >= 1 and col(i) != col(i - 1), D(t[i]) >= today])
    return rec, matches, allflips, bricks, full

def main():
    now = datetime.now(timezone.utc); today = now.strftime("%Y-%m-%d")
    prev = None
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT))
        except Exception: prev = None
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(fetch_retry, SYMS))
    summ, matches, errors = [], [], {}
    trx = {}
    prev_summ = {r["coin"]: r for r in (prev or {}).get("summary", [])}
    full_all = {}
    FULL = os.path.join(os.path.dirname(OUT), "data", "all_bricks.json")
    try: prev_full = json.load(open(FULL)).get("coins", {})
    except Exception: prev_full = {}
    for s, B, err in res:
        if err and not B:
            errors[s] = err
            if s in prev_summ:  # carry forward last good data for this coin
                summ.append(dict(prev_summ[s], stale=True))
                matches += [m for m in prev.get("matches", []) if m["coin"] == s]
                if s == "BINGX:TRXUSDT.P": trx = prev.get("trx", {})
                if s in prev_full: full_all[s] = prev_full[s]
                continue
        rec, m, af, bricks, full = analyse(s, B, today)
        summ.append(rec); matches += m; full_all[s] = full
        if s == "BINGX:TRXUSDT.P": trx = {"flips": af, "bricks": bricks}
    # Guard: if most fetches failed keep previous data untouched
    if len(errors) > len(SYMS) // 3 and os.path.exists(OUT):
        print("Too many fetch errors, keeping previous data:", errors); sys.exit(1)
    matches.sort(key=lambda r: (r["date"], r["coin"]), reverse=True)
    data = {
        "source": "TradingView chart feed (BingX symbols), daily Renko ATR(14), wicks on; Hull Suite HMA 55 + MACD 12/26/9 on brick closes",
        "window_from": "2026-01-01",
        "rules": {"SELL": "green->red flip AND Hull RED AND hist DARK GREEN->LIGHT GREEN or LIGHT RED->DARK RED",
                  "BUY": "red->green flip AND Hull GREEN AND hist DARK RED->LIGHT RED or LIGHT GREEN->DARK GREEN"},
        "totals": {"coins": len(summ), "buys": sum(r.get("buys", 0) for r in summ), "sells": sum(r.get("sells", 0) for r in summ)},
        "summary": summ, "matches": matches, "trx": trx, "fetch_errors": {k: v[:120] for k, v in errors.items()},
    }
    core_changed = prev is None or {k: v for k, v in prev.items() if k not in ("last_scan_utc", "last_change_utc")} != data
    data["last_change_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ") if core_changed else prev.get("last_change_utc")
    data["last_scan_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w"), separators=(",", ":"))
    # Full per-brick dataset (2026 onwards) + per-coin CSVs
    cols = ["date", "open", "high", "low", "close", "brick_color", "mhull", "shull", "hull_color", "macd", "signal", "hist", "hist_color", "flip", "forming"]
    fulldoc = {"source": data["source"], "window_from": "2026-01-01", "columns": cols, "coins": full_all}
    old = None
    try: old = json.load(open(FULL))
    except Exception: pass
    if old != fulldoc:
        os.makedirs(os.path.join(os.path.dirname(FULL), "coins"), exist_ok=True)
        json.dump(fulldoc, open(FULL, "w"), separators=(",", ":"))
        import csv
        for sym, rows in full_all.items():
            with open(os.path.join(os.path.dirname(FULL), "coins", sym.replace(":", "_") + ".csv"), "w", newline="") as f:
                w = csv.writer(f); w.writerow(cols); w.writerows(rows)
    print("totals", data["totals"], "errors", len(errors), "changed", core_changed)
    if os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"changed={'true' if core_changed else 'false'}\n")

if __name__ == "__main__":
    main()
