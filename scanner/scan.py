"""Live Renko + Hull Suite 55 + MACD 12/26/9 strategy scan (signal only, no trades/alerts).
Data: TradingView public chart feed (anonymous), BingX symbols, daily Renko ATR(14), wicks on.
Writes trx/data.json. Usage: python scanner/scan.py [out_path]"""
import json, math, random, string, re, sys, time, os
from collections import Counter
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import websocket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
MARKET = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--market=")), "crypto")
OUT = args[0] if args else os.path.join(HERE, "..", "trx", "data.json")
if MARKET == "india":
    # Indian equities: NSE only (charting.nseindia.com daily OHLC -> own TradingView-style Renko). Constituents: NSE Indices list.
    SYMS = ["NSE:" + c["symbol"] for c in json.load(open(os.path.join(HERE, "nifty100.json")))["constituents"]]
    SOURCE = "NSE only: charting.nseindia.com daily OHLC (from 2021), Renko built by BrickFlow (traditional, close-based, ATR(14) box from the latest daily ATR rounded to 0.05, wicks); Hull Suite HMA 55 + MACD 12/26/9 on brick closes"
else:
    SYMS = json.load(open(os.path.join(HERE, "symbols.json")))
    SOURCE = "TradingView chart feed (BingX symbols), daily Renko ATR(14), wicks on; Hull Suite HMA 55 + MACD 12/26/9 on brick closes"
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

BHAV = None; BHAVSTATS = {}; SESSIONS = {}
# Follow-through "Strong setup" tag (Nifty only; a label, it never removes or changes setups).
# Gap = setup-day open vs the prior NSE close, signed in the setup direction; threshold STRONG_GAP_PCT %.
# Modes: "or" = gap OR 2+ bricks; "and" = gap AND 2+ bricks; "gap_single" = gap AND only one brick that day.
STRONG_MODE = "gap_single"
STRONG_GAP_PCT = 0.5
STRONG_MIN_BRICKS = 2
def strong_tag(gap_pct, nbricks):
    g = gap_pct is not None and gap_pct >= STRONG_GAP_PCT - 1e-9
    k = nbricks is not None and nbricks >= STRONG_MIN_BRICKS
    m = STRONG_MODE.lower()
    if m == "and": return g and k
    if m == "gap_single": return g and nbricks == 1
    return g or k
try:
    _ig = json.load(open(os.path.join(HERE, "nifty_integrity.json")))
    EXCLUDED = {r["symbol"]: r["reasons"] for r in _ig.get("rows", []) if r.get("gate") == "FAIL"}
    INTEGRITY = _ig
except Exception:
    EXCLUDED = {}; INTEGRITY = None

def fetch_retry(s):
    if MARKET == "india":
        import nse_source
        last = None
        for a in range(3):
            try:
                if s.split(":", 1)[1] in EXCLUDED: return s, [], "excluded by data-integrity gate: " + EXCLUDED[s.split(":", 1)[1]]
                b, e, meta = nse_source.fetch_bricks(s.split(":", 1)[1], BHAV)
                BHAVSTATS[s] = meta.get("bhav", {}); SESSIONS[s] = meta.get("sessions", {})
                if b or e: return s, b, e
            except Exception as ex: last = str(ex)[:200]
            time.sleep(2 * (a + 1) + random.random() * 2)
        return s, [], last or "no data"
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
        if MARKET == "india" and r["match"]:
            ses = SESSIONS.get(s, {}).get(d)
            sg = 1 if side == "BUY" else -1
            gp = ((ses[0] - ses[1]) / ses[1] * 100 * sg) if ses and ses[1] else None
            nbd = sum(1 for tt in t if D(tt) == d)
            r.update(gap_pct=round(gp, 3) if gp is not None else None, bricks_that_day=nbd, strong=strong_tag(gp, nbd))
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
    full = []; seq = {}
    for i in ib:
        hcol = None if (H[i] is None or i < 2 or H[i - 2] is None) else ("GREEN" if H[i] > H[i - 2] else "RED")
        hs = None if (hist[i] is None or i < 1 or hist[i - 1] is None) else state(hist[i], hist[i - 1])
        d = D(t[i]); seq[d] = seq.get(d, 0) + 1
        full.append([d, datetime.fromtimestamp(int(t[i]), timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), seq[d],
                     rnd(o[i]), rnd(B[i][2]), rnd(B[i][3]), rnd(c[i]), "GREEN" if col(i) == "G" else "RED", rnd(box),
                     rnd(H[i]), rnd(H[i - 2]) if i >= 2 else None, hcol, rnd(macd[i]), rnd(sig[i]), rnd(hist[i]), hs,
                     hcol is not None and hs is not None, i >= 1 and col(i) != col(i - 1), d >= today])
    return rec, matches, allflips, bricks, full

