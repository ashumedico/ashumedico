"""
signal_engine.py  —  the brain that REVALIDATES trade signals across 3 layers.

Your original scanner gave OI buildup. This adds two more independent lenses and
only fires a trade when they AGREE — exactly what you asked: take the scanner's
signals and cross-check them against chart-action before recommending anything.

  Layer 1  OI BUILDUP     (scanner.py)      — long/short buildup, covering, unwinding
  Layer 2  OPTION CHAIN   (option_chain.py) — PCR, Max Pain, Support/Resistance walls, writing
  Layer 3  CHART ACTION   (chart_action.py) — trend, R1/R2, S1/S2, 3-5 continuation, 60% body breakout

Convergence -> a confidence score (0-100). We then emit exactly:
  • ONE CE option idea   (the strongest bullish confluence)
  • ONE PE option idea   (the strongest bearish confluence)
  • ONE FUTURES idea     (the single highest-conviction directional name)

Each idea carries entry / stop / target and the WHY (which layers agreed).
NOT financial advice — signals are inputs; the decision is yours (@edge-seeker).
"""
import chart_action as ca
import option_chain as oc


# ---------- scoring ----------
def _dir_from_buildup(signal):
    return {"LONG BUILDUP": +1, "SHORT COVERING": +1,
            "SHORT BUILDUP": -1, "LONG UNWINDING": -1}.get(signal, 0)


def _near(price, level, tol=0.012):
    return level and abs(price - level) / price <= tol


def _dir_from_chart(chart):
    """Trend dominates. Aligned continuation/breakout add conviction; a counter
    pullback INTO support/resistance is the entry (buy-the-dip / sell-the-bounce),
    so it is not treated as a reversal."""
    tr = chart["trend"]["combined"]; L = chart["levels"]; px = chart["close"]
    bull = "Bullish" in tr; bear = "Bearish" in tr
    s = (1 if bull else 0) - (1 if bear else 0)          # primary trend vote
    cont = chart["continuation"]["dir"]
    if s > 0 and cont == "up":   s += 1                  # continuation confirms up
    if s < 0 and cont == "down": s -= 1                  # continuation confirms down
    b = chart["breakout"]
    if b and b["dir"] == "up" and s >= 0:   s += 1       # 60%-body breakout up
    if b and b["dir"] == "down" and s <= 0: s -= 1       # 60%-body breakout down
    # pullback-to-support in an uptrend (or bounce-to-resistance in a downtrend) = the setup
    if bull and _near(px, L["S1"]): s += 1
    if bear and _near(px, L["R1"]): s -= 1
    return s


def _dir_from_chain(oc_m, spot):
    """Bias from PCR + where spot sits vs max-pain."""
    s = 0
    if oc_m["pcr"] >= 1.2:  s += 1
    elif oc_m["pcr"] <= 0.7: s -= 1
    if oc_m["max_pain"] and spot:
        if spot < oc_m["max_pain"]: s += 1        # pull up toward pain
        elif spot > oc_m["max_pain"]: s -= 1      # pull down toward pain
    return s


def evaluate(name, buildup_row, chart, oc_m):
    """Fuse the 3 layers for one instrument into a signed conviction score + reasons."""
    spot = chart["close"]
    b_dir = _dir_from_buildup(buildup_row["signal"]) if buildup_row else 0
    c_dir = _dir_from_chart(chart)
    o_dir = _dir_from_chain(oc_m, spot) if oc_m else 0

    reasons = []
    if buildup_row:
        reasons.append(f"OI: {buildup_row['signal'].title()} "
                       f"({buildup_row['oi']:+.1f}% OI, {buildup_row['px']:+.1f}% px"
                       f"{', VOL✓' if buildup_row.get('conf') == 'yes' else ''})")
    tr = chart["trend"]; cont = chart["continuation"]
    reasons.append(f"Chart: {tr['combined']} trend, {cont['count']}/{cont['of']} candles {cont['dir']}")
    if chart["breakout"]:
        bk = chart["breakout"]
        reasons.append(f"60%-body breakout {bk['dir']} through {bk['level']} {bk['price']} "
                       f"(body {bk['body_pct']}%)")
    if oc_m:
        reasons.append(f"Chain: PCR {oc_m['pcr']}, Max-Pain {oc_m['max_pain']}, "
                       f"walls {oc_m['support']}/{oc_m['resistance']}")

    # weighted fusion: chart 2x (it's the S/R + breakout evidence), OI 2x, chain 1x
    raw = 2 * b_dir + 2 * c_dir + 1 * o_dir
    agree = sum(1 for d in (b_dir, c_dir, o_dir) if d != 0 and (d > 0) == (raw > 0))
    direction = "BULLISH" if raw > 0 else "BEARISH" if raw < 0 else "NEUTRAL"
    confidence = min(100, round(abs(raw) / 10 * 70 + agree * 10))   # magnitude + agreement
    return {"name": name, "spot": spot, "direction": direction, "score": raw,
            "confidence": confidence, "agree": agree, "reasons": reasons,
            "levels": chart["levels"], "chart": chart, "oc": oc_m}


