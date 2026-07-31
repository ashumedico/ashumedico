"""
desk.py  —  the dashboard: what the market is, what to buy, what it costs, how it went.

Built around the strategy that survived, not the one that looked good. The RRG that the
old cockpit put in the main window contributed -6.3% after costs and is not the headline
here; own-trend momentum is, because that is what the walk-forward kept.

Four questions, in the order they get asked:

    MAAHOL         is the tape worth trading at all
    AAJ KA TRADE   the exact ticket - contract, quantity, cost, stop, targets
    MAUKE          the names behind it, with the features that qualified or failed them
    SCORE          paper P&L against what the backtest claimed

    streamlit run desk.py

NOT financial advice.
"""
import os
import streamlit as st

st.set_page_config(page_title="Aashish Trading Desk", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
  .block-container {padding-top: 1.2rem; padding-bottom: 1rem;}
  [data-testid="stMetricValue"] {font-size: 1.4rem;}
  [data-testid="stMetricLabel"] {font-size: .75rem; color: #8b949e;}
  .tag {display:inline-block; padding:2px 9px; border-radius:10px;
        font-size:.72rem; font-weight:600; letter-spacing:.3px;}
  .ok   {background:#12341f; color:#3fb950;}
  .warn {background:#3a2e12; color:#d29922;}
  .bad  {background:#3d1519; color:#f85149;}
  .muted{background:#21262d; color:#8b949e;}
  h3 {margin-top: .4rem;}
</style>
""", unsafe_allow_html=True)

try:
    import config
except ImportError:
    class _C:
        CAPITAL = 200000
    config = _C()

DEMO = not os.path.exists(getattr(config, "TOKEN_FILE", "access_token.txt"))


def tag(text, kind="muted"):
    return f'<span class="tag {kind}">{text}</span>'


@st.cache_data(ttl=120, show_spinner="Data laa raha hoon...")
def load(demo):
    import rrg_engine as E
    if demo:
        pts, prices, bench = E.demo_points()
        return pts, prices, bench, {}, []
    pts, prices, bench = E.live_points(tail=6)
    return pts, prices, bench, E.LAST_BARS, E.LAST_DATES


# ------------------------------------------------------------------ header --
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("### Aashish Trading Desk")
with c2:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

mode_bits = []
bm = int(getattr(config, "BAR_MINUTES", 375))
mode_bits.append(tag(f"{'INTRADAY' if bm < 375 else 'SWING'} · {bm}min",
                     "ok" if bm < 375 else "warn"))
if DEMO:
    mode_bits.append(tag("DEMO DATA - koi asli signal nahi", "bad"))
try:
    import broker
    mode_bits.append(tag("LIVE ARMED", "bad") if broker.armed() and not broker.killed()
                     else tag("paper only", "muted"))
    if broker.killed():
        mode_bits.append(tag("KILL SWITCH ON", "bad"))
except Exception:
    pass
st.markdown(" ".join(mode_bits), unsafe_allow_html=True)

if not hasattr(config, "RESOLUTION") or not hasattr(config, "BAR_MINUTES"):
    st.error("RESOLUTION / BAR_MINUTES config mein set nahi hain - ye SWING chala raha "
             "hai, INTRADAY nahi.  Theek karo:  python configure.py --mode intraday")

try:
    pts, prices, bench, bars, dates = load(DEMO)
except Exception as e:      # noqa
    st.error(f"Data nahi aaya: {e}")
    st.info("Token expire ho gaya? Icon '1 - START DAY' chalao.")
    st.stop()

# ------------------------------------------------------------------ maahol --
st.markdown("#### Maahol")
try:
    import market_regime as MR
    reg = MR.Regime(prices, bench, dates=dates or None).at(len(bench))
    cols = st.columns(5)
    cols[0].metric("Regime", reg["state"], f"{reg['passed']}/{reg['of']} checks")
    if reg.get("breadth") is not None:
        cols[1].metric("Breadth", f"{reg['breadth']*100:.0f}%", "naam trend mein")
    if reg.get("drawdown") is not None:
        cols[2].metric("Index", f"-{reg['drawdown']*100:.1f}%", "high se")
    if reg.get("vol_ratio"):
        cols[3].metric("Vol", f"{reg['vol_ratio']:.2f}x", "normal ka")
    cols[4].metric("Universe", len(pts), "naam")
    if reg["state"] == "RISK-OFF":
        st.warning("Tape kharab hai. Neeche wala trade tab bhi dikhega - size chhota "
                   "rakho ya chhod do.")
except Exception as e:      # noqa
    st.caption(f"regime nahi bana: {e}")

# ------------------------------------------------------------ aaj ka trade --
import rrg_strategy as S, trade_card as TC

rule, params, _ = S.load_best()
sel = S.select(pts, rule, params, max_pos=8, prices=prices)
longs = sel["longs"]

st.markdown("#### Aaj ka trade")
if not longs:
    st.info("Koi naam setup pass nahi kar raha. Na lena bhi ek position hai.")
else:
    top = longs[0]
    closes = prices.get(top["symbol"]) or [top["close"]]
    card = TC.build_card(top, closes, expiry_label="—",
                         days_to_expiry=TC.min_days_for_thesis(),
                         capital=float(getattr(config, "CAPITAL", 200000)))
    o = card.get("option") or {}
    s = card["size"]
    k = st.columns([1.4, 1, 1, 1, 1, 1])
    k[0].metric(card["name"], f"{o.get('strike','?')} {o.get('type','')}",
                f"spot {card['spot']}")
    k[1].metric("Premium", o.get("premium", "?"), o.get("premium_source", ""))
    k[2].metric("Qty", s["qty"], f"{s['lots']} lot x {s['lot']}")
    k[3].metric("Lagega", f"Rs {s.get('cost_per_lot', 0) * s['lots']:,.0f}",
                f"{s.get('cost_pct', 0)}% capital")
    k[4].metric("Stop", card["stock"]["stop"])
    k[5].metric("T1 / T2", f"{card['stock']['t1']}", f"T2 {card['stock']['t2']}")
    for w in (o.get("premium_reject"), o.get("expiry_warning"),
              s.get("lot_warning"), s.get("cost_warning"), s.get("afford_note")):
        if w:
            st.warning(w)
    st.caption(card["entry_note"])

# ----------------------------------------------------------------- opportunities --
st.markdown("#### Mauke")
st.caption("Jo naam rule pass karte hain, aur unke features. Feature khaali = us naam ki "
           "history kam hai, aur khaali ko 'haan' nahi mana jaata.")
rows = []
for p in longs:
    f = p.get("feat") or {}
    rows.append({
        "naam": p["name"],
        "close": round(p.get("close", 0), 2),
        "trend %": p.get("abs_pct"),
        "VWAP": ("upar" if f.get("above_vwap") else "neeche") if f else "—",
        "RVOL": f.get("rvol", "—"),
        "squeeze": f.get("squeeze", "—"),
        "expansion": ("HAAN" if f.get("expanding") else "nahi") if f else "—",
        "R1 tak (ATR)": f.get("to_resistance_atr", "—"),
        "room": ("haan" if f.get("room_up") else "nahi") if f else "—",
        "OI": p.get("signal") or "—",
        "freshness": p.get("freshness"),
    })
if rows:
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.caption("koi naam nahi")

# ----------------------------------------------------------------- chart --
if longs:
    st.markdown("#### Chart")
    pick = st.selectbox("Naam", [p["name"] for p in longs], label_visibility="collapsed")
    p = next(x for x in longs if x["name"] == pick)
    sym = p["symbol"]
    b = (bars or {}).get(sym)
    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        if b:
            fig.add_candlestick(x=list(range(len(b))),
                                open=[r[1] for r in b], high=[r[2] for r in b],
                                low=[r[3] for r in b], close=[r[4] for r in b],
                                name=pick)
            import indicators as I
            vw = I.vwap_session(b, (dates or [""] * len(b))[-len(b):])
            fig.add_scatter(x=list(range(len(b))), y=vw, name="VWAP",
                            line=dict(color="#d29922", width=2))
        else:
            c = prices.get(sym, [])
            fig.add_scatter(x=list(range(len(c))), y=c, name=pick,
                            line=dict(color="#58a6ff"))
        f = p.get("feat") or {}
        for lvl, nm, col in ((f.get("r1"), "R1", "#f85149"), (f.get("s1"), "S1", "#3fb950")):
            if lvl:
                fig.add_hline(y=lvl, line_dash="dot", line_color=col,
                              annotation_text=nm, annotation_position="right")
        fig.update_layout(height=420, margin=dict(l=8, r=8, t=8, b=8),
                          xaxis_rangeslider_visible=False,
                          template="plotly_dark", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:      # noqa
        st.caption(f"chart nahi bana: {e}")

# ----------------------------------------------------------------- score --
st.markdown("#### Score")
try:
    import paper as P
    bk = P.load()
    closed, open_ = bk.get("closed", []), bk.get("open", [])
    if not closed and not open_:
        st.caption("Paper book khaali hai. Icon '4 - PAPER LIVE' chalao.")
    else:
        wins = [t for t in closed if t.get("pnl", 0) > 0]
        pnl = sum(t.get("pnl", 0) for t in closed)
        cap = float(getattr(config, "CAPITAL", 200000))
        m = st.columns(4)
        m[0].metric("Khule", len(open_))
        m[1].metric("Band", len(closed),
                    f"{100*len(wins)/len(closed):.0f}% jeete" if closed else "")
        m[2].metric("P&L", f"Rs {pnl:+,.0f}", f"{pnl/cap*100:+.1f}% capital")
        exp = P.expectation()
        if exp and closed:
            band = P.binomial_band(len(closed), exp["win_rate"] / 100.0)
            m[3].metric("Backtest kehta tha", f"{exp['win_rate']}%",
                        f"{band[0]:.0f}-{band[1]:.0f} jeet expected")
            if band[0] <= len(wins) <= band[1]:
                st.caption("Normal range ke andar - na proof, na problem. Chalate raho.")
        if closed:
            st.dataframe([{k: t.get(k) for k in
                           ("name", "premium_in", "premium_out", "reason", "pnl")}
                          for t in closed[-15:]],
                         use_container_width=True, hide_index=True)
except Exception as e:      # noqa
    st.caption(f"paper book nahi mila: {e}")

st.caption("NOT financial advice. Signals are inputs; the decision is yours.")
