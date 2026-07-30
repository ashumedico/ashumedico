"""
rrg_app.py  —  AASHISH TRADING OS · the auto-trader app with the RRG as its main window.

    streamlit run rrg_app.py          # opens http://localhost:8501

What it is: one cockpit. The RRG fills the main window (all F&O names, live), the validated
setup marks today's candidates, and the auto-trader panel sizes + places them through the risk
gate — PAPER by default, live only when you arm it.

Layout
  MAIN     interactive RRG: every F&O name, tails, OI-buildup shape, candidate halos
  RIGHT    setup in force (from your own backtest) · candidates · exits
  BELOW    positions & blotter · risk gate readout · auto-trader controls

NOT financial advice. Live orders need LIVE_TRADING=True and no kill switch.
"""
import os, time
from datetime import datetime, timezone, timedelta

import streamlit as st

import rrg_engine as E
import rrg_strategy as S
import risk_gate
import execution as ex

# Plotly gives the interactive RRG. If it is missing we still run — falling back to
# the matplotlib render — so a missing package never blanks the whole cockpit.
try:
    import rrg_view as V
    HAVE_PLOTLY = True
except Exception:                      # noqa
    V = None
    HAVE_PLOTLY = False

IST = timezone(timedelta(hours=5, minutes=30))
st.set_page_config(page_title="Aashish Trading OS · RRG", page_icon="🎯", layout="wide")

# Streamlit's defaults are sized for demos, not for a trading desk. A desk needs the
# whole ticket visible without scrolling, so tighten type and vertical rhythm.
st.markdown("""<style>
  .block-container {padding-top:1.1rem; padding-bottom:1rem; max-width:1500px;}
  h1 {font-size:1.35rem !important; margin:0 0 .3rem !important;}
  h2 {font-size:1.05rem !important; margin:.5rem 0 .3rem !important;}
  h3 {font-size:.95rem !important; margin:.5rem 0 .25rem !important;}
  [data-testid="stMetricValue"] {font-size:1.05rem !important; line-height:1.2 !important;}
  [data-testid="stMetricLabel"] {font-size:.68rem !important; text-transform:uppercase;
                                 letter-spacing:.4px; opacity:.75;}
  [data-testid="stMetricDelta"] {font-size:.68rem !important;}
  [data-testid="stMetric"] {padding:.2rem 0 !important;}
  div[data-testid="stVerticalBlock"] {gap:.45rem !important;}
  .stAlert {padding:.4rem .7rem !important; font-size:.8rem !important;}
  .stAlert p {margin:0 !important;}
  .stTabs [data-baseweb="tab"] {padding:.25rem .6rem !important; font-size:.8rem !important;}
  .stButton button {padding:.25rem .6rem !important; font-size:.82rem !important;}
  table {font-size:.78rem !important;}
  .stCaption, [data-testid="stCaptionContainer"] {font-size:.72rem !important;}
  hr {margin:.6rem 0 !important;}
  .tick {font-size:1.25rem; font-weight:800; letter-spacing:-.2px;}
  .sub {font-size:.75rem; opacity:.7;}
</style>""", unsafe_allow_html=True)

try:
    import config
except ImportError:
    class _C:
        CAPITAL = 500000; LIVE_TRADING = False; DEFAULT_LOT = 50
        RRG_BENCHMARK = "NSE:NIFTY50-INDEX"
    config = _C()

cap_cfg = float(getattr(config, "CAPITAL", 500000))   # used by the action board + auto-trader


# ---------------- data ----------------
@st.cache_data(show_spinner=False, ttl=900)
def load_universe(demo: bool, days: int, tail: int):
    if demo:
        pts, prices, bench = E.demo_points(tail=tail)
        return pts, prices, bench, "DEMO (synthetic)"
    pts, prices, bench = E.live_points(tail=tail, days=days)
    return pts, prices, bench, "LIVE (Fyers)"


# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    has_token = os.path.exists(getattr(config, "TOKEN_FILE", "access_token.txt"))
    demo = st.toggle("Demo data (no Fyers)", value=not has_token,
                     help="Off = live full-F&O data. Needs today's Fyers token.")
    if not has_token and not demo:
        st.warning("No Fyers token found — run **Fyers Login** first.")
    days = st.slider("History (bars)", 120, 600, 250, 10)
    tail = st.slider("Tail length", 2, 12, 6)
    max_pos = st.slider("Max positions", 1, 20, 8)
    st.divider()
    st.markdown("### 🎯 Setup in force")
    rule, params, best = S.load_best()
    if best:
        m = best["metrics"]
        st.success(f"**{best['setup']}**")
        st.caption(f"backtested: {m['total_return']:+.1f}% · Sharpe {m['sharpe']} · "
                   f"maxDD {m['max_dd']}% · win {m['win_rate']}%")
    else:
        st.info("**Default: cross into Leading/Improving + own-trend filter**")
        st.caption("Run `python rrg_strategy.py --sweep` to validate on your data.")
    st.caption(f"rule `{rule}` · {params}")
    st.divider()
    st.markdown(f"### {ex.mode_banner()}")
    if ex.kill_switch_on():
        if st.button("♻️ Clear kill switch", use_container_width=True):
            os.remove(getattr(config, "KILL_SWITCH", "STOP_TRADING.txt")); st.rerun()
    else:
        if st.button("🛑 STOP TRADING (kill switch)", use_container_width=True, type="primary"):
            open(getattr(config, "KILL_SWITCH", "STOP_TRADING.txt"), "w").write("halt")
            st.rerun()
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear(); st.rerun()


# ---------------- header ----------------
st.markdown("## 🎯 Aashish Trading OS — Relative Rotation")
prog = st.empty()
with st.spinner("Loading universe…"):
    try:
        points, prices, bench, mode = load_universe(demo, days, tail)
    except Exception as e:  # noqa
        st.error(f"Data load failed: {e}")
        st.info("If this is a token error, run **Fyers Login**, then Refresh data.")
        st.stop()
prog.empty()

sel = S.select(points, rule, params, max_pos=max_pos)
picks = [p["name"] for p in sel["longs"]]
c = E.counts(points)

k1, k2, k3, k4, k5 = st.columns(5)
n_skipped = len(getattr(E, "LAST_SKIPPED", []))
k1.metric("Universe", len(points),
          f"-{n_skipped} unavailable" if n_skipped else None, delta_color="off",
          help="Names that failed to fetch are excluded — the RRG only scores what it "
               "could actually load.")
k2.metric("🟢 Leading", c["LEADING"])
k3.metric("🔵 Improving", c["IMPROVING"])
k4.metric("Candidates", len(picks))
k5.metric("Mode", mode.split(" ")[0])

# ---------------- refresh bar (right above the signals) ----------------
if "loaded_at" not in st.session_state:
    st.session_state.loaded_at = datetime.now(IST)

