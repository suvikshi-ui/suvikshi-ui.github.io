"""Render TradingView-style Renko + Hull Suite 55 + MACD charts (PNG) from the scanned TradingView data."""
import os, json, hashlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

STYLE = "light-mint-v1"   # bump to force a full redraw
BG = "#FFFFFF"; PANEL = "#F7FEFC"; GRID = "#DDF3EE"; SPINE = "#B2F5EA"; TXT = "#475569"; TITLE = "#1E293B"
UP = "#0D9488"; DN = "#E11D48"
HC = {"DARK GREEN": "#0D9488", "LIGHT GREEN": "#99F6E4", "DARK RED": "#E11D48", "LIGHT RED": "#FECDD3"}

def _fmt(v):
    return f"{v:.6g}"

def render(path, sym, box, rows, mark=None, title_extra="", last=None, source="TradingView data (anonymous chart feed)"):
    """rows: list of dicts with date, open, high, low, close, mhull, shull, macd, signal, hist, hist_color.
    mark: dict(idx, side, date, close) index into rows."""
    n = len(rows)
    fig = plt.figure(figsize=(11, 6.4), dpi=100, facecolor=BG)
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1.25], hspace=0.04, left=0.02, right=0.915, top=0.92, bottom=0.12)
    ax = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1], sharex=ax)
    for a in (ax, ax2):
        a.set_facecolor(PANEL); a.grid(True, color=GRID, lw=0.8); a.tick_params(colors=TXT, labelsize=8)
        for s in a.spines.values(): s.set_color(SPINE)
        a.yaxis.tick_right()
    xs = list(range(n))
    # Hull band
    mh = [r["mhull"] for r in rows]; sh = [r["shull"] for r in rows]
    seg_x, seg_m, seg_s = [], [], []
    ok = [i for i in xs if mh[i] is not None and sh[i] is not None]
    if ok:
        X = [i for i in ok]; M = [mh[i] for i in ok]; S = [sh[i] for i in ok]
        g = [m > s for m, s in zip(M, S)]
        ax.fill_between(X, M, S, where=g, color=UP, alpha=0.28, lw=0, interpolate=True)
        ax.fill_between(X, M, S, where=[not v for v in g], color=DN, alpha=0.28, lw=0, interpolate=True)
        ax.plot(X, M, color="#64748B", lw=0.7, alpha=0.7)
    # Bricks
    for i, r in enumerate(rows):
        o, c = r["open"], r["close"]; up = c > o
        col = UP if up else DN
        if r.get("high") is not None and r.get("low") is not None:
            ax.plot([i, i], [r["low"], r["high"]], color=col, lw=0.8, alpha=0.7, zorder=2)
        ax.add_patch(Rectangle((i - 0.42, min(o, c)), 0.84, abs(c - o), facecolor=col, edgecolor=col, zorder=3))
    lo = min(min(r["open"], r["close"], r.get("low") or 1e18) for r in rows)
    hi = max(max(r["open"], r["close"], r.get("high") or -1e18) for r in rows)
    hv = [v for v in mh + sh if v is not None]
    if hv: lo, hi = min(lo, min(hv)), max(hi, max(hv))
    pad = (hi - lo) * 0.12 or box
    ax.set_ylim(lo - pad, hi + pad); ax.set_xlim(-1, n + 0.5)
    # price line
    lcol = (UP if rows[-1]["close"] > rows[-1]["open"] else DN)
    if last:  # one price line exactly like TradingView's Renko price scale: at the last brick's close, grey tag on the axis
        lcol = "#787B86"; pl = rows[-1]["close"]
        ax.axhline(pl, color=lcol, lw=0.9, ls=(0, (2, 2)), zorder=3)
        ax.annotate(f"{pl:,.2f}", xy=(1.0, pl), xycoords=ax.get_yaxis_transform(), xytext=(2, 0), textcoords="offset points",
                    ha="left", va="center", color="white", fontsize=8, fontweight="bold", annotation_clip=False, zorder=6,
                    bbox=dict(boxstyle="square,pad=0.25", fc=lcol, ec=lcol))
    else:
        ax.axhline(rows[-1]["close"], color=lcol, lw=0.6, ls=":")
    # MACD
    hist = [r["hist"] for r in rows]
    for i, r in enumerate(rows):
        if r["hist"] is None: continue
        ax2.bar(i, r["hist"], width=0.7, color=HC.get(r["hist_color"], "#888"), zorder=2)
    mc = [(i, r["macd"]) for i, r in enumerate(rows) if r["macd"] is not None]
    sg = [(i, r["signal"]) for i, r in enumerate(rows) if r["signal"] is not None]
    if mc: ax2.plot([a for a, _ in mc], [b for _, b in mc], color="#2563EB", lw=1.1)
    if sg: ax2.plot([a for a, _ in sg], [b for _, b in sg], color="#F97316", lw=1.1)
    ax2.axhline(0, color="#94A3B8", lw=0.8)
    # x labels: dates
    step = max(1, n // 12)
    # Nifty (last price given): ticks counted back from the last brick so the latest date is always labelled; crypto unchanged
    ticks = sorted({n - 1 - k for k in range(0, n, step)}) if last else list(range(0, n, step))
    ax2.set_xticks(ticks); ax2.set_xticklabels([rows[i]["date"][5:] if i else rows[i]["date"] for i in ticks], rotation=0, fontsize=7.5, color=TXT)
    plt.setp(ax.get_xticklabels(), visible=False)
    # mark
    if mark is not None:
        i = mark["idx"]; r = rows[i]; side = mark["side"]
        colr = UP if side == "BUY" else DN
        lab = f"{side}\n{mark['date']}\n{_fmt(mark['close'])}"
        if side == "SELL":
            y0 = max(r["open"], r["close"], r.get("high") or 0); yt = y0 + pad * 0.9
            ax.annotate(lab, xy=(i, y0), xytext=(i, yt), ha="center", va="bottom", color="white", fontsize=8.5, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.3", fc=colr, ec=colr), arrowprops=dict(arrowstyle="-|>", color=colr, lw=1.6), zorder=6)
        else:
            y0 = min(r["open"], r["close"], r.get("low") or 1e18); yt = y0 - pad * 0.9
            ax.annotate(lab, xy=(i, y0), xytext=(i, yt), ha="center", va="top", color="white", fontsize=8.5, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.3", fc=colr, ec=colr), arrowprops=dict(arrowstyle="-|>", color=colr, lw=1.6), zorder=6)
        ax.axvline(i, color=colr, lw=0.8, alpha=0.35, zorder=1); ax2.axvline(i, color=colr, lw=0.8, alpha=0.35)
    fig.text(0.02, 0.955, f"{sym} · 1D · Renko ATR(14), box {_fmt(box)}", color=TITLE, fontsize=11, fontweight="bold")
    fig.text(0.02, 0.928, "Hull Suite 55 band (green/red)  ·  MACD 12 26 9 (histogram in 4 shades, MACD blue, signal orange)" + title_extra, color=TXT, fontsize=8)
    fig.text(0.02, 0.03, "BrickFlow · rendered from " + source + ". Signal scan only, not financial advice.", color="#94A3B8", fontsize=7.5)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, facecolor=BG, metadata={"Software": None})
    plt.close(fig)

def slice_hash(sym, rows, mark):
    return hashlib.sha1(json.dumps([STYLE, sym, rows, mark], sort_keys=True, default=str).encode()).hexdigest()[:16]
