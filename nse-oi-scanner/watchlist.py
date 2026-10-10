"""
watchlist.py  —  a fundamental watchlist, checked against what can actually be traded.

The Q1 FY27 list is a *cash-equity* idea sheet: sector, the trigger, the guidance. Useful,
and none of it is an options signal. Two things stand between that list and this system:

1. **Options exist only on F&O names.** Most small caps are not in F&O at all. A brilliant
   thesis on a name with no option chain is a cash trade or nothing - and being told that
   plainly beats discovering it at the order window.
2. **A fundamental trigger does not time a 15-minute expansion bar.** Q1 guidance says who
   is worth owning over quarters. It says nothing about whether this candle is the one.

So this file does the one honest job available: it resolves each name against the **live
F&O symbol master** and reports which of them options can even be bought on. What survives
can narrow the universe - a bias, tagged and displayed, never a trigger.

NOTHING HERE IS BACKTESTED, AND IT CANNOT BE. Point-in-time fundamentals for these names do
not exist anywhere in this system, so a walk-forward on "trade only watchlist names" cannot
be run. That puts it in the same category as OI buildup: **NOT TESTED** - which is not
'passed' and not 'failed', and must never be reported as either. Use it to look, not to
size.

    python watchlist.py                 # which of these can be traded as options
    python watchlist.py --all           # the whole sheet, F&O or not
    python watchlist.py --json          # machine-readable, for the desk

Source: a public Q1 FY27 idea sheet Aashish was sent. "No buy/sell recommendations, do
your own diligence. These are just ideas." Not financial advice - that carries over intact.
"""
import json
import re
import sys

# (name as written on the sheet, sector, key trigger, guidance)
SHEET = [
    ("AU Small",              "Pvt Banks",       "microfinance + universal",        "2-2.5x of GDP, 1.7+ RoA"),
    ("Suryoday Small Fin Bk", "Pvt Banks",       "microfinance revival",            "30-35, 1.4+ RoA"),
    ("RBL Bank",              "Pvt Banks",       "new capital infusion",            "20%, RoA > 1"),
    ("SG Finserv",            "NBFC",            "0 NPA, supply chain finance",     "35+"),
    ("Poonawalla",            "NBFC",            "diversified, strong distribution", "45-40 AUM"),
    ("Onemi Tech (Kissht)",   "NBFC",            "tech led, digital persona",       "40, NPA < 2.25"),
    ("Bank of Maharashtra",   "PSU Bank",        "gold loan, consistent performer", ""),
    ("Cupid",                 "FMCG",            "contraceptive leader",            "90+"),
    ("V2 Retail",             "Retail",          "fastest retail player",           "50+"),
    ("Aeroflex",              "Pipes",           "AI proxy, cooling kits",          "35+"),
    ("Lloyd Metals",          "Metals & Mining", "copper",                          "25+ (volume)"),
    ("Sedemac",               "Auto Anc",        "ICE + EV, 3x capex",              ""),
    ("M&M",                   "Auto 4W",         "diversified platform",            ""),
    ("Ather Energy",          "Auto 2W",         "fast growing EV 2W",              ""),
    ("Krishana Phoschem",     "Fertilizer",      "capex done, top class execution", "30-35"),
    ("MBAPL",                 "Fertilizer",      "capex to track",                  "50"),
    ("ICICI Pru AMC",         "Asset Mgmt",      "2nd player, solid execution",     ""),
    ("Anand Rathi Wealth",    "Wealth Mgmt",     "top class execution",             "20-25"),
    ("NUVOCO",                "Cement",          "capex ahead of schedule",         "~20"),
    ("Emmvee",                "Solar Cell",      "strong execution",                "2400cr EBITDA"),
    ("Groww",                 "Wealth Platform", "market leader",                   ""),
    ("Manakcoat",             "Metals",          "coated and value addition",       "3x in 3 years"),
    ("TATVA",                 "Chemicals",       "2nd largest SDA mfg",             "25-30%"),
    ("Menon Brg",             "Industrials",     "precision bearing",               "20%"),
    ("Steel Strip Wheels",    "Auto Anc",        "export recovery",                 "20"),
    ("E2E Networks",          "GPU Renting",     "massive turnaround, GPU prices",  ""),
    ("TVS Motor",             "Auto 2W",         "market leader",                   ""),
    ("Atlanta Electricals",   "Transformers",    "EHV transition",                  "40% for 3 yrs, 17% EBITDA"),
    ("HFCL",                  "Optical Fibre",   "AI data centre",                  "40"),
    ("Nam India (Nippon AMC)", "Asset Mgmt",     "fastest growing",                 ""),
    ("Ujjivan SFB",           "Micro Finance",   "strong momentum",                 "25+, 1.8-2.0 RoA"),
    ("FCL",                   "Chemicals",       "crude chem play",                 "40+"),
    ("RK Forge",              "Forging",         "capex phase ends",                ""),
    ("Sterlite Tech",         "Optical Fibre",   "AI data centre",                  ""),
    ("Acutaas",               "Chemicals/Pharma", "speciality chem battery",        "25"),
    ("Senores",               "Pharma",          "CDMO, regulated, branded",        "30-40, 2500-3000 in 3-4 yrs"),
    ("KFin Tech",             "Platform Cap Mkts", "",                              "18-20, 40-45 EBITDA"),
    ("RR Kabel",              "Wires & Cables",  "market share gains",              "18% vol growth, 10.5 EBITDA"),
    ("Rossell Techsys",       "Aerospace",       "semicon biz",                     "80+"),
]


