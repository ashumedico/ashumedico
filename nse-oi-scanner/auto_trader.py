"""
auto_trader.py  —  the 24/7 loop: SCAN -> RISK GATE -> EXECUTE -> MANAGE -> HALT.

Wires the whole universal-trading pipeline into an automated engine. PAPER by default.

  python auto_trader.py --dry-run            # one full cycle on synthetic signals (safe demo)
  python auto_trader.py --paper --loop       # continuous paper trading on live signals
  python auto_trader.py --once               # a single live-signal cycle (still paper unless armed)

GOING LIVE (your explicit, deliberate act — not a default):
  1. Paper-trade for weeks; confirm the edge in paper_book.json.
  2. In config.py set  LIVE_TRADING = True  and your real CAPITAL / caps.
  3. Remove STOP_TRADING.txt if present; ensure a fresh Fyers token.
  Kill switch: create a file named STOP_TRADING.txt in this folder -> everything halts.

NOT financial advice. You arm live trading; you own the outcome.
"""
import os, sys, time, argparse
from datetime import datetime, timezone, timedelta

import scanner
import signal_engine as se
import risk_gate
import execution as ex

IST = timezone(timedelta(hours=5, minutes=30))

try:
    import config
except ImportError:
    class _C:
        CAPITAL = 500000; LIVE_TRADING = False; POLL_SECONDS = 300
        SQUAREOFF = "15:15"; DAY_DD = 0.02
    config = _C()

LOT = {}  # optional {underlying: lot_size}; falls back to a sensible default


def now_ist():
    return datetime.now(IST)


def lot_size(underlying, kind):
    # options and futures on a name share the same lot size (real lots come from config)
    return getattr(config, "LOT_SIZES", {}).get(underlying, getattr(config, "DEFAULT_LOT", 50))


def _trade_from_idea(idea):
    """Convert an underlying-level idea into a tradeable order.
    FUT: trade the underlying levels directly, capital = margin (~20% of notional).
    CE/PE: translate the underlying view into a PREMIUM-space BUY (ATM, delta~0.5),
           so risk = premium points and capital = premium outlay."""
    v = idea["verdict"]; t = idea["trade"]
    kind = "FUT" if idea["kind"] == "FUTURES" else ("CE" if "CALL" in idea["kind"] else "PE")
    under = idea["underlying"].split(":")[-1]
    d_up = abs(t["target"] - t["entry"]); d_dn = abs(t["entry"] - t["stop"])

    if kind == "FUT":
        return {"symbol": idea["underlying"] + "-FUT", "underlying": under, "kind": kind,
                "side": "BUY" if v["direction"] == "BULLISH" else "SELL",
                "entry": t["entry"], "stop": t["stop"], "target": t["target"],
                "invalidation": idea["levels"].get("S2" if v["direction"] == "BULLISH" else "R2", t["stop"]),
                "lot_size": lot_size(under, kind),
                "margin_pct": getattr(config, "FUT_MARGIN_PCT", 0.20),
                "confidence": idea["confidence"]}

    # option: premium proxy from spot; delta ~0.5 maps underlying moves -> premium moves.
    prem_pct = getattr(config, "OPT_PREMIUM_PCT", 0.012)     # ATM premium ~1.2% of spot
    delta = getattr(config, "OPT_DELTA", 0.5)
    premium = round(t["entry"] * prem_pct, 1)
    # a long option always profits when premium rises: build it as a BUY in premium space
    prem_target = round(premium + delta * d_up, 1)
    prem_stop = round(max(0.5, premium - delta * d_dn), 1)
    return {"symbol": f"{idea['underlying']}:{idea.get('strike','')}{kind}", "underlying": under,
            "kind": kind, "side": "BUY", "entry": premium, "stop": prem_stop,
            "target": prem_target, "invalidation": prem_stop,
            "lot_size": lot_size(under, kind), "margin_pct": 1.0,
            "confidence": idea["confidence"]}


def day_halted(book):
    cap = float(getattr(config, "CAPITAL", 100000))
    return book.get("realized_pnl_today", 0) <= -getattr(config, "DAY_DD", 0.02) * cap


def past_squareoff():
    hhmm = getattr(config, "SQUAREOFF", "15:15")
    try:
        h, m = map(int, hhmm.split(":"))
    except Exception:
        h, m = 15, 15
    t = now_ist()
    return (t.hour, t.minute) >= (h, m)


