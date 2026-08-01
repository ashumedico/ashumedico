"""
momentum_open.py  —  the opening-momentum engine, which this system did not have.

THE MISMATCH THIS FIXES. Everything upstream of here was built around RRG: relative
rotation against a benchmark, measured over weeks, held for days. That is a real strategy
and it is not the one he asked for. His requirement, in his words: catch the trade within
the first half hour of the open, on the name most likely to CONTINUE its move, either
direction, one or two trades a day. A grep for opening_range / ORB / time_of_day over the
whole repo returned nothing. The signal he wanted had never been written.

WHAT DECIDES CONTINUATION IN THE FIRST THIRTY MINUTES
Five things, each cheap to compute and each independently defensible. None of them is
clever; the discipline is in measuring them correctly rather than approximately.

  OPENING RANGE   the high and low of the first N minutes. A break of it is the literal
                  event he is trying to catch. Everything else is a filter on that break.
  RVOL            today's opening volume against the SAME WINDOW on previous days. This is
                  the one people get wrong: comparing 9:15-9:30 volume to a full-day
                  average compares fifteen minutes to three hundred and seventy-five, so
                  every stock looks quiet every morning and the filter silently never
                  fires. Time-of-day normalised or not at all.
  GAP vs TREND    a gap in the direction of the multi-day trend continues more often than
                  one against it. The same gap number is a different event depending on
                  which way the stock has been going, which is why gap size alone ranks
                  badly.
  VWAP            the intraday arbiter of who is winning. Above it for longs, below for
                  shorts. Cheap, and it disqualifies the break that immediately fails.
  REL STRENGTH    the stock's opening move minus the index's. A stock up 1% on a day the
                  whole market is up 1% has shown nothing.

WHAT THIS MODULE REFUSES TO DO
Score a name it could not measure. Every input returns None when the data is absent, and
absent propagates: a name missing its history has no RVOL, and no RVOL means no score, not
a default one. `scan()` reports what it dropped and why. A screen that quietly ranks a
half-measured name above a fully-measured one is worse than a shorter list.

NOT a backtested edge. Not one line of this has been tested against real intraday data
yet, and it must not be automated until it has - see `/factor-admission`. It is the
hypothesis, written down precisely enough to be refuted.
"""
from datetime import datetime, time as _time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
SESSION_OPEN = _time(9, 15)

#: how much of the open defines the range he trades the break of
OPEN_MINUTES = 15
#: how many previous sessions the volume comparison is drawn from
RVOL_LOOKBACK = 20


def _ts(bar):
    """A bar's timestamp as an aware datetime, whatever shape it arrived in."""
    t = bar.get("t") if isinstance(bar, dict) else None
    if t is None:
        return None
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=IST)
    try:                            # epoch seconds, which is what Fyers history returns
        return datetime.fromtimestamp(float(t), IST)
    except (TypeError, ValueError, OSError):
        return None


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def session_bars(bars, day, minutes=OPEN_MINUTES):
    """The bars belonging to one day's opening window. [] when there are none.

    Bounded at both ends on purpose. An open-ended 'before 9:30' would sweep in the
    previous session's tail whenever a day's data is incomplete, and a range built from
    yesterday's prices is not a range - it is a number that looks like one.
    """
    lo = datetime.combine(day, SESSION_OPEN, IST)
    hi = lo + timedelta(minutes=minutes)
    out = []
    for b in bars or []:
        t = _ts(b)
        if t and lo <= t < hi:
            out.append(b)
    return out


def opening_range(bars, day, minutes=OPEN_MINUTES):
    """(high, low, volume, n_bars) for the opening window, or Nones when unmeasurable.

    Returns None rather than a partial answer when the window is empty. A range of
    (0, 0) breaks upward on every tick.
    """
    ws = session_bars(bars, day, minutes)
    if not ws:
        return {"high": None, "low": None, "volume": None, "bars": 0}
    highs = [b.get("h") for b in ws if b.get("h") is not None]
    lows = [b.get("l") for b in ws if b.get("l") is not None]
    vols = [b.get("v") or 0 for b in ws]
    if not highs or not lows:
        return {"high": None, "low": None, "volume": None, "bars": len(ws)}
    return {"high": max(highs), "low": min(lows),
            "volume": sum(vols), "bars": len(ws)}


