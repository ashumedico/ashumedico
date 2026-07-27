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

# --- Optional Telegram alerts (leave blank to disable) ---
TELEGRAM_TOKEN = ""         # from @BotFather
TELEGRAM_CHAT  = ""         # your chat id (from @userinfobot)

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

# Instrument modelling
DEFAULT_LOT      = 50       # fallback lot size; override per name in LOT_SIZES
LOT_SIZES        = {}       # e.g. {"RELIANCE": 500, "HDFCBANK": 550, "NIFTY": 75}
FUT_MARGIN_PCT   = 0.20     # futures margin as fraction of notional
OPT_PREMIUM_PCT  = 0.012    # ATM premium proxy (~1.2% of spot) for paper sizing
OPT_DELTA        = 0.5      # ATM delta for underlying->premium mapping

# Session controls
SQUAREOFF   = "15:15"                 # flatten all intraday positions at this IST time
KILL_SWITCH = "STOP_TRADING.txt"      # create this file in the folder -> halt everything
PAPER_BOOK  = "paper_book.json"       # simulated positions + P&L live here
