"""
Copy this file to  config.py  and fill in your Fyers app credentials.
config.py is git-ignored so your keys never get committed.

Get these from https://myapi.fyers.in/dashboard/  ->  Create App.
"""

# --- Fyers API credentials ---
CLIENT_ID    = "XXXXXXX-100"          # App ID, e.g. "ABCD1234-100"
SECRET_KEY   = "XXXXXXXXXX"           # App secret
REDIRECT_URI = "https://127.0.0.1"    # must match what you set in the Fyers app

# --- Scanner settings ---
# The F&O underlyings to scan (futures OI-change buildup).
UNIVERSE = [
    "NSE:NIFTY50-INDEX", "NSE:NIFTYBANK-INDEX",
    "NSE:RELIANCE-EQ", "NSE:HDFCBANK-EQ", "NSE:ICICIBANK-EQ",
    "NSE:INFY-EQ", "NSE:TCS-EQ", "NSE:SBIN-EQ", "NSE:TATAMOTORS-EQ",
    "NSE:AXISBANK-EQ", "NSE:LT-EQ", "NSE:BHARTIARTL-EQ",
]

MIN_OI_CHANGE_PCT = 5.0     # only surface names whose OI moved at least this %
TOP_N             = 15      # show top N by absolute OI change
POLL_SECONDS      = 300     # re-scan every 5 min when run with --loop
TOKEN_FILE        = "access_token.txt"
SNAPSHOT_FILE     = "oi_snapshot.json"
