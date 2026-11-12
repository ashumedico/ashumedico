"""
oi_history.py  —  records which way open interest moved, one session at a time.

The chart wants to colour each candle by whether positions were being OPENED or CLOSED on
that day. The feed cannot supply that retrospectively: buildup is computed from live
quotes against a day-open baseline - open interest now against open interest at the open -
and nothing in the history endpoint carries per-candle open interest. So the state exists
only while the session is live, and then it is gone unless something writes it down.

Two dishonest ways out, both refused, and they are the same two `iv_history` refused:

  - Colour the old candles from something else - where the close sat in its range, say -
    and let the eye read it as open interest. Every candle coloured, nothing measured.
  - Declare that historical OI is unavailable and leave the chart grey forever. A
    limitation that never expires, because nothing ever starts collecting.

So this collects. One state per name per session, written when the desk runs. The coloured
span grows by one day per day, and `states_for()` returns only what was actually recorded -
a date with no entry comes back absent, and the chart's legend counts it out loud rather
than letting an uncoloured candle read as a neutral one.

The file is git-ignored: it is his data, and this repository is public.

    python oi_history.py            # what has been collected so far
    python oi_history.py --purge 400
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
STORE = "oi_history.json"

VALID = ("LONG BUILDUP", "SHORT BUILDUP", "SHORT COVERING", "LONG UNWINDING")


def _path(path=None):
    return path or os.path.join(os.path.dirname(os.path.abspath(__file__)), STORE)


def _load(path=None):
    p = _path(path)
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (ValueError, OSError):
        # A torn file is not an empty one. Returning {} here would silently restart the
        # collection and the chart would go grey with no explanation, so it is reported.
        return {"__error__": f"{p} could not be read"}


def _save(d, path=None):
    with open(_path(path), "w") as f:
        json.dump(d, f, indent=2, sort_keys=True)


def record(states, day=None, path=None):
    """Write one session's buildup states. {name: state}. Returns how many were kept.

    Unknown strings are DROPPED rather than stored. A state the chart cannot interpret
    would be written once and then colour a candle by accident years later, and the
    cheapest place to refuse it is on the way in.
    """
    if not states:
        return 0
    d = _load(path)
    if "__error__" in d:
        return 0
    key = (day or datetime.now(IST).date()).isoformat()
    kept = 0
    for name, st in states.items():
        if st not in VALID:
            continue
        d.setdefault(name, {})[key] = st
        kept += 1
    if kept:
        _save(d, path)
    return kept


def states_for(name, path=None):
    """{date -> state} for one name. Empty when nothing was ever recorded.

    Only what was written. There is no interpolation between two recorded days: a gap is
    a session nobody observed, and filling it would make the chart most confident about
    exactly the days it knows least.
    """
    d = _load(path)
    if "__error__" in d:
        return {}
    return dict(d.get(name) or {})


def coverage(name=None, path=None):
    """(sessions, first, last, error) — how much is actually known."""
    d = _load(path)
    if "__error__" in d:
        return 0, None, None, d["__error__"]
    if name:
        days = sorted((d.get(name) or {}).keys())
    else:
        days = sorted({k for v in d.values() if isinstance(v, dict) for k in v})
    if not days:
        return 0, None, None, None
    return len(days), days[0], days[-1], None


def purge(older_than_days, path=None):
    d = _load(path)
    if "__error__" in d:
        return 0
    cut = (datetime.now(IST).date() - timedelta(days=int(older_than_days))).isoformat()
    dropped = 0
    for name, days in list(d.items()):
        if not isinstance(days, dict):
            continue
        for k in list(days):
            if k < cut:
                del days[k]
                dropped += 1
        if not days:
            del d[name]
    if dropped:
        _save(d, path)
    return dropped


def main():
    if "--purge" in sys.argv:
        n = purge(sys.argv[sys.argv.index("--purge") + 1])
        print(f"\n  dropped {n} observations\n")
        return 0
    n, first, last, err = coverage()
    print("\n  OI HISTORY")
    print("  " + "-" * 56)
    if err:
        print(f"  {err}\n")
        return 1
    if not n:
        print("  nothing recorded yet - it starts collecting the first time the desk")
        print("  runs against a live feed.\n")
        return 0
    d = _load()
    print(f"  {len(d)} names · {n} sessions · {first} to {last}")
    print("  the chart can colour exactly these days, and no others.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
