"""
iv_history.py  —  the recorder that makes IV RANK possible, one day at a time.

IV rank is where today's implied volatility sits within its OWN past year, and it is the
first thing a professional option buyer screens on: near the bottom of its range, options
are cheap and a buyer has an edge; near the top, the premium already contains the move.

This system has never recorded implied volatility, so there is no year of it to rank
against. Two dishonest ways out were available and both were refused:

  - Print a percentile computed from three days of history. It would be a real-looking
    number ranking against almost nothing.
  - Say "IV rank needs a year of data" and stop. That is a limitation that never expires,
    because nothing ever starts collecting.

So this collects. It writes one ATM implied-vol observation per name per day, and
`rank()` refuses to answer until there are enough of them - reporting HOW MANY it has, so
the wait is visible and finite rather than an excuse. `option_metrics.vol_verdict()`
carries the IV-against-realised comparison that IS available from day one, and this takes
over as the better answer once the series is long enough to deserve the word "rank".

The file is git-ignored: it is his data, and this repository is public.

    python iv_history.py              # what has been collected so far
    python iv_history.py --purge 400  # drop observations older than N days
"""
import json
import os
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
STORE = "iv_history.json"

# A percentile over a handful of points is arithmetic, not information. Below this the
# rank is refused and the count is reported instead.
MIN_OBSERVATIONS = 60          # ~3 months of trading days
FULL_WINDOW = 252              # the year a true IV rank is quoted against


def _today():
    return datetime.now(IST).strftime("%Y-%m-%d")


def load(path=None):
    path = path or STORE
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:      # noqa - a corrupt store must not stop the desk from rendering
        return {}


def save(data, path=None):
    path = path or STORE
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)          # atomic: a half-written store is worse than none


def record(symbol, iv, spot=None, dte=None, when=None, path=None):
    """One ATM implied-vol observation per name per DAY.

    Once per day, not once per page load: the desk reruns on every click, and a store
    that took an observation each time would weight a day he happened to browse a lot far
    above one he did not - a percentile skewed by how often he opened the website.
    """
    if iv is None or float(iv) <= 0:
        return False
    day = when or _today()
    data = load(path)
    rows = data.setdefault(symbol, [])
    if rows and rows[-1].get("d") == day:
        return False                      # already have today
    rows.append({"d": day, "iv": round(float(iv), 6),
                 "s": round(float(spot), 2) if spot else None,
                 "t": int(dte) if dte else None})
    if len(rows) > FULL_WINDOW * 2:
        del rows[:-FULL_WINDOW * 2]
    save(data, path)
    return True


def series(symbol, path=None):
    return [r["iv"] for r in load(path).get(symbol, []) if r.get("iv")]


def rank(symbol, iv, path=None, window=FULL_WINDOW):
    """(rank_pct, note). None until there are enough observations to mean anything.

    rank_pct is the IV PERCENTILE - the share of recorded days whose implied vol was
    below today's. 10 means options are cheaper than on 90% of the days observed.
    """
    hist = series(symbol, path)[-window:]
    if iv is None:
        return None, "no implied vol today"
    if len(hist) < MIN_OBSERVATIONS:
        need = MIN_OBSERVATIONS - len(hist)
        return None, (f"{len(hist)} of {MIN_OBSERVATIONS} observations — {need} more "
                      f"trading days before a rank means anything. Use IV vs realised "
                      f"until then.")
    below = sum(1 for x in hist if x < float(iv))
    pct = round(100.0 * below / len(hist), 1)
    if pct <= 20:
        v = "CHEAP — cheaper than most days this name has traded at"
    elif pct >= 80:
        v = "EXPENSIVE — dearer than most days; the premium already holds the move"
    else:
        v = "middling"
    return pct, f"{v} ({len(hist)} observations)"


def purge(older_than_days, path=None):
    cut = (datetime.now(IST) - timedelta(days=int(older_than_days))).strftime("%Y-%m-%d")
    data = load(path)
    n = 0
    for sym, rows in list(data.items()):
        keep = [r for r in rows if r.get("d", "") >= cut]
        n += len(rows) - len(keep)
        if keep:
            data[sym] = keep
        else:
            del data[sym]
    save(data, path)
    return n


def main():
    import sys
    if "--purge" in sys.argv:
        i = sys.argv.index("--purge")
        n = purge(sys.argv[i + 1] if len(sys.argv) > i + 1 else 400)
        print(f"  dropped {n} observations")
        return 0
    data = load()
    print("\n  IV HISTORY")
    print("  " + "-" * 62)
    if not data:
        print("  nothing recorded yet. It fills one observation per name per day the")
        print("  desk is opened with a token. A rank needs "
              f"{MIN_OBSERVATIONS} of them.\n")
        return 0
    rows = sorted(data.items(), key=lambda kv: -len(kv[1]))
    ready = sum(1 for _s, r in rows if len(r) >= MIN_OBSERVATIONS)
    print(f"  {len(rows)} names, {sum(len(r) for _s, r in rows)} observations, "
          f"{ready} with enough history to rank")
    for sym, r in rows[:12]:
        last = r[-1]
        print(f"    {sym.split(':')[-1].replace('-EQ',''):<14} {len(r):>4} obs   "
              f"last {last['d']}  IV {last['iv']*100:.1f}%"
              + ("" if len(r) >= MIN_OBSERVATIONS else "   (not enough to rank)"))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
