"""
rrg.py  —  Relative Rotation Graph (RRG) for the F&O universe vs a benchmark.

The same rotation picture StockCharts / Strike show: each stock is a dot in a
2x2 plane, plus a "tail" of where it has been. Two axes (both centred on 100):

  X = RS-Ratio     — relative STRENGTH vs the benchmark (NIFTY). >100 = outperforming.
  Y = RS-Momentum  — the MOMENTUM of that relative strength. >100 = strength rising.

Four quadrants (stocks rotate clockwise through them):
  LEADING    (top-right)    strong & still gaining     -> ride / hold longs
  WEAKENING  (bottom-right) strong but losing steam    -> book / trail
  LAGGING    (bottom-left)  weak & still falling        -> avoid / shorts
  IMPROVING  (top-left)     weak but turning up         -> watchlist / early longs

Method (JdK-style, standardised): RS = price / benchmark; RS-Ratio is RS z-scored
over a window and shifted to ~100; RS-Momentum is the same transform of RS-Ratio's
rate-of-change. Live uses Fyers daily candles; --dry-run synthesises a clean rotation.

    python rrg.py --dry-run        # synthetic universe -> writes charts/rrg.png + table
    python rrg.py                  # live (needs Fyers token)

NOT financial advice. Rotation is context, not a trigger.
"""
import os, math

try:
    import config
except ImportError:
    class _C:
        CLIENT_ID = ""; TOKEN_FILE = "access_token.txt"
        UNIVERSE = []; RRG_BENCHMARK = "NSE:NIFTY50-INDEX"
    config = _C()

QUAD_COLOR = {"LEADING": "#1f9d63", "WEAKENING": "#e0a11b",
              "LAGGING": "#d1495b", "IMPROVING": "#2f6fed"}


# ---------- math ----------
def _sma(v, n):
    return [sum(v[max(0, i - n + 1):i + 1]) / len(v[max(0, i - n + 1):i + 1]) for i in range(len(v))]


def rs_deviations(stock, bench, win=10, mwin=4):
    """Raw RRG deviations for one stock vs the benchmark (unscaled).
      ratio_dev = RS relative to its own rolling mean (outperforming its trend?)
      mom_dev   = change in that over `mwin` bars (is the outperformance improving?)
    Signs of these decide the quadrant; a shared scale (in analyse) sets the spread."""
    n = min(len(stock), len(bench))
    stock, bench = stock[-n:], bench[-n:]
    rs = [s / b for s, b in zip(stock, bench)]                 # relative strength line
    rs_sma = _sma(rs, win)
    ratio_dev = [rs[i] / rs_sma[i] - 1 for i in range(n)]      # ~0, + = strong
    mom_dev = [ratio_dev[i] - ratio_dev[max(0, i - mwin)] for i in range(n)]
    return ratio_dev, mom_dev


def quadrant(ratio, mom):
    if ratio >= 100 and mom >= 100:  return "LEADING"
    if ratio >= 100 and mom < 100:   return "WEAKENING"
    if ratio < 100 and mom < 100:    return "LAGGING"
    return "IMPROVING"


def analyse(prices, bench, names=None, tail=5, win=10, spread=8.0):
    """prices: {name: [closes]}. bench: [closes]. Returns per-name RRG points + tails.
    Deviations are scaled by a SHARED factor so the cloud fills ~100±spread — the
    quadrant (sign) is scale-invariant; scaling only makes the picture readable."""
    names = names or list(prices)
    devs = {nm: rs_deviations(prices[nm], bench, win) for nm in names}
    # shared scale per axis from the tail region we will actually plot
    all_r = [abs(r) for nm in names for r in devs[nm][0][-tail:]]
    all_m = [abs(m) for nm in names for m in devs[nm][1][-tail:]]
    sx = spread / (max(all_r) or 1e-9)
    sy = spread / (max(all_m) or 1e-9)
    out = []
    for nm in names:
        rdev, mdev = devs[nm]
        pts = [(100 + rdev[i] * sx, 100 + mdev[i] * sy)
               for i in range(len(rdev))][-tail:]
        x, y = pts[-1]
        out.append({"name": nm.split(":")[-1], "x": round(x, 2), "y": round(y, 2),
                    "quadrant": quadrant(x, y), "tail": pts})
    return out


def table_2x2(points):
    """Group names into the 2x2 leading/weakening/improving/lagging buckets."""
    grid = {q: [] for q in QUAD_COLOR}
    for p in points:
        grid[p["quadrant"]].append(p["name"])
    return grid


# ---------- data ----------
def fetch_prices_live(symbols, benchmark, resolution="D", days=90):
    import chart_action as ca
    bench = [c["c"] for c in ca.fetch_candles(benchmark, resolution=resolution, days=days)]
    prices = {}
    for s in symbols:
        try:
            prices[s] = [c["c"] for c in ca.fetch_candles(s, resolution=resolution, days=days)]
        except Exception as e:      # noqa
            print(f"  [skip] {s}: {e}")
    return prices, bench


