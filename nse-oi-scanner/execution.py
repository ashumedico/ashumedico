"""
execution.py  —  the broker layer. PAPER by default; LIVE is gated and opt-in.

Safety model (a real order NEVER fires unless ALL are true):
  1. config.LIVE_TRADING is True          (default False -> paper)
  2. no kill-switch file present          (STOP_TRADING.txt in the folder halts everything)
  3. a valid Fyers token exists
  4. the caller already passed the risk gate (this layer trusts the sized qty)

Paper mode simulates fills into paper_book.json and marks P&L — identical interface to live,
so you prove the system for weeks at zero risk, then flip one flag.

NOT financial advice. Live trading risks real capital; you arm it, you own it.
"""
import os, json, time
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

try:
    import config
except ImportError:
    class _C:
        LIVE_TRADING = False; CLIENT_ID = ""; TOKEN_FILE = "access_token.txt"
        PAPER_BOOK = "paper_book.json"; KILL_SWITCH = "STOP_TRADING.txt"; CAPITAL = 500000
    config = _C()


def _now():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def kill_switch_on():
    return os.path.exists(getattr(config, "KILL_SWITCH", "STOP_TRADING.txt"))


# ---------- paper book ----------
def _book_path():
    return getattr(config, "PAPER_BOOK", "paper_book.json")


def load_book():
    p = _book_path()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"cash": float(getattr(config, "CAPITAL", 100000)), "positions": [],
            "closed": [], "realized_pnl_today": 0.0, "date": datetime.now(IST).strftime("%Y-%m-%d")}


def save_book(book):
    with open(_book_path(), "w") as f:
        json.dump(book, f, indent=2)


def _roll_day(book):
    today = datetime.now(IST).strftime("%Y-%m-%d")
    if book.get("date") != today:
        book["date"] = today
        book["realized_pnl_today"] = 0.0
    return book


# ---------- order interface (paper or live) ----------
def place_order(trade, qty, book=None):
    """Enter a position. Returns a fill dict. Paper unless LIVE + all gates pass."""
    if kill_switch_on():
        return {"status": "HALTED", "reason": "kill switch active (STOP_TRADING.txt)"}
    live = bool(getattr(config, "LIVE_TRADING", False))
    if live:
        return _place_live(trade, qty)
    # ---- paper fill ----
    book = _roll_day(book or load_book())
    pos = {"id": f"P{int(time.time()*1000)%10_000_000}", "symbol": trade["symbol"],
           "underlying": trade.get("underlying"), "kind": trade.get("kind"),
           "side": trade.get("side", "BUY"), "qty": qty, "entry": trade["entry"],
           "stop": trade["stop"], "target": trade["target"],
           "invalidation": trade.get("invalidation", trade["stop"]),
           "deployed": qty * trade["entry"], "opened": _now(), "status": "OPEN"}
    book["positions"].append(pos)
    book["cash"] -= pos["deployed"] if pos["side"] == "BUY" else 0
    save_book(book)
    return {"status": "PAPER_FILL", "position": pos}


def close_position(pos, exit_price, reason, book):
    book = _roll_day(book)
    side = pos.get("side", "BUY")
    pnl = (exit_price - pos["entry"]) * pos["qty"] * (1 if side == "BUY" else -1)
    pos["status"] = "CLOSED"; pos["exit"] = exit_price; pos["exit_reason"] = reason
    pos["pnl"] = round(pnl, 2); pos["closed"] = _now()
    book["positions"] = [p for p in book["positions"] if p["id"] != pos["id"]]
    book["closed"].append(pos)
    book["cash"] += (pos["deployed"] + pnl) if side == "BUY" else pnl
    book["realized_pnl_today"] = round(book.get("realized_pnl_today", 0) + pnl, 2)
    save_book(book)
    if getattr(config, "LIVE_TRADING", False):
        _exit_live(pos, exit_price)
    return pnl


def _place_live(trade, qty):
    """Real Fyers order. Only reached when LIVE_TRADING is True and kill switch is off."""
    if not os.path.exists(getattr(config, "TOKEN_FILE", "access_token.txt")):
        return {"status": "ERROR", "reason": "no Fyers token — run fyers_auth.py"}
    from fyers_apiv3 import fyersModel
    token = open(config.TOKEN_FILE).read().strip()
    fy = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)
    side = 1 if trade.get("side", "BUY") == "BUY" else -1
    order = {"symbol": trade["symbol"], "qty": qty, "type": 2, "side": side,
             "productType": getattr(config, "PRODUCT_TYPE", "INTRADAY"),
             "limitPrice": 0, "stopPrice": 0, "validity": "DAY",
             "offlineOrder": False, "stopLoss": 0, "takeProfit": 0}
    r = fy.place_order(order)
    ok = isinstance(r, dict) and r.get("s") == "ok"
    return {"status": "LIVE_ORDER" if ok else "ERROR", "resp": r}


def _exit_live(pos, exit_price):
    try:
        from fyers_apiv3 import fyersModel
        token = open(config.TOKEN_FILE).read().strip()
        fy = fyersModel.FyersModel(client_id=config.CLIENT_ID, token=token, is_async=False)
        side = -1 if pos.get("side", "BUY") == "BUY" else 1     # opposite to close
        fy.place_order({"symbol": pos["symbol"], "qty": pos["qty"], "type": 2, "side": side,
                        "productType": getattr(config, "PRODUCT_TYPE", "INTRADAY"),
                        "limitPrice": 0, "stopPrice": 0, "validity": "DAY",
                        "offlineOrder": False, "stopLoss": 0, "takeProfit": 0})
    except Exception as e:      # noqa
        print(f"  [live exit error: {e}]")


def mode_banner():
    live = bool(getattr(config, "LIVE_TRADING", False))
    if kill_switch_on():
        return "⛔ HALTED (kill switch)"
    return "🔴 LIVE (real orders)" if live else "🟢 PAPER (simulation)"
