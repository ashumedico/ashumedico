"""
events.py  —  the blackout around results, which is where option buyers die quietly.

THE FAILURE THIS PREVENTS
Implied volatility rises into a results date because the market knows a jump is coming.
A buyer who enters then pays for that jump in the premium. The result prints, the
uncertainty resolves, and IV collapses - often 30-50% in a single session. The stock can
move exactly the way he predicted and the option still loses, because he was long
volatility into the event that removes it. It is the most reliable way to be right about
a company and wrong about the trade, and nothing in this system checked for it.

WHAT THIS DOES NOT PRETEND
There is no free, reliable, machine-readable NSE results calendar this system can depend
on - the endpoints move, they rate-limit, and they block server IPs. So this is built the
other way round: a small local calendar he controls, plus a best-effort fetch that fills
it when it can. And critically:

  **An empty calendar is reported as NOT CHECKED, never as clear.**

That distinction is the whole design. "No event found" and "no calendar loaded" produce
identical output in a naive implementation - and the naive version would put a green tick
on a ticket the day before results.

    python events.py --add RELIANCE 2026-08-14 results
    python events.py --list
    python events.py --check RELIANCE
    python events.py --refresh            # best-effort NSE pull; says plainly if it fails
"""
import json
import os
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
STORE = "events.json"

# A long option bought two days before results is already carrying the IV premium; the
# day after, it is carrying the crush. Both sides are blacked out.
DEFAULT_BEFORE = 2
DEFAULT_AFTER = 1


def today():
    return datetime.now(IST).date()


def _d(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:      # noqa
        return None


def load(path=None):
    path = path or STORE
    if not os.path.exists(path):
        return {"events": [], "source": None, "fetched": None}
    try:
        with open(path) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return {"events": [], "source": "unreadable", "fetched": None}
        d.setdefault("events", [])
        return d
    except Exception:      # noqa
        return {"events": [], "source": "unreadable", "fetched": None}


def save(d, path=None):
    path = path or STORE
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, path)


def add(name, date, kind="results", path=None):
    """One event. `name` is the plain symbol - RELIANCE, not NSE:RELIANCE-EQ."""
    d = load(path)
    nm = str(name).upper().replace("NSE:", "").replace("-EQ", "")
    if not _d(date):
        return False, f"{date!r} is not a YYYY-MM-DD date"
    d["events"] = [e for e in d["events"]
                   if not (e.get("name") == nm and e.get("date") == str(date)[:10])]
    d["events"].append({"name": nm, "date": str(date)[:10], "kind": kind})
    d["source"] = d.get("source") or "manual"
    save(d, path)
    return True, f"{nm} {kind} on {str(date)[:10]}"


def has_calendar(path=None):
    """(bool, note) — is there anything to check against at all?

    Called before any verdict, because a calendar with no rows cannot clear a name; it
    can only fail to find one. Those are different answers and only one of them is safe
    to act on."""
    d = load(path)
    n = len(d.get("events") or [])
    if d.get("source") == "unreadable":
        return False, f"{STORE} could not be read — event risk is NOT being checked"
    if not n:
        return False, ("no results calendar loaded — event risk is NOT being checked. "
                       "Add dates with `python events.py --add NAME YYYY-MM-DD results`, "
                       "or run `--refresh`.")
    upcoming = sum(1 for e in d["events"] if (_d(e.get("date")) or today()) >= today())
    return True, f"{n} events on file, {upcoming} still ahead"


def next_event(name, path=None, within_days=45):
    """The soonest event for a name, or None. Plain symbol in, dict out."""
    nm = str(name).upper().replace("NSE:", "").replace("-EQ", "")
    t = today()
    best = None
    for e in load(path).get("events") or []:
        if e.get("name") != nm:
            continue
        d = _d(e.get("date"))
        if not d or (d - t).days < -DEFAULT_AFTER or (d - t).days > within_days:
            continue
        if best is None or d < _d(best["date"]):
            best = e
    return best