def main():
    now = datetime.now(timezone.utc); today = now.strftime("%Y-%m-%d")
    if MARKET == "india":  # NSE daily candle closes 15:30 IST; after that nothing is "forming"
        from datetime import timedelta
        ist = now + timedelta(hours=5, minutes=30)
        today = (ist if (ist.hour, ist.minute) < (15, 30) else ist + timedelta(days=1)).strftime("%Y-%m-%d")
    prev = None
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT))
        except Exception: prev = None
    global BHAV
    if MARKET == "india":
        import nse_source
        BHAV = nse_source.load_cache()
        try:
            ses = [datetime.fromtimestamp(b["t"], timezone.utc).strftime("%Y-%m-%d") for b in nse_source.daily("RELIANCE")]
            ses = [d for d in ses if d < today] if (datetime.now(timezone.utc) + __import__("datetime").timedelta(hours=5, minutes=30)).hour < 19 else ses
            print("bhavcopies added", nse_source.update_cache(BHAV, ses, {x.split(":", 1)[1] for x in SYMS}))
        except Exception as ex_: print("bhav cache update failed:", ex_)
    with ThreadPoolExecutor(4 if MARKET == "india" else 2) as ex:
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
    # ---- active flag + charts ----
    cols_idx = {k: i for i, k in enumerate(["brick_date", "brick_time_utc", "brick_seq_in_day", "open", "high", "low", "close", "brick_color", "box_size", "mhull", "shull", "hull_color", "macd", "signal", "histogram", "hist_color", "indicators_ready", "flip", "forming"])}
    def rowdict(r):
        g = lambda k: r[cols_idx[k]]
        return {"date": g("brick_date"), "open": g("open"), "high": g("high"), "low": g("low"), "close": g("close"), "mhull": g("mhull"),
                "shull": g("shull"), "macd": g("macd"), "signal": g("signal"), "hist": g("histogram"), "hist_color": g("hist_color")}
    charts_dir = os.path.join(os.path.dirname(OUT), "charts")
    man_path = os.path.join(charts_dir, "manifest.json")
    try: manifest = json.load(open(man_path))
    except Exception: manifest = {}
    rendered = 0
    try:
        import charts as CH
    except Exception as ex:
        CH = None; print("charts disabled:", ex)
    def chart(fname, sym, box, rows, mark):
        nonlocal rendered
        h = CH.slice_hash(sym, rows, mark)
        fp = os.path.join(charts_dir, fname)
        if manifest.get(fname) != h or not os.path.exists(fp):
            CH.render(fp, sym, box, rows, mark, source=("NSE data (charting.nseindia.com, reconciled to NSE bhavcopy)" if MARKET == "india" else "TradingView data (anonymous chart feed)")); manifest[fname] = h; rendered += 1
        return "charts/" + fname
    box_of = {r["coin"]: r.get("box_size") for r in summ}
    for m in matches:
        fr = full_all.get(m["coin"], [])
        k = next((j for j, r in enumerate(fr) if r[0] == m["date"] and r[17] and abs(r[6] - m["brick_close"]) < 1e-12), None)
        if k is None: m["active"] = False; continue
        col_k = fr[k][7]
        m["active"] = all(fr[j][7] == col_k for j in range(k + 1, len(fr)))
        m["bricks_since"] = len(fr) - 1 - k
        if CH:
            a, b = max(0, k - 45), min(len(fr), k + 13)
            rows = [rowdict(r) for r in fr[a:b]]
            mark = {"idx": k - a, "side": m["side"], "date": m["date"], "close": m["brick_close"]}
            m["chart"] = chart(f"{m['coin'].replace(':', '_')}_{m['date']}_{m['side']}_{fr[k][2]}.png", m["coin"], box_of.get(m["coin"]), rows, mark)
    if CH:
        for r in summ:
            fr = full_all.get(r["coin"], [])
            if not fr: continue
            a = max(0, len(fr) - 55)
            rows = [rowdict(x) for x in fr[a:]]
            act = [m for m in matches if m["coin"] == r["coin"] and m.get("active")]
            mark = None
            if act:
                m = act[0]; k = len(fr) - 1 - m["bricks_since"]
                if k >= a: mark = {"idx": k - a, "side": m["side"], "date": m["date"], "close": m["brick_close"]}
            r["chart_latest"] = chart(f"latest/{r['coin'].replace(':', '_')}.png", r["coin"], r.get("box_size"), rows, mark)
        os.makedirs(charts_dir, exist_ok=True)
        json.dump(manifest, open(man_path, "w"), indent=0, sort_keys=True)
    print("charts rendered", rendered)
    matches.sort(key=lambda r: (r["date"], r["coin"]), reverse=True)
    data = {
        "market": MARKET, "source": SOURCE,
        "window_from": "2026-01-01",
        "rules": {"SELL": "green->red flip AND Hull RED AND hist DARK GREEN->LIGHT GREEN or LIGHT RED->DARK RED",
                  "BUY": "red->green flip AND Hull GREEN AND hist DARK RED->LIGHT RED or LIGHT GREEN->DARK GREEN"},
        "totals": {"coins": len(summ), "buys": sum(r.get("buys", 0) for r in summ), "sells": sum(r.get("sells", 0) for r in summ)},
        **({"strong_rule": {"mode": STRONG_MODE, "gap_pct": STRONG_GAP_PCT, "min_bricks": STRONG_MIN_BRICKS,
                            "text": f"Strong = setup-day open gapped >= {STRONG_GAP_PCT}% in the setup's direction vs the prior NSE close " +
                                    {"and": f"AND {STRONG_MIN_BRICKS}+ Renko bricks formed that day",
                                     "gap_single": "AND only one Renko brick formed that day"}.get(STRONG_MODE.lower(),
                                     f"OR {STRONG_MIN_BRICKS}+ Renko bricks formed that day")}} if MARKET == "india" else {}),
        "summary": summ, "matches": matches, "trx": trx,
        "integrity": ({"generated_ist": INTEGRITY.get("generated_ist"), "summary": INTEGRITY.get("summary"), "excluded": EXCLUDED,
                       "bhav_correction": {"stocks": len(BHAVSTATS), "corrected_days": sum(v.get("corrected", 0) for v in BHAVSTATS.values()),
                                           "unresolved_days": sum(v.get("unresolved", 0) for v in BHAVSTATS.values()),
                                           "bhav_cache_days": len((BHAV or {}).get("data", {}))}} if MARKET == "india" and INTEGRITY else None), "fetch_errors": {k: v[:120] for k, v in errors.items()},
    }
    core_changed = prev is None or {k: v for k, v in prev.items() if k not in ("last_scan_utc", "last_change_utc")} != data
    data["last_change_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ") if core_changed else prev.get("last_change_utc")
    data["last_scan_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w"), separators=(",", ":"))
    # Full per-brick dataset (2026 onwards) + per-coin CSVs
    cols = ["brick_date", "brick_time_utc", "brick_seq_in_day", "open", "high", "low", "close", "brick_color", "box_size", "mhull", "shull", "hull_color", "macd", "signal", "histogram", "hist_color", "indicators_ready", "flip", "forming"]
    fulldoc = {"market": MARKET, "source": data["source"], "window_from": "2026-01-01", "columns": cols, "coins": full_all}
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
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"changed={'true' if (core_changed or rendered) else 'false'}\n")

if __name__ == "__main__":
    main()
