"""Anchor Break live scanner -> trx/anchor_live.json (schema consumed unchanged by trx/anchor_live.html).
Data: TradingView public chart feed only (same websocket protocol/helpers as scanner/tv_source.py).
Rules: see scanner/ANCHOR_README.md (reconstructed from the page's own rule text, rule_a1 2 Nov 2026 16:35 IST)."""
import json, os, re, sys, time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import websocket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv_source import _frame, _rs

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.path.join(HERE, "..", "trx", "anchor_live.json")
IST = timezone(timedelta(hours=5, minutes=30))
DEPTH, DEV_TICKS, BACKSTEP = 12, 5, 2          # ZigZag++ 12/5/2
HIST_KEEP = 30
RULE = ("Rule (2 Nov 2026 16:35 IST): ZigZag++ 12/5/2 pivots (exact DevLucem/ZigLib port, confirmed only), raw swings ignored. SELL: A1 = previous day's last ZigZag HH; "
        "a ZigZag LH between A1 and A2 rejects (LL/HL allowed); A2 = first complete candle today fully above A1; entry = first close below A1. "
        "BUY mirror (ZigZag HH rejects). Stop = prior candle high/low, target 1:2, both-touch = stop. NSE entries 09:30-14:00, force-close 15:00. "
        "Crypto entries from 05:30 IST, no cutoff; unfilled Running force-closed at next 05:30.")
CRYPTO = json.load(open(os.path.join(HERE, "anchor_symbols.json")))
NSE = [c["tv_ticker"] for c in json.load(open(os.path.join(HERE, "nifty100.json")))["constituents"]]

def bars(ticker, res, n):
    """TradingView OHLC bars [t, o, h, l, c, v] + mintick."""
    for attempt in range(1):   # single attempt here; retries (fresh websocket each) happen in run_market's second pass
        try:
            ws = websocket.create_connection("wss://data.tradingview.com/socket.io/websocket?from=chart%2F&type=chart",
                                             header=["Origin: https://www.tradingview.com"], timeout=30)
            cs = "cs_" + _rs(); sym = {"symbol": ticker, "adjustment": "splits", "session": "regular"}
            for m, p in [("set_auth_token", ["unauthorized_user_token"]), ("chart_create_session", [cs, ""]),
                         ("resolve_symbol", [cs, "s1", "=" + json.dumps(sym)]), ("create_series", [cs, "sds_1", "s1", "s1", res, n, ""])]:
                ws.send(_frame(m, p))
            out, tick, err, t0 = {}, None, None, time.time()
            while time.time() - t0 < 40:
                raw = ws.recv()
                for part in re.split(r"~m~\d+~m~", raw):
                    if not part: continue
                    if part.startswith("~h~"): ws.send(f"~m~{len(part)}~m~{part}"); continue
                    try: j = json.loads(part)
                    except Exception: continue
                    m = j.get("m")
                    if m == "symbol_resolved":
                        x = j["p"][2]; tick = (x.get("minmov") or 1) / (x.get("pricescale") or 100)
                    elif m in ("timescale_update", "du"):
                        for b in j["p"][1].get("sds_1", {}).get("s", []): out[b["v"][0]] = b["v"][:6]
                    elif m in ("symbol_error", "critical_error", "series_error"): err = m; t0 = 0
                    elif m == "series_completed": t0 = 0
            ws.close()
            if out: return [out[k] for k in sorted(out)], tick or 1e-8, None
            if err: return [], None, err
        except Exception as e:
            err = str(e)
    return [], None, err or "no data"

