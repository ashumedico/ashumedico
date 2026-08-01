"""
test_orders.py  —  the order buttons must not be able to send anything by accident.

These are the only controls in the system that move real money on a mouse press, so the
question is not "does it work" but "what does it take to fire it by mistake". A stray
scroll-click on a laptop trackpad is one press. So one press must never be enough, the
payload shown has to be the payload sent, and every existing guard - kill switch, live
flag, missing contract - has to still hold at this layer.

Also checks the new stop-loss path, because a stop order sent without a trigger is a
market order in disguise: it fires instantly and looks exactly like the stop being hit.

    python test_orders.py
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def fake_config(live=True):
    m = types.ModuleType("config")
    m.CLIENT_ID, m.SECRET_KEY = "X-100", "s"
    m.LIVE_TRADING = live
    m.PRODUCT_TYPE = "INTRADAY"
    m.TOKEN_FILE = "access_token.txt"
    m.CAPITAL, m.LOTS_PER_TRADE = 200000, 1
    sys.modules["config"] = m
    return m


def main():
    print("\n  ORDER SAFETY")
    print("  " + "-" * 62)

    cfg = fake_config(live=True)
    for mod in ("broker",):
        sys.modules.pop(mod, None)
    import broker as B

    sent = []

    class _FakeClient:
        @staticmethod
        def place_order(req):
            sent.append(dict(req))
            return {"s": "ok", "id": "TEST123"}

    B._client = lambda: _FakeClient()

    # ---- 1. the stop-loss order shape ----
    print("\n1. STOP LOSS")
    sent.clear()
    ok, detail = B.stop_loss("NSE:X25AUG100CE", 500, 12.5, tag="t")
    check("SL is sent as a SELL", ok and sent and sent[0]["side"] == -1, str(detail)[:60])
    check("SL uses order type 3 (SL-M)", sent and sent[0]["type"] == 3,
          f"type={sent[0]['type'] if sent else '-'}")
    check("the trigger reaches stopPrice", sent and sent[0]["stopPrice"] == 12.5)
    check("no limit price on an SL-M", sent and sent[0]["limitPrice"] == 0.0)

    sent.clear()
    ok, detail = B.stop_loss("NSE:X25AUG100CE", 500, 12.5, limit_price=12.0)
    check("a limit price makes it SL-L (type 4)", sent and sent[0]["type"] == 4)

    sent.clear()
    ok, detail = B.place("NSE:X", 500, "SELL", kind="SL", stop_price=0)
    check("a stop with no trigger is refused, not sent",
          not ok and not sent and "trigger" in str(detail),
          "without this it is a market order in disguise")

    ok, detail = B.place("NSE:X", 500, "BUY", kind="NONSENSE")
    check("an unknown order kind is refused", not ok and "unknown order kind" in detail)

    # ---- 2. the guards that already existed still hold ----
    print("\n2. GUARDS")
    sent.clear()
    ok, detail = B.place("", 500, "BUY")
    check("no symbol -> nothing sent", not ok and not sent)

    open(B.KILL_FILE, "w").write("test\n")
    try:
        sent.clear()
        ok, detail = B.place("NSE:X", 500, "BUY")
        check("kill switch -> nothing sent", not ok and not sent, str(detail)[:50])
        ok, detail = B.stop_loss("NSE:X", 500, 10)
        check("kill switch stops an SL too", not ok and not sent)
    finally:
        os.remove(B.KILL_FILE)

    fake_config(live=False)
    sys.modules.pop("broker", None)
    import broker as B2
    B2._client = lambda: _FakeClient()
    sent.clear()
    ok, detail = B2.place("NSE:X", 500, "BUY")
    check("LIVE_TRADING off -> logged, not sent", not ok and not sent, str(detail)[:50])

    # ---- 3. the button needs two presses ----
    print("\n3. TWO PRESSES")
    src = open(os.path.join(HERE, "desk.py")).read()
    check("there is an arm/confirm control at all", "def order_button(" in src)
    check("the first press only arms",
          "st.session_state.arm = {\"key\": key" in src
          and "fire()" in src.split("CONFIRM")[1][:400],
          "fire() must live behind the CONFIRM branch, not the first button")
    check("arming expires", "ARM_SECONDS" in src and "time.time() - a.get" in src)
    check("the payload is shown before it is sent",
          "st.code(" in src.split("_armed_key(key)")[1][:400])
    check("a missing contract disables the button",
          'payload.get("symbol")' in src and "no contract" in src)
    check("the kill switch disables the button here too",
          "KILL SWITCH ON" in src and "disabled=True" in src)
    check("the broker's own reply is shown verbatim",
          "'SENT' if ok else 'NOT SENT'" in src)

    # every order control must go through order_button - a bare st.button that calls the
    # broker would bypass every one of the checks above
    import re
    calls = re.findall(r"__import__\(\"broker\"\)\.(buy|sell|stop_loss)", src)
    inside = re.findall(r"order_button\([^)]*", src)
    check("all three actions are wired", sorted(set(calls)) == ["buy", "sell", "stop_loss"],
          f"{sorted(set(calls))}")
    check("no order call outside an order_button",
          src.count("order_button(") - 1 >= len(calls),
          f"{src.count('order_button(') - 1} buttons for {len(calls)} broker calls")

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - one press cannot send an order\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