# ---------- turn a verdict into a tradeable idea ----------
def _levels_trade(v, side):
    """Entry / stop / target from the S/R levels, sized to the structure."""
    L = v["levels"]; spot = v["spot"]
    if side == "CE":      # bullish buy-the-dip: enter at support, target the ceilings
        entry = spot; stop = L["S2"]; target = L["R2"]
    else:                 # PE bearish sell-the-bounce: enter at resistance, target the floors
        entry = spot; stop = L["R2"]; target = L["S2"]
    rr = abs(target - entry) / (abs(entry - stop) or 1)
    return {"entry": round(entry, 1), "stop": round(stop, 1),
            "target": round(target, 1), "rr": round(rr, 2)}


def _atm_strike(spot, step=None):
    step = step or (100 if spot > 5000 else 50 if spot > 1000 else 10)
    return round(spot / step) * step


def build_ideas(verdicts):
    """From all evaluated instruments, pick ONE CE, ONE PE, ONE Future."""
    bulls = [v for v in verdicts if v["direction"] == "BULLISH"]
    bears = [v for v in verdicts if v["direction"] == "BEARISH"]
    bulls.sort(key=lambda v: v["confidence"], reverse=True)
    bears.sort(key=lambda v: v["confidence"], reverse=True)

    ideas = {}
    if bulls:
        v = bulls[0]; t = _levels_trade(v, "CE"); K = _atm_strike(v["spot"])
        ideas["CE"] = {"kind": "CALL (CE)", "underlying": v["name"], "strike": K,
                       "bias": "BULLISH", "confidence": v["confidence"],
                       "trade": t, "levels": v["levels"], "reasons": v["reasons"],
                       "verdict": v,
                       "thesis": f"Buy {v['name']} {K} CE — long confluence: "
                                 f"{'; '.join(v['reasons'])}. Enter {t['entry']}, "
                                 f"stop {t['stop']} (below S2), target {t['target']} (R2). "
                                 f"R:R {t['rr']}."}
    if bears:
        v = bears[0]; t = _levels_trade(v, "PE"); K = _atm_strike(v["spot"])
        ideas["PE"] = {"kind": "PUT (PE)", "underlying": v["name"], "strike": K,
                       "bias": "BEARISH", "confidence": v["confidence"],
                       "trade": t, "levels": v["levels"], "reasons": v["reasons"],
                       "verdict": v,
                       "thesis": f"Buy {v['name']} {K} PE — short confluence: "
                                 f"{'; '.join(v['reasons'])}. Enter {t['entry']}, "
                                 f"stop {t['stop']} (above R2), target {t['target']} (S2). "
                                 f"R:R {t['rr']}."}
    # future = single highest-conviction directional name (either side)
    ranked = sorted(verdicts, key=lambda v: v["confidence"], reverse=True)
    directional = [v for v in ranked if v["direction"] != "NEUTRAL"]
    if directional:
        v = directional[0]; side = "CE" if v["direction"] == "BULLISH" else "PE"
        t = _levels_trade(v, side)
        ideas["FUT"] = {"kind": "FUTURES", "underlying": v["name"],
                        "bias": v["direction"], "confidence": v["confidence"],
                        "trade": t, "levels": v["levels"], "reasons": v["reasons"],
                        "verdict": v,
                        "thesis": f"{'Long' if v['direction']=='BULLISH' else 'Short'} "
                                  f"{v['name']} FUT — highest-conviction directional name "
                                  f"({v['confidence']}% confidence). "
                                  f"Enter {t['entry']}, stop {t['stop']}, target {t['target']}. "
                                  f"R:R {t['rr']}. Why: {'; '.join(v['reasons'])}"}
    return ideas


