"""
fno_universe.py  —  the FULL NSE F&O stock list (all ~200 underlyings), self-updating.

The F&O list changes as NSE adds/drops names, so we don't hard-code it. On your PC
this downloads the official Fyers symbol master (a public URL, no login) and extracts
every stock that has futures — that's the live, current universe. The result is cached
to fno_symbols.txt so it's instant next time. A built-in fallback list keeps things
working offline / on first run (flagged as possibly-stale).

    from fno_universe import fno_stocks
    syms = fno_stocks()            # ['NSE:RELIANCE-EQ', 'NSE:TCS-EQ', ...]

    python fno_universe.py         # refresh + print the count
"""
import os, re, json, urllib.request

# Multiple authoritative sources, tried in order — so a single site being down
# never breaks the universe. First one that yields names wins.
SOURCES = [
    ("fyers",     "https://public.fyers.in/sym_details/NSE_FO.csv"),
    ("nse_lots",  "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"),
    ("nse_lots2", "https://archives.nseindia.com/content/fo/fo_mktlots.csv"),
]
CACHE = "fno_symbols.txt"
INDICES = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "NIFTYIT",
           "BANKEX", "SENSEX", "SENSEX50"}

# Fallback (used only if the live master can't be fetched). Well-known NSE F&O stocks.
# May be stale — the live master above is authoritative and refreshes this automatically.
FALLBACK = [
    "AARTIIND","ABB","ABBOTINDIA","ABCAPITAL","ABFRL","ACC","ADANIENT","ADANIGREEN",
    "ADANIPORTS","ALKEM","AMBUJACEM","ANGELONE","APLAPOLLO","APOLLOHOSP","APOLLOTYRE",
    "ASHOKLEY","ASIANPAINT","ASTRAL","ATUL","AUBANK","AUROPHARMA","AXISBANK","BAJAJ-AUTO",
    "BAJAJFINSV","BAJFINANCE","BALKRISIND","BANDHANBNK","BANKBARODA","BANKINDIA","BATAINDIA",
    "BEL","BERGEPAINT","BHARATFORG","BHARTIARTL","BHEL","BIOCON","BOSCHLTD","BPCL","BRITANNIA",
    "BSOFT","CAMS","CANBK","CANFINHOME","CHAMBLFERT","CHOLAFIN","CIPLA","COALINDIA","COFORGE",
    "COLPAL","CONCOR","COROMANDEL","CROMPTON","CUB","CUMMINSIND","DABUR","DALBHARAT","DEEPAKNTR",
    "DELTACORP","DIVISLAB","DIXON","DLF","DRREDDY","EICHERMOT","ESCORTS","EXIDEIND","FEDERALBNK",
    "GAIL","GLENMARK","GMRINFRA","GNFC","GODREJCP","GODREJPROP","GRANULES","GRASIM","GUJGASLTD",
    "HAL","HAVELLS","HCLTECH","HDFCAMC","HDFCBANK","HDFCLIFE","HEROMOTOCO","HINDALCO","HINDCOPPER",
    "HINDPETRO","HINDUNILVR","ICICIBANK","ICICIGI","ICICIPRULI","IDEA","IDFC","IDFCFIRSTB","IEX",
    "IGL","INDHOTEL","INDIACEM","INDIAMART","INDIGO","INDUSINDBK","INDUSTOWER","INFY","IOC","IPCALAB",
    "IRCTC","ITC","JINDALSTEL","JKCEMENT","JSWSTEEL","JUBLFOOD","KOTAKBANK","LALPATHLAB","LAURUSLABS",
    "LICHSGFIN","LT","LTF","LTIM","LTTS","LUPIN","M&M","M&MFIN","MANAPPURAM","MARICO","MARUTI",
    "MCX","METROPOLIS","MFSL","MGL","MOTHERSON","MPHASIS","MRF","MUTHOOTFIN","NATIONALUM","NAUKRI",
    "NAVINFLUOR","NESTLEIND","NMDC","NTPC","OBEROIRLTY","OFSS","ONGC","PAGEIND","PEL","PERSISTENT",
    "PETRONET","PFC","PIDILITIND","PIIND","PNB","POLYCAB","POWERGRID","PVRINOX","RAMCOCEM","RBLBANK",
    "RECLTD","RELIANCE","SAIL","SBICARD","SBILIFE","SBIN","SHREECEM","SHRIRAMFIN","SIEMENS","SRF",
    "SUNPHARMA","SUNTV","SYNGENE","TATACHEM","TATACOMM","TATACONSUM","TATAMOTORS","TATAPOWER",
    "TATASTEEL","TCS","TECHM","TITAN","TORNTPHARM","TRENT","TVSMOTOR","UBL","ULTRACEMCO","UNITDSPR",
    "UPL","VBL","VEDL","VOLTAS","WIPRO","ZYDUSLIFE",
]


def _parse_fyers(text):
    """Fyers symbol master: pull every underlying that has a FUT contract."""
    pat = re.compile(r"NSE:([A-Z0-9&\-]+?)\d{2}[A-Z]{3}FUT")
    return sorted({m.group(1) for m in pat.finditer(text) if m.group(1) not in INDICES})