r1, r2, r3 = st.columns([1.1, 2.2, 1.2])
with r1:
    if st.button("🔄 Refresh now", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.session_state.loaded_at = datetime.now(IST)
        st.rerun()
with r2:
    loaded = st.session_state.loaded_at
    mins = int((datetime.now(IST) - loaded).total_seconds() // 60)
    age_txt = "just now" if mins < 1 else f"{mins} min ago"
    bar_date = points[0].get("last_date") if points else None
    st.markdown(
        f"<div style='padding-top:6px'>Data loaded <b>{age_txt}</b> "
        f"({loaded:%H:%M IST})"
        + (f" &nbsp;·&nbsp; latest bar <b>{bar_date}</b>" if bar_date else "")
        + (" &nbsp;·&nbsp; <span style='color:#d29922'>market closed</span>"
           if not (9 <= datetime.now(IST).hour < 16) else
           " &nbsp;·&nbsp; <span style='color:#3fb950'>market hours</span>")
        + "</div>", unsafe_allow_html=True)
with r3:
    auto = st.toggle("Auto every 5 min", value=False,
                     help="Re-pulls data and re-scores the board every 5 minutes.")

if mins >= 15 and not demo:
    st.warning(f"⚠️ This data is **{mins} minutes old** — hit **Refresh now** before acting on it.")

# ---------------- ACTION BOARD (what the RRG alone never tells you) ----------------
st.markdown("### 📋 Action board — what to do right now")
if not sel["longs"]:
    st.info("**No trade today.** Nothing passes the setup. Standing down is a position — "
            "the edge comes from only taking the A+ ones.")
else:
    import trade_card as TC
    expiry_label = getattr(config, "FUT_EXPIRY", "current")
    # one batched quote call covers every card's live entry check
    live_ltp = {} if demo else E.live_quote([p["symbol"] for p in sel["longs"][:5]])
    tabs = st.tabs([f"#{i+1}  {p['name']}" for i, p in enumerate(sel["longs"][:5])])
    for tab, p in zip(tabs, sel["longs"][:5]):
        with tab:
            closes = prices.get(p["symbol"]) or [p["close"]]
            chain = None
            if not demo:
                try:                     # real premiums when the market/chain is reachable
                    import option_chain as oc
                    chain, _spot = oc.fetch_live(p["symbol"])
                except Exception:
                    chain = None
            card = TC.build_card(p, closes, chain=chain, expiry_label=expiry_label,
                                 capital=cap_cfg, risk_pct=getattr(config, "RISK_PCT", 0.005))
            o = card.get("option", {})
            badge = {"BUY NOW": "🟢", "WAIT FOR PULLBACK": "🟡", "SKIP": "🔴"}.get(card["action"], "⚪")

            # --- one dense header line: verdict + freshness + why ---
            fresh = p.get("freshness", "?")
            age = p.get("age_bars", "?")
            sdate = p.get("signal_date") or "—"
            fcol = {"FRESH": "#3fb950", "NEW": "#d29922",
                    "AGEING": "#e07a4b", "STALE": "#f4516c"}.get(fresh, "#8b98a5")
            fnote = {"FRESH": "entry bar", "NEW": "still actionable",
                     "AGEING": "much of the move may be gone",
                     "STALE": "watch-only — do NOT chase"}.get(fresh, "")
            st.markdown(
                f"<div class='tick'>{badge} {card['action']} — {card['name']}"
                f"<span style='font-size:.72rem;font-weight:700;color:{fcol};"
                f"border:1px solid {fcol};border-radius:5px;padding:1px 6px;margin-left:8px;"
                f"vertical-align:middle'>{fresh} · {sdate} · {age}d · {fnote}</span></div>"
                f"<div class='sub'>{card['entry_note']}</div>",
                unsafe_allow_html=True)
            if fresh in ("AGEING", "STALE"):
                st.warning(f"Signal is {age} sessions old — {fnote}.")

            # --- LIVE entry check: can Aashish press buy right now, or not yet? ---
            ltp = live_ltp.get(p.get("symbol")) or (None if not demo else p["close"])
            chk = E.entry_check(card, ltp)
            if chk["state"] == "ENTER NOW":
                st.success(f"### ✅ You can enter now, Aashish\n{chk['line']}")
            elif chk["state"] == "WAIT":
                need = card["stock"]["entry"]
                st.info(f"### ⏳ Not yet, Aashish — wait for ₹{need}\n{chk['line']}\n\n"
                        f"**Do this now:** place a **limit BUY at ₹{need}** "
                        f"(valid for the day). The moment it fills, your stop and targets "
                        f"are already decided below.")
            elif chk["state"] == "SKIP":
                st.error(f"### ❌ Skip this one, Aashish\n{chk['line']}")
            elif chk["state"] == "MISSED":
                st.warning(f"### 🏃 Too late, Aashish\n{chk['line']}")
            else:
                st.caption(chk["line"])
            if ltp:
                gap = ltp - (card["stock"]["entry"] or ltp)
                q1, q2, q3 = st.columns(3)
                q1.metric("Live price", f"₹{ltp:,.2f}")
                q2.metric("Your limit", f"₹{card['stock']['entry']}",
                          f"{-gap:+.2f} away", delta_color="off")
                q3.metric("Verdict", chk["state"])

            a, b, c_, d = st.columns(4)
            if o:
                a.metric("Buy this", f"{card['name']} {o['strike']:g} {o['type']}",
                         help=f"expiry {o['expiry']} · slightly ITM (delta ~0.6) so it tracks "
                              f"the stock instead of bleeding theta")
                b.metric("Premium", f"₹{o['premium']}", o["premium_source"])
                c_.metric("Quantity", f"{card['size']['qty']}",
                          f"{card['size']['lots']} lot × {card['size']['lot']}")
                d.metric("Risk budget", f"₹{card['size']['risk_budget']:,}",
                         f"{getattr(config,'RISK_PCT',0.005)*100:.2f}% of capital")
            else:
                a.metric("Buy this", card["name"])
                b.metric("Entry", f"₹{card['stock']['entry']}")
                c_.metric("Quantity", f"{card['size']['qty']}")
                d.metric("Risk budget", f"₹{card['size']['risk_budget']:,}")

            e1, e2, e3 = st.columns(3)
            e1.metric("🛑 Exit if (stop)", f"₹{card['stock']['stop']}",
                      f"premium ₹{o['stop']}" if o else None, delta_color="off")
            e2.metric("💰 Book half (T1)", f"₹{card['stock']['t1']}",
                      f"premium ₹{o['t1']}  ·  R:R {card['stock']['rr1']}" if o
                      else f"R:R {card['stock']['rr1']}", delta_color="off")
            e3.metric("🏦 Book rest (T2)", f"₹{card['stock']['t2']}",
                      f"premium ₹{o['t2']}  ·  R:R {card['stock']['rr2']}" if o
                      else f"R:R {card['stock']['rr2']}", delta_color="off")

            # --- the trade drawn out: entry, stop, T1, T2, signal bar, live price ---
            if HAVE_PLOTLY:
                st.plotly_chart(
                    V.trade_chart(card, closes, dates=getattr(E, "LAST_DATES", None),
                                  point=p, ltp=ltp),
                    use_container_width=True,
                    key=f"trade_chart_{card['name']}")
                st.caption("Green block = reward to T2 · red block = risk to stop · "
                           "amber dashed = the bar the signal fired on")

            st.markdown("**The exit contract — decided now, followed without renegotiating**")
            st.table([{"When": lbl, "Do this": rule} for lbl, rule in card["rules"]])

            bits = card["confidence_bits"]
            st.caption(
                f"Why this name: rotation **{bits['rotation']}**"
                + ("  · just crossed in" if bits["crossed_in"] else "")
                + f"  · distance {bits['distance']:.2f}  · velocity {bits['velocity']:.2f}"
                + f"  · own trend {'UP' if bits['own_trend'] > 0 else 'not up'}"
                + (f"  · OI {bits['oi'].title()}" if bits.get("oi") else ""))

st.divider()

# ---------------- MAIN WINDOW: the RRG ----------------
main, side = st.columns([2.5, 1])
with main:
    if HAVE_PLOTLY:
        st.plotly_chart(
            V.rrg_figure(points, picks=picks,
                         title=f"{len(points)} F&O names vs NIFTY · {mode}"),
            use_container_width=True)
    else:
        st.warning("Interactive chart needs **plotly** — showing the static render. "
                   "Install it once with:  `python -m pip install plotly`")
        import rrg as rrg_static
        legacy = [{**p, "signal": p.get("signal"), "tail": p.get("tail", [(p["x"], p["y"])])}
                  for p in points]
        st.image(rrg_static.render_chart(legacy, "charts/app_rrg.png"))
    st.caption("Position = rotation · ▲ fresh buying / ▼ fresh selling · "
               "gold ring = candidate under your validated setup · hover any dot for detail")

with side:
    st.markdown("#### ▲ Candidates")
    if not sel["longs"]:
        st.info("No name passes the setup right now. Standing down is a position.")
    for p in sel["longs"]:
        tr = "↑" if p["abs_trend"] > 0 else ("↓" if p["abs_trend"] < 0 else "→")
        st.markdown(
            f"**{p['name']}**  ·  {p['quadrant'].title()}  \n"
            f"<span style='color:#8b98a5;font-size:12px'>dist {p['distance']:.2f} · "
            f"vel {p['velocity']:.2f} · head {p['heading']:.0f}° · own-trend {tr} "
            f"{p['abs_pct']:+.1f}%{' · ' + p['signal'].title() if p.get('signal') else ''}</span>",
            unsafe_allow_html=True)
    if sel["exits"]:
        st.markdown("#### ▼ Exit / avoid")
        st.caption(", ".join(p["name"] for p in sel["exits"][:18]))

# ---------------- auto-trader ----------------
st.divider()
st.markdown("### 🤖 Auto-trader")
book = ex._roll_day(ex.load_book())
cap = cap_cfg
b1, b2, b3, b4 = st.columns(4)
b1.metric("Cash", f"₹{book['cash']:,.0f}")
b2.metric("Open", len(book["positions"]))
b3.metric("Day P&L", f"₹{book.get('realized_pnl_today',0):+,.0f}")
b4.metric("Risk / trade", f"{getattr(config,'RISK_PCT',0.005)*100:.2f}%")

if ex.kill_switch_on():
    st.error("⛔ Kill switch is ON — no orders will be placed. Clear it in the sidebar to resume.")

col_a, col_b = st.columns([1, 3])
with col_a:
    stage = st.button("📋 Stage candidates through risk gate", use_container_width=True)
    fire = st.button(f"{'🔴 PLACE LIVE' if getattr(config,'LIVE_TRADING',False) else '🟢 Paper-fill'} candidates",
                     use_container_width=True, disabled=ex.kill_switch_on())

if stage or fire:
    if not sel["longs"]:
        st.warning("Nothing to stage — no candidates today.")
    open_syms = {p["symbol"] for p in book["positions"]}
    rows = []
    for p in sel["longs"]:
        entry = p["close"]
        stop = round(entry * (1 - getattr(config, "RRG_STOP_PCT", 0.04)), 2)
        target = round(entry * (1 + getattr(config, "RRG_TARGET_PCT", 0.10)), 2)
        trade = {"symbol": p["symbol"], "underlying": p["name"], "kind": "EQ",
                 "side": "BUY", "entry": entry, "stop": stop, "target": target,
                 "invalidation": stop, "margin_pct": 1.0,
                 "lot_size": getattr(config, "LOT_SIZES", {}).get(p["name"], 1)}
        port = {"capital": cap, "realized_pnl_today": book.get("realized_pnl_today", 0),
                "open_positions": book["positions"]}
        v = risk_gate.check(trade, port, config)
        placed = ""
        if fire and v["ok"] and trade["symbol"] not in open_syms:
            r = ex.place_order(trade, v["qty"], book)
            book = ex.load_book()
            placed = r["status"]
        rows.append({"Name": p["name"], "Entry": entry, "Stop": stop, "Target": target,
                     "Qty": v["qty"], "Gate": "PASS" if v["ok"] else "BLOCK",
                     "Why": "; ".join(v["failed"]) or (v["notes"][0] if v["notes"] else ""),
                     "Order": placed})
    st.dataframe(rows, use_container_width=True, hide_index=True)

if book["positions"]:
    st.markdown("#### Open positions")
    st.dataframe([{k: p.get(k) for k in ("symbol", "side", "qty", "entry", "stop", "target", "opened")}
                  for p in book["positions"]], use_container_width=True, hide_index=True)
if book.get("closed"):
    st.markdown("#### Blotter (closed)")
    st.dataframe([{k: p.get(k) for k in ("symbol", "qty", "entry", "exit", "exit_reason", "pnl")}
                  for p in book["closed"][-25:]], use_container_width=True, hide_index=True)

# ---------------- journal: did the calls actually work? ----------------
st.divider()
st.markdown("### 📚 Journal — what my own calls actually did")
import journal as J

jc1, jc2, jc3 = st.columns([1, 1, 2])
if jc1.button("📝 Log today's signals", use_container_width=True):
    for p in sel["longs"]:
        p["bar_index"] = len(prices.get(p["symbol"], [])) - 1
    import trade_card as TC2
    cards = {p["name"]: TC2.build_card(p, prices.get(p["symbol"], [p["close"]]))
             for p in sel["longs"]}
    n = J.log_signals(points, picks, "DEMO" if demo else "LIVE", cards)
    st.success(f"Logged {n} new signal(s).")
if jc2.button("✅ Grade outcomes", use_container_width=True):
    _e, changed = J.review(prices)
    st.success(f"Graded {changed} trade(s).")
if jc3.button("⏪ Build track record from history (backfill)", use_container_width=True):
    with st.spinner("Replaying history point-in-time…"):
        n = J.backfill(prices, bench, quiet=True)
        _e, changed = J.review(prices)
    st.success(f"Backfilled {n} historical signals · graded {changed}.")

entries = J.load()
L = J.lessons(entries)
o = L["overall"]
if o:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Graded trades", o["n"])
    m2.metric("Win rate", f"{o['win_rate']}%")
    m3.metric("Avg per trade", f"{o['avg_r']}R",
              help="R = multiples of the risk you took. +0.5R average with a 1R stop is a real edge.")
    m4.metric("Total", f"{o['total_r']}R")

    st.markdown("**Trade-by-trade — profit or loss**")
    rows = J.table(entries, limit=60)
    def _tint(v):
        s = str(v)
        if "WIN" in s:  return "color:#3fb950;font-weight:700"
        if "LOSS" in s: return "color:#f4516c;font-weight:700"
        return ""
    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        st.dataframe(df.style.map(_tint, subset=["Result"]),
                     use_container_width=True, hide_index=True)
    except Exception:
        st.table(rows)

    st.markdown("**Lessons — what to keep, what to stop**")
    for label, buckets in L["slices"].items():
        if not buckets:
            continue
        with st.expander(label, expanded=(label == "by freshness at entry")):
            st.table([{"bucket": k, "n": s["n"], "win %": s["win_rate"], "avg R": s["avg_r"]}
                      for k, s in sorted(buckets.items(), key=lambda kv: kv[1]["avg_r"], reverse=True)])
            for k, s in buckets.items():
                if s["avg_r"] < 0 and s["n"] >= 3:
                    st.error(f"STOP taking **{k}** — losing {abs(s['avg_r']):.2f}R over {s['n']} trades.")
                elif s["avg_r"] > 0.3 and s["n"] >= 3:
                    st.success(f"KEEP taking **{k}** — making {s['avg_r']:.2f}R over {s['n']} trades.")
else:
    st.info("No graded trades yet. Hit **Build track record from history** for an instant "
            "read, or log daily and grade as outcomes arrive.")

st.caption(f"{datetime.now(IST):%a %d %b %Y · %H:%M IST} · NOT financial advice · "
           "signals are inputs; the decision is yours")

# auto-refresh last, so the whole page has rendered before we sleep
if auto:
    time.sleep(300)
    st.cache_data.clear()
    st.session_state.loaded_at = datetime.now(IST)
    st.rerun()
