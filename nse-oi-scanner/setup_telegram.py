"""
setup_telegram.py  —  Telegram alerts, set up for you.

Only one step genuinely needs a human: creating the bot in @BotFather, because that
happens inside your own Telegram account. Everything after that is automated here -
the chat id is discovered by polling the bot instead of making you hunt for it with
another bot, config.py is written for you, and a test message proves it works before
anything is scheduled.

    python setup_telegram.py

Nothing personal is ever written outside config.py, which is git-ignored. That matters:
this repository is public.
"""
import os, re, json, time, sys, urllib.request, urllib.parse

CONFIG = "config.py"
API = "https://api.telegram.org/bot{token}/{method}"


def _api(token, method, params=None, timeout=12):
    url = API.format(token=token, method=method)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def check_token(token):
    """Confirm the token is real and return the bot's @username."""
    try:
        r = _api(token, "getMe")
        if r.get("ok"):
            return r["result"].get("username")
    except Exception as e:      # noqa
        print(f"  [X] Telegram tak pahunch nahi paya: {e}")
    return None


def discover_chat_id(token, wait=180):
    """Poll getUpdates until he messages the bot, then read the chat id off it.

    This replaces the usual "go find @userinfobot" detour - the id is already in the
    update, so there is no reason to make him fetch it by hand."""
    print(f"\n  Ab apne bot ko Telegram pe koi bhi message bhej (kuch bhi - 'hi').")
    print(f"  Main wait kar raha hoon...", flush=True)
    deadline = time.time() + wait
    seen_offset = 0
    while time.time() < deadline:
        try:
            r = _api(token, "getUpdates", {"offset": seen_offset, "timeout": 5}, timeout=15)
            for u in r.get("result", []):
                seen_offset = max(seen_offset, u.get("update_id", 0) + 1)
                msg = u.get("message") or u.get("channel_post") or {}
                chat = msg.get("chat") or {}
                if chat.get("id"):
                    who = chat.get("first_name") or chat.get("title") or "you"
                    print(f"\n  [OK] Mil gaya - {who} (chat id {chat['id']})")
                    return str(chat["id"])
        except Exception:
            pass
        left = int(deadline - time.time())
        print(f"  ...{left}s baaki  ", end="\r", flush=True)
        time.sleep(2)
    print("\n  [X] Koi message nahi aaya. Dobara chala aur bot ko message bhej.")
    return None


def write_config(token, chat_id):
    """Set the two keys in config.py without disturbing anything else."""
    if not os.path.exists(CONFIG):
        print(f"  [X] {CONFIG} nahi mila. Pehle chala:  python setup.py")
        return False
    with open(CONFIG) as f:
        text = f.read()
    for key, val in (("TELEGRAM_TOKEN", token), ("TELEGRAM_CHAT", chat_id)):
        pat = re.compile(rf'^{key}\s*=\s*.*$', re.M)
        line = f'{key} = "{val}"'
        text = pat.sub(line, text, count=1) if pat.search(text) else text + f"\n{line}\n"
    with open(CONFIG, "w") as f:
        f.write(text)
    return True


def main():
    print("\n" + "=" * 66)
    print("  TELEGRAM ALERTS SETUP")
    print("=" * 66)
    print("""
  Sirf ek step tere haath mein hai (30 second):

    1. Telegram khol  ->  search:  @BotFather
    2. Bhej:  /newbot
    3. Bot ka naam pooche  ->  kuch bhi likh (e.g. Aashish Trading)
    4. Username pooche     ->  kuch bhi jo 'bot' pe khatam ho
                              (e.g. aashish_trade_9x_bot)
    5. Woh ek TOKEN dega - lamba, aisa:
       8123456789:AAH7x...  <- poora copy kar
""")
    token = input("  Token yahan paste kar: ").strip().strip('"')
    if not token or ":" not in token:
        print("  [X] Ye token jaisa nahi lag raha. Dobara chala.")
        return 1

    print("\n  Token check kar raha hoon...")
    username = check_token(token)
    if not username:
        print("  [X] Token kaam nahi kar raha. BotFather se dobara copy kar.")
        return 1
    print(f"  [OK] Bot mil gaya:  @{username}")
    print(f"       Khol:  https://t.me/{username}")

    chat_id = discover_chat_id(token)
    if not chat_id:
        return 1

    if not write_config(token, chat_id):
        return 1
    print(f"  [OK] config.py mein save kar diya (git-ignored - repo pe nahi jaayega)")

    print("\n  Test message bhej raha hoon...")
    try:
        import importlib, alert_watch
        importlib.reload(alert_watch.config) if hasattr(alert_watch, "config") else None
    except Exception:
        pass
    r = _api(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "✅ Trading OS alerts chalu.\n"
                "Ab jab T1 ya stop hit hoga, yahin message aayega. "
                "Warna main chup rahunga."})
    if not r.get("ok"):
        print(f"  [X] Test fail: {r}")
        return 1

    print("  [OK] Bheja - phone check kar.\n")
    print("=" * 66)
    print("  HO GAYA. Ab schedule lagane ke liye chala:")
    print("     SETUP-ALERTS.bat      (roz 12:30 aur 15:10 pe khud check karega)")
    print("  Ya khud kabhi bhi:")
    print("     python alert_watch.py")
    print("=" * 66 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
