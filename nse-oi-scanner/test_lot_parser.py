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
            }
            order = ["token", "desc", "instype", "lot", "tick", "isin",
                     "expiry", "ticker", "segment", "strike"]
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