# The company's NSE ticker, where the ticker is a settled fact. This map answers ONLY
# "what is this company called on the exchange" - it never asserts F&O membership. That
# question is answered by the downloaded symbol master, every time, because the F&O list
# is revised twice a year and a hardcoded answer would go stale silently.
#
# Fuzzy matching was tried first and had to go. It missed AUBANK entirely (nothing in
# "AU Small" is long enough to match on) and paired "ICICI Pru AMC" with ICICIPRULI - the
# life insurer, a different company. A near-miss here is not a bad row on a screen; it is
# an order in the wrong stock.
ALIAS = {
    "AU Small":              "AUBANK",
    "RBL Bank":              "RBLBANK",
    "M&M":                   "M&M",
    "TVS Motor":             "TVSMOTOR",
    "Bank of Maharashtra":   "MAHABANK",
    "Poonawalla":            "POONAWALLA",
    "HFCL":                  "HFCL",
    "Ujjivan SFB":           "UJJIVANSFB",
    "Sterlite Tech":         "STLTECH",
    "NUVOCO":                "NUVOCO",
    "KFin Tech":             "KFINTECH",
    "RR Kabel":              "RRKABEL",
    "Anand Rathi Wealth":    "ANANDRATHI",
    "V2 Retail":             "V2RETAIL",
    "Suryoday Small Fin Bk": "SURYODAY",
    "Cupid":                 "CUPID",
    "Aeroflex":              "AEROFLEX",
    "RK Forge":              "RKFORGE",
    "Krishana Phoschem":     "KRISHANA",
    "Lloyd Metals":          "LLOYDSME",
    "Steel Strip Wheels":    "SSWL",
    "Nam India (Nippon AMC)": "NAM-INDIA",
    "E2E Networks":          "E2E",
    "TATVA":                 "TATVA",
}

# Names where the ticker itself is not something to state from memory - recent listings,
# renames and SME counters. Reported as unknown rather than guessed, because "confirm this
# on NSE" costs thirty seconds and a wrong ticker costs a position.
UNKNOWN_TICKER = {
    "SG Finserv", "Onemi Tech (Kissht)", "Sedemac", "Ather Energy", "MBAPL",
    "ICICI Pru AMC", "Emmvee", "Groww", "Manakcoat", "Menon Brg",
    "Atlanta Electricals", "FCL", "Acutaas", "Senores", "Rossell Techsys",
}