def blackout(name, before=None, after=None, path=None):
    """(state, note) where state is 'clear' | 'blackout' | 'unchecked'.

    THREE states, not two. A boolean would collapse "no event near this name" and "no
    calendar exists" into the same False, and the second one must never read as safe.
    """
    ok, cal_note = has_calendar(path)
    if not ok:
        return "unchecked", cal_note
    before = DEFAULT_BEFORE if before is None else int(before)
    after = DEFAULT_AFTER if after is None else int(after)
    e = next_event(name, path)
    if not e:
        return "clear", "no event on file within the next 45 days"
    d = _d(e["date"])
    days = (d - today()).days
    if -after <= days <= before:
        when = ("today" if days == 0 else
                f"in {days} day{'s' if days != 1 else ''}" if days > 0 else
                f"{-days} day{'s' if days != -1 else ''} ago")
        side = ("IV is already carrying the jump — a buyer pays for the move before it "
                "happens" if days >= 0 else
                "IV has just collapsed — the premium lost value the moment the "
                "uncertainty resolved")
        return "blackout", (f"{e['kind']} {when} ({e['date']}). {side}.")
    return "clear", f"next {e['kind']} {e['date']}, {days} days away"


def refresh(path=None, timeout=10):
    """Best effort at NSE's results calendar. Returns (added, note).

    Written to fail LOUDLY and change nothing on failure. A refresh that silently leaves
    an empty calendar behind is how "no event found" starts meaning "not checked" without
    anyone noticing.
    """
    import urllib.request
    url = ("https://www.nseindia.com/api/event-calendar")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json",
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-event-calendar",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rows = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:      # noqa
        return 0, (f"could not reach NSE ({str(e)[:90]}). The calendar is unchanged — "
                   f"add dates by hand with --add, which is the reliable path anyway.")
    if not isinstance(rows, list):
        return 0, "NSE returned something that is not a list of events; nothing changed"
    d = load(path)
    have = {(e["name"], e["date"]) for e in d["events"]}
    added = 0
    for r in rows:
        nm = str(r.get("symbol") or "").upper()
        dt = _d(r.get("date") or r.get("Date"))
        purpose = str(r.get("purpose") or r.get("Purpose") or "").lower()
        if not nm or not dt or "result" not in purpose:
            continue
        key = (nm, dt.isoformat())
        if key in have:
            continue
        d["events"].append({"name": nm, "date": dt.isoformat(), "kind": "results"})
        have.add(key)
        added += 1
    d["source"] = "nse"
    d["fetched"] = datetime.now(IST).isoformat()
    save(d, path)
    return added, f"added {added} results dates from NSE"


def main():
    import sys
    a = sys.argv[1:]
    if "--add" in a:
        i = a.index("--add")
        args = a[i + 1:i + 4]
        if len(args) < 2:
            print("  usage: python events.py --add RELIANCE 2026-08-14 [results]")
            return 2
        ok, msg = add(args[0], args[1], args[2] if len(args) > 2 else "results")
        print(f"  {'added' if ok else 'refused'}: {msg}")
        return 0 if ok else 1
    if "--refresh" in a:
        n, note = refresh()
        print(f"  {note}")
        return 0
    if "--check" in a:
        i = a.index("--check")
        nm = a[i + 1] if len(a) > i + 1 else None
        if not nm:
            print("  usage: python events.py --check RELIANCE")
            return 2
        st, note = blackout(nm)
        print(f"\n  {nm.upper()}  ->  {st.upper()}\n  {note}\n")
        return 0
    ok, note = has_calendar()
    d = load()
    print("\n  EVENT CALENDAR")
    print("  " + "-" * 62)
    print(f"  {note}")
    if d.get("fetched"):
        print(f"  last fetched {d['fetched'][:16]} from {d.get('source')}")
    rows = sorted([e for e in d.get("events") or []
                   if (_d(e.get("date")) or today()) >= today()],
                  key=lambda e: e["date"])[:20]
    for e in rows:
        days = (_d(e["date"]) - today()).days
        print(f"    {e['name']:<14} {e['date']}  {e['kind']:<10} in {days}d")
    if not ok:
        print("\n  Until something is on file, every ticket will say event risk was NOT")
        print("  checked. That is deliberate: an empty calendar cannot clear a name.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
