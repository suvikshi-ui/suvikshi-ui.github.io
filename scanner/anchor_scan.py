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
RULE = ("Rule (2 Nov 2026 16:35 IST): ZigZag++ 12/5/2 pivots final, raw swings ignored. SELL: A1 = previous day's last ZigZag HH; "
        "a ZigZag LH between A1 and A2 rejects (LL/HL allowed); A2 = first complete candle today fully above A1; entry = first close below A1. "
        "BUY mirror (ZigZag HH rejects). Stop = prior candle high/low, target 1:2, both-touch = stop. NSE entries 09:30-14:00, force-close 15:00. "
        "Crypto entries from 05:30 IST, no cutoff; unfilled Running force-closed at next 05:30.")
CRYPTO = json.load(open(os.path.join(HERE, "anchor_symbols.json")))
NSE = [c["tv_ticker"] for c in json.load(open(os.path.join(HERE, "nifty100.json")))["constituents"]]

def bars(ticker, res, n):
    """TradingView OHLC bars [t, o, h, l, c, v] + mintick."""
    for attempt in range(3):
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
            err = str(e); time.sleep(2 + attempt * 3)
    return [], None, err or "no data"

def zigzag(H, L, tick):
    """MT4-style ZigZag (depth/deviation/backstep) as used by ZigZag++. Returns [(index, 'H'|'L', price)] alternating.
    The last pivot is still forming (repaints) and is dropped -> remaining pivots are final."""
    n, dev = len(H), DEV_TICKS * tick
    hb, lb = [0.0] * n, [0.0] * n; lastlow = lasthigh = None
    for i in range(DEPTH, n):
        v = min(L[i - DEPTH + 1:i + 1])
        if v == lastlow: v = 0.0
        else:
            lastlow = v
            if L[i] - v > dev: v = 0.0
            else:
                for b in range(1, BACKSTEP + 1):
                    if lb[i - b] and lb[i - b] > v: lb[i - b] = 0.0
        lb[i] = v if L[i] == v else 0.0
        v = max(H[i - DEPTH + 1:i + 1])
        if v == lasthigh: v = 0.0
        else:
            lasthigh = v
            if v - H[i] > dev: v = 0.0
            else:
                for b in range(1, BACKSTEP + 1):
                    if hb[i - b] and hb[i - b] < v: hb[i - b] = 0.0
        hb[i] = v if H[i] == v else 0.0
    piv = []
    for i in range(n):
        for typ, val in (("H", hb[i]), ("L", lb[i])):
            if not val: continue
            if piv and piv[-1][1] == typ:
                if (typ == "H" and val >= piv[-1][2]) or (typ == "L" and val <= piv[-1][2]): piv[-1] = (i, typ, val)
            else: piv.append((i, typ, val))
    return piv[:-1]

def label(piv):
    """HH/LH for highs, LL/HL for lows (vs previous pivot of the same kind)."""
    out, ph, pl = [], None, None
    for i, t, v in piv:
        if t == "H": lab = "HH" if ph is None or v > ph else "LH"; ph = v
        else: lab = "LL" if pl is None or v < pl else "HL"; pl = v
        out.append((i, lab, v))
    return out

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
    ok = [r for r, e in results if r]
    errs = [s for s, (r, e) in zip(syms, results) if not r]
    if errs: print(market, "errors:", len(errs), errs[:10], file=sys.stderr)
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
    now = datetime.now(IST)
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

if __name__ == "__main__": main()
