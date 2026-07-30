"""
rrg_engine.py  —  the upgraded RRG core: proper metrics + live data for the FULL F&O universe.

Why this exists: a plain RRG is a picture, not a system (StockCharts say so themselves).
What makes it tradeable is the stuff around the dot:

  x  RS-Ratio      relative STRENGTH vs benchmark, cross-sectionally normalised (100 = par)
  y  RS-Momentum   the MOMENTUM of that strength                                (100 = par)
  ── heading       direction of travel in degrees (0=E, 90=N) — where the dot is GOING
  ── velocity      how fast it is travelling (tail length per period) — conviction
  ── distance      distance from (100,100) — inside the "noise blob" or a real trend?
  ── crossing      did it just change quadrant this period? (the actual signal)
  ── abs_trend     the stock's OWN price trend — the regime filter RRG lacks
  ── buildup       OI intent overlay (fresh buying / selling)

Live data covers every F&O name via batched Fyers history with an on-disk day cache,
so a full-universe refresh is one slow call in the morning and instant afterwards.

NOT financial advice.
"""
import os, json, math, time
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
CACHE_DIR = "cache"

try:
    import config
except ImportError:
    class _C:
        CLIENT_ID = ""; TOKEN_FILE = "access_token.txt"
        RRG_BENCHMARK = "NSE:NIFTY50-INDEX"
    config = _C()

LAST_SKIPPED = []          # symbols the last live fetch could not load

QUADRANTS = ("LEADING", "WEAKENING", "LAGGING", "IMPROVING")
QUAD_COLOR = {"LEADING": "#1f9d63", "WEAKENING": "#e0a11b",
              "LAGGING": "#d1495b", "IMPROVING": "#2f6fed"}


# ---------------- math helpers ----------------
def sma(v, n):
    out, s = [], 0.0
    for i, x in enumerate(v):
        s += x
        if i >= n:
            s -= v[i - n]
        out.append(s / min(i + 1, n))
    return out


