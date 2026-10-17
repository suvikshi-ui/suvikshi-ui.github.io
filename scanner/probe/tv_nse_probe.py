"""Feasibility probe only: TradingView feed for NSE symbols, prints brick counts and date ranges (no prices)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from datetime import datetime, timezone
from scan import fetch
for s in ["NSE:RELIANCE", "NSE:TCS", "NSE:HDFCBANK"]:
    b, e = fetch(s)
    d = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
    print(s, ("bricks %d from %s to %s" % (len(b), d(b[0][0]), d(b[-1][0]))) if b else "no data", "err", e, flush=True)