def rvol_open(bars, day, minutes=OPEN_MINUTES, lookback=RVOL_LOOKBACK):
    """(ratio, note) — today's opening volume against the median of the SAME window.

    The comparison is like-for-like by construction: fifteen minutes of today against
    fifteen minutes of each previous session, never against a daily average. Median rather
    than mean because one event day in the lookback would drag a mean enough to hide a
    genuinely busy morning.

    ratio is None when there is not enough history to compare against, and the note says
    so. Unknown is not 1.0 - a name whose past cannot be read has not been shown to be
    normal, and ranking it as average is exactly the silent pass this system refuses.
    """
    today = opening_range(bars, day, minutes)
    if not today["volume"]:
        return None, "no opening bars today"
    days, seen = [], set()
    for b in bars or []:
        t = _ts(b)
        if t and t.date() < day:
            seen.add(t.date())
    for d in sorted(seen, reverse=True)[:lookback]:
        w = opening_range(bars, d, minutes)
        if w["volume"]:
            days.append(w["volume"])
    if len(days) < 5:
        return None, f"only {len(days)} past sessions in the window - too few to compare"
    med = _median(days)
    if not med:
        return None, "past opening volume was zero"
    return round(today["volume"] / med, 2), f"vs median of {len(days)} sessions"


def vwap(bars, day, until_minutes=OPEN_MINUTES):
    """Volume-weighted average price across the opening window. None if unmeasurable.

    Typical price rather than close, and volume-weighted rather than averaged: an
    unweighted mean of bar closes is not a VWAP and would sit in a different place on
    exactly the days volume is lopsided, which are the days this is for.
    """
    ws = session_bars(bars, day, until_minutes)
    num = den = 0.0
    for b in ws:
        h, l, c, v = b.get("h"), b.get("l"), b.get("c"), b.get("v")
        if None in (h, l, c) or not v:
            continue
        num += ((h + l + c) / 3.0) * v
        den += v
    return round(num / den, 2) if den else None


def gap_vs_trend(open_px, prev_close, trend_pct):
    """(gap_pct, aligned, note) — is the gap going the way the stock already was?

    A gap is not a direction on its own. The same +1.5% opening is a continuation setup on
    a name that has been climbing and a fade candidate on one that has been falling, and
    ranking on gap size alone mixes the two into one list.

    aligned is None when the trend is unknown, never False. "I do not know which way this
    has been going" and "it has been going the other way" are different findings.
    """
    if not open_px or not prev_close:
        return None, None, "no open or previous close"
    gap = round(100.0 * (open_px - prev_close) / prev_close, 2)
    if trend_pct is None:
        return gap, None, "trend unknown - not scored"
    if gap == 0:
        return 0.0, None, "flat open"
    aligned = (gap > 0) == (trend_pct > 0)
    return gap, aligned, ("gap runs with the trend" if aligned
                          else "gap runs against the trend")


def relative_strength(stock_open_pct, index_open_pct):
    """The stock's opening move minus the index's. None when either is unknown.

    A stock up 1% on a morning the whole market is up 1% has demonstrated nothing, and
    scoring it as strong is how a screen fills up with names that are simply present.
    """
    if stock_open_pct is None or index_open_pct is None:
        return None
    return round(stock_open_pct - index_open_pct, 2)


