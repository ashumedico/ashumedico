"""
alerts.py  —  optional Telegram push for strong buildup signals.
Set TELEGRAM_TOKEN and TELEGRAM_CHAT in config.py to enable; leave blank to disable.
"""
import urllib.request, urllib.parse

# only ping on the strongest, most tradeable signals
ALERT_ON = {"LONG BUILDUP", "SHORT BUILDUP"}
ALERT_MIN_OI = 8.0   # only if OI moved at least this much


def send_alerts(rows, config):
    token = getattr(config, "TELEGRAM_TOKEN", "")
    chat = getattr(config, "TELEGRAM_CHAT", "")
    if not token or not chat:
        return
    hot = [r for r in rows if r["signal"] in ALERT_ON and abs(r["oi"]) >= ALERT_MIN_OI]
    if not hot:
        return
    lines = ["📊 *OI Buildup Alert*"]
    for r in hot:
        arrow = "🟢" if "LONG" in r["signal"] else "🔴"
        lines.append(f"{arrow} `{r['sym']}`  px {r['px']:+.1f}%  OI {r['oi']:+.1f}%  — {r['signal']}")
    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "Markdown"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=8)
    except Exception:
        pass  # never let an alert failure break the scan
