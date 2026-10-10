"""
journal.py  —  the memory. Records every signal, scores what happened, learns daily.

A system that doesn't remember its own calls can't improve. This logs each signal the
day it fires, then marks it forward against real prices and answers the only questions
that matter:

    Did it work?          WIN / LOSS / OPEN, per trade, with the actual return
    What is working?      hit-rate sliced by signal AGE, quadrant, OI state, own-trend
    What should I stop?    the slices that lose money — printed as plain lessons

Two files, both plain text so nothing is hidden:
    journal.jsonl        one line per signal, append-only (the raw record)
    journal_report.md    today's scorecard + lessons

    python journal.py --log            # record today's signals (live) or --demo
    python journal.py --review         # mark outcomes forward + print the table
    python journal.py --lessons        # what to keep doing / stop doing

NOT financial advice. These are the system's own calls being graded honestly.
"""
import os, json, argparse
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
JOURNAL = "journal.jsonl"
REPORT = "journal_report.md"

# outcome thresholds, in units of the trade's own risk (R)
WIN_R, LOSS_R = 1.0, -1.0


def today():
    return datetime.now(IST).strftime("%Y-%m-%d")


# ---------------- write ----------------
def load():
    if not os.path.exists(JOURNAL):
        return []
    out = []
    with open(JOURNAL) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def log_signals(points, picks, mode="LIVE", cards=None):
    """Append today's candidates. Idempotent: one entry per (name, signal_date)."""
    have = {(e["name"], e.get("signal_date")) for e in load()}
    cards = cards or {}
    n = 0
    with open(JOURNAL, "a") as f:
        for p in points:
            if p["name"] not in picks:
                continue
            key = (p["name"], p.get("signal_date"))
            if key in have:
                continue
            card = cards.get(p["name"], {})
            stock = card.get("stock", {})
            entry = stock.get("entry") or p["close"]
            stop = stock.get("stop")
            t1 = stock.get("t1")
            rec = {
                "logged_on": today(), "mode": mode,
                "name": p["name"], "symbol": p.get("symbol"),
                "signal_date": p.get("signal_date"), "age_bars": p.get("age_bars"),
                "freshness": p.get("freshness"),
                "quadrant": p.get("quadrant"), "crossed": p.get("crossed"),
                "distance": p.get("distance"), "velocity": p.get("velocity"),
                "heading": p.get("heading"),
                "own_trend": p.get("abs_trend"), "oi": p.get("signal"),
                "entry": entry, "stop": stop, "t1": t1,
                "entry_close": p["close"],
                # exact bar the signal fired at -> review grades the RIGHT forward window.
                # Counting back from the end of the series instead silently graded every
                # backfilled trade against the last 10 bars of history (fake +22R wins).
                "bar_index": p.get("bar_index"),
                "option": ({"strike": card["option"]["strike"], "type": card["option"]["type"],
                            "premium": card["option"]["premium"]} if card.get("option") else None),
                "outcome": "OPEN", "r_multiple": None, "exit_close": None, "reviewed_on": None,
            }
            f.write(json.dumps(rec) + "\n")
            n += 1
    return n


