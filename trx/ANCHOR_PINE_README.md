# Anchor Break – Pine Script (`trx/anchor_break.pine`)

Pine v5 port of `scanner/anchor_scan.py`. Swing points come from **ZigZag++ [LD] by DevLucem** itself: the script does `import DevLucem/ZigLib/1` (the same library ZigZag++ calls) with Depth 12 / Deviation 5 / Backstep 2. The HH/LH/HL/LL labels use ZigZag++'s own non-repaint rule: a pivot counts only once direction flips. The leg that is still forming is ignored.

Rules: SELL A1 = previous day's last ZigZag HH. A ZigZag LH between A1 and A2 rejects the setup. A2 = first complete candle today whose low is above A1. Entry = first close below A1. SL = the prior candle's high. TP = 1:2. If the same bar touches both, it counts as a stop. BUY is the mirror (an HH rejects).
NSE: entries 09:30–14:00 IST, force-close 15:00. Crypto: the day starts 05:30 IST, with no cutoff. An unfilled setup expires at the next 05:30.
All logic runs on confirmed bars only.

## Add in TradingView
1. Pine Editor → paste the file → Save → Add to chart.
2. Market = Auto (NSE stocks are detected from the exchange or type), or set NSE or Crypto by hand.
3. Timeframes: **crypto 15m** on the 33 BingX perps (`BINGX:<COIN>USDT.P`, list in `scanner/anchor_symbols.json`). **NSE 5m** on Nifty 100.

## Alert / webhook
- Create an alert. Condition: *Anchor Break → Any alert() function call*, once per bar close.
- Webhook URL: `https://trading.hotelstatusresidency.com/webhook`
- Put the real secret in the indicator's "Webhook secret" input on your chart only. The repo holds just the `{{SECRET}}` placeholder.
- Payload (field names match `src/webhook.js`):
  `{"secret","source":"anchor","symbol","coin","market","side":"buy|sell","entry","stop","target","time"}`

## What the VPS does with these alerts (checked in `src/webhook.js`)
`webhook.js` **ignores `source`**. It treats an anchor alert exactly like a bridge alert. If the secret matches, it checks these, in order:
- the coin is in the scanner's 34-coin whitelist;
- the signal is fresh (under 2 h old);
- the mark price is between SL and TP, and within 1 % of entry;
- the stop is under 15 % away.

If all pass, it calls `scanner.handleEntry`. **With MODE=live, that places a real BingX market order** (10 USDT, 11x, SL/TP attached; the margin gate and max-open limit still apply).
- NSE symbols are not on the whitelist, so they are rejected (HTTP 400) and logged only.
- Crypto coins on the whitelist **would trade live**. To get crypto alerts without trading, leave the secret as a placeholder or don't add the webhook URL.
