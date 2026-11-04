# Anchor Break – Pine Script (`trx/anchor_break.pine`)

Pine v5 port of `scanner/anchor_scan.py`. Swing points come from **ZigZag++ [LD] by DevLucem** itself: the script does `import DevLucem/ZigLib/1` (the same library ZigZag++ calls) with Depth 12 / Deviation 5 / Backstep 2. The HH/LH/HL/LL labels use ZigZag++'s own non-repaint rule: a pivot counts only once direction flips. The leg that is still forming is ignored.

Rules: SELL A1 = previous day's last ZigZag HH. A ZigZag LH between A1 and A2 rejects the setup. A2 = first complete candle today whose low is above A1. Entry = first close below A1. SL = the prior candle's high. TP = 1:2. If the same bar touches both, it counts as a stop. BUY is the mirror (an HH rejects).
NSE: entries 09:30–14:00 IST, force-close 15:00. Crypto: the day starts 05:30 IST, with no cutoff. An unfilled setup expires at the next 05:30.
All logic runs on confirmed bars only.

## Add in TradingView
1. Open a chart → **Pine Editor** (bottom panel) → delete the template → paste `anchor_break.pine` → **Save** → **Add to chart**.
2. Use **15m** for the 33 BingX perps (`BINGX:<COIN>USDT.P`, list in `scanner/anchor_symbols.json`) and **5m** for Nifty 100 NSE stocks. Leave Market on **Auto**, or set NSE or Crypto by hand.
3. For webhook use: open the indicator's ⚙ Settings → **Webhook secret** → enter the real secret (you get it privately; it is never in this repo).

## Create the alert (one alert per chart symbol)
1. With the symbol open, press **Alt+A** (Create Alert).
2. **Condition** = `Anchor Break`, then pick one:
   - **"Any alert() function call"**: sends the JSON payload for the webhook/dashboard.
   - **"Anchor BUY"** or **"Anchor SELL"**: a readable message such as `Anchor Break BUY NSE:HINDUNILVR (5) | Entry … | SL … | TP …`. Each needs its own alert.
3. **Trigger** = **Once Per Bar Close**.
4. **Expiration**: set the longest date allowed (Basic 1 month, Essential/Plus 2 months, Premium+ open-ended).
5. **Notifications** tab:
   - **Notify in app**: push to your phone; you must be logged in to the TradingView mobile app.
   - **Show popup** and **Play sound**: browser alerts.
   - **Webhook URL** = `https://trading.hotelstatusresidency.com/webhook`, used with "Any alert() function call".
6. Create. Repeat for every symbol: an indicator alert covers only the chart symbol it was made on.

**Plan limits** (TradingView pricing page, checked Nov 2026):
- Webhooks need a paid plan (Essential or higher) and 2-factor authentication turned on.
- Free Basic allows 0 indicator/technical alerts (3 price alerts only).
- Essential allows 20 technical alerts, Plus 100, Premium 400.
- So covering 33 coins + Nifty 100 needs Premium. Otherwise, alert only a chosen subset.

## Webhook payload
`{"secret","source":"anchor","symbol","coin","market","side":"buy|sell","entry","stop","target","time"}`

## What the VPS does with these alerts: SIGNALS ONLY
`src/webhook.js` checks the secret. Then, for `source:"anchor"`, it **never** calls `handleEntry` or BingX. It stores the alert in `data/anchor_signals.json` (last 500 kept) and returns `200 {"ok":true,"signalOnly":true}`. NSE and crypto symbols are both accepted.
Stored signals appear in the dashboard's **Anchor Break** tab, under the **Anchor Signals** table (`/api/anchor-signals`, password protected). No Anchor alert can place a trade, even with MODE=live.