def zigzag(H, L, tick, with_live=False):
    """Exact port of DevLucem ZigZag++ / ZigLib (MT4-style), identical to live-scanner strategy.js zigzagPP().
    p_lw=-lowestbars(Depth), p_hg=-highestbars(Depth); lowing = lw==p_lw or low-low[p_lw] > Dev*mintick (highing mirror);
    lh=barssince(not highing[1]), ll=barssince(not lowing[1]); down = barssince(not(lh>ll)) >= Backstep;
    if lw!=p_lw and (not down[1] or lower): lw = p_lw<hg ? p_lw : 0 ; if hg!=p_hg and (down[1] or higher): hg = p_hg<lw ? p_hg : 0.
    down flips true -> swing HIGH confirmed at bar-hg; flips false -> swing LOW at bar-lw.
    Returns confirmed pivots [(index, 'H'|'L', price, confirm_index)]; the repainting live leg end is excluded
    (returned separately when with_live=True)."""
    n, D = len(H), DEV_TICKS * tick
    def low_off(i):
        o = 0
        for j in range(1, DEPTH):
            if i - j < 0: break
            if L[i - j] < L[i - o]: o = j
        return o
    def high_off(i):
        o = 0
        for j in range(1, DEPTH):
            if i - j < 0: break
            if H[i - j] > H[i - o]: o = j
        return o
    nan = float("nan")
    lowat = lambda i, o: L[i - o] if i - o >= 0 else nan
    highat = lambda i, o: H[i - o] if i - o >= 0 else nan
    lw = hg = 1
    lowing, highing, down, piv = [False] * n, [False] * n, [False] * n, []
    nh = nl = nd = None
    for i in range(n):
        lw += 1; hg += 1
        pl, ph = low_off(i), high_off(i)
        lowing[i] = lw == pl or L[i] - lowat(i, pl) > D
        highing[i] = hg == ph or highat(i, ph) - H[i] > D
        if i > 0 and not highing[i - 1]: nh = i
        if i > 0 and not lowing[i - 1]: nl = i
        lh = nan if nh is None else i - nh
        ll = nan if nl is None else i - nl
        if not (lh > ll): nd = i
        down[i] = nd is not None and i - nd >= BACKSTEP
        pd = down[i - 1] if i > 0 else False
        lower, higher = lowat(i, lw) > lowat(i, pl), highat(i, hg) < highat(i, ph)
        if lw != pl and (not pd or lower): lw = pl if pl < hg else 0
        if hg != ph and (pd or higher): hg = ph if ph < lw else 0
        if i > 0 and down[i] != pd and i - (hg if down[i] else lw) >= 0:
            if down[i]: piv.append((i - hg, "H", H[i - hg], i))
            else: piv.append((i - lw, "L", L[i - lw], i))
    if not with_live: return piv
    x = lw if down[-1] else hg
    return piv, (n - 1 - x, "L" if down[-1] else "H", (L if down[-1] else H)[n - 1 - x], None)

def label(piv):
    """HH/LH for highs, LL/HL for lows (vs previous pivot of the same kind)."""
    out, ph, pl = [], None, None
    for i, t, v, *_ in piv:
        if t == "H": lab = "HH" if ph is None or v > ph else "LH"; ph = v
        else: lab = "LL" if pl is None or v < pl else "HL"; pl = v
        out.append((i, lab, v))
    return out

RETRY_BACKOFF = (2, 4, 6)                         # seconds before retry pass 1/2/3 for failed symbol fetches
def ts(): return datetime.now(IST).strftime("[%Y-%m-%d %H:%M:%S IST]")

def rnd(v): return float(f"{v:.6g}")

def scan(sym, market, now):
    res, nb = ("15", 700) if market == "crypto" else ("5", 900)
    B, tick, err = bars(("BINGX:" + sym) if market == "crypto" else sym, res, nb)
    if err or len(B) < 50: return None, err or "short"
    step = int(res) * 60
    B = [b for b in B if b[0] + step <= now.timestamp()]               # complete candles only
    T = [datetime.fromtimestamp(b[0], IST) for b in B]
    if market == "crypto": day = [(t - timedelta(hours=5, minutes=30)).date() for t in T]
    else: day = [t.date() for t in T]
    O, H, L, C = ([b[k] for b in B] for k in (1, 2, 3, 4))
    piv = label(zigzag(H, L, tick))
    days = sorted(set(day)); today, prev = days[-1], (days[-2] if len(days) > 1 else None)
    name = sym if market == "crypto" else sym.split(":")[1]
    fmt = lambda i: T[i].strftime("%Y-%m-%d %H:%M")
    res_out = {"last_closed": fmt(len(B) - 1), "armed": [], "trades": []}
    if prev is None: return res_out, None
    for side in ("SELL", "BUY"):
        want, bad = ("HH", "LH") if side == "SELL" else ("LL", "HH")
        a1 = [p for p in piv if day[p[0]] == prev and p[1] == want]
        if not a1: continue
        i1, _, A1 = a1[-1]
        start = day.index(today)
        i2 = next((i for i in range(start, len(B)) if (L[i] > A1 if side == "SELL" else H[i] < A1)), None)
        if i2 is None: continue
        if any(i1 < p[0] <= i2 and p[1] == bad for p in piv): continue    # rejected entirely
        A2 = H[i2] if side == "SELL" else L[i2]
        base = {"symbol": name, "side": side, "anchor1": rnd(A1), "anchor1_time": fmt(i1), "anchor2": rnd(A2),
                "anchor2_time": fmt(i2), "anchor2_confirmed": fmt(i2), "trigger": rnd(A1)}
        ie = None
        for i in range(i2, len(B)):
            if market == "nse" and not ("09:30" <= T[i].strftime("%H:%M") <= "14:00"): continue
            if (C[i] < A1) if side == "SELL" else (C[i] > A1): ie = i; break
        if ie is None:
            res_out["armed"].append(dict(base, status="waiting entry (anchor 1 close)")); continue
        e = C[ie]; s = H[ie - 1] if side == "SELL" else L[ie - 1]
        risk = (s - e) if side == "SELL" else (e - s)
        if risk <= 0: continue
        tgt = e - 2 * risk if side == "SELL" else e + 2 * risk
        tr = dict(base, id=f"{name}|{side}|{fmt(ie)}", entry=rnd(e), stop=rnd(s), target=rnd(tgt), entry_time=fmt(ie),
                  stop_pct=round(risk / e * 100, 3), variant="Filter" if risk / e >= 0.01 else "No Filter", status="OPEN")
        last = C[-1]
        for i in range(ie + 1, len(B)):
            hs = H[i] >= s if side == "SELL" else L[i] <= s
            ht = L[i] <= tgt if side == "SELL" else H[i] >= tgt
            if hs: tr.update(status="STOP", exit_time=fmt(i), R=-1.0); last = C[i]; break
            if ht: tr.update(status="TARGET", exit_time=fmt(i), R=2.0); last = C[i]; break
            if market == "nse" and T[i].strftime("%H:%M") >= "15:00":
                r = ((e - C[i]) if side == "SELL" else (C[i] - e)) / risk
                tr.update(status="EOD", exit_time=fmt(i), R=round(r, 2)); last = C[i]; break
        tr["last"] = rnd(last)
        tr["R_now"] = round(((e - last) if side == "SELL" else (last - e)) / risk, 2)
        res_out["trades"].append(tr)
    return res_out, None