# ---------- dry-run universe (revalidates the scanner's own signals) ----------
def dry_verdicts():
    """Three synthetic names, one per archetype, each cross-validated across all 3 layers.
    This mirrors: scanner buildup + option chain + chart action -> fused verdict."""
    universe = [
        # name,            buildup row (from scanner.classify),                shape,        base
        ("NSE:RELIANCE",  {"signal": "LONG BUILDUP",  "oi": 11.4, "px": 2.1, "conf": "yes"}, "bull_flag", 2950.0),
        ("NSE:HDFCBANK",  {"signal": "SHORT BUILDUP", "oi": 9.7,  "px": -1.8, "conf": "yes"}, "bear",      1660.0),
        ("NSE:NIFTY50",   {"signal": "SHORT COVERING","oi": -4.2, "px": 0.4, "conf": "check"}, "range",     24200.0),
    ]
    verdicts = []
    for name, row, shape, base in universe:
        candles = ca.fetch_dry(name, base=base, shape=shape)
        chart = ca.analyse(candles)
        # centre the dry option chain on THIS name's live price so walls are meaningful
        chain, spot = oc.fetch_dry(name, spot=chart["close"])
        oc_m = oc.analyse(chain, spot)
        verdicts.append(evaluate(name, row, chart, oc_m))
    return verdicts


def _underlying_of(fut_symbol):
    """NSE:RELIANCE25JULFUT -> NSE:RELIANCE-EQ ;  NSE:NIFTY25JULFUT -> NSE:NIFTY50-INDEX."""
    short = fut_symbol.split(":")[-1]
    name = short.split("2")[0]                       # strip expiry+FUT
    idx = {"NIFTY": "NSE:NIFTY50-INDEX", "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
           "FINNIFTY": "NSE:FINNIFTY-INDEX", "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX"}
    return idx.get(name, f"NSE:{name}-EQ")


def live_verdicts(top_n=6):
    """Assemble the 3-layer verdict from LIVE Fyers data (runs on your PC).
    Buildup (scanner) x option chain x chart action, per top-OI name."""
    import scanner
    curr = scanner.fetch_live()
    baseline = scanner.load_baseline()
    if baseline is None:
        scanner.save_baseline(curr); baseline = curr
    rows = scanner.build_rows(baseline, curr, scanner.config.MIN_OI_CHANGE_PCT)[:top_n]
    full = {s.split(":")[-1]: s for s in curr}       # short -> full symbol
    verdicts = []
    for row in rows:
        fut = full.get(row["sym"], f"NSE:{row['sym']}")
        try:
            candles = ca.fetch_candles(fut)
            if len(candles) < 12:
                continue
            chart = ca.analyse(candles)
            und = _underlying_of(fut)
            try:
                chain, spot = oc.fetch_live(und)
                oc_m = oc.analyse(chain, spot)
            except Exception:
                oc_m = None                          # option chain optional
            verdicts.append(evaluate(fut, row, chart, oc_m))
        except Exception as e:                       # noqa
            print(f"  [skip] {fut}: {e}")
    return verdicts


def render(ideas):
    print("\n" + "=" * 64)
    print("  REVALIDATED TRADE SIGNALS  ·  3-layer confluence")
    print("  OI buildup  ×  option chain  ×  chart action")
    print("=" * 64)
    for key in ("CE", "PE", "FUT"):
        idea = ideas.get(key)
        if not idea:
            print(f"\n  [{key}]  no qualifying confluence today.")
            continue
        t = idea["trade"]; L = idea["levels"]
        head = f"{idea['kind']}"
        if idea.get("strike"):
            head += f"  {idea['underlying']} {idea['strike']}"
        else:
            head += f"  {idea['underlying']}"
        print(f"\n  ► {head}   [{idea['bias']} · {idea['confidence']}%]")
        print(f"    Entry {t['entry']}   Stop {t['stop']}   Target {t['target']}   R:R {t['rr']}")
        print(f"    Levels:  R2 {L['R2']}  R1 {L['R1']}  |  S1 {L['S1']}  S2 {L['S2']}")
        for r in idea["reasons"]:
            print(f"      • {r}")
    print("\n" + "=" * 64)
    print("  NOT financial advice. Signals are inputs; the trade is yours.")
    print("=" * 64 + "\n")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="synthetic data, no Fyers")
    args = ap.parse_args()
    verdicts = dry_verdicts() if args.dry_run else live_verdicts()
    if not verdicts:
        print("  No qualifying names (need live Fyers data + OI-change candidates).")
        return {}
    ideas = build_ideas(verdicts)
    render(ideas)
    return ideas


if __name__ == "__main__":
    main()