def ema(v, n):
    if not v:
        return []
    k = 2.0 / (n + 1)
    out = [v[0]]
    for x in v[1:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def quadrant(x, y):
    if x >= 100 and y >= 100:  return "LEADING"
    if x >= 100 and y < 100:   return "WEAKENING"
    if x < 100 and y < 100:    return "LAGGING"
    return "IMPROVING"


def _zn(vals):
    """Cross-sectional normalise a list to mean 100, sd 1 unit (RRG convention)."""
    n = len(vals)
    if n == 0:
        return []
    m = sum(vals) / n
    sd = (sum((v - m) ** 2 for v in vals) / n) ** 0.5 or 1e-9
    return [100 + (v - m) / sd for v in vals]


# ---------------- per-stock raw series ----------------
def rs_series(stock, bench, win=10, mom_win=5):
    """Raw (unnormalised) relative-strength and momentum series for one stock."""
    n = min(len(stock), len(bench))
    if n < win + mom_win + 2:
        return None
    st, bm = stock[-n:], bench[-n:]
    rs = [s / b for s, b in zip(st, bm)]
    base = ema(rs, win)
    # strength: how far RS sits above/below its own trend
    ratio_raw = [rs[i] / (base[i] or 1e-9) - 1.0 for i in range(n)]
    # momentum: rate of change of that strength
    mom_raw = [ratio_raw[i] - ratio_raw[max(0, i - mom_win)] for i in range(n)]
    return ratio_raw, mom_raw


def abs_trend(closes, fast=10, slow=30):
    """The stock's OWN trend (the filter a relative tool is blind to).
    Returns (+1 up / -1 down / 0 flat, pct above slow MA)."""
    if len(closes) < slow + 2:
        return 0, 0.0
    f = ema(closes, fast)[-1]; s = ema(closes, slow)[-1]
    pct = (closes[-1] / s - 1) * 100
    if f > s and closes[-1] > s:   return 1, pct
    if f < s and closes[-1] < s:   return -1, pct
    return 0, pct


# ---------------- universe-level build ----------------
def build_points(prices, bench, buildup=None, tail=6, win=10, mom_win=5,
                 dates=None, age_window=30):
    """prices {sym:[closes]} + bench [closes] -> list of point dicts with full metrics.
    Normalisation is CROSS-SECTIONAL per period (the RRG convention): every stock is
    scored against the whole universe at that moment, so positions are comparable.

    `dates` (aligned to the close series) lets each point carry the DATE its signal
    actually fired, plus how many bars old it is — so a stale idea can't be mistaken
    for a fresh one."""
    buildup = buildup or {}
    raws, syms = {}, []
    for sym, closes in prices.items():
        r = rs_series(closes, bench, win, mom_win)
        if r:
            raws[sym] = r
            syms.append(sym)
    if not syms:
        return []

    # walk back far enough to date the signal, even though we only DRAW `tail` points
    depth = min(min(len(raws[s][0]) for s in syms), max(tail + 1, age_window))
    # normalise each historical period across the universe
    series = {s: [] for s in syms}
    for k in range(depth, 0, -1):
        xs = _zn([raws[s][0][-k] for s in syms])
        ys = _zn([raws[s][1][-k] for s in syms])
        for i, s in enumerate(syms):
            series[s].append((xs[i], ys[i]))

    pts = []
    for s in syms:
        full = series[s]                       # long history, for dating the signal
        trail = full[-(tail + 1):]             # short history, for drawing
        x, y = full[-1]
        px, py = full[-2] if len(full) > 1 else (x, y)
        dx, dy = x - px, y - py
        short = s.split(":")[-1].replace("-EQ", "")
        tr, tr_pct = abs_trend(prices[s])

        # --- how long has it been in this quadrant? (age of the signal) ---
        qnow = quadrant(x, y)
        bars_in = 1
        for k in range(2, len(full) + 1):
            qx, qy = full[-k]
            if quadrant(qx, qy) == qnow:
                bars_in += 1
            else:
                break
        capped = bars_in >= len(full)           # older than our window — unknown, treat as stale
        sig_date = None
        if dates:
            idx = len(prices[s]) - bars_in
            ref = dates if len(dates) == len(prices[s]) else dates[-len(prices[s]):]
            if 0 <= idx < len(ref):
                sig_date = ref[idx]

        pts.append({
            "name": short, "symbol": s, "x": round(x, 3), "y": round(y, 3),
            "tail": [(round(a, 3), round(b, 3)) for a, b in trail],
            "quadrant": qnow,
            "prev_quadrant": quadrant(px, py),
            "crossed": qnow != quadrant(px, py),
            "heading": round(math.degrees(math.atan2(dy, dx)) % 360, 1),
            "velocity": round(math.hypot(dx, dy), 3),
            "distance": round(math.hypot(x - 100, y - 100), 3),
            "abs_trend": tr, "abs_pct": round(tr_pct, 2),
            "signal": buildup.get(short),
            "close": prices[s][-1],
            "age_bars": bars_in, "age_capped": capped,
            "signal_date": sig_date,
            "freshness": ("FRESH" if bars_in <= 1 else
                          "NEW" if bars_in <= 3 else
                          "AGEING" if bars_in <= 7 else "STALE"),
            "last_date": (dates[-1] if dates else None),
        })
    return pts


def counts(points):
    return {q: sum(1 for p in points if p["quadrant"] == q) for q in QUADRANTS}


# ---------------- live data (full F&O universe, cached) ----------------
def _cache_path(key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    day = datetime.now(IST).strftime("%Y%m%d")
    return os.path.join(CACHE_DIR, f"{key}_{day}.json")


def _fy():
    from fyers_apiv3 import fyersModel
    token = open(config.TOKEN_FILE).read().strip()
    return fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)


def fetch_history(symbols, benchmark=None, resolution="D", days=200,
                  use_cache=True, progress=None, throttle=0.22):
    """Daily closes for every symbol + the benchmark. Cached per day so the
    full-universe pull happens once, then loads instantly."""
    benchmark = benchmark or getattr(config, "RRG_BENCHMARK", "NSE:NIFTY50-INDEX")
    key = f"hist2_{resolution}_{days}"      # v2 = includes candle dates
    cp = _cache_path(key)
    if use_cache and os.path.exists(cp):
        with open(cp) as f:
            d = json.load(f)
        # a cache without dates cannot date signals -> treat it as a miss and refetch
        if d.get("bench") and d.get("dates") and len(d.get("prices", {})) > 5:
            return d["prices"], d["bench"], d["dates"]

    fy = _fy()
    to = datetime.now(IST)
    # `days` is in BARS; ~250 trading days per calendar year -> pad to calendar days
    span_days = int(days * 1.45) + 15
    frm = to - timedelta(days=span_days)

    # Fyers rejects any single 1D/1W/1M request spanning more than 366 days,
    # so walk the range in sub-year chunks and stitch the candles together.
    CHUNK = 360

    def one(sym):
        candles = {}
        cur = frm
        while cur < to:
            chunk_end = min(cur + timedelta(days=CHUNK), to)
            r = fy.history({"symbol": sym, "resolution": resolution, "date_format": "1",
                            "range_from": cur.strftime("%Y-%m-%d"),
                            "range_to": chunk_end.strftime("%Y-%m-%d"), "cont_flag": "1"})
            if not isinstance(r, dict) or r.get("s") != "ok":
                raise RuntimeError(str(r)[:150])
            for c in r.get("candles", []):
                candles[c[0]] = c          # keyed by epoch -> de-dupes chunk overlaps
            cur = chunk_end + timedelta(days=1)
        keys = sorted(candles)
        closes = [candles[k][4] for k in keys]
        dts = [datetime.fromtimestamp(k, IST).strftime("%Y-%m-%d") for k in keys]
        return closes, dts

    bench, bench_dates = one(benchmark)
    prices, total = {}, len(symbols)
    skipped = []
    for i, s in enumerate(symbols):
        got = None
        for attempt in range(3):
            try:
                c, _d = one(s)
                if len(c) > 40:
                    got = c
                break
            except Exception as err:      # noqa
                msg = str(err)
                if "rate" in msg.lower() or "limit" in msg.lower() or "429" in msg:
                    time.sleep(1.5 * (attempt + 1))   # back off, then retry
                    continue
                skipped.append((s, msg[:80]))
                break
        else:
            skipped.append((s, "rate-limited after 3 attempts"))
        if got:
            prices[s] = got
        elif not any(x[0] == s for x in skipped):
            skipped.append((s, "no usable history"))
        if progress and (i + 1) % 10 == 0:
            progress(i + 1, total)
        time.sleep(throttle)

    # partial data is a fact the caller must be able to see, not swallow
    global LAST_SKIPPED
    LAST_SKIPPED = skipped
    if skipped:
        print(f"  [fetch] {len(prices)}/{total} loaded, {len(skipped)} skipped "
              f"(first: {skipped[0][0]} -> {skipped[0][1]})")
    with open(cp, "w") as f:
        json.dump({"prices": prices, "bench": bench, "dates": bench_dates,
                   "skipped": [x[0] for x in skipped],
                   "at": datetime.now(IST).isoformat()}, f)
    return prices, bench, bench_dates


def live_quote(symbols):
    """Current LTP for a handful of symbols — used to answer "can I enter right now?"."""
    if not symbols:
        return {}
    out = {}
    try:
        fy = _fy()
        for i in range(0, len(symbols), 50):
            r = fy.quotes({"symbols": ",".join(symbols[i:i + 50])})
            for d in (r.get("d", []) if isinstance(r, dict) else []):
                v = d.get("v", {}) or {}
                if v.get("lp"):
                    out[d.get("n")] = float(v["lp"])
    except Exception:      # noqa — no feed/off-hours: caller falls back to last close
        pass
    return out


def entry_check(card, ltp):
    """Compare the live price against the card's plan and give a plain verdict.

    This is the question the RRG never answers: not "is this a good stock" but
    "can I press buy at this exact moment, or am I still waiting?" """
    plan = card.get("stock", {})
    limit = plan.get("entry")
    stop = plan.get("stop")
    t1 = plan.get("t1")
    if ltp is None or not limit:
        return {"state": "NO PRICE", "line": "No live price — check again in market hours.",
                "can_enter": False}
    if stop and ltp <= stop:
        return {"state": "SKIP", "can_enter": False,
                "line": f"Already below the stop ({stop}) — the thesis is broken. Skip it."}
    if t1 and ltp >= t1:
        return {"state": "MISSED", "can_enter": False,
                "line": f"Already past T1 ({t1}) — the move is gone. Wait for the next setup."}
    if ltp <= limit:
        room = (limit - ltp) / limit * 100
        return {"state": "ENTER NOW", "can_enter": True,
                "line": f"Price {ltp} is at/below your limit {limit} "
                        f"({room:.2f}% of room left) — you can enter now."}
    gap = ltp - limit
    return {"state": "WAIT", "can_enter": False,
            "line": f"Price {ltp} is {gap:.2f} above your limit {limit} "
                    f"({gap / ltp * 100:.2f}% too high) — place a limit buy at {limit} "
                    f"and let it come to you."}


def fetch_buildup(fut_symbols, baseline=None):
    """{SHORTNAME: buildup signal} from live futures quotes vs the day-open baseline."""
    if not fut_symbols:
        return {}
    fy = _fy()
    quotes = {}
    for i in range(0, len(fut_symbols), 50):
        chunk = fut_symbols[i:i + 50]
        try:
            r = fy.quotes({"symbols": ",".join(chunk)})
            for d in (r.get("d", []) if isinstance(r, dict) else []):
                v = d.get("v", {})
                quotes[d.get("n")] = {"ltp": v.get("lp", 0), "oi": v.get("oi", 0)}
        except Exception:
            pass
    if baseline is None:
        try:
            import scanner
            baseline = scanner.load_baseline() or {}
        except Exception:
            baseline = {}
    out = {}
    for sym, now in quotes.items():
        b = baseline.get(sym)
        if not b or not b.get("oi") or not now.get("oi"):
            continue
        oi_chg = (now["oi"] - b["oi"]) / b["oi"] * 100
        px_chg = (now["ltp"] - b["ltp"]) / b["ltp"] * 100 if b["ltp"] else 0
        short = sym.split(":")[-1].split("2")[0]
        if oi_chg > 0:
            out[short] = "LONG BUILDUP" if px_chg >= 0 else "SHORT BUILDUP"
        else:
            out[short] = "SHORT COVERING" if px_chg >= 0 else "LONG UNWINDING"
    return out


def live_points(tail=6, days=200, progress=None, with_oi=True):
    """One call: full F&O universe -> RRG points with live metrics + OI overlay."""
    from fno_universe import fno_stocks, fno_futures
    syms = fno_stocks()
    prices, bench, dates = fetch_history(syms, progress=progress, days=days)
    buildup = {}
    if with_oi:
        try:
            exp = getattr(config, "FUT_EXPIRY", None)
            if exp:
                buildup = fetch_buildup(fno_futures(exp))
        except Exception:
            buildup = {}
    return build_points(prices, bench, buildup, tail=tail, dates=dates), prices, bench


# ---------------- synthetic (no feed) ----------------
def demo_points(tail=6, n_bars=400, seed=7):
    """Synthetic universe for plumbing/layout proof — NOT market data.

    Deliberately a *realistic* random walk (seeded, so reproducible): market factor +
    idiosyncratic noise + a weak momentum term. Earlier versions used clean sine waves,
    which made any rotation strategy look magical (191,000% "returns") — that flatters the
    backtest and teaches you nothing. Noise is the honest test: on this data a real edge
    should look modest or absent."""
    import random
    from fno_universe import FALLBACK
    rnd = random.Random(seed)
    names = FALLBACK
    # market factor: small positive drift + daily vol
    bench, b = [100.0], 100.0
    for _ in range(n_bars - 1):
        b *= 1 + rnd.gauss(0.0004, 0.009)
        bench.append(b)

    prices = {}
    for i, nm in enumerate(names):
        beta = 0.6 + (i % 9) * 0.1                      # 0.6 .. 1.4
        idio_vol = 0.010 + (i % 5) * 0.003
        mom = 0.0                                        # slow-moving persistent tilt
        px, series = 100.0, []
        for t in range(n_bars):
            mkt = (bench[t] / bench[t - 1] - 1) if t else 0.0
            mom = 0.97 * mom + rnd.gauss(0, 0.0006)      # autocorrelated drift -> trends exist
            r = beta * mkt + mom + rnd.gauss(0, idio_vol)
            px *= 1 + r
            series.append(px)
        prices[f"NSE:{nm}-EQ"] = series

    # synthetic business-day dates ending today, so signal ages/dates work offline too
    dts, d = [], datetime.now(IST)
    while len(dts) < n_bars:
        if d.weekday() < 5:
            dts.append(d.strftime("%Y-%m-%d"))
        d -= timedelta(days=1)
    dts.reverse()

    buildup = {}
    for i, nm in enumerate(names):
        buildup[nm] = ["LONG BUILDUP", "SHORT COVERING", "SHORT BUILDUP", "LONG UNWINDING"][i % 4]
    return build_points(prices, bench, buildup, tail=tail, dates=dts), prices, bench