def run_market(market, prev, now):
    syms = CRYPTO if market == "crypto" else NSE
    with ThreadPoolExecutor(8) as ex: results = list(ex.map(lambda s: scan(s, market, now), syms))
    results = dict(zip(syms, results))
    failed = [s for s in syms if not results[s][0]]
    first_failed, recovered = list(failed), []
    for k, delay in enumerate(RETRY_BACKOFF, 1):      # second pass at end of run: fresh websocket per attempt
        if not failed: break
        time.sleep(delay)
        with ThreadPoolExecutor(8) as ex: again = list(ex.map(lambda s: scan(s, market, now), failed))
        for s_, r in zip(failed, again):
            results[s_] = r
            if r[0]: recovered.append(s_)
        failed = [s_ for s_ in failed if not results[s_][0]]
    for s_ in failed: print(f"{ts()} [retry-failed] {s_}: {str(results[s_][1]).split(" -+-+- ")[0][:160]}", file=sys.stderr)
    print(f"{ts()} {market} fetch summary: {len(syms)} symbols, {len(first_failed)} failed first pass, "
          f"{len(recovered)} recovered {recovered}, {len(failed)} skipped {failed}", file=sys.stderr)
    ok = [results[s_][0] for s_ in syms if results[s_][0]]
    if not ok: return prev
    armed = [a for r in ok for a in r["armed"]]
    trades = [t for r in ok for t in r["trades"]]
    hist = {h["id"]: h for h in (prev or {}).get("a1break_history", [])}
    for t in trades:
        if t["status"] != "OPEN": hist[t["id"]] = t
    hist = sorted(hist.values(), key=lambda r: r.get("exit_time", ""), reverse=True)[:HIST_KEEP]
    opn = [t for t in trades if t["status"] == "OPEN"]
    armed.sort(key=lambda a: a["anchor2_time"], reverse=True)
    return {"universe": "BingX perps (%d)" % len(CRYPTO) if market == "crypto" else "Nifty 100 (NSE)",
            "timeframe": "15m" if market == "crypto" else "5m",
            "last_closed_candle": max(r["last_closed"] for r in ok), "armed": armed, "a1break_open": opn,
            "a1break_history": hist, "closed_R": round(sum(h["R"] for h in hist), 2),
            "run": now.strftime("%Y-%m-%d %H:%M IST")}

def main():
    now = datetime.now(IST); t_start = time.time()
    print(f"{ts()} run start", flush=True)
    try: data = json.load(open(OUT))
    except Exception: data = {}
    nse_open = now.weekday() < 5 and "09:15" <= now.strftime("%H:%M") <= "15:35"
    only = [a.split("=")[1] for a in sys.argv if a.startswith("--only=")]
    data["crypto"] = run_market("crypto", data.get("crypto"), now) if not only or "crypto" in only else data.get("crypto")
    if nse_open or "--force-nse" in sys.argv: data["nse"] = run_market("nse", data.get("nse"), now)
    else: print("NSE closed - keeping last NSE data")
    data["updated"] = now.strftime("%Y-%m-%d %H:%M IST"); data["rule_a1"] = RULE
    data = {k: data.get(k) for k in ("crypto", "nse", "updated", "rule_a1")}
    json.dump(data, open(OUT, "w"), indent=1)
    for k in ("crypto", "nse"):
        d = data.get(k) or {}
        print(k, "armed", len(d.get("armed", [])), "open", len(d.get("a1break_open", [])), "hist", len(d.get("a1break_history", [])), "data to", d.get("last_closed_candle"))

    print(f"{ts()} run end ({time.time() - t_start:.0f}s)", flush=True)

if __name__ == "__main__": main()
