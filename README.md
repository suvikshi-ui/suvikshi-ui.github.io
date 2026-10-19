# BrickFlow — Live Setup Scanner

Live site: https://suvikshi-ui.github.io/trx/

The BrickFlow strategy: daily Renko ATR(14), Hull Suite 55 and MACD 12/26/9 flip setups. It covers cryptocurrency (37 BingX coins, TradingView data) and the Indian stock market (Nifty 100, TradingView data only: TradingView's CNX100 constituents, TradingView daily Renko and daily candles). The scanner lives in `scanner/` and runs every 15 minutes from `.github/workflows/live-scan.yml`.

Signal scan only: no trades, alerts, stop losses or targets. Not financial advice.
