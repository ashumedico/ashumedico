"""
test_short.py  —  the short book is a mirror, not a copy.

Every direction-bearing number has to flip: the stop goes above, targets go below, the
option becomes a put, the intrinsic formula inverts, the continuation count reads down
candles, and the ranking picks the WEAKEST name rather than the strongest. Each of those
is a place where a copied long rule silently produces a card that says SHORT and behaves
long.

    python test_short.py
"""
import sys

fail = 0


def ok(cond, good, bad):
    global fail
    if cond:
        print(f"   ok - {good}")
    else:
        print(f"   *** {bad} ***")
        fail += 1


def wobbly(start, drift, n=60, amp=6.0):
    """A series with real bar-to-bar movement, so realised vol is not zero."""
    out, px = [], float(start)
    for i in range(n):
        px += drift + (amp if i % 2 else -amp) * 0.5
        out.append(round(px, 2))
    return out


print("\n  SHORT BOOK")
print("  " + "-" * 64)

# ---------- 1. the card mirrors ----------
print("\n1. TRADE CARD")
import trade_card as TC

up = {"name": "UP", "symbol": "NSE:UP-EQ", "close": 1000.0, "abs_trend": 1.0, "abs_pct": 4.0}
dn = {"name": "DN", "symbol": "NSE:DN-EQ", "close": 1000.0, "abs_trend": -1.0, "abs_pct": -4.0}
L = TC.build_card(up, wobbly(900, +2), expiry_label="28AUG", days_to_expiry=25,
                  capital=200000)
S = TC.build_card(dn, wobbly(1100, -2), expiry_label="28AUG", days_to_expiry=25,
                  capital=200000, side="SHORT")

ok(L["option"]["type"] == "CE" and S["option"]["type"] == "PE",
   "long is a CE, short is a PE", f"types wrong: {L['option']['type']}/{S['option']['type']}")
ok(S["stock"]["stop"] > S["spot"],
   f"short stop {S['stock']['stop']} sits ABOVE spot {S['spot']}",
   "short stop is below spot - that is a long's stop")
ok(S["stock"]["t1"] < S["spot"] and S["stock"]["t2"] < S["stock"]["t1"],
   "short targets step down", "short targets point the wrong way")
ok(S["stock"]["rr1"] > 0 and L["stock"]["rr1"] > 0,
   "both sides report positive R:R", "R:R went negative on one side")
ok(S["option"]["t1"] > S["option"]["premium"] > S["option"]["stop"],
   "put premium rises to target and falls to stop",
   "put option levels are inverted")

# a short on a rising name must refuse itself
bad = TC.build_card(up, wobbly(900, +2), days_to_expiry=25, capital=200000, side="SHORT")
ok(bad["action"] == "SKIP",
   "short on an up-trending name is SKIPped",
   f"shorted an uptrend anyway: {bad['action']}")

# ---------- 2. put intrinsic ----------
print("\n2. PUT INTRINSIC  (a call's formula rejects every real put)")
# an in-the-money put: strike 1100, spot 1000 -> intrinsic 100, a quote of 120 is normal
chain = [{"type": "PE", "strike": 1100, "ltp": 120.0, "symbol": "NSE:DN25AUG1100PE"},
         {"type": "CE", "strike": 1100, "ltp": 5.0, "symbol": "NSE:DN25AUG1100CE"}]
c = TC.build_card({"name": "DN", "symbol": "NSE:DN-EQ", "close": 1000.0,
                   "abs_trend": -1.0}, wobbly(1100, -2), chain=chain,
                  days_to_expiry=25, capital=200000, side="SHORT")
rej = (c.get("option") or {}).get("premium_reject")
ok(not rej or "intrinsic 0.0" not in str(rej),
   "in-the-money put is not rejected as fake",
   f"put judged by the call formula: {rej}")

# ---------- 3. features mirror ----------
print("\n3. FEATURES")
import features as F

p_no_feat = {"name": "X"}
ok(not F.passes_short(p_no_feat, {"need_vwap": True}),
   "missing features fail the short gate too",
   "unknown counted as a yes on the short side")

below = {"feat": {"above_vwap": False, "rvol": 2.0, "room_down": True,
                  "cont_down": 4, "breakdown": True, "expanding": True, "squeeze": 0.5}}
above = {"feat": {"above_vwap": True, "rvol": 2.0, "room_down": True,
                  "cont_down": 4, "breakdown": True, "expanding": True, "squeeze": 0.5}}
params = {"need_vwap": True, "min_rvol": 1.2, "need_room": True,
          "need_breakout": True, "min_cont": 3, "need_expansion": True}
ok(F.passes_short(below, params) and not F.passes_short(above, params),
   "short needs price BELOW vwap", "short accepted a name above vwap")
ok(not F.passes(below, params),
   "the same name does not pass the LONG gate",
   "one name passed both gates - the mirror is not a mirror")

up_cont = {"feat": dict(below["feat"], cont_down=0, cont_up=4)}
ok(not F.passes_short(up_cont, {"min_cont": 3}),
   "a run of UP candles is not short continuation",
   "counted up-candles as continuation for a short")

