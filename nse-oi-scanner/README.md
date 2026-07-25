# NSE F&O OI-Change Options Scanner (Fyers) — v2

Version-controlled, hardened rebuild of the scanner that used to live only on your PC at
`C:\claude\`. Now in git: backed up, diff-able, improvable.

> **Not financial advice.** Signals are inputs; every trade decision is yours (`@edge-seeker`).

## The signal engine
Price × open-interest matrix, measured **from the day's opening OI** (real intraday buildup):

| Price | OI | Signal |
|---|---|---|
| ↑ | ↑ | **Long Buildup** (bullish) |
| ↓ | ↑ | **Short Buildup** (bearish) |
| ↑ | ↓ | **Short Covering** (bullish) |
| ↓ | ↓ | **Long Unwinding** (bearish) |

## What v2 fixed (critical review of the first rebuild)
1. **OI baseline** — now vs **day-open OI**, not vs the last 5-min poll (which was noise).
2. **Futures symbols** — cash `-EQ` has no OI; the universe now uses `...FUT` symbols.
3. **Market-hours guard** — only scans 09:15–15:30 IST, Mon–Fri (override with `--force`).
4. **Token expiry** — a Fyers auth error is caught and tells you to re-login instead of crashing.
5. **Retries + backoff** on every API call.
6. **History + logging** — `scanner.log` + a daily `signals_YYYYMMDD.csv`.
7. **Optional Telegram alerts** on strong buildups (`alerts.py`, config-gated).

## Setup
```bash
pip install -r requirements.txt
copy config.example.py config.py     # add Fyers keys + your FUT universe
```

## Desktop icons (Windows)
Double-click **`install.bat`** once → it drops 3 icons on your Desktop:
- **NSE OI Scanner** → `run_scanner.bat` (console, live loop)
- **Fyers Login** → `run_login.bat` (daily token)
- **OI Scanner Board** → `run_dashboard.bat` (Streamlit → localhost:8501)

## Run
```bash
python fyers_auth.py         # each morning: today's token
python scanner.py            # one scan
python scanner.py --loop     # continuous (every POLL_SECONDS)
python scanner.py --dry-run  # synthetic data, no Fyers needed
streamlit run app.py         # dashboard at http://localhost:8501
```

## Files
| File | Role |
|---|---|
| `scanner.py` | hardened OI-change scanner (console) |
| `app.py` | Streamlit dashboard (localhost:8501) |
| `fyers_auth.py` | daily Fyers token refresh |
| `alerts.py` | optional Telegram push |
| `config.example.py` | copy → `config.py` (git-ignored) |
| `install.bat` / `create_desktop_shortcuts.ps1` | desktop icons |
| `run_*.bat` | Windows launchers your shortcuts point to |

## Reconcile with your original (still worth doing)
Rebuilt from what the shortcuts revealed, not a byte-copy. Tell me and I'll merge:
your exact **universe**, **thresholds**, **futures vs option-chain (strike-wise) OI / PCR**,
and any **alerting** the original had.
