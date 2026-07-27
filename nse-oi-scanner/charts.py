"""
charts.py  —  renders ONE annotated candlestick chart per trade idea.

Each chart draws exactly what you asked for: the candles, the four levels
(R2/R1/S1/S2) marked with price labels, the entry / stop / target zones, and a
justification box that says WHY the trade fires (the 3-layer confluence).

    python charts.py            # dry-run: writes 3 PNGs (CE, PE, FUT) into charts/
    from charts import render_idea

NOT financial advice — the chart explains the signal; the decision is yours.
"""
import os, textwrap
import matplotlib
matplotlib.use("Agg")                       # headless: write files, no display
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BULL = "#1f9d63"; BEAR = "#d1495b"; INK = "#1a1d24"; GRID = "#e6e8ec"
LVL_R = "#d1495b"; LVL_S = "#1f9d63"; ENTRY = "#2f6fed"; STOP = "#c0392b"; TGT = "#178a52"


def _candles(ax, candles):
    for i, c in enumerate(candles):
        up = c["c"] >= c["o"]
        col = BULL if up else BEAR
        ax.plot([i, i], [c["l"], c["h"]], color=col, lw=1.0, zorder=2)      # wick
        lo, hi = sorted((c["o"], c["c"]))
        ax.add_patch(Rectangle((i - 0.3, lo), 0.6, max(hi - lo, (c["h"]-c["l"])*0.02),
                               facecolor=col, edgecolor=col, zorder=3))


def _hline(ax, y, color, label, n, ls="-"):
    ax.axhline(y, color=color, lw=1.4, ls=ls, alpha=0.9, zorder=1)
    ax.text(n - 0.5, y, f" {label} {y:g}", color=color, va="center", ha="left",
            fontsize=8.5, fontweight="bold")


def render_idea(idea, path):
    """idea: a build_ideas() entry (CE/PE/FUT). Writes an annotated PNG to `path`."""
    v = idea["verdict"]; candles = v["chart"]["candles"]; L = idea["levels"]; t = idea["trade"]
    n = len(candles)
    bull = idea["bias"] == "BULLISH"

    fig, ax = plt.subplots(figsize=(12, 6.8), dpi=130)
    fig.subplots_adjust(left=0.06, right=0.72, top=0.84, bottom=0.12)
    _candles(ax, candles)

    # ---- the four levels ----
    _hline(ax, L["R2"], LVL_R, "R2", n); _hline(ax, L["R1"], LVL_R, "R1", n, ls="--")
    _hline(ax, L["S1"], LVL_S, "S1", n, ls="--"); _hline(ax, L["S2"], LVL_S, "S2", n)

    # ---- entry / stop / target bands ----
    _hline(ax, t["entry"], ENTRY, "ENTRY", n)
    ax.axhspan(min(t["entry"], t["target"]), max(t["entry"], t["target"]),
               color=TGT, alpha=0.05, zorder=0)
    ax.axhspan(min(t["entry"], t["stop"]), max(t["entry"], t["stop"]),
               color=STOP, alpha=0.06, zorder=0)
    ax.annotate(f"TARGET {t['target']:g}", xy=(n * 0.5, t["target"]), color=TGT,
                fontsize=9, fontweight="bold", ha="center",
                va="bottom" if bull else "top")
    ax.annotate(f"STOP {t['stop']:g}", xy=(n * 0.5, t["stop"]), color=STOP,
                fontsize=9, fontweight="bold", ha="center",
                va="top" if bull else "bottom")

    # direction arrow (entry -> target)
    ax.annotate("", xy=(n * 0.28, t["target"]), xytext=(n * 0.28, t["entry"]),
                arrowprops=dict(arrowstyle="-|>", color=TGT if bull else BEAR, lw=2.2))

    # ---- title + subtitle (above the plot, no overlap) ----
    head = idea["kind"] + (f"  ·  {idea['underlying']} {idea.get('strike','')}").rstrip()
    fig.text(0.06, 0.945, f"{head}   [{idea['bias']} · {idea['confidence']}% confluence]",
             fontsize=15, fontweight="bold", color=INK, ha="left", va="center")
    tr = v["chart"]["trend"]
    fig.text(0.06, 0.895, f"Trend: {tr['combined']}    ·    Entry {t['entry']:g}   "
             f"Stop {t['stop']:g}   Target {t['target']:g}    ·    R:R {t['rr']}",
             fontsize=10, color="#555", ha="left", va="center")

    # ---- the WHY box (right margin), wrapped to fit ----
    lines = ["WHY THIS TRADE"]
    for r in idea["reasons"]:
        wrapped = textwrap.wrap(r, 30)
        lines.append("• " + wrapped[0])
        lines += ["  " + w for w in wrapped[1:]]
    lines += ["", "SETUP"]
    setup = ("Buy-the-dip: uptrend pulling back into support S1 — long toward R1/R2, stop below S2."
             if bull else
             "Sell-the-bounce: downtrend stalling at resistance R1 — short toward S1/S2, stop above R2.")
    lines += ["• " + textwrap.wrap(setup, 30)[0]] + ["  " + w for w in textwrap.wrap(setup, 30)[1:]]
    fig.text(0.735, 0.86, "\n".join(lines), va="top", ha="left", fontsize=8.4, color=INK,
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.6", facecolor="#f7f8fa", edgecolor="#d5d8dd"))

    ax.set_xlim(-1, n + 3); ax.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_xlabel("candles (recent →)", fontsize=8, color="#888")
    ax.set_ylabel("price", fontsize=8, color="#888")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.text(0.07, 0.03, "NOT financial advice · 3-layer confluence: OI buildup × option chain × chart action",
             fontsize=7.5, color="#999")
    fig.savefig(path)
    plt.close(fig)
    return path


def render_all(ideas, outdir="charts"):
    os.makedirs(outdir, exist_ok=True)
    out = {}
    for key in ("CE", "PE", "FUT"):
        idea = ideas.get(key)
        if not idea:
            continue
        name = idea["underlying"].split(":")[-1]
        path = os.path.join(outdir, f"signal_{key}_{name}.png")
        out[key] = render_idea(idea, path)
    return out


def main():
    import argparse, signal_engine as se
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="synthetic data, no Fyers")
    args = ap.parse_args()
    verdicts = se.dry_verdicts() if args.dry_run else se.live_verdicts()
    if not verdicts:
        print("  No qualifying names today (need live Fyers data + OI-change candidates).")
        return
    ideas = se.build_ideas(verdicts)
    se.render(ideas)
    paths = render_all(ideas)
    print("\n  Charts written:")
    for k, p in paths.items():
        print(f"    {k}:  {p}")
    print("  (open the 'charts' folder to view)")


if __name__ == "__main__":
    main()
