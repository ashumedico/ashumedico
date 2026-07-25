# NSE F&O OI-Change Options Scanner (Fyers)

Rebuilt & version-controlled copy of the scanner that used to live only on your PC at
`C:\claude\`. Now it's in git — backed up, diff-able, and improvable.

> **Not financial advice.** Signals are inputs; every trade decision is yours (per `@edge-seeker`).

## What it does
Polls the Fyers API for LTP + open interest on your F&O universe and classifies each name
by the price × OI matrix:

| Price | OI | Signal |
|---|---|---|
| ↑ | ↑ | **Long Buildup** (bullish) |
| ↓ | ↑ | **Short Buildup** (bearish) |
| ↑ | ↓ | **Short Covering** (bullish) |
| ↓ | ↓ | **Long Unwinding** (bearish) |

Each scan is compared to the previous snapshot to compute OI-change %, filtered by
`MIN_OI_CHANGE_PCT`, ranked, and printed. Last scan becomes the next baseline.

## Setup
```bash
pip install -r requirements.txt
copy config.example.py config.py     # then fill in your Fyers keys
```

## Daily use (maps to your two shortcuts)
| Old shortcut | Runs | Now |
|---|---|---|
| **Fyers_Login** | `run_login.bat` → `fyers_auth.py` | refresh daily token |
| **NSE_Options_Scanner** | `run_scanner.bat` → `scanner.py --loop` | live scan every 5 min |

```bash
python fyers_auth.py       # each morning: get today's access token
python scanner.py          # one scan
python scanner.py --loop   # continuous (every POLL_SECONDS)
python scanner.py --dry-run  # test the pipeline with no Fyers/creds/market
```

## Files
- `fyers_auth.py` — daily token refresh (= `run_login.bat`)
- `scanner.py` — the OI-change scanner (= `run_scanner.bat`)
- `config.example.py` — copy to `config.py`, add keys (git-ignored)
- `run_login.bat` / `run_scanner.bat` — Windows launchers your shortcuts point to

## Reconcile with your original
This is rebuilt from what the shortcuts revealed (Fyers + NSE F&O OI-change), **not** a
copy of your exact logic. Check these against your real version and tell me the deltas:
- your exact **universe** (which F&O symbols)
- your **OI-change threshold** and any RVOL / price filters
- whether you scanned **futures OI** or **option-chain (strike-wise) OI / PCR**
- any **alerting** (Telegram/webhook/sound) the original had
