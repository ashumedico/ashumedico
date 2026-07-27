"""
app.py  —  NSE F&O OI-Change Scanner dashboard (Streamlit, localhost:8501).
This is the web UI version of scanner.py — matches your original localhost:8501 setup.

    pip install streamlit fyers-apiv3
    streamlit run app.py            # opens http://localhost:8501
    (toggle "Dry run" in the sidebar to demo with no Fyers/creds/market)

NOT financial advice. Signals are inputs; every trade decision is yours.
"""
import time
import pandas as pd
import streamlit as st

import scanner  # reuse the exact scan logic

SIG_COLOR = {
    "LONG BUILDUP":   "#1f9d63",   # bullish green
    "SHORT COVERING": "#3fae6a",   # bullish green (lighter)
    "SHORT BUILDUP":  "#d1495b",   # bearish red
    "LONG UNWINDING": "#e07a4b",   # bearish orange
}

st.set_page_config(page_title="NSE F&O OI-Change Scanner", page_icon="📊", layout="wide")

st.markdown("## 📊 NSE F&O OI-Change Scanner")
st.caption("Price × Open-Interest buildup matrix · Fyers · not financial advice")

with st.sidebar:
    st.header("Controls")
    dry = st.toggle("Dry run (no Fyers)", value=True,
                    help="Synthetic data to preview the dashboard without live keys.")
    min_oi = st.slider("Min OI change %", 0.0, 30.0, float(scanner.config.MIN_OI_CHANGE_PCT), 0.5)
    auto = st.toggle("Auto-refresh", value=False)
    every = st.number_input("Refresh every (sec)", 30, 600, 300, 30)
    if st.button("🔄 Scan now", use_container_width=True):
        st.rerun()

scanner.config.MIN_OI_CHANGE_PCT = min_oi

# run one scan (dry uses synthetic; live compares to the day-open OI baseline)
if dry:
    prev, curr = scanner.fetch_dry()
else:
    try:
        curr = scanner.fetch_live()
        prev = scanner.load_baseline()
        if prev is None:          # first scan of the day -> set reference
            scanner.save_baseline(curr); prev = curr
    except scanner.AuthError as e:
        st.error(str(e)); st.stop()
    except Exception as e:        # noqa
        st.error(f"Fyers error: {e}"); st.stop()

rows = []
for sym, now in curr.items():
    old = prev.get(sym)
    if not old or not old.get("oi"):
        continue
    oi_chg = (now["oi"] - old["oi"]) / old["oi"] * 100
    px_chg = (now["ltp"] - old["ltp"]) / old["ltp"] * 100 if old["ltp"] else 0
    if abs(oi_chg) < min_oi:
        continue
    rows.append({"Symbol": sym.split(":")[-1], "Price %": round(px_chg, 2),
                 "OI %": round(oi_chg, 2), "Signal": scanner.classify(px_chg, oi_chg)})
rows.sort(key=lambda r: abs(r["OI %"]), reverse=True)

# summary tiles
c1, c2, c3, c4 = st.columns(4)
counts = {k: sum(1 for r in rows if r["Signal"] == k) for k in SIG_COLOR}
c1.metric("Long Buildup", counts["LONG BUILDUP"])
c2.metric("Short Buildup", counts["SHORT BUILDUP"])
c3.metric("Short Covering", counts["SHORT COVERING"])
c4.metric("Long Unwinding", counts["LONG UNWINDING"])

st.caption(f"Last scan: {time.strftime('%Y-%m-%d %H:%M:%S')}  ·  {len(rows)} names over {min_oi:.1f}% OI change")

if rows:
    df = pd.DataFrame(rows)
    def color_sig(v):
        return f"color:{SIG_COLOR.get(v,'#888')};font-weight:700"
    st.dataframe(
        df.style.map(color_sig, subset=["Signal"]).format({"Price %": "{:+.2f}", "OI %": "{:+.2f}"}),
        use_container_width=True, hide_index=True,
    )
