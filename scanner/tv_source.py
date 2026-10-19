"""TradingView-only data source for Indian equities (Nifty 100 tab).
Everything comes from TradingView's public (anonymous) chart feed for NSE:<SYMBOL>:
  * Renko bricks: TradingView's own Renko series - ATR box, length 14, source OHLC (high-low), wicks on.
    Box size, rounding, brick open/high/low/close and wicks are exactly what TradingView returns.
  * Daily candles (for the follow-through gap): TradingView 1D series, split-adjusted, regular session.
  * Symbol mapping and session: TradingView's resolved symbol info.
No other data source is used."""
import json, random, re, string, time
import websocket

ATR_LEN = 14
def _rs(n=12): return "".join(random.choice(string.ascii_lowercase) for _ in range(n))
def _frame(m, p):
    s = json.dumps({"m": m, "p": p}, separators=(",", ":")); return f"~m~{len(s)}~m~{s}"
def tv_symbol(sym):
    """Symbol as listed by TradingView (from its CNX100 constituents, e.g. M&M, BAJAJ_AUTO) -> TradingView ticker."""
    return sym if sym.startswith("NSE:") else "NSE:" + sym

def _series(ticker, renko, n=5000, ver="40"):
    ws = websocket.create_connection("wss://data.tradingview.com/socket.io/websocket?from=chart%2F&type=chart",
                                     header=["Origin: https://www.tradingview.com"], timeout=30)
    cs = "cs_" + _rs()
    sym = {"symbol": ticker, "adjustment": "splits", "session": "regular"}
    if renko:
        sym = {"symbol": sym, "type": f"BarSetRenko@tv-prostudies-{ver}!",
               "inputs": {"source": "close", "sources": "OHLC", "boxSize": 1, "style": "ATR", "atrLength": ATR_LEN, "wicks": True}}
    for m, p in [("set_auth_token", ["unauthorized_user_token"]), ("chart_create_session", [cs, ""]),
                 ("resolve_symbol", [cs, "sds_sym_1", "=" + json.dumps(sym)]),
                 ("create_series", [cs, "sds_1", "s1", "sds_sym_1", "1D", n, ""])]:
        ws.send(_frame(m, p))
    bars, err, info, t0 = [], None, {}, time.time()
    while time.time() - t0 < 40:
        try: raw = ws.recv()
        except Exception as e: err = "recv " + str(e); break
        for part in re.split(r"~m~\d+~m~", raw):
            if not part: continue
            if part.startswith("~h~"): ws.send(f"~m~{len(part)}~m~{part}"); continue
            try: j = json.loads(part)
            except Exception: continue
            m = str(j.get("m"))
            if m == "symbol_resolved":
                x = j["p"][2]; info = {k: x.get(k) for k in ("name", "full_name", "pro_name", "exchange", "session", "timezone", "minmov", "pricescale", "type")}
            if m in ("timescale_update", "du"):
                for b in j["p"][1].get("sds_1", {}).get("s", []): bars.append(b["v"])
            if m in ("symbol_error", "critical_error", "series_error"): err = m; t0 = 0
            if m == "series_completed": t0 = 0
    try: ws.close()
    except Exception: pass
    return bars, err, info

def fetch(sym):
    """Returns (bricks, error, meta). bricks = TradingView Renko [t, open, high, low, close, volume];
    meta = {"sessions": {date: [open, prev_close]}, "symbol": resolved info, "daily_last": date}."""
    from datetime import datetime, timezone
    D = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
    tk = tv_symbol(sym)
    bricks, err, info = _series(tk, True)
    if err or not bricks: return [], err or "no TradingView Renko data", {}
    daily, err2, _ = _series(tk, False, n=400)
    sess = {}
    for i, b in enumerate(daily):
        sess[D(b[0])] = [b[1], daily[i - 1][4] if i else None]
    return bricks, None, {"sessions": sess, "symbol": info, "daily_last": D(daily[-1][0]) if daily else None,
                          "daily_error": err2,
                          "last": [D(daily[-1][0]), daily[-1][4]] if daily else None}


# ---------- Universe: TradingView's own Nifty 100 constituents (index NSE:CNX100) ----------
SCANNER_URL = "https://scanner.tradingview.com/india/scan"
def tv_constituents(index="NSE:CNX100"):
    """Constituents of a TradingView index via TradingView's public screener (symbolset SYML:<index>).
    Returns (list of {symbol, tv_ticker, name, industry, market_cap}, error)."""
    import urllib.request
    body = {"columns": ["name", "description", "sector", "market_cap_basic", "exchange"],
            "symbols": {"symbolset": ["SYML:" + index.replace(":", ";")]}, "range": [0, 500],
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}}
    try:
        rq = urllib.request.Request(SCANNER_URL, data=json.dumps(body).encode(), method="POST",
                                    headers={"Content-Type": "application/json", "Origin": "https://www.tradingview.com",
                                             "User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(rq, timeout=30))
        out = [{"symbol": x["d"][0], "tv_ticker": x["s"], "name": x["d"][1], "industry": x["d"][2] or "",
                "market_cap": x["d"][3]} for x in d.get("data", []) if x["s"].startswith("NSE:")]
        return out, (None if out else "empty constituent list")
    except Exception as ex:
        return [], str(ex)[:200]
