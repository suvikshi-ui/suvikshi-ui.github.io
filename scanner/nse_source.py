"""NSE-only data source for Indian equities (charting.nseindia.com daily OHLC) + TradingView-style Renko builder.
No other data source is used for Indian stocks."""
import time, threading, math
from datetime import datetime, timezone, timedelta
import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
BASE = "https://charting.nseindia.com/v1"
FROM = datetime(2021, 1, 1, tzinfo=timezone.utc)
TICK = 0.05
_local = threading.local()

def _session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept": "application/json", "Referer": "https://charting.nseindia.com/"})
        try: s.get("https://charting.nseindia.com/", timeout=15)
        except Exception: pass
        _local.s = s
    return s

def daily(symbol):
    """Return list of dicts (t seconds UTC, open, high, low, close, volume) for NSE <symbol>-EQ from 2021, oldest first."""
    S = _session()
    r = S.get(BASE + "/exchanges/symbolsDynamic", params={"symbol": symbol, "segment": ""}, timeout=20)
    r.raise_for_status()
    want = symbol.upper() + "-EQ"
    hit = [x for x in r.json().get("data", []) if str(x.get("symbol", "")).upper() == want]
    if not hit: raise RuntimeError("symbol not found on NSE charting: " + want)
    p = {"token": hit[0]["scripcode"], "fromDate": int(FROM.timestamp()), "toDate": int(time.time()) + 86400,
         "symbol": want, "symbolType": "Equity", "chartType": "D", "timeInterval": 1}
    r = S.get(BASE + "/charts/symbolHistoricalData", params=p, timeout=30)
    r.raise_for_status()
    rows = r.json().get("data") or []
    out = []
    for x in rows:
        t = x["time"] / 1000
        if t < FROM.timestamp(): continue
        out.append({"t": t, "o": float(x["open"]), "h": float(x["high"]), "l": float(x["low"]), "c": float(x["close"]), "v": float(x.get("volume") or 0)})
    out.sort(key=lambda b: b["t"])
    # de-duplicate same day
    ded = {}
    for b in out: ded[datetime.fromtimestamp(b["t"], timezone.utc).date()] = b
    return [ded[k] for k in sorted(ded)]

# ---------- Official NSE bhavcopy correction ----------
# The charting feed's close/volume can differ from NSE's official closing price (e.g. 5-13 Feb 2026).
# For every session where the official CM bhavcopy (EQ series) is available we use the bhavcopy values,
# keeping the charting feed's corporate-action adjustment (if all four prices differ by one constant ratio,
# the charting row is a back-adjusted price and is kept).
import os, io, csv, zipfile, json
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "nifty100_bhav.json")
def _bhav_urls(d):
    dt = datetime.strptime(d, "%Y-%m-%d"); m = dt.strftime("%b").upper()
    return [f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{dt:%Y%m%d}_F_0000.csv.zip",
            f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{dt:%Y}/{m}/cm{dt:%d}{m}{dt:%Y}bhav.csv.zip"]
ALIAS = {"ADANIENSOL": ["ADANITRANS"], "ETERNAL": ["ZOMATO"], "LTM": ["LTIM", "LTI"], "MOTHERSON": ["MOTHERSUMI"],
         "SHRIRAMFIN": ["SRTRANSFIN"], "TMPV": ["TATAMOTORS"], "ZYDUSLIFE": ["CADILAHC"]}   # renamed symbols -> current
def fetch_bhav(d, syms):
    rev = {a: s for s in syms for a in ALIAS.get(s, [])}
    allsyms = set(syms) | set(rev)
    for u in _bhav_urls(d):
        try:
            r = requests.get(u, headers={"User-Agent": UA}, timeout=30)
            if r.status_code != 200 or r.content[:2] != b"PK": continue
            z = zipfile.ZipFile(io.BytesIO(r.content)); txt = z.read(z.namelist()[0]).decode("utf-8", "replace")
            out = {}
            for row in csv.DictReader(io.StringIO(txt)):
                row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                if "TckrSymb" in row and row.get("SctySrs") == "EQ" and row["TckrSymb"] in allsyms:
                    out[rev.get(row["TckrSymb"], row["TckrSymb"])] = [float(row["OpnPric"]), float(row["HghPric"]), float(row["LwPric"]), float(row["ClsPric"]), float(row["TtlTradgVol"] or 0)]
                elif "SYMBOL" in row and row.get("SERIES") == "EQ" and row["SYMBOL"] in allsyms:
                    out[rev.get(row["SYMBOL"], row["SYMBOL"])] = [float(row["OPEN"]), float(row["HIGH"]), float(row["LOW"]), float(row["CLOSE"]), float(row["TOTTRDQTY"] or 0)]
            # current symbol wins over an alias row on the same day
            return out
        except Exception: continue
    return None
def load_cache():
    try: return json.load(open(CACHE))
    except Exception: return {"source": "NSE CM bhavcopy archives (EQ series), nsearchives.nseindia.com", "data": {}, "missing": []}
def update_cache(cache, session_dates, syms, max_new=15):
    """Download bhavcopies for sessions not yet cached (newest first, at most max_new per run)."""
    have = cache["data"]; added = 0
    todo = sorted((x for x in session_dates if x not in have), reverse=True)
    if len(have) >= 100: todo = todo[:max_new]          # first run builds the full cache, later runs only add new sessions
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex:
        for d, b in zip(todo, ex.map(lambda x: fetch_bhav(x, syms), todo)):
            if b: have[d] = b; added += 1
    if added:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(cache, open(CACHE, "w"), separators=(",", ":"))
    return added
def _close(a, b): return abs(a - b) <= 0.05 or abs(a - b) <= 0.001 * max(abs(a), abs(b))
def correct(sym, bars, cache):
    """Apply official bhavcopy values. Returns stats dict."""
    st = {"bhav_days": 0, "corrected": 0, "adjusted_kept": 0, "unresolved": 0}
    data = cache.get("data", {})
    for b in bars:
        d = datetime.fromtimestamp(b["t"], timezone.utc).strftime("%Y-%m-%d")
        x = (data.get(d) or {}).get(sym)
        if not x: continue
        st["bhav_days"] += 1
        cur = [b["o"], b["h"], b["l"], b["c"]]
        if all(_close(cur[i], x[i]) for i in range(4)) and abs(b["v"] - x[4]) <= 0.001 * max(x[4], 1):
            continue
        # factor f > 1 means the charting row is back-adjusted for a later corporate action (bhav is raw)
        f = x[0] / cur[0] if cur[0] else 1.0
        if abs(f - 1) <= 0.002: f = 1.0
        sx = [x[0] / f, x[1] / f, x[2] / f, x[3] / f]
        if all(_close(cur[i], sx[i]) for i in range(4)) and f != 1.0:
            st["adjusted_kept"] += 1; continue                 # identical session, adjusted scale
        if _close(cur[0], sx[0]) and sx[1] >= cur[1] - 0.05 and sx[2] <= cur[2] + 0.05:
            # same session; charting row incomplete (close/volume or range not final) -> official bhavcopy values (scaled if adjusted)
            b["o"], b["h"], b["l"], b["c"], b["v"] = sx[0], sx[1], sx[2], sx[3], x[4] * f
            st["corrected"] += 1; continue
        st["unresolved"] += 1
    return st

def atr_box(bars, length=14):
    """Wilder ATR(14) on daily candles at the latest bar, rounded to the 0.05 tick (TradingView 'ATR' box style)."""
    trs = []
    for i, b in enumerate(bars):
        if i == 0: trs.append(b["h"] - b["l"]); continue
        pc = bars[i - 1]["c"]
        trs.append(max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc)))
    if len(trs) < length: return None
    a = sum(trs[:length]) / length
    for tr in trs[length:]: a = (a * (length - 1) + tr) / length
    return round(max(TICK, round(a / TICK) * TICK), 2)