# ---------- 4. ranking picks the weakest ----------
print("\n4. RANKING")
import rrg_strategy as S2

pts = [{"name": "STRONG", "abs_pct": 9.0, "distance": 5, "velocity": 1, "quadrant": "LAGGING",
        "prev_quadrant": "LAGGING", "abs_trend": -1, "close": 100, "symbol": "NSE:S-EQ",
        "x": 98.0, "y": 98.0, "heading": 200.0},
       {"name": "WEAK", "abs_pct": -9.0, "distance": 5, "velocity": 1, "quadrant": "LAGGING",
        "prev_quadrant": "LAGGING", "abs_trend": -1, "close": 100, "symbol": "NSE:W-EQ",
        "x": 96.0, "y": 96.0, "heading": 200.0}]
key = S2.rank_key("momentum_only", {})
picked = sorted(pts, key=key)[0]["name"]
ok(picked == "WEAK",
   "the short list starts with the weakest name",
   f"short list led with {picked} - that is the long ranking reused")

sel = S2.select(pts, "momentum_only", {}, max_pos=5)
ok("shorts" in sel, "select() returns a short book",
   "select() still hides the short book from the live path")
if sel.get("shorts"):
    ok(sel["shorts"][0]["name"] == "WEAK",
       "live short book is ranked weakest-first",
       f"live short book led with {sel['shorts'][0]['name']}")

# ---------- 5. the paper book marks a PUT the right way round ----------
print("\n5. PAPER BOOK  (a put gains when the stock FALLS)")
import paper as P

# Opened at the start of today's session, in the same timezone the book uses - a naive
# timestamp cannot be compared with an aware one, and the book is always aware.
P_OPENED = P.now().replace(hour=9, minute=30, second=0, microsecond=0).isoformat()


class _NoBroker:
    @staticmethod
    def buy(sym, qty, tag=""):
        return True, "ok"

    @staticmethod
    def sell(sym, qty, tag=""):
        return True, "ok"


sys.modules["broker"] = _NoBroker

pe = {"name": "DN", "symbol": "NSE:DN-EQ", "spot_in": 1000.0, "premium_in": 30.0,
      "type": "PE", "dir": -1, "qty": 1000, "lot": 1000,
      "stop": 1020.0, "t1": 970.0, "t2": 940.0,
      "high_water": 1000.0, "trail_dist": 20.0, "half_booked": False,
      "opened": P_OPENED}
ce = dict(pe, name="UP", type="CE", dir=1, stop=980.0, t1=1030.0, t2=1060.0)

ok(P.option_exit_premium(pe, 970.0) > pe["premium_in"],
   "put gains as the stock falls 1000 -> 970",
   f"put marked at {P.option_exit_premium(pe, 970.0)} on a 30-point fall - inverted")
ok(P.option_exit_premium(pe, 1030.0) < pe["premium_in"],
   "put loses as the stock rises", "put gained on a rise")
ok(P.option_exit_premium(ce, 1030.0) > ce["premium_in"],
   "call still gains as the stock rises", "call marking broke")

# a fresh put must not be stopped out on the tick it opens
bk = {"open": [dict(pe)], "closed": []}
P.mark(bk, {"NSE:DN-EQ": 1000.0}, 5)
ok(len(bk["open"]) == 1 and not bk["closed"],
   "put is not stopped out at its own entry price",
   "put stopped instantly - stop read with the long comparison")

# it stops when the stock RISES through the stop
bk = {"open": [dict(pe)], "closed": []}
P.mark(bk, {"NSE:DN-EQ": 1025.0}, 5)
ok(bk["closed"] and bk["closed"][0]["reason"] == "STOP",
   "put stops when the stock rises through 1020",
   f"expected STOP, got {[c.get('reason') for c in bk['closed']] or 'nothing'}")

# and targets when it falls
bk = {"open": [dict(pe)], "closed": []}
P.mark(bk, {"NSE:DN-EQ": 935.0}, 5)
ok(bk["closed"] and bk["closed"][0]["reason"] == "T2",
   "put hits T2 when the stock falls through 940",
   f"expected T2, got {[c.get('reason') for c in bk['closed']] or 'nothing'}")

# the trail must TIGHTEN (stop comes down) as the stock falls, never loosen
tr = dict(pe)
bk = {"open": [tr], "closed": []}
P.mark(bk, {"NSE:DN-EQ": 985.0}, 5)
ok(tr["stop"] < 1020.0,
   f"trail tightened the put's stop 1020 -> {tr['stop']}",
   f"put stop did not tighten on a favourable move: {tr['stop']}")
before = tr["stop"]
P.mark(bk, {"NSE:DN-EQ": 1005.0}, 5)
ok(tr["stop"] <= before,
   "and it never loosens when the stock comes back",
   f"put stop loosened {before} -> {tr['stop']}")

print("\n  " + ("ALL SHORT CHECKS PASS" if not fail else f"{fail} CHECK(S) FAILED") + "\n")
sys.exit(1 if fail else 0)
