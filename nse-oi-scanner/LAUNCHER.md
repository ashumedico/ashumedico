# AASHISH TRADING OS — the launcher, and how to build the .exe

One window instead of twenty-five icons. Credentials at the top, settings under them, one
green button that starts the engine, and a log that shows what the engine is actually doing.

> **Not financial advice.** Signals are inputs; the trade is yours. Arming live trading is a
> deliberate act — a filled order does not come back.

---

## 1. Build the .exe (once, ~3 minutes)

The `.exe` can only be built **on the Windows machine that will run it** — a Windows binary
cannot be produced from anywhere else. It is one double-click:

```
Tools  →  Build the .exe          (or run BUILD-EXE.bat in the code folder)
```

What it does: installs PyInstaller if missing → packages `launcher.py` into
`AASHISH TRADING OS.exe` → copies it into the Desktop folder → drops a shortcut on the
Desktop itself.

**You never have to build it again.** The `.exe` is only the launcher; all the trading code
runs from the code folder. `0 - UPDATE` updates that code, and the same `.exe` picks it up.

If the build fails, the two usual reasons:

| Message | Fix |
|---|---|
| `Python nahi mila` | Install Python from python.org, tick **Add to PATH** |
| `tkinter nahi hai` | Re-run the Python installer, tick **tcl/tk and IDLE** |

---

## 2. First run

1. **Fyers Client ID** and **Secret Key** — from your Fyers API app.
   Redirect URI must match the app exactly (default `https://127.0.0.1`).
2. Tick **remember credentials** → they are written to `config.py`, which is git-ignored.
   Untick it and nothing is stored; they live only for this session.
3. **1 Fyers login** → browser opens, you approve, the day's token is saved.
4. **Self-test** → every link checked one by one. Read it before starting anything.
5. **START ENGINE**.

### The self-test, line by line

```
Config          OK    INTRADAY 15min · capital Rs 2,00,000 · 1 lot
Token           OK    file 0.4 hrs purani
Universe        OK    214 F&O naam
Spot candles    OK    400 bars · 214 naam · 214 pe poore OHLCV
Expiry          OK    28AUG · 28 din baaki (chahiye 15)
Option chain    OK    RELIANCE · 285 strikes
Lot size        OK    500 × 1420 = Rs 7,10,000 contract
Regime          OK    RISK-ON (4/5 checks)
Live orders     OK    disarmed - sirf paper
Telegram        SKIP  configured nahi
```

Three verdicts, and they are not interchangeable:

- **OK** — tested, passed.
- **FAIL** — tested, failed. **Do not start the engine.**
- **SKIP** — could not be tested from here. **A skip is not a pass.** A skipped Telegram
  check means you will get no phone alerts, not that alerts work.

The **Lot size** line is the one that has caught real money bugs. An F&O contract is
roughly ₹5–10 lakh. If that line shows ₹1.7 lakh or ₹45 lakh, the lot is wrong — check NSE
and the broker before ordering, and pin it with `Tools → Lot Audit`.

---

## 3. The window

**CREDENTIALS** — Fyers Client ID · Secret Key · Redirect URI · Telegram Bot Token · Chat ID.
Secrets are masked; `show secrets` reveals them. `config.py` is git-ignored — this repo is
public, so nothing typed here reaches GitHub.

**SETTINGS**

| Field | What it does |
|---|---|
| Capital | Every "can I afford this" answer comes from here. Wrong number = wrong sizing. |
| Lots per trade | **The size. 1.** Not a starting point — the risk budget can only veto it, never raise it. |
| Target Rs (net) | Book and leave at this **net** profit (after spread and charges). 0 = off. |
| Price min / max | Universe filter: names outside the band are not scanned. **0 / 0 = off.** |
| Mode | Intraday 15m (default) or Swing. This one setting drives trend, stops, hold time and which expiry is correct. |

> The price band is a **universe filter, not a signal**, and it has **not** been
> walk-forward tested. It narrows what is eligible; it does not predict anything. The desk
> says so on screen whenever it is on.

**BUTTONS**

| Button | Runs | Notes |
|---|---|---|
| ▶ START ENGINE | `paper.py --session` | Every candle: take / mark / trail / exit. Turns into STOP ENGINE. |
| 1 Fyers login | `fyers_auth.py` | Day token |
| Self-test | `selftest.py` | Run it before the engine, every day |
| Check-in | `checkin.py` | Hold / book / new |
| Desk (website) | `streamlit run desk.py` | Own process — does not take the engine slot |
| ■ KILL SWITCH | creates `STOP_TRADING.txt` | Halts everything, everywhere. Stops the engine too. |
| LIVE TRADING | `LIVE_TRADING` in config | Asks first. Paper always runs; this only adds the live leg. |

Only **one** engine process at a time, on purpose: two engines marking the same book would
each think they own it.

**ENGINE LOG** — the subprocess's real output, live. If the window and the console ever
disagree, the console is right, because they are the same process.

---

## 4. The one thing the window cannot do

> **The trailing stop lives inside the running process, not at the exchange.**

Close the window, sleep the laptop, or lose the connection, and **nothing is watching the
position**. There is no resting stop order at Fyers to catch it. This is why the window
asks before closing while the engine runs.

`PRODUCT_TYPE = INTRADAY`, so if you never close a position the broker will — at market, at
a time of its choosing. The engine squares off at `SQUAREOFF` (15:15) to get there first.

---

## 5. Daily order

```
Launcher  →  1 Fyers login  →  Self-test  →  START ENGINE
                                    ↓
                            Desk (website) to look
                            Check-in for hold/book/new
```

---

## 6. If something breaks

| Symptom | Where to look |
|---|---|
| Window opens, nothing works | `Self-test` — the failing line names the link |
| "Token nahi hai" | `1 Fyers login`. Tokens are day tokens |
| Engine starts and exits immediately | Read the log; it is the real stdout |
| `-50` order rejection | IP whitelist at Fyers, or use `5 - ORDER` (browser flow, no whitelist) |
| Rejected for margin | Funds. The system does not check balance before ordering — by your instruction |
| Nothing scanning | Price band may be on. Set min/max to 0 |
| Window builds wrong after an update | `Tools → Launcher test` — 16 checks, no display needed on Windows |

---

## 7. Building software like this — what actually mattered

Notes for the next one, because most of these were learned by getting them wrong here:

1. **A control that does nothing is a lie.** The price band got wired into the actual
   universe filter the same hour the field appeared. A dead input on a screen is worse than
   no input, because it gets trusted.
2. **Never let a display invent a number.** Everything on the desk is computed from bars
   that were fetched. Where there is no data it says so — it does not draw a plausible line.
3. **Unknown is not a pass.** A missing feature fails its gate, a skipped check is reported
   as SKIP, and an untested filter stays off. The RRG measured −6.3% after costs; that is
   the standing precedent for not enabling things that merely look sensible.
4. **The GUI must not be a second system.** Every button shells out to the same file the
   icon ran. Two implementations of one rule will disagree, and you will find out live.
5. **One writer for config.** `configure.py` rewrites only named keys and keeps a backup —
   and same-second writes get separate backups, because the launcher writes twice in a row
   and the second copy was quietly overwriting the first.
6. **Secrets: masked, git-ignored, never in a log line, never a command-line argument.**
   The repo is public.
7. **Test the window, not just the imports.** A GUI imports fine and throws on the first
   click. `test_launcher.py` builds the real window off-screen and clicks the parts that
   touch state.
8. **The stop that isn't at the exchange must be said out loud**, in the log and in the
   docs. The most dangerous bug is the one where the software looks like it is watching.