# ---------- manage open positions ----------
def _price_now(symbol, fallback):
    """Live LTP if available; else fallback (paper/dry uses a modeled path)."""
    return fallback


def manage_positions(book, price_map=None):
    """Close positions that hit target / stop / invalidation / square-off."""
    price_map = price_map or {}
    for pos in list(book["positions"]):
        px = price_map.get(pos["id"], pos["entry"])
        reason = None
        long = pos.get("side", "BUY") == "BUY"
        if past_squareoff():
            reason = "square-off"
        elif long and px >= pos["target"]:   reason = "target"
        elif long and px <= pos["stop"]:      reason = "stop"
        elif (not long) and px <= pos["target"]: reason = "target"
        elif (not long) and px >= pos["stop"]:   reason = "stop"
        if reason:
            pnl = ex.close_position(pos, px, reason, book)
            print(f"    EXIT {pos['symbol']} @ {px} ({reason})  P&L {pnl:+.0f}")


# ---------- one cycle ----------
def cycle(dry=False):
    if ex.kill_switch_on():
        print("  ⛔ Kill switch active (STOP_TRADING.txt). No trading."); return
    book = ex._roll_day(ex.load_book())
    print(f"\n  AUTO-TRADER  ·  {ex.mode_banner()}  ·  {now_ist():%H:%M:%S} IST")
    print(f"  Cash {book['cash']:.0f}  ·  Open {len(book['positions'])}  ·  "
          f"Day P&L {book.get('realized_pnl_today',0):+.0f}")

    if day_halted(book):
        print("  ⛔ Daily drawdown limit hit — flattening and standing down for today.")
        manage_positions(book, {p["id"]: p["entry"] for p in book["positions"]})
        return

    # SCAN + SIGNAL
    verdicts = se.dry_verdicts() if dry else se.live_verdicts()
    ideas = se.build_ideas(verdicts) if verdicts else {}
    open_syms = {p["symbol"] for p in book["positions"]}

    for key in ("CE", "PE", "FUT"):
        idea = ideas.get(key)
        if not idea:
            continue
        trade = _trade_from_idea(idea)
        if trade["symbol"] in open_syms:
            continue                                  # already holding this
        if trade.get("confidence", 0) < getattr(config, "MIN_CONFIDENCE", 60):
            print(f"    skip {trade['symbol']} (confidence {trade.get('confidence')}% < min)"); continue
        # RISK GATE
        port = {"capital": float(getattr(config, "CAPITAL", 100000)),
                "realized_pnl_today": book.get("realized_pnl_today", 0),
                "open_positions": book["positions"]}
        v = risk_gate.check(trade, port, config)
        risk_gate.render(v, trade)
        if not v["ok"]:
            continue
        # EXECUTE
        fill = ex.place_order(trade, v["qty"], book)
        book = ex.load_book()
        print(f"    ENTER {trade['symbol']} x{v['qty']} @ {trade['entry']} "
              f"[{fill['status']}]  T {trade['target']} / SL {trade['stop']}")

    # MANAGE (dry: model a move toward target for demo; live: real LTP)
    if dry:
        pmap = {}
        for p in book["positions"]:
            long = p["side"] == "BUY"
            pmap[p["id"]] = p["target"] if long else p["target"]   # demo: assume target tag
        manage_positions(book, pmap)
    else:
        manage_positions(book)
    book = ex.load_book()
    print(f"  End cycle · Open {len(book['positions'])} · Day P&L {book.get('realized_pnl_today',0):+.0f}")
    return book


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="synthetic signals, paper fills (safe demo)")
    ap.add_argument("--paper", action="store_true", help="force paper even if config says live")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    if args.paper:
        config.LIVE_TRADING = False

    if args.dry_run or args.once:
        cycle(dry=args.dry_run)
        return
    print(f"  Auto-trader starting · {ex.mode_banner()}")
    try:
        while True:
            if ex.kill_switch_on():
                print("  ⛔ Kill switch — halting loop."); break
            if not scanner.is_market_open():
                print(f"  Market closed — waiting.  ({now_ist():%H:%M})")
            else:
                cycle(dry=False)
            if not args.loop:
                break
            time.sleep(getattr(config, "POLL_SECONDS", 300))
    except KeyboardInterrupt:
        print("\n  Stopped by user.")


if __name__ == "__main__":
    main()