def _save_all(entries):
    with open(JOURNAL, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


# ---------------- mark forward ----------------
def review(prices, dates=None, max_hold=10):
    """Grade every OPEN entry against what price actually did after the signal.

    Uses the trade's own risk unit (entry->stop) so a 2% move on a quiet stock and a
    6% move on a wild one are compared fairly. Path matters: if the low took out the
    stop before the high reached T1, it is a LOSS — no optimistic ordering."""
    entries = load()
    by_name = {s.split(":")[-1].replace("-EQ", ""): c for s, c in prices.items()}
    changed = 0
    for e in entries:
        if e.get("outcome") not in (None, "OPEN"):
            continue
        closes = by_name.get(e["name"])
        if not closes or not e.get("entry") or not e.get("stop"):
            continue
        # locate the signal bar: exact index > date lookup > last-resort age offset
        idx = e.get("bar_index")
        if isinstance(idx, int) and 0 <= idx < len(closes):
            pass
        elif dates and e.get("signal_date") in dates:
            idx = dates.index(e["signal_date"])
            if len(closes) != len(dates):
                idx -= (len(dates) - len(closes))
        else:
            idx = None
        if idx is None or idx < 0 or idx >= len(closes):
            idx = max(0, len(closes) - 1 - int(e.get("age_bars") or 1))
        fwd = closes[idx + 1: idx + 1 + max_hold]
        if not fwd:
            continue
        entry = float(e["entry"]); stop = float(e["stop"])
        risk = max(entry - stop, 1e-9)
        t1 = float(e["t1"]) if e.get("t1") else entry + risk
        outcome, r = "OPEN", None
        for px in fwd:                       # walk forward in order — path-honest
            if px <= stop:
                outcome, r = "LOSS", round((px - entry) / risk, 2); break
            if px >= t1:
                outcome, r = "WIN", round((px - entry) / risk, 2); break
        if outcome == "OPEN" and len(fwd) >= max_hold:
            r = round((fwd[-1] - entry) / risk, 2)
            outcome = "TIMEOUT WIN" if r > 0 else "TIMEOUT LOSS"
        if outcome != "OPEN":
            e["outcome"], e["r_multiple"] = outcome, r
            e["exit_close"] = round(fwd[-1], 2)
            e["reviewed_on"] = today()
            changed += 1
    _save_all(entries)
    return entries, changed


# ---------------- report ----------------
def table(entries=None, limit=40):
    entries = entries if entries is not None else load()
    rows = []
    for e in sorted(entries, key=lambda x: (x.get("signal_date") or "", x["name"]), reverse=True)[:limit]:
        opt = e.get("option") or {}
        rows.append({
            "Signal date": e.get("signal_date") or "-",
            "Age@log": e.get("age_bars"),
            "Fresh": e.get("freshness"),
            "Name": e["name"],
            "Option": (f"{opt.get('strike')}{opt.get('type')}" if opt else "-"),
            "Entry": e.get("entry"),
            "Stop": e.get("stop"),
            "Quadrant": e.get("quadrant"),
            "OI": (e.get("oi") or "-"),
            "Result": e.get("outcome"),
            "R": e.get("r_multiple"),
        })
    return rows


def _stats(group):
    done = [e for e in group if e.get("outcome") not in (None, "OPEN")]
    if not done:
        return None
    wins = [e for e in done if (e.get("r_multiple") or 0) > 0]
    rs = [e.get("r_multiple") or 0 for e in done]
    return {"n": len(done), "win_rate": round(len(wins) / len(done) * 100, 1),
            "avg_r": round(sum(rs) / len(rs), 2), "total_r": round(sum(rs), 2)}


def lessons(entries=None):
    """Slice the record to find what actually works — and what to stop doing."""
    entries = entries if entries is not None else load()
    out = {"overall": _stats(entries), "slices": {}}

    def add(label, keyfn):
        buckets = {}
        for e in entries:
            k = keyfn(e)
            if k is None:
                continue
            buckets.setdefault(str(k), []).append(e)
        got = {k: _stats(v) for k, v in buckets.items()}
        out["slices"][label] = {k: v for k, v in got.items() if v}

    add("by freshness at entry", lambda e: e.get("freshness"))
    add("by quadrant", lambda e: e.get("quadrant"))
    add("by own-trend", lambda e: {1: "own trend UP", -1: "own trend DOWN", 0: "flat"}.get(e.get("own_trend")))
    add("by OI buildup", lambda e: e.get("oi"))
    add("by crossed-in", lambda e: "fresh cross" if e.get("crossed") else "already inside")
    return out


def render_lessons(L):
    o = L["overall"]
    print("\n" + "=" * 68)
    print("  JOURNAL - what the system's own calls actually did")
    print("=" * 68)
    if not o:
        print("  No graded trades yet. Log signals daily, then run --review.")
        print("=" * 68 + "\n"); return
    print(f"  Overall: {o['n']} graded  ·  win rate {o['win_rate']}%  ·  "
          f"avg {o['avg_r']}R  ·  total {o['total_r']}R")
    for label, buckets in L["slices"].items():
        if not buckets:
            continue
        print(f"\n  {label}:")
        ranked = sorted(buckets.items(), key=lambda kv: kv[1]["avg_r"], reverse=True)
        for k, s in ranked:
            flag = "  <-- best" if s is ranked[0][1] and s["avg_r"] > 0 else (
                   "  <-- STOP THIS" if s["avg_r"] < 0 and s["n"] >= 3 else "")
            print(f"    {k:<22} n={s['n']:<4} win {s['win_rate']:>5.1f}%  "
                  f"avg {s['avg_r']:>6.2f}R{flag}")
    print("\n  Lessons:")
    for label, buckets in L["slices"].items():
        losers = [(k, s) for k, s in buckets.items() if s["avg_r"] < 0 and s["n"] >= 3]
        for k, s in losers:
            print(f"    - STOP: '{k}' ({label}) is losing {abs(s['avg_r']):.2f}R over {s['n']} trades.")
        winners = [(k, s) for k, s in buckets.items() if s["avg_r"] > 0.3 and s["n"] >= 3]
        for k, s in winners:
            print(f"    + KEEP: '{k}' ({label}) is making {s['avg_r']:.2f}R over {s['n']} trades.")
    print("=" * 68 + "\n")


def write_report(entries, L):
    lines = [f"# Trading journal - {today()}", ""]
    o = L["overall"]
    if o:
        lines += [f"**Overall:** {o['n']} graded trades · win rate **{o['win_rate']}%** · "
                  f"avg **{o['avg_r']}R** · total **{o['total_r']}R**", ""]
    rows = table(entries)
    if rows:
        hdr = list(rows[0].keys())
        lines += ["## Trades", "", "| " + " | ".join(hdr) + " |",
                  "|" + "|".join(["---"] * len(hdr)) + "|"]
        for r in rows:
            lines.append("| " + " | ".join("" if r[h] is None else str(r[h]) for h in hdr) + " |")
        lines.append("")
    for label, buckets in L["slices"].items():
        if not buckets:
            continue
        lines += [f"## {label}", "", "| bucket | n | win% | avg R |", "|---|---|---|---|"]
        for k, s in sorted(buckets.items(), key=lambda kv: kv[1]["avg_r"], reverse=True):
            lines.append(f"| {k} | {s['n']} | {s['win_rate']} | {s['avg_r']} |")
        lines.append("")
    lines += ["---", "_Not financial advice. The system grading its own calls._"]
    with open(REPORT, "w") as f:
        f.write("\n".join(lines))
    return REPORT


def backfill(prices, bench, dates=None, step=5, start=70, max_pos=10, quiet=False):
    """Replay history and log what the system WOULD have called, as of each past date.

    This gives a real track record on day one instead of waiting weeks. Strictly
    point-in-time: each snapshot sees only data up to that bar, so nothing is graded
    with information it could not have had."""
    import rrg_strategy as S, trade_card as TC
    rule, params, _ = S.load_best()
    n_bars = len(bench)
    logged = 0
    t = start
    while t < n_bars - 2:
        pts = S.snapshot(prices, bench, t, tail=3)
        if pts:
            # date/age fields must reflect that past bar, not today
            ref_date = dates[t - 1] if dates and t - 1 < len(dates) else None
            for p in pts:
                p["signal_date"] = ref_date
                p["last_date"] = ref_date
                p["bar_index"] = t - 1
            sel = S.select(pts, rule, params, max_pos=max_pos)
            picks = [p["name"] for p in sel["longs"]]
            cards = {}
            for p in sel["longs"]:
                closes = prices[p["symbol"]][:t]
                if len(closes) > 40:
                    p["close"] = closes[-1]
                    cards[p["name"]] = TC.build_card(p, closes)
            logged += log_signals(pts, picks, "BACKFILL", cards)
        t += step
    if not quiet:
        print(f"  backfilled {logged} historical signal(s)")
    return logged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true",
                    help="replay history to build an instant track record")
    ap.add_argument("--log", action="store_true", help="record today's signals")
    ap.add_argument("--review", action="store_true", help="grade open entries forward")
    ap.add_argument("--lessons", action="store_true", help="print what works / what to stop")
    ap.add_argument("--demo", action="store_true", help="use synthetic data")
    ap.add_argument("--all", action="store_true", help="log + review + lessons")
    a = ap.parse_args()
    if not (a.log or a.review or a.lessons or a.backfill or a.all):
        a.all = True

    import rrg_engine as E, rrg_strategy as S, trade_card as TC
    if a.demo:
        points, prices, bench = E.demo_points()
        dates = None
    else:
        from fno_universe import fno_stocks
        prices, bench, dates = E.fetch_history(fno_stocks())
        points = E.build_points(prices, bench, tail=6, dates=dates)

    if a.backfill:
        backfill(prices, bench, dates)

    if a.log or a.all:
        rule, params, _ = S.load_best()
        sel = S.select(points, rule, params, max_pos=10)
        picks = [p["name"] for p in sel["longs"]]
        for p in sel["longs"]:
            p["bar_index"] = len(prices[p["symbol"]]) - 1
        cards = {p["name"]: TC.build_card(p, prices[p["symbol"]]) for p in sel["longs"]}
        n = log_signals(points, picks, "DEMO" if a.demo else "LIVE", cards)
        print(f"  logged {n} new signal(s); journal has {len(load())} total")

    entries = load()
    if a.review or a.all:
        entries, changed = review(prices, dates)
        print(f"  graded {changed} entr{'y' if changed == 1 else 'ies'} this run")

    L = lessons(entries)
    if a.lessons or a.all:
        rows = table(entries, limit=15)
        if rows:
            hdr = ["Signal date", "Fresh", "Name", "Option", "Entry", "Stop", "Result", "R"]
            print("\n  Recent signals")
            print("  " + "-" * 78)
            print("  " + "".join(f"{h:<13}" for h in hdr))
            print("  " + "-" * 78)
            for r in rows:
                print("  " + "".join(f"{'' if r.get(h) is None else str(r.get(h)):<13}" for h in hdr))
            print("  " + "-" * 78)
        render_lessons(L)
        print(f"  report -> {write_report(entries, L)}")


if __name__ == "__main__":
    main()
