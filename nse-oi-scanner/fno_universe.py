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
import os, re, urllib.request

MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"
CACHE = "fno_symbols.txt"
INDICES = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "BANKEX", "SENSEX"}

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


def _extract_underlyings(csv_text):
    """Pull every stock underlying that has a FUT contract from the symbol master."""
    pat = re.compile(r"NSE:([A-Z0-9&\-]+?)\d{2}[A-Z]{3}FUT")
    found = set()
    for m in pat.finditer(csv_text):
        u = m.group(1)
        if u and u not in INDICES:
            found.add(u)
    return sorted(found)


def refresh(timeout=30):
    """Download the master and rewrite the cache. Returns the list of underlyings."""
    req = urllib.request.Request(MASTER_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = r.read().decode("utf-8", "ignore")
    names = _extract_underlyings(text)
    if names:
        with open(CACHE, "w") as f:
            f.write("\n".join(names))
    return names


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
    names, src = _underlyings()
    print(f"  F&O stock universe: {len(names)} names  (source: {src})")
    print("  " + ", ".join(names[:12]) + (" ..." if len(names) > 12 else ""))
    if src == "fallback":
        print("  (fallback list — run on a machine with internet to fetch the live set)")


if __name__ == "__main__":
    main()
