# Live strategy scanner

`scan.py` runs from `.github/workflows/live-scan.yml` every 5 minutes (GitHub's scheduler can run later than that).

- Data comes from TradingView's public chart feed (anonymous, no login): BingX symbols in `symbols.json`, daily Renko ATR(14) with wicks.
- Indicators: Hull Suite HMA 55 (colour = value vs 2 bricks back) and MACD 12/26/9 histogram on brick closes.
- It writes `trx/data.json`, and `trx/index.html` + `trx/app.js` render it.
- It's a signal scan only. There are no trades, alerts, stop losses or targets.