else:
    st.info(f"No names crossed the {min_oi:.1f}% OI-change threshold.")

# ---------------- Option chain (the piece futures-only was missing) ----------------
st.divider()
st.markdown("### 🔗 Option chain — PCR · Max Pain · walls")
import option_chain as oc
default_u = "NSE:NIFTY50-INDEX"
u = st.text_input("Underlying", default_u, help="Any F&O underlying, e.g. NSE:RELIANCE-EQ")
try:
    ch, spot = oc.fetch_dry(u) if dry else oc.fetch_live(u)
    m = oc.analyse(ch, spot)
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Spot", m["spot"])
    b2.metric("PCR", m["pcr"], m["bias"].split(" ")[0])
    b3.metric("Max Pain", m["max_pain"])
    b4.metric("Support → Resist", f'{m["support"]} → {m["resistance"]}')
    if m["call_writing"]:
        st.markdown(f"🔴 **Call writing** at `{m['call_writing']['strike']}` (+{m['call_writing']['oi_chg']:,} OI) — resistance building")
    if m["put_writing"]:
        st.markdown(f"🟢 **Put writing** at `{m['put_writing']['strike']}` (+{m['put_writing']['oi_chg']:,} OI) — support building")
except Exception as e:  # noqa
    st.info(f"Option chain unavailable: {e}")

# ---------------- Revalidated trade ideas (3-layer confluence) ----------------
st.divider()
st.markdown("### 🎯 Revalidated signals — 1 CE · 1 PE · 1 Future")
st.caption("OI buildup × option chain × chart action (support/resistance + 60%-body breakout)")
import signal_engine as se
import charts as ch
try:
    verdicts = se.dry_verdicts() if dry else se.live_verdicts()
    ideas = se.build_ideas(verdicts) if verdicts else {}
    if not ideas:
        st.info("No qualifying confluence right now.")
    else:
        cols = st.columns(3)
        for col, key in zip(cols, ("CE", "PE", "FUT")):
            idea = ideas.get(key)
            with col:
                if not idea:
                    st.caption(f"No {key} today."); continue
                t = idea["trade"]
                st.markdown(f"**{idea['kind']}** · {idea['underlying'].split(':')[-1]} "
                            f"{idea.get('strike','')}")
                st.markdown(f"{'🟢' if idea['bias']=='BULLISH' else '🔴'} "
                            f"**{idea['bias']} · {idea['confidence']}%**")
                st.markdown(f"Entry `{t['entry']}` · Stop `{t['stop']}` · "
                            f"Target `{t['target']}` · R:R `{t['rr']}`")
                st.image(ch.render_idea(idea, f"charts/dash_{key}.png"))
except Exception as e:  # noqa
    st.info(f"Signals unavailable: {e}")

# ---------------- Relative Rotation Graph ----------------
st.divider()
st.markdown("### 🔄 Relative Rotation Graph — leading / lagging vs NIFTY")
import rrg
try:
    if dry:
        rprices, rbench = rrg.fetch_dry()
    else:
        rprices, rbench = rrg.fetch_prices_live(
            getattr(scanner.config, "UNIVERSE", []),
            getattr(scanner.config, "RRG_BENCHMARK", "NSE:NIFTY50-INDEX"))
    if rprices:
        pts = rrg.analyse(rprices, rbench)
        grid = rrg.table_2x2(pts)
        st.image(rrg.render_chart(pts, "charts/rrg.png"))
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("🟢 Leading", ", ".join(grid["LEADING"]) or "—")
        g2.metric("🟡 Weakening", ", ".join(grid["WEAKENING"]) or "—")
        g3.metric("🔵 Improving", ", ".join(grid["IMPROVING"]) or "—")
        g4.metric("🔴 Lagging", ", ".join(grid["LAGGING"]) or "—")
    else:
        st.info("RRG needs price data (Fyers token + UNIVERSE).")
except Exception as e:  # noqa
    st.info(f"RRG unavailable: {e}")

if auto and not dry:
    time.sleep(every)
    st.rerun()
