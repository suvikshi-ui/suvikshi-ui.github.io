# Anchor Break live scanner

`scanner/anchor_scan.py` rebuilds `trx/anchor_live.json` (rendered unchanged by `trx/anchor_live.html`).
Scheduled by `.github/workflows/anchor-scan.yml` every 5 minutes (GitHub cron is best-effort; delays of 5–15 min are normal) plus manual `workflow_dispatch`.

Data: TradingView public chart feed only (websocket helpers from `tv_source.py`). Crypto `BINGX:<sym>` 15m, NSE `NSE:<sym>` 5m, complete candles only.

## Rules (from the page's rule text, 2 Nov 2026 16:35 IST)
- Pivots: ZigZag++ depth 12 / deviation 5 ticks / backstep 2 (MT4 ZigZag algorithm). The last, still-forming pivot is dropped, so only final pivots are used. Labels HH/LH vs previous high pivot, LL/HL vs previous low pivot.
- Day: crypto 05:30→05:30 IST; NSE session date (09:15–15:30).
- SELL: A1 = previous day's last ZigZag **HH**. A2 = first complete candle of today whose low > A1; `anchor2` = that candle's high. Any ZigZag **LH** between A1 and A2 rejects the setup (not shown anywhere). Entry = first close < A1 at/after A2.
- BUY mirror: A1 = previous day's last **LL**; A2 = first candle today with high < A1, `anchor2` = its low; a ZigZag **HH** between rejects; entry = first close > A1.
- Stop = previous candle high (SELL) / low (BUY); target = 2R; candle touching both = STOP.
- NSE entries only 09:30–14:00 IST; open NSE trades force-close (status `EOD`, R at close) on the first candle ≥ 15:00.
- Crypto: no entry cutoff; unfilled setups vanish at the next 05:30 day start (only today's A2 is scanned); filled trades run to stop/target.
- Variant: `Filter` if stop distance ≥ 1% of entry, else `No Filter`.

## Assumptions / choices
- Verified: replaying 3 Nov 10:30 IST reproduces the saved TRX SELL, BTC BUY, CFG BUY and NOT BUY anchors exactly (prices and times).
- Crypto universe (33, `anchor_symbols.json`): the 27 `.P` perps in `symbols.json` + APT, ATOM, DOT, NEAR, NOT, TAO perps (symbols seen in the old output; TAO added to reach 33).
- NSE universe: Nifty 100 from `nifty100.json`. NSE is scanned only Mon–Fri 09:15–15:35 IST; otherwise the last NSE block is kept (`--force-nse` overrides).
- History: closed trades merge with previous history by `id`, newest 30 kept; `closed_R` = sum of R in that list.
- Open trades in history are only recomputed while their entry day is still being scanned (crypto: current day; NSE: current session).
- Not regenerated: `trx/anchor_charts/*.svg` (static from the one-off run). Not implemented: ntfy/email alerts.