def _norm(s):
    """Strip everything a human adds and an exchange does not use."""
    s = re.sub(r"\(.*?\)", " ", s or "")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def resolve(universe=None):
    """For each sheet name: its ticker (if settled), and whether F&O carries it.

    Membership always comes from the master, never from this file.
    """
    stale = False
    if universe is None:
        import fno_universe as U
        try:
            universe = U.fno_stocks()
        except Exception:
            universe = list(U.FALLBACK)
        # fno_stocks() falls back silently on a failed fetch. Silently is the problem: the
        # built-in list is a snapshot, the F&O list is revised twice a year, and "not in
        # F&O" read off a stale snapshot is a wrong answer delivered confidently.
        def _bare(xs):
            return {str(x).split(":")[-1].replace("-EQ", "").upper() for x in xs}
        stale = _bare(universe) == _bare(U.FALLBACK)
    uni = {str(u).split(":")[-1].replace("-EQ", "").upper() for u in universe}
    unorm = {_norm(u): u for u in uni}

    out = []
    for name, sector, trigger, guidance in SHEET:
        sym = ALIAS.get(name)
        if not sym and name not in UNKNOWN_TICKER:
            sym = unorm.get(_norm(name))          # the sheet already wrote the ticker
        if sym:
            real = unorm.get(_norm(sym))
            out.append({"name": name, "sector": sector, "trigger": trigger,
                        "guidance": guidance, "symbol": real or sym,
                        "fno": bool(real), "ticker_known": True})
        else:
            out.append({"name": name, "sector": sector, "trigger": trigger,
                        "guidance": guidance, "symbol": None,
                        "fno": False, "ticker_known": False})
    if stale:
        for r in out:
            r["stale_universe"] = True
    return out


def tradeable_names(universe=None):
    """Just the F&O-eligible symbols, for narrowing a scan."""
    return [r["symbol"] for r in resolve(universe) if r["fno"]]


def main(argv):
    show_all = "--all" in argv
    rows = resolve()
    if "--json" in argv:
        print(json.dumps(rows, indent=1))
        return 0

    G, R, Y, D, X = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"
    hits = [r for r in rows if r["fno"]]
    unknown = [r for r in rows if not r["ticker_known"]]
    print(f"\n  Q1 FY27 WATCHLIST  ->  kya options mein trade ho sakta hai")
    print("  " + "=" * 76)
    print(f"  {'NAAM':<24}{'SECTOR':<18}{'F&O':<14}TRIGGER")
    print("  " + "-" * 76)
    for r in rows:
        if not show_all and not r["fno"]:
            continue
        if r["fno"]:
            mark, plain = f"{G}{r['symbol']}{X}", r["symbol"]
        elif not r["ticker_known"]:
            mark, plain = f"{Y}ticker?{X}", "ticker?"
        else:
            mark, plain = f"{R}nahi{X}", "nahi"
        pad = 14 + (len(mark) - len(plain))
        print(f"  {r['name'][:23]:<24}{r['sector'][:17]:<18}{mark:<{pad}}"
              f"{D}{r['trigger'][:28]}{X}")
    print("  " + "-" * 76)
    print(f"  {len(hits)} / {len(rows)} naam F&O mein hain - baaki pe option hi nahi milta.")
    if unknown:
        print(f"  {Y}ticker?{X} = {len(unknown)} naam aise hain jinka NSE symbol main "
              f"yaad se nahi bolunga (nayi listing / rename / SME).")
        print(f"           NSE pe symbol dekh kar bata de, main map mein daal dunga.")
    if any(r.get("stale_universe") for r in rows):
        print(f"  {Y}!!{X} F&O list live nahi aayi - built-in fallback use hui, jo "
              f"puraani ho sakti hai.")
        print(f"     Token ke saath dobara chala ({D}1 - START DAY{X}) toh gin-ti badal "
              f"sakti hai.")
    print(f"\n  {D}Ye ek BIAS hai, signal nahi. Fundamental trigger 15-min candle ko "
          f"time nahi karta.{X}")
    print(f"  {D}NOT TESTED - point-in-time fundamentals nahi hain, toh isko walk-forward "
          f"kiya hi nahi ja sakta.{X}")
    print(f"  {D}Results/guidance = binary event. Us din fresh position mat le.{X}")
    print(f"\n  {D}Not financial advice. Sheet ne khud likha tha: 'just ideas'.{X}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
