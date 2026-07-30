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
import rrg_view as V
import risk_gate
import execution as ex

IST = timezone(timedelta(hours=5, minutes=30))
st.set_page_config(page_title="Aashish Trading OS · RRG", page_icon="🎯", layout="wide")

try:
    import config
except ImportError:
    class _C:
        CAPITAL = 500000; LIVE_TRADING = False; DEFAULT_LOT = 50
        RRG_BENCHMARK = "NSE:NIFTY50-INDEX"
    config = _C()


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
k1.metric("Universe", len(points))
k2.metric("🟢 Leading", c["LEADING"])
k3.metric("🔵 Improving", c["IMPROVING"])
k4.metric("Candidates", len(picks))
k5.metric("Mode", mode.split(" ")[0])

# ---------------- MAIN WINDOW: the RRG ----------------
main, side = st.columns([2.5, 1])
with main:
    st.plotly_chart(
        V.rrg_figure(points, picks=picks,
                     title=f"{len(points)} F&O names vs NIFTY · {mode}"),
        use_container_width=True)
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
cap = float(getattr(config, "CAPITAL", 500000))
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

st.caption(f"{datetime.now(IST):%a %d %b %Y · %H:%M IST} · NOT financial advice · "
           "signals are inputs; the decision is yours")
