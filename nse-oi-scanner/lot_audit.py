"""
lot_audit.py  —  run the COFORGE check on EVERY F&O name, not just the one on the ticket.

One wrong lot size was caught because it happened to land on a live ticket. That is luck,
not a process. The same wrong-column / stale-after-split failure is sitting silently on
every other underlying until the day one of them is the trade.

So: check all of them at once. For each F&O name we know the lot and the live price, and
an NSE F&O contract is deliberately sized to roughly Rs 5-15 lakh of underlying. Multiply
and the wrong ones fall out immediately - no guessing, no memory of column layouts.

    python lot_audit.py             # audit every name against live prices
    python lot_audit.py --repair    # then ask the option chain for the flagged ones and fix
    python lot_audit.py --demo      # synthetic prices, to see what it does

A repair only ever writes a lot that came from the live option chain - the exchange's own
number. Nothing is guessed: a name we cannot verify stays flagged, not silently "fixed".

NOT financial advice.
"""
import os, sys, json, time, argparse

# NSE sizes every F&O contract into the same regulatory band, so contract values across
# the universe cluster tightly. That cluster is the yardstick - not a number typed in
# here, which would go stale the next time the exchange revises the band. We only
# hard-code the one bound that is a fact of arithmetic rather than of regulation:
# nothing worth a few thousand rupees is a real derivatives contract.
FLOOR = 200000
LOW_MULT, HIGH_MULT = 0.4, 4.0        # of the universe median
LOTS_CACHE = "fno_lots.json"


def band_verdict(value, median):
    """A lot is judged against what every other lot in the same universe looks like.

    A stale pre-split lot reads ~5x too small, a stale post-split one ~5x too big; both
    stand out against the cluster even though neither is absurd on its own. Bounds are
    deliberately wide - a stock that ran hard since its last lot revision is legitimately
    off-centre, and this only flags for verification, it never rewrites anything by itself.
    """
    if value < FLOOR:
        return "TOO SMALL"
    if not median:
        return "ok"
    if value < LOW_MULT * median:
        return "TOO SMALL"
    if value > HIGH_MULT * median:
        return "TOO BIG"
    return "ok"


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


def audit(prices, lots):
    """prices/lots keyed by underlying name. Returns (rows, flagged, median)."""
    rows = []
    for name, lot in sorted(lots.items()):
        px = prices.get(name)
        value = px * lot if px else None
        rows.append({"name": name, "lot": lot, "price": px, "value": value,
                     "verdict": "no price" if not px else None})
    # median over priced names first, then judge each against it
    median = _median([r["value"] for r in rows if r["value"]])
    for r in rows:
        if r["value"]:
            r["verdict"] = band_verdict(r["value"], median)
    flagged = [r for r in rows if r["verdict"] in ("TOO SMALL", "TOO BIG")]
    return rows, flagged, median


def repair(flagged, median, sleep=0.4):
    """Ask the live option chain for the exchange's own lot on the flagged names only.

    Chain-first is the whole point: it is the same source the order window uses, so it
    survives splits and column changes. Names the chain cannot answer stay flagged."""
    import option_chain as oc
    fixed, still = {}, []
    for r in flagged:
        sym = f"NSE:{r['name']}-EQ"
        try:
            oc.fetch_live(sym)
            lot = oc.LAST_LOT
        except Exception as e:      # noqa
            lot = None
        if lot and band_verdict(r["price"] * lot, median) == "ok":
            fixed[r["name"]] = int(lot)
            print(f"    {r['name']:<12} {r['lot']:>7} -> {lot:<7} "
                  f"(contract Rs {r['price']*lot:,.0f})")
        else:
            still.append(r["name"])
            print(f"    {r['name']:<12} {r['lot']:>7}    chain could not confirm - still flagged")
        time.sleep(sleep)
    return fixed, still


def _demo():
    """Synthetic universe carrying the exact failure modes seen in the wild."""
    import random
    random.seed(11)
    real = {}
    for i in range(180):
        px = round(random.uniform(90, 4000), 2)
        lot = max(1, int(round(700000 / px / 5) * 5))          # a sane ~Rs 7L contract
        real[f"STK{i:03d}"] = (px, lot)
    real["COFORGE"] = (1747.0, 375)
    prices = {k: v[0] for k, v in real.items()}
    lots = {k: v[1] for k, v in real.items()}
    lots["COFORGE"] = 13                     # wrong column, the original bug
    lots["STK004"] = lots["STK004"] // 5     # stale pre-split lot
    lots["STK009"] = lots["STK009"] * 5      # stale post-split lot the other way
    return prices, lots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repair", action="store_true",
                    help="ask the option chain for flagged names and write the fix")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        prices, lots = _demo()
    else:
        from fno_universe import lot_sizes, _underlyings
        import rrg_engine as E
        lots = lot_sizes()
        if not lots:
            print("  No lot sizes on disk and none could be fetched.")
            print("  Run:  python fno_universe.py --lots")
            return
        names, _src = _underlyings()
        print(f"  {len(names)} F&O names - pulling live prices...")
        q = E.live_quote([f"NSE:{n}-EQ" for n in names])
        prices = {k.split(":")[1].replace("-EQ", ""): v for k, v in q.items()}
        if not prices:
            print("  No live prices (market closed / token expired?).")
            print("  Run:  python fyers_auth.py    then try again in market hours.")
            return

    rows, flagged, med = audit(prices, lots)
    priced = [r for r in rows if r["value"]]
    print(f"\n  LOT AUDIT   {len(rows)} names   {len(priced)} priced   "
          f"{len(rows) - len(priced)} without price")
    print("  " + "-" * 62)
    if priced:
        print(f"  median contract value  Rs {med:,.0f}"
              f"   (accepted Rs {max(FLOOR, LOW_MULT*med):,.0f} - Rs {HIGH_MULT*med:,.0f})")
    if not flagged:
        print(f"  every priced lot lands inside the band - nothing to fix\n")
    else:
        print(f"  {len(flagged)} SUSPECT:\n")
        print(f"    {'NAME':<12}{'LOT':>8}{'PRICE':>10}{'CONTRACT':>14}   WHY")
        for r in flagged:
            print(f"    {r['name']:<12}{r['lot']:>8}{r['price']:>10,.1f}"
                  f"{r['value']:>14,.0f}   {r['verdict']}")
        print()

    with open("lot_audit.txt", "w") as f:
        for r in rows:
            f.write(f"{r['name']},{r['lot']},{r['price']},{r['value']},{r['verdict']}\n")
    print(f"  full table -> lot_audit.txt")

    if a.repair and flagged:
        if a.demo:
            print("\n  (--repair needs the live chain; not available in --demo)\n")
            return
        print(f"\n  REPAIR: asking the option chain for {len(flagged)} names")
        fixed, still = repair(flagged, med)
        if fixed:
            lots.update(fixed)
            with open(LOTS_CACHE, "w") as f:
                json.dump(lots, f, indent=1)
            print(f"\n  {len(fixed)} lots corrected from the exchange chain -> {LOTS_CACHE}")
        if still:
            print(f"  {len(still)} still unverified: {', '.join(still)}")
            print("  These stay flagged on purpose - a guessed lot is worse than a known gap.")
    elif flagged:
        print("  Fix them with:  python lot_audit.py --repair\n")


if __name__ == "__main__":
    main()
