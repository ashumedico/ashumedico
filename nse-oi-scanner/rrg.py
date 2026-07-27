"""
rrg.py  —  Relative Rotation Graph for the FULL F&O universe, with OI-buildup overlay.

Two forces on one map:
  • POSITION  = price rotation vs NIFTY (RS-Ratio x, RS-Momentum y) -> the 4 quadrants
                LEADING · WEAKENING · LAGGING · IMPROVING
  • MARKER    = OI buildup (fresh money direction), per stock:
                  ▲ solid  = LONG BUILDUP    (fresh buying,  price↑ OI↑)   bullish
                  ▲ hollow = SHORT COVERING  (shorts exiting, price↑ OI↓)  bullish-ish
                  ▼ solid  = SHORT BUILDUP   (fresh selling, price↓ OI↑)   bearish
                  ▼ hollow = LONG UNWINDING  (longs exiting,  price↓ OI↓)  bearish-ish
                  ● grey   = no OI read

The edge is the CONFLUENCE:
  FRESH LONGS  = Leading/Improving  +  Long Buildup     (price + fresh buying agree)
  FRESH SHORTS = Lagging/Weakening  +  Short Buildup     (price + fresh selling agree)

    python rrg.py --dry-run        # ~190-name synthetic universe -> charts/rrg.png
    python rrg.py                  # live: full F&O list (Fyers)

NOT financial advice. Rotation + OI is context, not a trigger.
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
# OI buildup -> (marker, colour, is_fresh, bullish)
BUILDUP_STYLE = {
    "LONG BUILDUP":   ("^", "#1f9d63", True,  True),
    "SHORT COVERING": ("^", "#3fae6a", False, True),
    "SHORT BUILDUP":  ("v", "#d1495b", True,  False),
    "LONG UNWINDING": ("v", "#e07a4b", False, False),
    None:             ("o", "#8b98a5", False, None),
}


# ---------- math ----------
def _sma(v, n):
    return [sum(v[max(0, i - n + 1):i + 1]) / len(v[max(0, i - n + 1):i + 1]) for i in range(len(v))]


def rs_deviations(stock, bench, win=10, mwin=4):
    n = min(len(stock), len(bench))
    stock, bench = stock[-n:], bench[-n:]
    rs = [s / b for s, b in zip(stock, bench)]
    rs_sma = _sma(rs, win)
    ratio_dev = [rs[i] / rs_sma[i] - 1 for i in range(n)]
    mom_dev = [ratio_dev[i] - ratio_dev[max(0, i - mwin)] for i in range(n)]
    return ratio_dev, mom_dev


def quadrant(ratio, mom):
    if ratio >= 100 and mom >= 100:  return "LEADING"
    if ratio >= 100 and mom < 100:   return "WEAKENING"
    if ratio < 100 and mom < 100:    return "LAGGING"
    return "IMPROVING"


def classify_buildup(px_chg, oi_chg):
    if oi_chg > 0:
        return "LONG BUILDUP" if px_chg >= 0 else "SHORT BUILDUP"
    return "SHORT COVERING" if px_chg >= 0 else "LONG UNWINDING"


def analyse(prices, bench, buildup=None, names=None, tail=5, win=10, spread=8.0):
    """prices: {name:[closes]}, bench:[closes], buildup: {SHORTNAME: signal}.
    Returns per-name RRG points with the OI-buildup signal attached."""
    names = names or list(prices)
    devs = {nm: rs_deviations(prices[nm], bench, win) for nm in names}
    all_r = [abs(r) for nm in names for r in devs[nm][0][-tail:]] or [1e-9]
    all_m = [abs(m) for nm in names for m in devs[nm][1][-tail:]] or [1e-9]
    sx = spread / (max(all_r) or 1e-9); sy = spread / (max(all_m) or 1e-9)
    buildup = buildup or {}
    out = []
    for nm in names:
        rdev, mdev = devs[nm]
        pts = [(100 + rdev[i] * sx, 100 + mdev[i] * sy) for i in range(len(rdev))][-tail:]
        x, y = pts[-1]
        short = nm.split(":")[-1].replace("-EQ", "")
        out.append({"name": short, "x": round(x, 2), "y": round(y, 2),
                    "quadrant": quadrant(x, y), "tail": pts,
                    "signal": buildup.get(short)})
    return out


def confluence(points):
    """The money picks where price rotation and fresh OI agree."""
    fresh_longs, fresh_shorts = [], []
    for p in points:
        s = p["signal"]
        if s == "LONG BUILDUP" and p["quadrant"] in ("LEADING", "IMPROVING"):
            fresh_longs.append(p)
        if s == "SHORT BUILDUP" and p["quadrant"] in ("LAGGING", "WEAKENING"):
            fresh_shorts.append(p)
    dist = lambda p: (p["x"] - 100) ** 2 + (p["y"] - 100) ** 2
    fresh_longs.sort(key=dist, reverse=True)
    fresh_shorts.sort(key=dist, reverse=True)
    return {"fresh_longs": fresh_longs, "fresh_shorts": fresh_shorts}


def table_2x2(points):
    grid = {q: [] for q in QUAD_COLOR}
    for p in points:
        grid[p["quadrant"]].append(p["name"])
    return grid


# ---------- data ----------
def fetch_prices_live(symbols, benchmark, resolution="D", days=90, throttle=0.12):
    """Daily closes for the whole universe + benchmark. Throttled + progress."""
    import time, chart_action as ca
    bench = [c["c"] for c in ca.fetch_candles(benchmark, resolution=resolution, days=days)]
    prices = {}
    for i, s in enumerate(symbols):
        try:
            prices[s] = [c["c"] for c in ca.fetch_candles(s, resolution=resolution, days=days)]
        except Exception as e:      # noqa
            pass
        if (i + 1) % 25 == 0:
            print(f"  RRG prices: {i + 1}/{len(symbols)}")
        time.sleep(throttle)        # be kind to the Fyers rate limit
    return prices, bench


def fetch_buildup_live(expiry=None):
    """{SHORTNAME: OI-buildup signal} for the whole futures universe, from day-open."""
    import scanner
    from fno_universe import fno_futures
    if expiry is None:
        return {}
    curr = {}
    fut = fno_futures(expiry)
    # scanner.fetch_live reads config.UNIVERSE; here we query our full FUT list in chunks
    from fyers_apiv3 import fyersModel
    token = open(config.TOKEN_FILE).read().strip()
    fy = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)
    quotes = {}
    for i in range(0, len(fut), 50):
        chunk = fut[i:i + 50]
        r = fy.quotes({"symbols": ",".join(chunk)})
        for d in r.get("d", []) if isinstance(r, dict) else []:
            v = d.get("v", {})
            quotes[d.get("n")] = {"ltp": v.get("lp", 0), "oi": v.get("oi", 0)}
    # baseline (day-open) reuse scanner's file if present
    base = scanner.load_baseline() or {}
    out = {}
    for sym, now in quotes.items():
        b = base.get(sym)
        if not b or not b.get("oi") or not now.get("oi"):
            continue
        oi_chg = (now["oi"] - b["oi"]) / b["oi"] * 100
        px_chg = (now["ltp"] - b["ltp"]) / b["ltp"] * 100 if b["ltp"] else 0
        short = sym.split(":")[-1].split("2")[0]
        out[short] = classify_buildup(px_chg, oi_chg)
    return out


def dry_points_large():
    """~190 real F&O tickers placed deterministically across the plane, each with a
    synthetic OI-buildup — so the full-universe render (position + OI overlay) is provable."""
    from fno_universe import FALLBACK
    names = FALLBACK
    golden = math.radians(137.508)
    pts = []
    for i, nm in enumerate(names):
        theta = i * golden
        r = 2.0 + (i % 9) * 0.8                      # radius 2.0 .. 8.4
        x = 100 + r * math.cos(theta); y = 100 + r * math.sin(theta)
        q = quadrant(x, y)
        # correlate OI buildup with rotation, with ~1-in-5 divergence for realism
        diverge = (i % 5 == 0)
        if q in ("LEADING", "IMPROVING"):
            sig = "SHORT BUILDUP" if diverge else ("LONG BUILDUP" if i % 2 == 0 else "SHORT COVERING")
        else:
            sig = "LONG BUILDUP" if diverge else ("SHORT BUILDUP" if i % 2 == 0 else "LONG UNWINDING")
        pts.append({"name": nm, "x": round(x, 2), "y": round(y, 2),
                    "quadrant": q, "tail": [(x, y)], "signal": sig})
    return pts


# ---------- render ----------
def render_chart(points, path="charts/rrg.png", label_max=10):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    big = len(points) > 30

    xs = [p["x"] for p in points] + [100]; ys = [p["y"] for p in points] + [100]
    pad = max(2.5, max(abs(v - 100) for v in xs + ys) * 1.18)
    lo, hi = 100 - pad, 100 + pad

    fig, ax = plt.subplots(figsize=(10.5, 9.6), dpi=130)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.83, bottom=0.14)
    ax.axhspan(100, hi, xmin=0.5, xmax=1, facecolor=QUAD_COLOR["LEADING"], alpha=0.06)
    ax.axhspan(lo, 100, xmin=0.5, xmax=1, facecolor=QUAD_COLOR["WEAKENING"], alpha=0.06)
    ax.axhspan(lo, 100, xmin=0, xmax=0.5, facecolor=QUAD_COLOR["LAGGING"], alpha=0.06)
    ax.axhspan(100, hi, xmin=0, xmax=0.5, facecolor=QUAD_COLOR["IMPROVING"], alpha=0.06)
    ax.axhline(100, color="#888", lw=1); ax.axvline(100, color="#888", lw=1)

    counts = {q: sum(1 for p in points if p["quadrant"] == q) for q in QUAD_COLOR}
    corners = {"LEADING": (hi, hi, "right", "top"), "WEAKENING": (hi, lo, "right", "bottom"),
               "LAGGING": (lo, lo, "left", "bottom"), "IMPROVING": (lo, hi, "left", "top")}
    for q, (cx, cy, ha, va) in corners.items():
        dx = -0.3 if ha == "right" else 0.3; dy = -0.3 if va == "top" else 0.3
        ax.text(cx + dx, cy + dy, f"{q} · {counts[q]}", color=QUAD_COLOR[q], ha=ha, va=va,
                fontsize=12, fontweight="bold", alpha=0.75)

    # group by marker style so each scatter call is one shape
    groups = {}
    for p in points:
        mk, col, fresh, bull = BUILDUP_STYLE.get(p["signal"], BUILDUP_STYLE[None])
        groups.setdefault((mk, col, fresh), []).append(p)
    size = 46 if big else 150
    for (mk, col, fresh), ps in groups.items():
        gx = [p["x"] for p in ps]; gy = [p["y"] for p in ps]
        if fresh:
            ax.scatter(gx, gy, marker=mk, s=size, c=col, edgecolor="white",
                       linewidth=0.5, alpha=0.9, zorder=3)
        else:
            ax.scatter(gx, gy, marker=mk, s=size, facecolor="none", edgecolor=col,
                       linewidth=1.3, alpha=0.85, zorder=3)

    # label only the confluence picks (fresh longs leading / fresh shorts lagging)
    conf = confluence(points)
    to_label = conf["fresh_longs"][:label_max] + conf["fresh_shorts"][:label_max]
    if not big:
        to_label = points
    for p in to_label:
        ax.annotate(p["name"], (p["x"], p["y"]), xytext=(5, 4),
                    textcoords="offset points", fontsize=8 if big else 9,
                    fontweight="bold", color="#222", zorder=4)

    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("RS-Ratio  (relative strength vs NIFTY →)", fontsize=10, color="#555")
    ax.set_ylabel("RS-Momentum  (strength rising ↑)", fontsize=10, color="#555")
    fig.text(0.08, 0.945, f"Relative Rotation Graph — {len(points)} F&O stocks vs NIFTY",
             fontsize=14.5, fontweight="bold", ha="left", va="center")
    fig.text(0.08, 0.908, "Position = price rotation · Marker = OI buildup "
             "(▲ buying / ▼ selling · solid = fresh money) · labels = confluence picks",
             fontsize=9, color="#777", ha="left", va="center")
    # legend
    from matplotlib.lines import Line2D
    leg = [
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#1f9d63", markersize=10, label="Long buildup (fresh buy)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="none", markeredgecolor="#3fae6a", markersize=10, label="Short covering"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor="#d1495b", markersize=10, label="Short buildup (fresh sell)"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor="none", markeredgecolor="#e07a4b", markersize=10, label="Long unwinding"),
    ]
    ax.legend(handles=leg, loc="upper left", fontsize=8, framealpha=0.9,
              facecolor="white", edgecolor="#ddd", ncol=1)
    fig.text(0.08, 0.03, "NOT financial advice · rotation + OI is context, not a trigger",
             fontsize=7.5, color="#999")
    fig.savefig(path)
    plt.close(fig)
    return path


def render_console(points):
    conf = confluence(points)
    counts = {q: sum(1 for p in points if p["quadrant"] == q) for q in QUAD_COLOR}
    print(f"\n  RRG · {len(points)} F&O stocks vs NIFTY  ×  OI buildup overlay")
    print("  " + "-" * 60)
    print(f"  Leading {counts['LEADING']}  ·  Weakening {counts['WEAKENING']}  ·  "
          f"Improving {counts['IMPROVING']}  ·  Lagging {counts['LAGGING']}")
    print("  " + "-" * 60)
    print(f"  ▲ FRESH LONGS  (leading/improving + long buildup):")
    print("     " + (", ".join(p["name"] for p in conf["fresh_longs"][:15]) or "-"))
    print(f"  ▼ FRESH SHORTS (lagging/weakening + short buildup):")
    print("     " + (", ".join(p["name"] for p in conf["fresh_shorts"][:15]) or "-"))
    print("  " + "-" * 60)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--expiry", default=None, help="FUT expiry for OI overlay, e.g. 26JUL")
    args = ap.parse_args()
    if args.dry_run:
        points = dry_points_large()
    else:
        from fno_universe import fno_stocks
        prices, bench = fetch_prices_live(fno_stocks(),
                                          getattr(config, "RRG_BENCHMARK", "NSE:NIFTY50-INDEX"))
        if not prices:
            print("  No price data (need Fyers token)."); return
        buildup = {}
        try:
            buildup = fetch_buildup_live(args.expiry) if args.expiry else {}
        except Exception as e:      # noqa
            print(f"  [OI overlay skipped: {e}]")
        points = analyse(prices, bench, buildup)
    render_console(points)
    path = render_chart(points)
    print(f"\n  RRG chart written: {path}\n")


if __name__ == "__main__":
    main()
