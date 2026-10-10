"""
Copy this file to  config.py  and fill in your details.
config.py is git-ignored so your keys never get committed.
Get API keys from  https://myapi.fyers.in/dashboard/  ->  Create App.
"""

# --- Fyers API credentials ---
CLIENT_ID    = "XXXXXXX-100"          # App ID, e.g. "ABCD1234-100"
SECRET_KEY   = "XXXXXXXXXX"           # App secret
REDIRECT_URI = "https://127.0.0.1"    # must match the Fyers app setting

# --- Universe: use F&O FUTURES symbols (cash -EQ has NO open interest) ---
# Format: NSE:<UNDERLYING><YY><MON>FUT   e.g. NSE:RELIANCE26JULFUT
UNIVERSE = [
    "NSE:NIFTY26JULFUT", "NSE:BANKNIFTY26JULFUT",
    "NSE:RELIANCE26JULFUT", "NSE:HDFCBANK26JULFUT", "NSE:ICICIBANK26JULFUT",
    "NSE:INFY26JULFUT", "NSE:TCS26JULFUT", "NSE:SBIN26JULFUT",
    "NSE:TATAMOTORS26JULFUT", "NSE:AXISBANK26JULFUT", "NSE:LT26JULFUT",
]

# --- Scanner settings ---
MIN_OI_CHANGE_PCT = 5.0     # surface names whose OI moved >= this % since day-open
TOP_N             = 15
POLL_SECONDS      = 300     # re-scan every 5 min in --loop
TOKEN_FILE        = "access_token.txt"
BASELINE_FILE     = "oi_baseline.json"
OC_STRIKES        = 10      # option-chain: strikes each side of ATM
RRG_BENCHMARK     = "NSE:NIFTY50-INDEX"   # relative-rotation benchmark
FUT_EXPIRY        = "26JUL"                # current F&O expiry for the RRG OI overlay

# --- F&O ban list (>= 95% MWPL): no fresh positions allowed, so we skip them.
# Update daily from NSE (https://www.nseindia.com -> Securities in F&O Ban).
BAN_LIST = [
    # "IDEA", "RBLBANK",     # examples — put today's banned underlyings here
]

# --- Alerts (leave blank to disable). config.py is git-ignored, so anything
# --- personal you put here never reaches the repository. That matters: this
# --- repo is PUBLIC, so a phone number committed to it would be scraped.
TELEGRAM_TOKEN = ""         # from @BotFather        <- free, recommended
TELEGRAM_CHAT  = ""         # your chat id (from @userinfobot)

# Optional SMS fallback, used only if Telegram is unset or fails.
SMS_API_KEY    = ""         # Fast2SMS dev API key (free tier, no DLT for personal use)
SMS_TO         = ""         # your 10-digit mobile number, e.g. "9876543210"

# ============================================================
# AUTO-TRADER  (paper by default — LIVE is your deliberate opt-in)
# ============================================================
LIVE_TRADING   = False      # <<< KEEP FALSE until you trust the paper record. True = REAL orders.
CAPITAL        = 500000     # your trading capital (drives all sizing)
PRODUCT_TYPE   = "INTRADAY" # Fyers product: INTRADAY / MARGIN / CNC
MIN_CONFIDENCE = 60         # ignore setups below this confluence score

# Risk caps (Conservative preset: 0.5% per trade, 2% daily stop)
RISK_PCT       = 0.005      # risk per trade as a fraction of capital
MAX_EXPOSURE   = 0.40       # max total capital deployed at once
MAX_PER_NAME   = 0.15       # max in any one underlying
DAY_DD         = 0.02       # daily drawdown auto-halt (flatten + stand down)
WEEK_DD        = 0.06
MAX_LOSS       = 5000       # hard worst-case rupee cap per trade
# Counted from orders.jsonl, not from the book: a loop re-sending the same entry books
# no P&L, so the drawdown halt watches a number that never moves while orders keep going.
MAX_ORDERS_PER_DAY = 20     # runaway-loop backstop for unattended runs
# How far the stop may sit from entry, as a fraction of the stock. MAX_LOSS caps the
# RUPEES at risk and a wide stop passes it by simply shrinking the size - leaving a trade
# that must travel twice this to make 2R. Bites hardest when a late confirmation is
# bought with the entry price.
MAX_STOP_PCT   = 0.015      # 1.5% of the underlying

