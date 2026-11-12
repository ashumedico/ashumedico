"""
order_page.py  —  place an order through Fyers API Connect, in the browser.

The REST route is blocked by the account's IP whitelist. API Connect is a second route to
the same account: Fyers hosts the button, the click opens their own flow, and the order is
placed from their infrastructure - so a home IP never enters into it, and no access token
is needed here at all.

What this does: resolve the contract exactly as the order path does - symbol, premium and
lot from the live chain, never assembled by hand - write a small local page with the
button pre-filled, and open it. One click on that page places the order.

    python order_page.py --buy SONACOMS --strike 750 --month AUG
    python order_page.py --buy SONACOMS --strike 750 --month AUG --market
    python order_page.py --sell SONACOMS --strike 750 --month AUG

The page is written locally and git-ignored. It carries the app id, which is not a secret
in the way the app secret is, but there is no reason for it to travel either.

NOT financial advice. Clicking that button places a real order.
"""
import os, argparse, webbrowser
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
PAGE = "order.html"

try:
    import config
except ImportError:
    class _C:
        CLIENT_ID = ""
    config = _C()

LIB = "https://api-connect-docs.fyers.in/fyers-lib.js"


def build_html(c, qty, side, order_type, price, api_key):
    """One page, one button, every number visible above it.

    The numbers are repeated in plain text next to the button on purpose: the button
    itself shows none of them, and an order placed from a page that displays nothing is
    an order nobody checked.
    """
    cost = (price or c["premium"]) * qty
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{side} {c['symbol']}</title>
<script src="{LIB}"></script>
<style>
 body {{ font-family: -apple-system, Segoe UI, sans-serif; background:#0d1117; color:#e6edf3;
        margin:0; display:flex; align-items:center; justify-content:center; min-height:100vh; }}
 .card {{ background:#161b22; border:1px solid #30363d; border-radius:12px;
          padding:28px 32px; max-width:520px; width:100%; }}
 h1 {{ font-size:17px; margin:0 0 4px; letter-spacing:.3px; }}
 .sym {{ font-family:ui-monospace,Consolas,monospace; color:#58a6ff; font-size:15px;
         margin-bottom:18px; word-break:break-all; }}
 table {{ width:100%; border-collapse:collapse; margin-bottom:20px; font-size:14px; }}
 td {{ padding:6px 0; border-bottom:1px solid #21262d; }}
 td:last-child {{ text-align:right; font-family:ui-monospace,Consolas,monospace; }}
 .big {{ font-size:18px; color:#f0f6fc; }}
 .note {{ color:#8b949e; font-size:12px; margin-top:16px; line-height:1.5; }}
 .warn {{ color:#f85149; }}
</style></head><body>
<div class="card">
  <h1>{side}</h1>
  <div class="sym">{c['symbol']}</div>
  <table>
    <tr><td>strike</td><td>{c['strike']:g} {c['type']}</td></tr>
    <tr><td>expiry</td><td>{c['expiry']} &nbsp; ({c['days']} din baaki)</td></tr>
    <tr><td>premium</td><td>{c['premium']}</td></tr>
    <tr><td>quantity</td><td>{qty} &nbsp; ({qty // c['lot']} lot x {c['lot']})</td></tr>
    <tr><td>order</td><td>{order_type}{f' @ {price}' if order_type == 'LIMIT' else ''}</td></tr>
    <tr><td class="big">lagega</td><td class="big">Rs {cost:,.0f}</td></tr>
  </table>

  <fyers-button data-fyers="{api_key}"
     data-symbol="{c['symbol']}"
     data-product="{c['product']}"
     data-quantity={qty}
     data-price={price if order_type == 'LIMIT' else 0}
     data-order_type="{order_type}"
     data-transaction_type="{side}">
  </fyers-button>

  <div class="note">
    Button dabane se Fyers apna login/confirm flow kholega aur <span class="warn">asli order</span>
    lagayega. Ye page tere computer pe hai, kahin bheja nahi gaya.<br>
    Banaya: {datetime.now(IST):%d %b %Y, %H:%M IST}
  </div>
</div>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--buy", metavar="NAME")
    ap.add_argument("--sell", metavar="NAME")
    ap.add_argument("--strike", type=float, required=True)
    ap.add_argument("--type", default="CE", choices=["CE", "PE", "ce", "pe"])
    ap.add_argument("--month", help="expiry month, e.g. AUG")
    ap.add_argument("--lots", type=int, default=1)
    ap.add_argument("--lot", type=int, help="override the lot size")
    ap.add_argument("--market", action="store_true",
                    help="market order instead of a limit at the current premium")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()

    name = a.buy or a.sell
    if not name:
        print("  --buy NAAM ya --sell NAAM chahiye.")
        return
    side = "BUY" if a.buy else "SELL"

    api_key = getattr(config, "CLIENT_ID", "")
    if not api_key:
        print("  config.py mein CLIENT_ID nahi hai - button uske bina kaam nahi karega.")
        return

    import broker
    c, err = broker.find_contract(name, a.strike, a.type, a.month)
    if err:
        print(f"\n  {err}\n")
        return
    if a.lot:
        c["lot"], c["lot_source"] = int(a.lot), "tera diya hua"
    c["product"] = getattr(config, "PRODUCT_TYPE", "MARGIN")

    qty = int(c["lot"]) * int(a.lots)
    if qty <= 0 or not c.get("premium"):
        print(f"\n  quantity {qty}, premium {c.get('premium')} - ye ticket nahi hai.\n")
        return

    # A limit at the touch beats a market order on a single-stock option: the spread is
    # a couple of percent of premium, and a market order pays all of it.
    order_type = "MARKET" if a.market else "LIMIT"
    price = round(c["premium"] * (1.01 if side == "BUY" else 0.99), 1)

    html = build_html(c, qty, side, order_type, price, api_key)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)

    cost = (price if order_type == "LIMIT" else c["premium"]) * qty
    print(f"\n  {'=' * 60}")
    print(f"  {side}  {c['symbol']}")
    print(f"  {'=' * 60}")
    print(f"  strike      {c['strike']:g} {c['type']}      expiry {c['expiry']} "
          f"({c['days']} din baaki)")
    print(f"  premium     {c['premium']}")
    print(f"  quantity    {qty}   ({a.lots} lot x {c['lot']})   [lot {c.get('lot_source')} se]")
    print(f"  order       {order_type}" + (f" @ {price}" if order_type == "LIMIT" else ""))
    print(f"  LAGEGA      Rs {cost:,.0f}")
    print(f"  {'=' * 60}")
    print(f"  Page bana: {os.path.abspath(PAGE)}")
    print(f"  Browser mein 'Buy'/'Sell' dabane pe Fyers apna flow kholega.")
    print(f"  IP whitelist ki zaroorat nahi - order Fyers ke server se jayega.\n")

    if not a.no_open:
        webbrowser.open("file:///" + os.path.abspath(PAGE).replace("\\", "/"))


if __name__ == "__main__":
    main()