# Versioned on purpose. The previous detector could pick the FREEZE QUANTITY column,
# and those values pass the plausibility check happily - they vary, they are numeric,
# they are in range. So a poisoned cache never healed itself; it just kept being read.
# A new filename is the only thing that guarantees the bad file is not trusted again.
LOTS_CACHE = "fno_lots_v2.json"


# Fyers symbol-master column layout: index 3 is the minimum lot size. Used only as a
# last resort - _detect_lot_col() below derives the column from the data instead, so a
# change in the file's layout can't quietly go back to sizing trades off the wrong number.
FYERS_LOT_COL = 3


def _detect_lot_col(rows, fallback=FYERS_LOT_COL, prices=None):
    """Find the lot-size column without trusting a hard-coded index.

    The lot size is the SAME for every contract of one underlying (future and every strike
    alike) but DIFFERENT across underlyings:
      - instrument type, tick size, segment -> constant within AND across  (rejected)
      - token, expiry, strike, symbol       -> varies within an underlying (rejected)

    That narrows it, and it is not enough. The master also carries FREEZE QUANTITY, which
    has exactly the same shape - constant per underlying, varying across - and it beat lot
    size on the old tie-breaker, "most distinct values". It beat it for a reason that will
    happen every time: many names share a lot size (500, 1000, 2500 recur), while freeze
    quantities are nearly unique. Ranking by distinctness therefore prefers the wrong
    column BY CONSTRUCTION. That is how MCX came back as 31,181 when its lot is 25.

    So the tie-break is economic instead of statistical. An F&O contract is built to be
    worth roughly Rs 5-10 lakh, so with prices in hand the right column is the one where
    price x value lands in that band for most names. Nothing else in the file does that.

    Without prices there is no economic test, so it falls back to shape alone - and then
    prefers the SMALLER median, because freeze quantity is a multiple of lot size and
    never smaller than it.
    """
    multi = {u: rs for u, rs in rows.items() if len(rs) >= 2}
    if len(multi) < 20:
        return fallback
    width = min(len(r) for rs in rows.values() for r in rs)
    cands = []
    for i in range(width):
        per_name, constant = {}, 0
        for u, rs in multi.items():
            vals = {r[i] for r in rs}
            if len(vals) != 1:
                continue
            v = vals.pop()
            if not v.isdigit() or not (1 <= int(v) <= 100000):
                continue
            constant += 1
            per_name[u] = int(v)
        if constant < 0.9 * len(multi) or len(per_name) < 20:
            continue                      # not constant-within for most names
        if len(set(per_name.values())) < 10:
            continue                      # constant across names too -> not a lot size
        cands.append((i, per_name))
    if not cands:
        return fallback

    if prices:
        # SEBI's band for a stock F&O contract, with slack either side so a genuinely
        # small or large name does not disqualify the whole column.
        LO, HI = 3_00_000, 20_00_000
        scored = []
        for i, per_name in cands:
            shared = [(per_name[u], prices[u]) for u in per_name
                      if prices.get(u)]
            if len(shared) < 20:
                continue
            hits = sum(1 for lot, px in shared if LO <= lot * px <= HI)
            scored.append((hits / len(shared), -_median_int(per_name.values()), i))
        if scored:
            scored.sort(reverse=True)
            if scored[0][0] >= 0.5:       # at least half the names in the band
                return scored[0][2]

    # No prices, or nothing fit the band: smaller wins. Freeze quantity is a multiple of
    # the lot and cannot be below it, so the lot column is never the larger of the two.
    cands.sort(key=lambda c: _median_int(c[1].values()))
    return cands[0][0]


