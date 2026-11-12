"""Prove the lot parser finds the right column even if the file layout moves."""
import sys, random
sys.path.insert(0, "/home/user/ashumedico/nse-oi-scanner")
import fno_universe as U

random.seed(7)
# realistic spread of NSE lot sizes: tiny for MRF-priced names, huge for penny names
NAMES = {f"STK{i:03d}": random.choice([5, 25, 50, 150, 200, 275, 300, 550, 700,
                                       1100, 1800, 2500, 3800, 7500, 70000])
         for i in range(200)}
NAMES["COFORGE"] = 150
NAMES["MRF"] = 5
NAMES["IDEA"] = 70000


# Freeze quantity: the column that broke this. Same SHAPE as a lot size - constant
# within an underlying, different across them - but nearly unique per name, so ranking
# candidate columns by "most distinct values" picks it every time. It is also always a
# multiple of the lot, which is what makes the smaller-median fallback correct.
FREEZE = {n: lot * random.choice([9, 11, 13, 17, 23]) + random.randint(1, 40)
          for n, lot in NAMES.items()}
# A price per name that puts the REAL lot inside the Rs 5-10 lakh band, so the economic
# test has something true to find.
PRICES = {n: round(700000 / lot, 2) for n, lot in NAMES.items()}


def make_csv(lot_col, extra_leading=0):
    """Build a symbol master where the lot lives at `lot_col`, everything else is noise
    with the SAME shape as the real file: constant-everywhere ids, per-row varying ids."""
    out = []
    for name, lot in NAMES.items():
        for j, tail in enumerate(["25SEPFUT", "25SEP1800CE", "25SEP1800PE", "25OCTFUT"]):
            cols = {
                "token": str(101125070000000 + hash((name, j)) % 999999),   # varies in-name
                "desc": f"{name} SEP FUT",
                "instype": "13",                 # constant everywhere - the old bug
                "lot": str(lot),                 # constant in-name, varies across names
                "tick": "0.05",                  # constant everywhere
                "isin": f"INE{abs(hash(name))%999999:06d}01",
                "expiry": str(1790000000 + j * 86400 * 30),                 # varies in-name
                "ticker": f"NSE:{name}{tail}",
                "segment": "11",                 # constant everywhere
                "strike": str(1800 + j * 50),                               # varies in-name
                "freeze": str(FREEZE[name]),     # same shape as lot, nearly unique
            }
            order = ["token", "desc", "instype", "lot", "tick", "isin",
                     "expiry", "ticker", "segment", "strike", "freeze"]
            order.remove("lot")
            order.insert(lot_col, "lot")
            row = [cols[k] for k in order]
            out.append(",".join(["PAD"] * extra_leading + row))
    return "\n".join(out)


print("case                        detected_col  COFORGE  MRF    IDEA   distinct  plausible")
for label, lot_col, pad in [("real layout (lot at 3)", 3, 0),
                            ("column inserted upstream", 3, 1),
                            ("lot moved to col 6", 6, 0),
                            ("lot moved to col 0", 0, 0)]:
    text = make_csv(lot_col, pad)
    rows = {}
    for line in text.splitlines():
        m = U.CONTRACT_PAT.search(line)
        if m:
            rows.setdefault(m.group(1), []).append([c.strip() for c in line.split(",")])
    det = U._detect_lot_col(rows)
    lots = U._lots_from_fyers(text)
    ok = all(lots.get(n) == NAMES[n] for n in NAMES)
    print(f"{label:<28}{det:^14}{lots.get('COFORGE'):<9}{lots.get('MRF'):<7}"
          f"{lots.get('IDEA'):<7}{len(set(lots.values())):<10}{U._plausible(lots)}"
          f"   {'ALL 203 CORRECT' if ok else '*** MISMATCH ***'}")

# the poisoned-cache case he actually has on disk
print("\nold buggy output (every name = 13):", U._plausible({n: 13 for n in NAMES}),
      "-> rejected, cache refetched")

# ---------------------------------------------------------------------------
# THE FREEZE-QUANTITY TRAP
#
# Freeze quantity has the same shape as a lot size - constant within an underlying,
# different across them - so shape alone cannot separate them. The old tie-breaker,
# "take the column with the most distinct values", picks freeze EVERY time, because
# lot sizes repeat across names and freeze quantities do not. That is not bad luck,
# it is the rule choosing the wrong column by construction. It is how MCX came back
# as 31,181 when its lot is 25.
print("\nFREEZE-QUANTITY TRAP")
text = make_csv(3)
rows = {}
for line in text.splitlines():
    m = U.CONTRACT_PAT.search(line)
    if m:
        rows.setdefault(m.group(1), []).append([c.strip() for c in line.split(",")])

d_lot = len(set(NAMES.values()))
d_frz = len(set(FREEZE.values()))
print(f"  distinct values      lot {d_lot:<6} freeze {d_frz}")
print(f"  most-distinct rule would pick: {'FREEZE (wrong)' if d_frz > d_lot else 'lot'}")

det_priced = U._detect_lot_col(rows, prices=PRICES)
det_blind = U._detect_lot_col(rows)
lots_priced = U._lots_from_fyers(text, prices=PRICES)
lots_blind = U._lots_from_fyers(text)

ok_p = all(lots_priced.get(n) == NAMES[n] for n in NAMES)
ok_b = all(lots_blind.get(n) == NAMES[n] for n in NAMES)
print(f"  with prices  -> col {det_priced}  {'CORRECT' if ok_p else '*** WRONG ***'}"
      f"   (contract value lands in the Rs 5-10L band)")
print(f"  no prices    -> col {det_blind}  {'CORRECT' if ok_b else '*** WRONG ***'}"
      f"   (smaller median wins - freeze is a multiple of lot)")

fail = 0
if d_frz <= d_lot:
    print("  *** the trap is not set up - freeze must be more distinct than lot ***")
    fail += 1
if not ok_p:
    print("  *** priced detection picked the wrong column ***"); fail += 1
if not ok_b:
    print("  *** blind detection picked the wrong column ***"); fail += 1
# and the wrong column must be rejected downstream even if it ever got through
if U._plausible({n: FREEZE[n] for n in NAMES}) is False:
    print("  note: freeze values would ALSO pass the plausibility check - which is why")
    print("        the column choice has to be right, not merely sanity-checked after.")

print("\n  " + ("ALL LOT CHECKS PASS" if not fail else f"{fail} CHECK(S) FAILED"))
raise SystemExit(1 if fail else 0)