def fetch_dry():
    """Synthetic universe: each name is at a different PHASE of the rotation cycle,
    so all four quadrants populate (RS = benchmark x a sine of distinct phase)."""
    N = 60; P = 48; A = 0.09                                   # ~1 cycle over the window
    bench = [100 * (1 + 0.0010 * t) for t in range(N)]        # steady benchmark uptrend
    two_pi = 2 * math.pi

    def build(phase_deg):
        ph = math.radians(phase_deg)
        return [bench[t] * (1 + A * math.sin(two_pi * t / P + ph)) for t in range(N)]

    # ending angle ~= 2*pi*(N-1)/P + phase; choose phases to land each name in a quadrant.
    prices = {
        "NSE:RELIANCE":   build(60),    # LEADING     (strong, still gaining)
        "NSE:TATAMOTORS": build(30),    # LEADING/edge
        "NSE:TCS":        build(150),   # WEAKENING   (strong, losing steam)
        "NSE:HDFCBANK":   build(240),   # LAGGING     (weak, still falling)
        "NSE:INFY":       build(210),   # LAGGING/edge
        "NSE:SBIN":       build(330),   # IMPROVING   (weak, turning up)
    }
    return prices, bench


def render_console(points, grid):
    print("\n  RELATIVE ROTATION GRAPH  ·  F&O vs NIFTY")
    print("  " + "-" * 56)
    print(f"  {'NAME':<14}{'RS-Ratio':>10}{'RS-Mom':>9}   QUADRANT")
    for p in sorted(points, key=lambda p: (-p["x"], -p["y"])):
        print(f"  {p['name']:<14}{p['x']:>10.1f}{p['y']:>9.1f}   {p['quadrant']}")
    print("  " + "-" * 56)
    print("  2x2:")
    print(f"    IMPROVING : {', '.join(grid['IMPROVING']) or '-'}")
    print(f"    LEADING   : {', '.join(grid['LEADING']) or '-'}")
    print(f"    LAGGING   : {', '.join(grid['LAGGING']) or '-'}")
    print(f"    WEAKENING : {', '.join(grid['WEAKENING']) or '-'}")
    print("  " + "-" * 56)


def render_chart(points, path="charts/rrg.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    xs = [p["x"] for p in points] + [100]; ys = [p["y"] for p in points] + [100]
    pad = max(2.5, max(abs(v - 100) for v in xs + ys) * 1.25)
    lo, hi = 100 - pad, 100 + pad

    fig, ax = plt.subplots(figsize=(9.2, 8.6), dpi=130)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.86, bottom=0.08)
    # quadrant backgrounds
    ax.axhspan(100, hi, xmin=0.5, xmax=1, facecolor=QUAD_COLOR["LEADING"], alpha=0.07)
    ax.axhspan(lo, 100, xmin=0.5, xmax=1, facecolor=QUAD_COLOR["WEAKENING"], alpha=0.07)
    ax.axhspan(lo, 100, xmin=0, xmax=0.5, facecolor=QUAD_COLOR["LAGGING"], alpha=0.07)
    ax.axhspan(100, hi, xmin=0, xmax=0.5, facecolor=QUAD_COLOR["IMPROVING"], alpha=0.07)
    ax.axhline(100, color="#888", lw=1); ax.axvline(100, color="#888", lw=1)

    # quadrant labels
    ax.text(hi - 0.3, hi - 0.3, "LEADING", color=QUAD_COLOR["LEADING"], ha="right", va="top",
            fontsize=12, fontweight="bold", alpha=0.7)
    ax.text(hi - 0.3, lo + 0.3, "WEAKENING", color=QUAD_COLOR["WEAKENING"], ha="right", va="bottom",
            fontsize=12, fontweight="bold", alpha=0.7)
    ax.text(lo + 0.3, lo + 0.3, "LAGGING", color=QUAD_COLOR["LAGGING"], ha="left", va="bottom",
            fontsize=12, fontweight="bold", alpha=0.7)
    ax.text(lo + 0.3, hi - 0.3, "IMPROVING", color=QUAD_COLOR["IMPROVING"], ha="left", va="top",
            fontsize=12, fontweight="bold", alpha=0.7)

    for p in points:
        col = QUAD_COLOR[p["quadrant"]]
        tx = [t[0] for t in p["tail"]]; ty = [t[1] for t in p["tail"]]
        ax.plot(tx, ty, color=col, lw=1.6, alpha=0.5, zorder=2)            # the tail
        ax.scatter([p["x"]], [p["y"]], s=130, color=col, edgecolor="white",
                   linewidth=1.5, zorder=3)                                # the head
        ax.annotate(p["name"], (p["x"], p["y"]), xytext=(6, 6),
                    textcoords="offset points", fontsize=9, fontweight="bold", color="#222")

    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("RS-Ratio  (relative strength vs NIFTY →)", fontsize=10, color="#555")
    ax.set_ylabel("RS-Momentum  (strength rising ↑)", fontsize=10, color="#555")
    fig.text(0.09, 0.945, "Relative Rotation Graph — F&O universe vs NIFTY",
             fontsize=14, fontweight="bold", ha="left", va="center")
    fig.text(0.09, 0.905, "Dots rotate clockwise: Improving → Leading → Weakening → Lagging",
             fontsize=9.5, color="#777", ha="left", va="center")
    fig.text(0.09, 0.02, "NOT financial advice · rotation is context, not a trigger",
             fontsize=7.5, color="#999")
    fig.savefig(path)
    plt.close(fig)
    return path


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        prices, bench = fetch_dry()
    else:
        universe = getattr(config, "UNIVERSE", [])
        benchmark = getattr(config, "RRG_BENCHMARK", "NSE:NIFTY50-INDEX")
        prices, bench = fetch_prices_live(universe, benchmark)
        if not prices:
            print("  No price data (need Fyers token + a UNIVERSE in config.py)."); return
    points = analyse(prices, bench)
    grid = table_2x2(points)
    render_console(points, grid)
    path = render_chart(points)
    print(f"\n  RRG chart written: {path}\n")


if __name__ == "__main__":
    main()