# Instrument modelling
DEFAULT_LOT      = 50       # fallback lot size; override per name in LOT_SIZES
LOT_SIZES        = {}       # e.g. {"RELIANCE": 500, "HDFCBANK": 550, "NIFTY": 75}
FUT_MARGIN_PCT   = 0.20     # futures margin as fraction of notional
OPT_PREMIUM_PCT  = 0.012    # ATM premium proxy (~1.2% of spot) for paper sizing
OPT_DELTA        = 0.5      # ATM delta for underlying->premium mapping

# RRG strategy (the app trades whatever `run_sweep` validated on your data)
RRG_STOP_PCT   = 0.04       # initial stop as % below entry for an RRG rotation long
RRG_TARGET_PCT = 0.10       # target as % above entry
RRG_TAIL       = 6          # tail length shown on the RRG
RRG_HISTORY    = 250        # bars of history pulled for the rotation maths

# Session controls
SQUAREOFF   = "15:15"                 # flatten all intraday positions at this IST time
KILL_SWITCH = "STOP_TRADING.txt"      # create this file in the folder -> halt everything
PAPER_BOOK  = "paper_book.json"       # simulated positions + P&L live here

# Gap-up screen (the Chartink filter, rebuilt in gapup.py)
# These are the DEFAULTS the sidebar opens with; move them there for a session, or here
# to change what "open with" means. Chartink's comparisons are strict, and so are these:
# a name opening at exactly prev_close * GAP_MIN does not pass.
GAP_MIN           = 1.01    # Daily Open > previous Close x this   (below 1% is noise)
GAP_MAX           = 1.02    # Daily Open < previous Close x this   (above 2% has moved)
GAP_SMA           = 20      # Daily Close > SMA of the closes ENDING YESTERDAY
GAP_INTRADAY_GATE = False   # also require [0] 15-min Close > Daily Open. Off, as on your
                            # Chartink. With it on, a name with no intraday bar FAILS -
                            # "could not check" is not "checked out".

# ---------------------------------------------------------------- OPTION QUALITY --
# The gates an option BUYER needs and this system did not have. Selection was entirely
# stock-level: trend, VWAP, RVOL, squeeze, expansion. The option was chosen afterwards
# (ATM, current expiry) and priced - never judged. These make the option itself pass or
# fail, because for a buyer the contract is the trade, not a wrapper around it.
OPTION_SPREAD_PCT   = 0.02   # fallback ONLY, when the chain gives no bid/ask. The real
                             # spread is now measured per strike; this is the estimate of
                             # last resort, not the assumption it used to be.
MAX_SPREAD_PCT      = 0.05   # refuse a strike whose round trip costs more than 5% of the
                             # premium - paid twice, it eats a whole day's expected move
MIN_OPTION_OI       = 500    # contracts of open interest at the strike being bought
MIN_OPTION_VOLUME   = 100    # contracts traded today at that strike. OI without volume is
                             # a position somebody is stuck in, not a market you can exit
MAX_IV_TO_REALISED  = 2.0    # refuse when implied vol is this many times what the stock
                             # has actually been doing - paying for a move bigger than the
                             # one being forecast. None disables the gate.

# Results blackout (events.py). Implied vol rises into a results date and collapses after
# it, so a long option bought inside this window pays for a jump it then loses to the
# crush - the stock can move exactly as predicted and the trade still loses.
EVENT_BLACKOUT_BEFORE = 2    # trading days before the event
EVENT_BLACKOUT_AFTER  = 1    # and after, while IV is still resetting

# Look and feel. theme.py holds the palettes; this picks one.
#   "claude" — warm paper, serif prose, monospace numbers, one coral accent (default)
#   "neon"   — three neons on black, the previous look
# Override for a single session without editing anything:  ?theme=neon  in the URL.
THEME = "claude"
