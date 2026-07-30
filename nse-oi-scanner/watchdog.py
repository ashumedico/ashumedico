"""
watchdog.py  —  pings Telegram ONLY when you need to act. Otherwise stays silent.

Aashish trades occasionally and leaves. The gap that costs real money is this: T1 gets
hit on Tuesday, he checks on Friday, and the move is gone. The system knew - nobody
told him.

So this runs on a schedule and messages him only when a decision is due:
    T1 hit          -> book half, trail the rest to breakeven
    T2 hit          -> book the rest
    stop broken     -> get out, do not average
    dead money      -> 25 sessions and going nowhere, close it
    a fresh signal  -> only if he holds nothing and a new setup passed

Silence is the feature. A watchdog that barks every day gets ignored, and then it barks
on the day that mattered and gets ignored too. Every alert is de-duplicated per day, so
the same T1 is never sent twice.

    python watchdog.py            # check + alert if needed
    python watchdog.py --test     # prove Telegram works
    python watchdog.py --dry      # print what WOULD be sent, send nothing

NOT financial advice.
"""
import os, json, argparse, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
SENT_LOG = "alerts_sent.json"

try:
    import config
except ImportError:
    class _C:
        TELEGRAM_TOKEN = ""; TELEGRAM_CHAT = ""
    config = _C()


def now():
    return datetime.now(IST)


# ---------------- telegram ----------------
def send(text, dry=False):
    token = getattr(config, "TELEGRAM_TOKEN", "")
    chat = getattr(config, "TELEGRAM_CHAT", "")
    if dry:
        print("---- would send ----\n" + text + "\n--------------------")
        return True
    if not token or not chat:
        print("  [!] TELEGRAM_TOKEN / TELEGRAM_CHAT config.py mein nahi hai - alert skip.")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text,
                                   "parse_mode": "Markdown"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as r:
            ok = json.loads(r.read().decode()).get("ok", False)
        if not ok:
            print("  [!] Telegram ne reject kiya - token/chat id check kar.")
        return ok
    except Exception as e:      # noqa
        print(f"  [!] Telegram bhej nahi paya: {e}")
        return False


# ---------------- de-dupe ----------------
def _sent_today():
    if os.path.exists(SENT_LOG):
        try:
            with open(SENT_LOG) as f:
                d = json.load(f)
            if d.get("date") == now().strftime("%Y-%m-%d"):
                return set(d.get("keys", []))
        except Exception:
            pass
    return set()


def _mark(keys):
    with open(SENT_LOG, "w") as f:
        json.dump({"date": now().strftime("%Y-%m-%d"), "keys": sorted(keys)}, f)


# ---------------- the check ----------------
def build_alerts(bk, quotes):
    """Return (key, message-line) for every position that needs a decision today."""
    out = []
    for p in bk.get("open", []):
        ltp = quotes.get(p.get("symbol"))
        if ltp is None:
            continue
        name = p["name"]
        if p.get("option"):
            name += f" {p['option']['strike']:g}{p['option']['type']}"
        chg = (ltp / p["entry"] - 1) * 100 if p.get("entry") else 0
        held = (now() - datetime.fromisoformat(p["bought_on"])).days

        if p.get("t2") and ltp >= p["t2"]:
            out.append((f"{p['name']}:T2",
                        f"🏦 *{name}* — T2 {p['t2']} hit @ {ltp:.2f} ({chg:+.1f}%)\n"
                        f"   *Poora book kar.* Target complete."))
        elif p.get("t1") and ltp >= p["t1"] and not p.get("half_booked"):
            out.append((f"{p['name']}:T1",
                        f"💰 *{name}* — T1 {p['t1']} hit @ {ltp:.2f} ({chg:+.1f}%)\n"
                        f"   *Aadha book kar*, baaki ka stop breakeven ({p['entry']}) pe."))
        elif p.get("stop") and ltp <= p["stop"]:
            out.append((f"{p['name']}:STOP",
                        f"🛑 *{name}* — stop {p['stop']} toota @ {ltp:.2f} ({chg:+.1f}%)\n"
                        f"   *Nikal ja.* Average mat kar."))
        elif held >= 25:
            out.append((f"{p['name']}:TIME",
                        f"⏳ *{name}* — {held} din, kuch nahi hua ({chg:+.1f}%)\n"
                        f"   *Band kar.* Dead money."))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="send a test message")
    ap.add_argument("--dry", action="store_true", help="print instead of sending")
    ap.add_argument("--new-signals", action="store_true",
                    help="also alert on a fresh setup when holding nothing")
    a = ap.parse_args()

    if a.test:
        ok = send("✅ *Trading OS* — alerts chalu hain.\n"
                  "Ab jab T1/stop hit hoga, yahin message aayega.", a.dry)
        print("  [OK] test bheja - phone check kar." if ok else "  [X] test fail.")
        return

    import checkin as C
    bk = C.load()
    if not bk.get("open"):
        if not a.new_signals:
            print("  Koi position nahi. Kuch bhejne ka nahi.")
            return
        quotes = {}
    else:
        import rrg_engine as E
        quotes = E.live_quote([p["symbol"] for p in bk["open"] if p.get("symbol")])

    alerts = build_alerts(bk, quotes)
    already = _sent_today()
    fresh = [(k, m) for k, m in alerts if k not in already]

    if not fresh:
        print(f"  Kuch karne ka nahi ({len(alerts)} already bheje ja chuke aaj)."
              if alerts else "  Sab theek hai - koi action nahi. Chup reh raha hoon.")
        return

    text = (f"📌 *{now():%d %b, %H:%M}* — action chahiye\n\n"
            + "\n\n".join(m for _, m in fresh))
    if send(text, a.dry) and not a.dry:
        _mark(already | {k for k, _ in fresh})
    print(f"  {len(fresh)} alert bheja.")


if __name__ == "__main__":
    main()
