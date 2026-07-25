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
# Format: NSE:<UNDERLYING><YY><MON>FUT   e.g. NSE:RELIANCE25JULFUT
UNIVERSE = [
    "NSE:NIFTY25JULFUT", "NSE:BANKNIFTY25JULFUT",
    "NSE:RELIANCE25JULFUT", "NSE:HDFCBANK25JULFUT", "NSE:ICICIBANK25JULFUT",
    "NSE:INFY25JULFUT", "NSE:TCS25JULFUT", "NSE:SBIN25JULFUT",
    "NSE:TATAMOTORS25JULFUT", "NSE:AXISBANK25JULFUT", "NSE:LT25JULFUT",
]

# --- Scanner settings ---
MIN_OI_CHANGE_PCT = 5.0     # surface names whose OI moved >= this % since day-open
TOP_N             = 15
POLL_SECONDS      = 300     # re-scan every 5 min in --loop
TOKEN_FILE        = "access_token.txt"
BASELINE_FILE     = "oi_baseline.json"
OC_STRIKES        = 10      # option-chain: strikes each side of ATM

# --- F&O ban list (>= 95% MWPL): no fresh positions allowed, so we skip them.
# Update daily from NSE (https://www.nseindia.com -> Securities in F&O Ban).
BAN_LIST = [
    # "IDEA", "RBLBANK",     # examples — put today's banned underlyings here
]

# --- Optional Telegram alerts (leave blank to disable) ---
TELEGRAM_TOKEN = ""         # from @BotFather
TELEGRAM_CHAT  = ""         # your chat id (from @userinfobot)