# ------------------------------------------------------------------ the score --
# WEIGHTS ARE A HYPOTHESIS, NOT A RESULT. Nothing here has been fitted to anything -
# fitting them before the components are validated would be curve-fitting a curve nobody
# has drawn yet. They are deliberately blunt (an ordering, not a model) so that when the
# backtest runs, what gets tested is whether these FACTORS carry information, not whether
# one particular weighting of them happened to fit one particular sample.
#
# The ablation harness exists for exactly this: each weight is one arm, changed one at a
# time. Until that has run, this ranking is a shortlist for a human to look at, and the
# option layer downstream still has to agree the contract is tradeable.
WEIGHTS = {"break": 3.0, "rvol": 2.0, "rel_str": 2.0, "gap_align": 1.5, "vwap": 1.5}

#: an RVOL below this is an ordinary morning, whatever else the name is doing
RVOL_FLOOR = 1.5


def score_name(m):
    """(score, reasons, missing) for one measured name.

    `missing` is the point of this function. A name that could not be measured on a factor
    does not score zero on it - it is REPORTED as unmeasured and, if anything material is
    missing, refused outright by scan(). Zero is a measurement; absent is not. Scoring the
    two the same is how a half-read name outranks a fully-read one and nobody can tell
    from the list which is which.
    """
    pts, why, missing = 0.0, [], []

    br = m.get("break")                  # +1 broke up, -1 broke down, 0 inside
    if br is None:
        missing.append("opening range")
    elif br:
        pts += WEIGHTS["break"]
        why.append("broke the opening range " + ("up" if br > 0 else "down"))
    else:
        why.append("still inside the opening range")

    rv = m.get("rvol")
    if rv is None:
        missing.append("rvol")
    elif rv >= RVOL_FLOOR:
        # Capped: a 40x print is a corporate event or a block deal, not forty times the
        # conviction, and uncapped it would own the top of the list every time it happens.
        pts += WEIGHTS["rvol"] * min(rv / RVOL_FLOOR, 3.0)
        why.append(f"rvol {rv}x")
    else:
        why.append(f"rvol only {rv}x - an ordinary morning")

    rs = m.get("rel_strength")
    if rs is None:
        missing.append("relative strength")
    elif br and (rs > 0) == (br > 0):
        pts += WEIGHTS["rel_str"]
        why.append(f"{abs(rs):.2f}% {'ahead of' if rs > 0 else 'behind'} the index")

    al = m.get("gap_aligned")
    if al is True:
        pts += WEIGHTS["gap_align"]
        why.append("gap runs with the trend")
    elif al is False:
        why.append("gap runs against the trend")
    # al is None -> the trend was unknown. Not scored, not penalised, and not missing:
    # a name can genuinely have no readable trend and still be a valid break.

    vw = m.get("vs_vwap")
    if vw is None:
        missing.append("vwap")
    elif br and (vw > 0) == (br > 0):
        pts += WEIGHTS["vwap"]
        why.append("on the right side of vwap")
    elif br:
        why.append("wrong side of vwap")

    return round(pts, 2), why, missing


#: factors without which a name is not ranked at all
REQUIRED = ("opening range", "rvol", "vwap")


def scan(measured, top=30):
    """Rank measured names. {'names': [...], 'dropped': [...]}.

    Two lists, always. The dropped one is not diagnostics - it is the answer to "why is
    this name not here", which is the first question a screen gets asked and the one most
    screens cannot answer. A name is dropped for a stated reason or it is ranked; there is
    no third state and nothing disappears quietly.
    """
    ranked, dropped = [], []
    for m in measured or []:
        pts, why, missing = score_name(m)
        blocking = [f for f in missing if f in REQUIRED]
        if blocking:
            dropped.append({"name": m.get("name"),
                            "why": f"not measured: {', '.join(blocking)}"})
            continue
        if not m.get("break"):
            dropped.append({"name": m.get("name"),
                            "why": "has not broken its opening range"})
            continue
        ranked.append({**m, "score": pts, "reasons": why,
                       "unmeasured": [f for f in missing if f not in REQUIRED],
                       "side": "LONG" if m["break"] > 0 else "SHORT"})
    ranked.sort(key=lambda r: -r["score"])
    return {"names": ranked[:top], "dropped": dropped,
            "shown": min(len(ranked), top), "passed": len(ranked)}
