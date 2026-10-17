"""Feasibility probe only: prints status codes and row counts / date ranges. Prints no prices."""
import json, time, sys
from datetime import datetime, timezone
import requests
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def d(ms):
    v = ms / 1000 if ms > 1e11 else ms
    return datetime.fromtimestamp(v, timezone.utc).strftime("%Y-%m-%d")
res = {}
# (1) charting.nseindia.com daily
try:
    S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept": "application/json", "Referer": "https://charting.nseindia.com/"})
    r0 = S.get("https://charting.nseindia.com/", timeout=15)
    B = "https://charting.nseindia.com/v1"
    r = S.get(B + "/exchanges/symbolsDynamic", params={"symbol": "RELIANCE", "segment": ""}, timeout=15)
    out = {"home": r0.status_code, "symbolsDynamic": r.status_code}
    tok = [x for x in r.json()["data"] if x["symbol"].upper() == "RELIANCE-EQ"][0]["scripcode"]
    for ct, ti in (("D", 1), ("I", 1)):
        p = {"token": tok, "fromDate": 0, "toDate": int(time.time()), "symbol": "RELIANCE-EQ", "symbolType": "Equity", "chartType": ct, "timeInterval": ti}
        r = S.get(B + "/charts/symbolHistoricalData", params=p, timeout=25)
        info = {"status": r.status_code}
        try:
            j = r.json(); rows = j.get("data") if isinstance(j, dict) else j
            info["rows"] = len(rows or [])
            if rows:
                t0 = rows[0].get("time") or rows[0].get("t"); t1 = rows[-1].get("time") or rows[-1].get("t")
                info["from"], info["to"] = d(t0), d(t1)
        except Exception as e: info["parse"] = str(e)[:80]
        out[f"chartType_{ct}"] = info
    res["charting"] = out
except Exception as e: res["charting"] = {"error": str(e)[:160]}
# (2) www.nseindia.com historical API (needs cookies)
try:
    S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Referer": "https://www.nseindia.com/"})
    h = S.get("https://www.nseindia.com/", timeout=15)
    out = {"home": h.status_code}
    for y in (2023, 2025):
        r = S.get("https://www.nseindia.com/api/historical/cm/equity", params={"symbol": "RELIANCE", "series": '["EQ"]', "from": f"01-01-{y}", "to": f"31-12-{y}"}, timeout=25)
        info = {"status": r.status_code}
        try:
            rows = r.json().get("data", []); info["rows"] = len(rows)
            if rows: info["dates"] = [rows[-1].get("CH_TIMESTAMP"), rows[0].get("CH_TIMESTAMP")]
        except Exception as e: info["parse"] = str(e)[:80]
        out[f"year_{y}"] = info
    res["www_api"] = out
except Exception as e: res["www_api"] = {"error": str(e)[:160]}
print(json.dumps(res, indent=1))
