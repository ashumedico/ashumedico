"""
features.py  —  one place where every candidate signal becomes a number.

Support/resistance, price action, volume, OI buildup, VWAP - each was asked for, and each
already existed in some corner of this codebase or none at all. Scattered, they could be
looked at but not tested. Here they become a dict per name per bar, which is the shape an
ablation can consume.

Everything is computed from bars STRICTLY BEFORE the decision bar. That is not politeness:
a feature that peeks one bar ahead improves every backtest it touches and is
indistinguishable from an edge until real money is on it.

WHAT CANNOT BE HERE, AND WHY

OI buildup. fetch_buildup reads today's futures quotes against the day-open baseline;
there is no historical open-interest series anywhere in this system. So buildup can be
displayed and journalled forward, but it cannot be walk-forward tested - not because it
is unimportant, but because the data to test it does not exist. Anything claiming to have
tested it would be claiming something impossible.
"""
import indicators as I

try:
    import chart_action as CA
except Exception:
    CA = None


def at(bars, dates, t=None, rvol_win=20, sr_lookback=60):
    """Every feature for one name, as of bar t (exclusive - t itself is not seen).

    Returns None when there is not enough history, rather than a dict of zeros: a missing
    feature and a feature that happens to be zero are different facts, and the second one
    silently passes filters the first should fail.
    """
    t = len(bars) if t is None else t
    hist = bars[:t]
    if len(hist) < max(rvol_win, 35):
        return None
    d = dates[:t] if dates else [""] * len(hist)
    closes = [b[4] for b in hist]
    px = closes[-1]

    vw = I.vwap_session(hist, d)
    rv = I.rvol(hist, rvol_win)
    a = I.atr(hist)
    sq = I.squeeze(hist)
    ex = I.expansion(hist)

    f = {
        "close": px,
        # VWAP: the session's volume-weighted reference. Above it, buyers have been
        # paying up on average today.
        "vwap": round(vw[-1], 2),
        "above_vwap": px > vw[-1],
        "vwap_dist_pct": round(100 * (px / vw[-1] - 1), 2) if vw[-1] else 0.0,
        # Volume, relative to the name's own norm - absolute volume says more about the
        # stock's size than about today.
        "rvol": round(rv[-1], 2),
        "atr": round(a[-1], 2),
        # Compression, and the bar it releases. The closest measurable thing to entering
        # before a move rather than five bars into one.
        "squeeze": round(sq[-1], 2),
        "coiled": sq[-1] < 0.7,
        "expanding": bool(ex[-1]),
    }

    # --- support / resistance and price action, from the module that already had them ---
    # chart_action predates this and speaks a different dialect: dict candles keyed
    # o/h/l/c, and UPPERCASE level names. Both mismatches were being swallowed by a bare
    # except, so every S/R field came back missing and the filters that need them simply
    # never fired. Translate once, here, and let a real failure be visible.
    if CA is not None:
        try:
            win = [{"o": b[1], "h": b[2], "l": b[3], "c": b[4], "v": b[5]}
                   for b in hist[-sr_lookback:]]
            sr = CA.support_resistance(win)
            r1, r2 = sr.get("R1"), sr.get("R2")
            s1, s2 = sr.get("S1"), sr.get("S2")
            f.update({"r1": r1, "r2": r2, "s1": s1, "s2": s2})
            # Distance to the nearest level, in ATR - "5 rupees away" means nothing
            # without knowing what the name moves in a bar.
            unit = f["atr"] or 1e-9
            f["to_resistance_atr"] = round((r1 - px) / unit, 2) if r1 else None
            f["to_support_atr"] = round((px - s1) / unit, 2) if s1 else None
            # Room: a long into overhead resistance has less to gain than the same
            # signal with clear air above it.
            f["room_up"] = (f["to_resistance_atr"] is None or f["to_resistance_atr"] > 1.0)
            # continuation() returns {dir, count, of}; keep the parts a filter can use
            # rather than the dict, which compares as neither a number nor a direction.
            c = CA.continuation(win) or {}
            f["cont_dir"] = c.get("dir")
            f["cont_up"] = c.get("count", 0) if c.get("dir") == "up" else 0
            f["breakout"] = bool(r1 and CA.body_breakout(win[-1], r1))
            tr = CA.trend(win) or {}
            f["trend_struct"] = tr.get("combined") or tr.get("primary")
        except Exception as e:      # noqa
            # Say what broke. A silently missing feature is a filter that never fires,
            # and nothing on screen would ever mention it.
            f["feature_error"] = f"{type(e).__name__}: {e}"[:120]
    return f


def for_universe(bars_by_symbol, dates, t=None):
    """{SHORTNAME: features} for every name that has enough history."""
    out = {}
    for sym, bars in (bars_by_symbol or {}).items():
        if not bars:
            continue
        name = sym.split(":")[-1].replace("-EQ", "")
        got = at(bars, dates, t)
        if got:
            out[name] = got
    return out


def attach(points, feats):
    """Hang the features on the RRG points so a rule can filter on them."""
    for p in points:
        f = feats.get(p["name"])
        if f:
            p["feat"] = f
    return points


def passes(p, params):
    """Feature-based entry conditions. Absent features never pass a filter that needs
    them - an unknown must not be treated as a yes."""
    f = p.get("feat")
    if params.get("need_vwap"):
        if not f or not f.get("above_vwap"):
            return False
    if params.get("min_rvol"):
        if not f or (f.get("rvol") or 0) < float(params["min_rvol"]):
            return False
    if params.get("need_room"):
        if not f or not f.get("room_up"):
            return False
    if params.get("need_breakout"):
        if not f or not f.get("breakout"):
            return False
    if params.get("min_cont"):
        # up-candles in a row, not just "some continuation" - a run of down candles is
        # continuation too, and it is the opposite trade
        if not f or (f.get("cont_up") or 0) < int(params["min_cont"]):
            return False
    if params.get("need_expansion"):
        # the bar a coil breaks - the entry bar, not the fifth bar of a move
        if not f or not f.get("expanding"):
            return False
    if params.get("max_squeeze"):
        if not f or (f.get("squeeze") or 99) > float(params["max_squeeze"]):
            return False
    return True


if __name__ == "__main__":
    bars, dates = I._demo_bars()
    f = at(bars, dates)
    print("\n  FEATURES (synthetic bars - mechanics only)")
    print("  " + "-" * 54)
    for k in ("close", "vwap", "above_vwap", "vwap_dist_pct", "rvol", "atr",
              "squeeze", "coiled", "expanding",
              "r1", "s1", "to_resistance_atr", "to_support_atr",
              "room_up", "cont_dir", "cont_up", "breakout", "trend_struct",
              "feature_error"):
        if k in f:
            print(f"  {k:<20} {f[k]}")
    print("  " + "-" * 54)
    for params in ({"need_vwap": True}, {"min_rvol": 1.5}, {"need_room": True},
                   {"need_breakout": True}, {"min_cont": 3},
                   {"need_expansion": True}, {"max_squeeze": 0.7},
                   {"need_vwap": True, "min_rvol": 1.2}):
        print(f"  {str(params):<38} -> {passes({'feat': f}, params)}")
    print(f"  {'features missing entirely':<38} -> {passes({}, {'need_vwap': True})}"
          f"   (unknown must not pass)")
    print()
