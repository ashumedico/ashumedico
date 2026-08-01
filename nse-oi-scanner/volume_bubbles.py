"""
volume_bubbles.py  —  a bubble per candle: how busy it was, and who was positioning.

WHAT WAS ASKED FOR, AND WHY IT IS NOT WHAT GETS BUILT
The request was bubbles sized by volume and coloured by "whether the buying is happening
or the selling", to show "whether big players are making position or not".

The first half is measurable. The second is not, from this data - and not because the feed
is poor. EVERY TRADE HAS A BUYER AND A SELLER. Volume is one number and it belongs to both
sides of every print. Splitting it into buy-volume and sell-volume needs tick data carrying
the bid and ask at the moment of each trade, so a trade at the ask can be called a buy.
Fyers serves that on the live socket; the history endpoint does not carry it. Every retail
"buy/sell volume" overlay that runs off OHLCV is really reading where the close sat inside
the candle's range, which is a guess with a confident colour on it.

And the actual question - are big players BUILDING POSITIONS - is one volume cannot answer
even with perfect tick data. Volume cannot tell a new position from churn: the same lot
passed back and forth ten times prints ten times the volume and leaves open interest
exactly where it started.

OPEN INTEREST ANSWERS IT DIRECTLY, which is the whole point of the four states this
system has been computing since before the chart existed:

                      price UP              price DOWN
      OI UP     LONG BUILDUP           SHORT BUILDUP        <- new money, a position taken
      OI DOWN   SHORT COVERING         LONG UNWINDING       <- old money leaving

The two BUILDUP states are the answer to the question as asked. The other two are the same
price direction produced by positions closing rather than opening, which is the distinction
that makes a chart worth looking at and the one a volume bubble cannot draw.

WHAT IS KNOWN, AND FOR HOW LONG
Buildup is computed from LIVE quotes against a day-open baseline - open interest now
versus open interest at the open. There is no per-candle history of it anywhere in the
feed, so yesterday's candles cannot be coloured without inventing the colour. They are not
coloured. `oi_history.py` records each session's state from today forward, exactly as
iv_history does for implied vol, so the coloured span grows by one day per day and starts
honest rather than starting full and wrong.

    size    volume of the bar against the median of the SAME bar-of-day in past sessions
    colour  the recorded buildup state, where one exists
    absent  no bubble at all - never a default-sized one
"""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

#: the four states, and whether each one means a position was OPENED
BUILDUP = {
    "LONG BUILDUP":   {"opening": True,  "side": "LONG"},
    "SHORT BUILDUP":  {"opening": True,  "side": "SHORT"},
    "SHORT COVERING": {"opening": False, "side": "LONG"},
    "LONG UNWINDING": {"opening": False, "side": "SHORT"},
}

MIN_SESSIONS = 5          # below this there is no norm to compare a bar against
MAX_SCALE = 4.0           # a bubble stops growing here; see size_of()


def _ts(bar):
    t = bar.get("t") if isinstance(bar, dict) else None
    if t is None:
        return None
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=IST)
    try:
        return datetime.fromtimestamp(float(t), IST)
    except (TypeError, ValueError, OSError):
        return None


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def volume_norm(bars, index, lookback=20, intraday=True):
    """(ratio, note) — this bar's volume against what this bar of the day normally does.

    Bar-of-day matters and is the thing usually skipped. The 9:15 candle is the busiest of
    every session and the 13:00 candle is among the quietest, so comparing either against
    a flat average of all bars makes the morning look permanently extraordinary and the
    afternoon permanently dead. Matching bar-of-day removes the shape of the day and
    leaves only what is unusual about THIS one.

    ratio is None when there is no norm to compare against, and None draws no bubble.
    A missing comparison is not an average one.
    """
    if index < 0 or index >= len(bars or []):
        return None, "no such bar"
    here = bars[index]
    v = here.get("v")
    if not v:
        return None, "bar carries no volume"
    t = _ts(here)
    if t is None:
        return None, "bar carries no timestamp"

    past = []
    for b in bars[:index]:
        bt = _ts(b)
        if bt is None or not b.get("v"):
            continue
        if intraday:
            if bt.date() == t.date():
                continue                       # today is what we are measuring
            if (bt.hour, bt.minute) != (t.hour, t.minute):
                continue                       # same bar-of-day only
        past.append(b["v"])
    past = past[-lookback:]
    if len(past) < MIN_SESSIONS:
        return None, f"only {len(past)} comparable bars - no norm yet"
    med = _median(past)
    if not med:
        return None, "comparable bars carry no volume"
    return round(v / med, 2), f"vs median of {len(past)} same-time bars"


def size_of(ratio, base=6.0):
    """Marker area for a volume ratio. None stays None.

    Capped at MAX_SCALE because the tail is not information. A block deal prints thirty
    times the usual volume, and a bubble thirty times the size stops being a mark on a
    chart and becomes the chart - hiding the ordinary 2x day next to it, which is the one
    a trade might be built on.
    """
    if ratio is None:
        return None
    return round(base * min(max(ratio, 0.25), MAX_SCALE), 2)


def bubbles(bars, states=None, lookback=20, intraday=True):
    """One entry per bar that can be measured. Bars that cannot be are simply absent.

    states: {date -> buildup string}, as recorded by oi_history. A date with no recorded
    state yields state=None, which renders in the neutral colour and is COUNTED, so the
    chart can say how much of itself is uncoloured instead of implying it is all known.
    """
    states = states or {}
    out, uncoloured = [], 0
    for i, b in enumerate(bars or []):
        ratio, note = volume_norm(bars, i, lookback, intraday)
        if ratio is None:
            continue
        t = _ts(b)
        st = states.get(t.date().isoformat()) if t else None
        if st not in BUILDUP:
            st = None
            uncoloured += 1
        out.append({
            "t": t, "index": i,
            "close": b.get("c"), "high": b.get("h"), "low": b.get("l"),
            "volume": b.get("v"), "ratio": ratio, "size": size_of(ratio),
            "state": st,
            "opening": BUILDUP[st]["opening"] if st else None,
            "note": note,
        })
    return {"bubbles": out, "uncoloured": uncoloured,
            "measured": len(out), "bars": len(bars or [])}


def legend(result):
    """One line under the chart saying what it does and does not know.

    A chart that colours 6 of 200 candles and says nothing reads as a chart where 194
    candles were judged neutral. The count is the difference between a legend and a lie.
    """
    n, un = result.get("measured", 0), result.get("uncoloured", 0)
    total = result.get("bars", 0)
    bits = [f"{n} of {total} candles have a volume norm to measure against"]
    if un:
        bits.append(f"{un} carry no recorded OI state yet — not neutral, unknown")
    return " · ".join(bits)