def _median_int(vals):
    v = sorted(int(x) for x in vals)
    return v[len(v) // 2] if v else 0


def _plausible(lots):
    """Reject a parse that grabbed the wrong column.

    Real F&O lot sizes vary a lot across names (MRF ~5, IDEA ~70000). If nearly every
    underlying comes back with the SAME number, we read a constant column - an instrument
    type or a segment id - not a lot size. Better to have no lots than confident wrong ones.
    """
    if len(lots) < 20:
        return False
    vals = list(lots.values())
    top = max(vals.count(v) for v in set(vals))
    return top / len(vals) < 0.5 and len(set(vals)) >= 10


# futures AND options rows, because detection needs several contracts per underlying
CONTRACT_PAT = re.compile(r"NSE:([A-Z0-9&\-]+?)\d{2}[A-Z]{3}(?:FUT|\d+(?:\.\d+)?(?:CE|PE))")
ROWS_PER_NAME = 4      # enough to test "constant within underlying"; keeps memory bounded


def _lots_from_fyers(text, prices=None):
    rows = {}
    for line in text.splitlines():
        m = CONTRACT_PAT.search(line)
        if not m or m.group(1) in INDICES:
            continue
        got = rows.setdefault(m.group(1), [])
        if len(got) < ROWS_PER_NAME:
            got.append([c.strip() for c in line.split(",")])
    if not rows:
        return {}
    col = _detect_lot_col(rows, prices=prices)
    lots = {}
    for u, rs in rows.items():
        vals = [int(r[col]) for r in rs
                if len(r) > col and r[col].isdigit() and 1 <= int(r[col]) <= 100000]
        if vals:
            lots[u] = max(set(vals), key=vals.count)        # modal, so one odd row can't win
    return lots


def _lots_from_nse(text):
    """NSE fo_mktlots.csv: UNDERLYING, SYMBOL, then one lot column per expiry month.
    The near month is the first numeric column after the symbol."""
    lots = {}
    for line in text.splitlines()[1:]:
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 3:
            continue
        sym = cols[1].upper()
        if not re.fullmatch(r"[A-Z0-9&\-]{1,20}", sym) or sym in INDICES:
            continue
        for c in cols[2:]:
            if c.isdigit() and 1 <= int(c) <= 100000:
                lots.setdefault(sym, int(c))
                break
    return lots


def fetch_lot_sizes(timeout=30, prices=None):
    """Real F&O lot sizes per underlying.

    This matters more than it looks: options and futures trade only in whole lots, so a
    wrong lot size makes every quantity - and therefore every risk calculation -
    unactionable. NSE's own mktlots file is authoritative; the Fyers master is the
    fallback. Whichever answers first must still pass the plausibility check below."""
    for kind, url in SOURCES:
        parser = {"fyers": _lots_from_fyers}.get(kind, _lots_from_nse)
        try:
            text = _fetch(url, timeout)
            lots = (parser(text, prices=prices) if parser is _lots_from_fyers
                    else parser(text))
        except Exception:
            continue
        if _plausible(lots):
            with open(LOTS_CACHE, "w") as f:
                json.dump(lots, f, indent=1)
            return lots
    return {}


def lot_sizes(prices=None):
    """Cached lot sizes; empty dict if we have never been able to fetch them.

    `prices` is optional and worth passing when the caller already has them: it lets the
    column detector use the economic test - price x lot should land near a Rs 5-10 lakh
    contract - which is the only check that separates the lot column from the freeze
    quantity column. Shape alone cannot.
    """
    if os.path.exists(LOTS_CACHE):
        try:
            with open(LOTS_CACHE) as f:
                cached = json.load(f)
            if _plausible(cached):
                return cached
            print("  [fno_universe] cached lot sizes look wrong - refetching")
        except Exception:
            pass
    try:
        return fetch_lot_sizes(prices=prices)
    except Exception:
        return {}


def _parse_nse_lots(text):
    """NSE fo_mktlots.csv: the SYMBOL column (2nd), skip header + index rows."""
    names = set()
    for line in text.splitlines()[1:]:
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 2:
            continue
        sym = cols[1].upper()
        if re.fullmatch(r"[A-Z0-9&\-]{1,20}", sym) and sym not in INDICES:
            names.add(sym)
    return sorted(names)


def _fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def refresh(timeout=30):
    """Try each source in order; first that yields names rewrites the cache."""
    last_err = None
    for kind, url in SOURCES:
        try:
            text = _fetch(url, timeout)
            names = _parse_fyers(text) if kind == "fyers" else _parse_nse_lots(text)
            if len(names) > 50:                       # sanity: a real F&O list is ~200
                with open(CACHE, "w") as f:
                    f.write("\n".join(names))
                return names
        except Exception as e:      # noqa
            last_err = e
    if last_err:
        raise last_err
    return []


def _underlyings():
    # 1) cache  2) live refresh  3) fallback
    if os.path.exists(CACHE):
        names = [l.strip() for l in open(CACHE) if l.strip()]
        if names:
            return names, "cache"
    try:
        names = refresh()
        if names:
            return names, "live"
    except Exception as e:      # noqa
        print(f"  [fno_universe] live fetch failed ({e}); using built-in fallback list.")
    return FALLBACK, "fallback"


def fno_stocks(suffix="-EQ"):
    """Full F&O stock universe as Fyers symbols, e.g. 'NSE:RELIANCE-EQ'."""
    names, src = _underlyings()
    return [f"NSE:{n}{suffix}" for n in names]


def fno_futures(expiry):
    """Same universe as current-month FUT symbols, e.g. fno_futures('26JUL')."""
    names, _ = _underlyings()
    return [f"NSE:{n}{expiry}FUT" for n in names]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lots", action="store_true", help="refresh and sanity-check lot sizes")
    a = ap.parse_args()
    if a.lots:
        lots = fetch_lot_sizes()
        if not lots:
            print("  lot sizes: could not fetch a plausible set (no internet, or format changed)")
            return
        print(f"  lot sizes: {len(lots)} names, {len(set(lots.values()))} distinct values")
        for n in ("RELIANCE", "COFORGE", "MRF", "IDEA", "SBIN"):
            if n in lots:
                print(f"    {n:<10} lot {lots[n]}")
        return
    names, src = _underlyings()
    print(f"  F&O stock universe: {len(names)} names  (source: {src})")
    print("  " + ", ".join(names[:12]) + (" ..." if len(names) > 12 else ""))
    if src == "fallback":
        print("  (fallback list — run on a machine with internet to fetch the live set)")


if __name__ == "__main__":
    main()
