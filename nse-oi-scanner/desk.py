"""
desk.py  —  the website: what the market is, what to buy, what it costs, how it went.

Laid out the way the Chart Action Analyzer reference is laid out - a left rail you choose
from, a status banner that says in one line whether the trend is identified, a ribbon with
the live numbers, the chart with its levels drawn and named, and a scenario block that
states what would have to happen for each of the three outcomes.

The difference from the reference is that nothing here is illustrative. Every level, every
premium, every scenario threshold is computed from the bars that were actually fetched. A
scenario is an "if X then Y" over real levels - it is not a prediction, and the code will
say "not enough history" rather than draw a line it cannot justify.

Built around the strategy that survived, not the one that looked good. The RRG that the old
cockpit put in the main window contributed -6.3% after costs; it is context here, not the
headline. Own-trend momentum is the headline, because that is what the walk-forward kept.

    streamlit run desk.py

NOT financial advice.
"""
import os
import streamlit as st

st.set_page_config(page_title="AASHISH · Trading Desk", layout="wide",
                   page_icon="📈", initial_sidebar_state="expanded")

st.markdown("""
<style>
  .block-container {padding-top: 1rem; padding-bottom: 4.5rem; max-width: 1500px;}
  [data-testid="stMetricValue"] {font-size: 1.35rem;}
  [data-testid="stMetricLabel"] {font-size: .72rem; color: #8b949e; letter-spacing:.4px;
                                 text-transform: uppercase;}

  /* the pill tags used for mode / state */
  .tag {display:inline-block; padding:3px 10px; border-radius:12px; margin-right:6px;
        font-size:.71rem; font-weight:700; letter-spacing:.4px;}
  .ok   {background:#0d2b18; color:#3fb950; border:1px solid #1c5c31;}
  .warn {background:#3a2e12; color:#d29922; border:1px solid #6b5316;}
  .bad  {background:#3d1519; color:#f85149; border:1px solid #7a2429;}
  .muted{background:#161b22; color:#8b949e; border:1px solid #21262d;}

  /* green status banner - the one-line "is this thing trending" read */
  .banner {padding:11px 16px; border-radius:8px; font-weight:700; font-size:.92rem;
           margin:.35rem 0 .8rem 0; display:flex; align-items:center; gap:10px;}
  .banner-ok  {background:#0d2b18; color:#56d364; border:1px solid #1c5c31;}
  .banner-mid {background:#33280f; color:#e3b341; border:1px solid #6b5316;}
  .banner-bad {background:#3d1519; color:#ff7b72; border:1px solid #7a2429;}

  /* blue ribbon carrying the live numbers for the selected name */
  .ribbon {background:linear-gradient(90deg,#0d2847 0%,#123a63 60%,#0d2847 100%);
           border:1px solid #1f4d80; border-radius:8px; padding:10px 16px;
           display:flex; flex-wrap:wrap; gap:26px; align-items:center; margin-bottom:.9rem;}
  .rb-k {color:#7fb6ee; font-size:.66rem; letter-spacing:.6px; text-transform:uppercase;}
  .rb-v {color:#e6edf3; font-size:1.02rem; font-weight:700;}
  .up   {color:#56d364;} .dn {color:#ff7b72;}

  /* the "SCENARIO ANALYSIS [...] — rules used" strip */
  .scen {background:#121821; border-left:4px solid #58a6ff; border-radius:6px;
         padding:9px 14px; font-size:.8rem; color:#adbac7; margin:.2rem 0 .7rem 0;
         font-family: ui-monospace, SFMono-Regular, Menlo, monospace;}

  .sec {font-size:.72rem; letter-spacing:1.4px; text-transform:uppercase; color:#6e7781;
        border-bottom:1px solid #21262d; padding-bottom:5px; margin:1.4rem 0 .7rem 0;}

  /* the wordmark - his desk, with his name on it */
  .mark {display:flex; align-items:baseline; gap:12px; margin-bottom:.1rem;}
  .mark-name {font-size:2.05rem; font-weight:800; letter-spacing:5px;
              background:linear-gradient(90deg,#3fb950 0%,#58a6ff 55%,#d29922 100%);
              -webkit-background-clip:text; background-clip:text; color:transparent;}
  .mark-sub {font-size:.82rem; color:#6e7781; letter-spacing:2.6px;
             text-transform:uppercase;}

  /* the disclaimer the reference keeps nailed to the bottom, and so does this */
  .disclaim {position:fixed; left:0; right:0; bottom:0; z-index:99;
             background:#3d1519; color:#ff9a93; border-top:1px solid #7a2429;
             text-align:center; padding:7px 10px; font-size:.74rem; font-weight:600;}
  section[data-testid="stSidebar"] {border-right:1px solid #21262d;}
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
    else:
        pts, prices, bench = E.live_points(tail=6)
    return pts, prices, bench, E.LAST_BARS, E.LAST_DATES


@st.cache_data(ttl=3600)
def watch_map():
    """{SYMBOL: (trigger, guidance)} for the F&O-tradeable watchlist names. Display only -
    a fundamental trigger is a reason a name is interesting, never a reason this candle
    is the one."""
    try:
        import watchlist as W
        return {r["symbol"]: (r["trigger"], r["guidance"])
                for r in W.resolve() if r["fno"]}
    except Exception:
        return {}


def touches(bars, level, atr):
    """How many bars came within a quarter-ATR of a level. A line nobody has traded
    against is a line drawn on a chart, not a level."""
    if not bars or not level or not atr:
        return 0
    tol = atr * 0.25
    return sum(1 for b in bars if b[3] - tol <= level <= b[2] + tol)


# ================================================================== sidebar ==
with st.sidebar:
    st.markdown("### AASHISH TRADING OS")
    if st.button("↻  Refresh data", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.markdown('<div class="sec">Segment</div>', unsafe_allow_html=True)
    st.radio("Segment", ["NSE F&O — stock options"], index=0, label_visibility="collapsed")
    st.caption("Index, commodity aur global feed is system mein wired nahi hai. "
               "Jo nahi hai, uska button nahi banaya — khaali button jhooth hai.")

    st.markdown('<div class="sec">Mode</div>', unsafe_allow_html=True)
    bits = []
    bm = int(getattr(config, "BAR_MINUTES", 375))
    bits.append(tag(f"{'INTRADAY' if bm < 375 else 'SWING'} · {bm}min",
                    "ok" if bm < 375 else "warn"))
    if DEMO:
        bits.append(tag("DEMO DATA", "bad"))
    try:
        import broker
        bits.append(tag("LIVE ARMED", "bad") if broker.armed() and not broker.killed()
                    else tag("paper only", "muted"))
        if broker.killed():
            bits.append(tag("KILL SWITCH", "bad"))
    except Exception:
        pass
    st.markdown(" ".join(bits), unsafe_allow_html=True)
    st.caption(f"Capital Rs {float(getattr(config, 'CAPITAL', 200000)):,.0f} · "
               f"{int(getattr(config, 'LOTS_PER_TRADE', 1) or 1)} lot fixed · ATM only")

# ------------------------------------------------------------------- header --
st.markdown('<div class="mark"><span class="mark-name">AASHISH</span>'
            '<span class="mark-sub">Trading Desk · Chart Action</span></div>',
            unsafe_allow_html=True)
st.caption("Support/resistance · price action · volume · buildup — one page, "
           "computed live, nothing illustrative.")

if not hasattr(config, "RESOLUTION") or not hasattr(config, "BAR_MINUTES"):
    st.error("RESOLUTION / BAR_MINUTES config mein set nahi hain — ye SWING chala raha hai, "
             "INTRADAY nahi.  Theek karo:  python configure.py --mode intraday")

if DEMO:
    st.warning("Token nahi mila — ye DEMO data hai. Koi bhi number asli nahi. "
               "Icon '1 - START DAY' chala ke login kar.")

try:
    pts, prices, bench, bars, dates = load(DEMO)
except Exception as e:      # noqa
    st.error(f"Data nahi aaya: {e}")
    st.info("Token expire ho gaya? Icon '1 - START DAY' chalao.")
    st.stop()

# ================================================================== regime ==
reg = None
try:
    import market_regime as MR
    reg = MR.Regime(prices, bench, dates=dates or None).at(len(bench))
except Exception as e:      # noqa
    st.caption(f"regime nahi bana: {e}")

# ------------------------------------------------------- candidates + picks --
import rrg_strategy as S, trade_card as TC

rule, params, _ = S.load_best()
sel = S.select(pts, rule, params, max_pos=8, prices=prices)
longs = sel["longs"]

with st.sidebar:
    st.markdown('<div class="sec">Naam</div>', unsafe_allow_html=True)
    names = [p["name"] for p in longs] or [p["name"] for p in pts[:25]]
    pick = st.selectbox("Naam", names, label_visibility="collapsed") if names else None
    st.caption(f"{len(longs)} naam rule pass · {len(pts)} universe mein")

P = next((x for x in (longs or pts) if x["name"] == pick), None)
F = (P or {}).get("feat") or {}
SYM = (P or {}).get("symbol")
BARS = (bars or {}).get(SYM) or []

# ============================================================ status banner ==
# The reference's green bar. Two things have to be true for it to go green: the tape is
# tradeable, and the selected name has a direction. Either one missing and it is not green.
struct = F.get("trend_struct")
regime_state = (reg or {}).get("state", "UNKNOWN")
trend_known = struct in ("HH-HL", "LH-LL") or bool(F.get("expanding"))
if regime_state == "RISK-ON" and trend_known:
    cls, msg = "banner-ok", f"{regime_state} · {pick or '—'} {struct or 'expansion bar'} — Trend Identified ✓"
elif trend_known or regime_state == "RISK-ON":
    cls, msg = "banner-mid", f"{regime_state} · {pick or '—'} {struct or 'no structure'} — Partial: ek taraf confirm, doosri nahi"
else:
    cls, msg = "banner-bad", f"{regime_state} · {pick or '—'} — Koi trend nahi. Na lena bhi ek position hai."
if F.get("feature_error"):
    cls, msg = "banner-bad", f"Feature calculation fail: {F['feature_error']}"
st.markdown(f'<div class="banner {cls}">{msg}</div>', unsafe_allow_html=True)

# ================================================================== ribbon ==
if P:
    px = P.get("close", 0)
    chg = P.get("abs_pct")
    rv = F.get("rvol")
    vw = F.get("above_vwap")
    cells = [
        ("Naam", pick),
        ("Spot", f"{px:,.2f}"),
        ("Trend", f'<span class="{"up" if (chg or 0) >= 0 else "dn"}">{chg:+.2f}%</span>'
         if chg is not None else "—"),
        ("vs VWAP", f'<span class="{"up" if vw else "dn"}">{"UPAR" if vw else "NEECHE"}</span>'
         if F else "—"),
        ("RVOL", f"{rv:.2f}x" if rv else "—"),
        ("ATR", F.get("atr", "—")),
        ("Squeeze", f'{F.get("squeeze","—")}{" · COILED" if F.get("coiled") else ""}'),
        ("Expansion", '<span class="up">HAAN</span>' if F.get("expanding") else "nahi"),
    ]
    st.markdown('<div class="ribbon">' + "".join(
        f'<div><div class="rb-k">{k}</div><div class="rb-v">{v}</div></div>'
        for k, v in cells) + '</div>', unsafe_allow_html=True)

# ================================================================== maahol ==
st.markdown('<div class="sec">Maahol — is the tape worth trading</div>', unsafe_allow_html=True)
if reg:
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
        st.warning("Tape kharab hai. Neeche wala trade tab bhi dikhega — size chhota rakho "
                   "ya chhod do.")

# ============================================================ aaj ka trade ==
st.markdown('<div class="sec">Aaj ka trade — the ticket</div>', unsafe_allow_html=True)
card = None
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

# =================================================================== chart ==
st.markdown('<div class="sec">Chart — levels, and how often they held</div>',
            unsafe_allow_html=True)
if P:
    LV = [("R2", F.get("r2"), "#f85149"), ("R1", F.get("r1"), "#f85149"),
          ("S1", F.get("s1"), "#3fb950"), ("S2", F.get("s2"), "#3fb950")]
    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        if BARS:
            fig.add_candlestick(x=list(range(len(BARS))),
                                open=[r[1] for r in BARS], high=[r[2] for r in BARS],
                                low=[r[3] for r in BARS], close=[r[4] for r in BARS],
                                name=pick,
                                increasing_line_color="#3fb950",
                                decreasing_line_color="#f85149")
            import indicators as I
            vwl = I.vwap_session(BARS, (dates or [""] * len(BARS))[-len(BARS):])
            fig.add_scatter(x=list(range(len(BARS))), y=vwl, name="VWAP",
                            line=dict(color="#d29922", width=2))
        else:
            c = prices.get(SYM, [])
            fig.add_scatter(x=list(range(len(c))), y=c, name=pick,
                            line=dict(color="#58a6ff"))
            st.caption("OHLCV bars nahi mile — sirf close line. Levels tab bhi asli hain.")
        atr = F.get("atr")
        for nm, lvl, col in LV:
            if not lvl:
                continue
            n = touches(BARS, lvl, atr)
            fig.add_hline(y=lvl, line_dash="dot", line_color=col, line_width=1.4,
                          annotation_text=f"  {nm} {lvl}" + (f" · {n}x" if n else ""),
                          annotation_position="right",
                          annotation_font=dict(color=col, size=11))
        if card and card["name"] == pick:
            for nm, lvl, col in (("STOP", card["stock"]["stop"], "#ff7b72"),
                                 ("T1", card["stock"]["t1"], "#56d364"),
                                 ("T2", card["stock"]["t2"], "#56d364")):
                fig.add_hline(y=lvl, line_dash="dash", line_color=col, line_width=1,
                              annotation_text=f"  {nm}", annotation_position="left",
                              annotation_font=dict(color=col, size=10))
        fig.update_layout(height=440, margin=dict(l=8, r=70, t=10, b=8),
                          xaxis_rangeslider_visible=False, template="plotly_dark",
                          paper_bgcolor="#0b0f14", plot_bgcolor="#0b0f14",
                          showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:      # noqa
        st.caption(f"chart nahi bana: {e}")

    # ------------------------------------------------------------ scenarios --
    st.markdown(
        f'<div class="scen">SCENARIO ANALYSIS [{pick} · NSE F&O] — support/resistance '
        f'+ 3-5 candle continuation + 60% body breakout rule</div>',
        unsafe_allow_html=True)

    r1, r2, s1, s2 = F.get("r1"), F.get("r2"), F.get("s1"), F.get("s2")
    if not (r1 and s1):
        st.caption("Levels nahi bane — is naam ki history kam hai. Scenario bhi nahi banega.")
    else:
        which = st.radio("Scenario", ["Bullish", "Sideways", "Bearish"],
                         horizontal=True, label_visibility="collapsed")
        cont = f"{F.get('cont_up', 0)}/5 up-candles"
        if which == "Bullish":
            st.success(
                f"**Agar** {pick} {r1} ke upar band ho **60% body candle** se, RVOL "
                f"{F.get('rvol','—')}x ke saath → **target {r2}**, **invalidation {s1}** "
                f"(us se neeche gaya toh thesis khatam, flatten). Abhi: {cont}, "
                f"{'expansion bar HAAN' if F.get('expanding') else 'abhi expansion bar nahi'}."
                + ("" if F.get("room_up") else
                   f"  ⚠ R1 sirf {F.get('to_resistance_atr')} ATR door hai — upar jagah kam hai."))
        elif which == "Bearish":
            st.error(
                f"**Agar** {pick} {s1} tod de 60% body se → **target {s2}**, "
                f"**invalidation {r1}**. Ye system long-only hai — is scenario mein trade "
                f"nahi, exit hai. Khuli position ho toh stop {card['stock']['stop'] if card and card['name']==pick else s1} pe.")
        else:
            st.info(
                f"**Agar** {pick} {s1}–{r1} ke beech rahe → koi trade nahi. "
                f"Squeeze {F.get('squeeze','—')}"
                f"{' (COILED — expansion bar ka intezaar)' if F.get('coiled') else ''}. "
                f"Range mein premium theta khata hai; buyer ke liye ye sabse mehnga scenario hai.")
        st.caption("Ye 'if X then Y' hai, prediction nahi. Levels bars se bane hain, "
                   "invalidation pehle se likha hai.")

# =================================================================== mauke ==
st.markdown('<div class="sec">Mauke — jo rule pass karte hain</div>', unsafe_allow_html=True)
st.caption("Feature khaali = us naam ki history kam hai, aur khaali ko 'haan' nahi mana jaata. "
           "**thesis** = Q1 watchlist ka fundamental trigger, agar wo naam us list pe hai — "
           "ye ek bias hai, signal nahi, aur iska koi backtest nahi hai.")
WM = watch_map()
rows = []
for p in longs:
    f = p.get("feat") or {}
    rows.append({
        "naam": p["name"],
        "thesis": (WM.get(p["name"]) or ("", ""))[0] or "—",
        "close": round(p.get("close", 0), 2),
        "trend %": p.get("abs_pct"),
        "VWAP": ("upar" if f.get("above_vwap") else "neeche") if f else "—",
        "RVOL": f.get("rvol", "—"),
        "squeeze": f.get("squeeze", "—"),
        "expansion": ("HAAN" if f.get("expanding") else "nahi") if f else "—",
        "structure": f.get("trend_struct", "—"),
        "R1 tak (ATR)": f.get("to_resistance_atr", "—"),
        "room": ("haan" if f.get("room_up") else "nahi") if f else "—",
        "OI": p.get("signal") or "—",
        "freshness": p.get("freshness"),
    })
if rows:
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.caption("koi naam nahi")

# =================================================================== score ==
st.markdown('<div class="sec">Score — paper vs what the backtest claimed</div>',
            unsafe_allow_html=True)
try:
    import paper as PB
    bk = PB.load()
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
        exp = PB.expectation()
        if exp and closed:
            band = PB.binomial_band(len(closed), exp["win_rate"] / 100.0)
            m[3].metric("Backtest kehta tha", f"{exp['win_rate']}%",
                        f"{band[0]:.0f}-{band[1]:.0f} jeet expected")
            if band[0] <= len(wins) <= band[1]:
                st.caption("Normal range ke andar — na proof, na problem. Chalate raho.")
        if closed:
            st.dataframe([{k: t.get(k) for k in
                           ("name", "premium_in", "premium_out", "reason", "pnl")}
                          for t in closed[-15:]],
                         use_container_width=True, hide_index=True)
except Exception as e:      # noqa
    st.caption(f"paper book nahi mila: {e}")

st.markdown(
    '<div class="disclaim">NOT FINANCIAL ADVICE — signals are inputs, the decision is yours. '
    'Options can lose 100% of the premium. Levels are computed from past bars and can fail.</div>',
    unsafe_allow_html=True)