def renko(bars, box):
    """Traditional close-based Renko anchored to box multiples, 2-box reversal, with wicks.
    Returns bricks as [t, open, high, low, close, volume] (same shape as the TradingView feed)."""
    if not bars or not box: return []
    base = math.floor(bars[0]["c"] / box) * box
    lo = hi = base; d = 0
    run_h, run_l, vol = -1e18, 1e18, 0.0
    out = []
    r = lambda v: round(v, 4)
    for b in bars:
        run_h = max(run_h, b["h"]); run_l = min(run_l, b["l"]); vol += b["v"]
        c = b["c"]; made = 0
        while True:
            if d >= 0 and c >= hi + box - 1e-9:
                o, cl = hi, hi + box; lo, hi, d = o, cl, 1
                out.append([b["t"] + made * 0.001, r(o), r(max(cl, run_h) if False else cl), r(min(o, run_l)), r(cl), vol])
            elif d <= 0 and c <= lo - box + 1e-9:
                o, cl = lo, lo - box; hi, lo, d = o, cl, -1
                out.append([b["t"] + made * 0.001, r(o), r(max(o, run_h)), r(cl), r(cl), vol])
            elif d == 1 and c <= lo - box + 1e-9:
                o, cl = lo, lo - box; hi, lo, d = o, cl, -1
                out.append([b["t"] + made * 0.001, r(o), r(max(o, run_h)), r(cl), r(cl), vol])
            elif d == -1 and c >= hi + box - 1e-9:
                o, cl = hi, hi + box; lo, hi, d = o, cl, 1
                out.append([b["t"] + made * 0.001, r(o), r(cl), r(min(o, run_l)), r(cl), vol])
            else:
                break
            made += 1; run_h, run_l, vol = -1e18, 1e18, 0.0
    return out

def fetch_bricks(symbol, cache=None):
    """Plug-in entry point used by scan.py: returns (bricks, error, meta)."""
    bars = daily(symbol)
    stats = correct(symbol, bars, cache) if cache else {}
    if len(bars) < 30: return [], "too little NSE daily history (%d days)" % len(bars), {}
    box = atr_box(bars)
    gaps = [datetime.fromtimestamp(bars[i]["t"], timezone.utc).strftime("%Y-%m-%d") for i in range(1, len(bars))
            if bars[i]["o"] < 0.6 * bars[i - 1]["c"] or bars[i]["o"] > 1.6 * bars[i - 1]["c"]]
    # per-session open and previous close (used for the follow-through "Strong setup" tag; same NSE bars as the Renko)
    sess = {datetime.fromtimestamp(bars[i]["t"], timezone.utc).strftime("%Y-%m-%d"): [bars[i]["o"], bars[i - 1]["c"] if i else None]
            for i in range(len(bars))}
    return renko(bars, box), None, {"box": box, "sessions": sess, "daily_from": datetime.fromtimestamp(bars[0]["t"], timezone.utc).strftime("%Y-%m-%d"),
                                   "daily_to": datetime.fromtimestamp(bars[-1]["t"], timezone.utc).strftime("%Y-%m-%d"), "days": len(bars), "gaps": gaps, "bhav": stats}
