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

# --- F&O ban list (>= 95% MWPL): no fresh positions allowed, so we skip them.
# Update daily from NSE (https://www.nseindia.com -> Securities in F&O Ban).
BAN_LIST = [
    # "IDEA", "RBLBANK",     # examples — put today's banned underlyings here
]

# --- Optional Telegram alerts (leave blank to disable) ---
TELEGRAM_TOKEN = ""         # from @BotFather
TELEGRAM_CHAT  = ""         # your chat id (from @userinfobot)
