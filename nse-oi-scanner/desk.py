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

  /* --- command deck: heatmap tiles, radar badges, trade cards --- */
  .hm {border-radius:8px; padding:10px 13px; margin-bottom:8px; position:relative;
       border:1px solid #21262d;}
  .hm-n {font-size:.68rem; letter-spacing:1.1px; color:#c9d1d9; text-transform:uppercase;
         font-weight:700;}
  .hm-p {font-size:1.5rem; font-weight:800; font-family:ui-monospace,Consolas,monospace;}
  .hm-r {position:absolute; top:8px; right:11px; font-size:.62rem; color:#6e7781;}
  .hm-t {font-size:.6rem; letter-spacing:1.4px; font-weight:800;}

  .badge {display:inline-block; padding:5px 12px; border-radius:6px; margin:0 7px 7px 0;
          font-size:.7rem; font-weight:800; letter-spacing:.7px;}
  .b-up   {background:#0d2b18; color:#56d364; border:1px solid #1c5c31;}
  .b-dn   {background:#3d1519; color:#ff7b72; border:1px solid #7a2429;}
  .b-turn {background:#33280f; color:#e3b341; border:1px solid #6b5316;}
  .b-bnc  {background:#0c2b3a; color:#56c8d3; border:1px solid #1b5566;}
  .b-none {background:#161b22; color:#8b949e; border:1px solid #21262d;}

  .card {background:#121821; border:1px solid #21262d; border-left:4px solid #3fb950;
         border-radius:8px; padding:11px 15px; margin-bottom:9px;}
  .card-h {display:flex; align-items:center; gap:10px; margin-bottom:6px;}
  .side {font-size:.64rem; font-weight:800; letter-spacing:1px; padding:3px 9px;
         border-radius:4px; background:#0d2b18; color:#56d364;}
  .grade {font-size:.72rem; font-weight:800; color:#e3b341;}
  .card-n {font-size:1.02rem; font-weight:800; color:#e6edf3; letter-spacing:.5px;}
  .lv {display:flex; flex-wrap:wrap; gap:20px; font-family:ui-monospace,Consolas,monospace;
       font-size:.82rem;}
  .lv b {color:#6e7781; font-weight:600; font-size:.66rem; letter-spacing:.6px;
         text-transform:uppercase; display:block;}

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


# --------------------------------------------------------------- charting --
# WHERE THE CHART COMES FROM
#
# StockCharts.com is a fine site and it is not usable here: it covers US and Canadian
# listings, not NSE India equities, so an NSE F&O name would come back empty. Wiring a
# source that returns nothing for the names he actually trades would look like a feature
# and behave like a dead link.
#
# So the floating window draws OUR data - the same bars the signals were computed from,
# with R1/R2/S1/S2, VWAP and this trade's stop and targets already on it. No external site
# can draw those, because they do not have the levels this system computed.
#
# For the things a full charting site does better - drawing tools, multi-year history,
# indicators we deliberately deleted - there are links out. TradingView carries every NSE
# name; so does Fyers, which is where the order goes anyway.
EXTERNAL_CHARTS = [
    ("TradingView", "https://www.tradingview.com/chart/?symbol=NSE%3A{name}"),
    ("Fyers", "https://trade.fyers.in/?symbol=NSE:{name}-EQ"),
    ("NSE India", "https://www.nseindia.com/get-quotes/equity?symbol={name}"),
]


def touches(bars, level, atr):
    """How many bars came within a quarter-ATR of a level. A line nobody has traded
    against is a line drawn on a chart, not a level."""
    if not bars or not level or not atr:
        return 0
    tol = atr * 0.25
    return sum(1 for b in bars if b[3] - tol <= level <= b[2] + tol)


def make_fig(name, closes, bars_, dates_, feat, plan=None, height=440):
    """One chart builder, used by the page and by the floating window alike.

    Two copies of this would drift - the inline one would get the trade levels and the
    popup would quietly keep showing a chart without them, and nobody would notice until
    a stop looked wrong on one screen and right on the other.
    """
    import plotly.graph_objects as go
    feat = feat or {}
    fig = go.Figure()
    if bars_:
        fig.add_candlestick(x=list(range(len(bars_))),
                            open=[r[1] for r in bars_], high=[r[2] for r in bars_],
                            low=[r[3] for r in bars_], close=[r[4] for r in bars_],
                            name=name, increasing_line_color="#3fb950",
                            decreasing_line_color="#f85149")
        try:
            import indicators as I
            vwl = I.vwap_session(bars_, (dates_ or [""] * len(bars_))[-len(bars_):])
            fig.add_scatter(x=list(range(len(bars_))), y=vwl, name="VWAP",
                            line=dict(color="#d29922", width=2))
        except Exception:
            pass
    else:
        c = closes or []
        fig.add_scatter(x=list(range(len(c))), y=c, name=name,
                        line=dict(color="#58a6ff"))
    atr = feat.get("atr")
    for nm, lvl, col in (("R2", feat.get("r2"), "#f85149"),
                         ("R1", feat.get("r1"), "#f85149"),
                         ("S1", feat.get("s1"), "#3fb950"),
                         ("S2", feat.get("s2"), "#3fb950")):
        if not lvl:
            continue
        n = touches(bars_, lvl, atr)
        fig.add_hline(y=lvl, line_dash="dot", line_color=col, line_width=1.4,
                      annotation_text=f"  {nm} {lvl}" + (f" · {n}x" if n else ""),
                      annotation_position="right",
                      annotation_font=dict(color=col, size=11))
    for nm, lvl, col in (plan or []):
        if lvl:
            fig.add_hline(y=lvl, line_dash="dash", line_color=col, line_width=1,
                          annotation_text=f"  {nm}", annotation_position="left",
                          annotation_font=dict(color=col, size=10))
    fig.update_layout(height=height, margin=dict(l=8, r=70, t=10, b=8),
                      xaxis_rangeslider_visible=False, template="plotly_dark",
                      paper_bgcolor="#0b0f14", plot_bgcolor="#0b0f14",
                      showlegend=False)
    return fig


@st.dialog("Chart", width="large")
def chart_window(name):
    """The floating window. Opens over whatever you were reading, on any name, anywhere.

    It draws the system's own bars because those are the only ones that carry the levels
    this system computed - R1/R2/S1/S2, the session VWAP, and the stop and targets of the
    live ticket if this name has one. An external site can draw a prettier candle and
    cannot draw any of that.
    """
    p = next((x for x in _ALL_POINTS if x["name"] == name), None)
    if not p:
        st.warning(f"{name} is scan mein nahi hai — koi bars nahi mile.")
        return
    f = p.get("feat") or {}
    sym = p.get("symbol")
    b = (_BARS or {}).get(sym) or []

    m = st.columns(5)
    m[0].metric(name, round(p.get("close", 0), 2),
                f"{p.get('abs_pct'):+.2f}%" if p.get("abs_pct") is not None else None)
    try:
        import scorecard as SC
        s = SC.score(p)
        m[1].metric("Score", f"{s['total']}/{s['of']}", SC.label(s["total"]))
    except Exception:
        pass
    m[2].metric("RVOL", f.get("rvol", "—"))
    m[3].metric("ATR", f.get("atr", "—"))
    m[4].metric("vs VWAP", "UPAR" if f.get("above_vwap") else
                ("NEECHE" if f else "—"))

    plan = []
    for c in (_CARDS or {}).values():
        if c and c.get("name") == name:
            plan = [("STOP", c["stock"]["stop"], "#ff7b72"),
                    ("T1", c["stock"]["t1"], "#56d364"),
                    ("T2", c["stock"]["t2"], "#56d364")]
            break
    if not b:
        st.caption("Is naam ke OHLCV bars nahi aaye — sirf close line. "
                   "Levels tab bhi asli hain.")
    try:
        st.plotly_chart(make_fig(name, _PRICES.get(sym, []), b, _DATES, f, plan,
                                 height=380),
                        use_container_width=True)
    except Exception as e:      # noqa
        st.caption(f"chart nahi bana: {e}")

    if f.get("feature_error"):
        st.warning(f"Feature calculation fail: {f['feature_error']}")

    links = "  ·  ".join(f'<a href="{u.format(name=name)}" target="_blank" '
                         f'style="color:#58a6ff;text-decoration:none">{t} ↗</a>'
                         for t, u in EXTERNAL_CHARTS)
    st.markdown(f'<div class="scen">Poora chart kahin aur: {links}'
                f'<br><span style="color:#6e7781">StockCharts.com yahan nahi hai — '
                f'wo US/Canada listings cover karta hai, NSE India nahi. Jo source '
                f'tere naam hi na dikhaye, uska link dena dead link dena hai.</span>'
                f'</div>', unsafe_allow_html=True)


def clickable(rows, key, name_col="naam", **kw):
    """A table whose rows open the chart. Selection, not a button per row - a button
    beside every name turns a readable table into a wall of controls."""
    ev = st.dataframe(rows, use_container_width=True, hide_index=True,
                      on_select="rerun", selection_mode="single-row", key=key, **kw)
    try:
        sel = (ev.selection.rows or []) if hasattr(ev, "selection") else []
        if sel:
            nm = rows[sel[0]].get(name_col)
            if nm:
                chart_window(nm)
    except Exception:
        pass


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

# --- scanner strip: clock, status, universe, and the button that refetches ----------
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
if "last_scan" not in st.session_state:
    st.session_state.last_scan = None
sc = st.columns([1, 1, 1, 1, 1.4])
sc[0].metric("IST", f"{datetime.now(IST):%H:%M:%S}")
sc[1].metric("Status", "idle")
sc[2].metric("Last scan", st.session_state.last_scan or "—")
if sc[4].button("⟳  RUN SCAN NOW", use_container_width=True, type="primary"):
    st.cache_data.clear()
    st.session_state.last_scan = f"{datetime.now(IST):%H:%M:%S}"
    st.rerun()

if not hasattr(config, "RESOLUTION") or not hasattr(config, "BAR_MINUTES"):
    st.error("RESOLUTION / BAR_MINUTES config mein set nahi hain — ye SWING chala raha hai, "
             "INTRADAY nahi.  Theek karo:  python configure.py --mode intraday")

if DEMO:
    st.warning("Token nahi mila — ye DEMO data hai. Koi bhi number asli nahi. "
               "Icon '1 - START DAY' chala ke login kar.")

try:
    pts, prices, bench, bars, dates = load(DEMO)
    # The floating window is defined before the data exists, so it reads these. Module
    # globals rather than arguments because st.dialog callbacks take only what the click
    # passes - a name - and everything else has to be reachable from inside.
    _ALL_POINTS, _PRICES, _BARS, _DATES, _CARDS = pts, prices, bars, dates, {}
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
sc[3].metric("Universe", len(pts), "F&O naam")
if sel.get("band"):
    b = sel["band"]
    st.info(f"Price band ON: Rs {b['min']:.0f}–{b['max']:.0f} — {b['dropped']} naam "
            f"is se bahar the aur scan se hat gaye. Ye universe filter hai, signal nahi, "
            f"aur iska backtest nahi hua.")

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

# =========================================================== command deck ==
# The reference calls this the Intraday Command Deck. Everything in it is context - where
# the money is today and which names just turned. None of it is a trigger, and none of it
# has been walk-forward tested (there is no sector-index history here to test against).
st.markdown('<div class="sec">Command deck — aaj paisa kidhar hai</div>',
            unsafe_allow_html=True)

engine_bits = []
try:
    import paper as _P
    _bk = _P.load()
    engine_bits.append(f"{len(_bk.get('open', []))} khuli")
    engine_bits.append(f"{len(_bk.get('closed', []))} band")
except Exception:
    pass
mkt = "market khula" if 915 <= int(f"{datetime.now(IST):%H%M}") <= 1530 else "market band"
try:
    import broker as _B
    live_txt = ("HALTED - kill switch" if _B.killed()
                else "LIVE ARMED" if _B.armed() else "paper only")
except Exception:
    live_txt = "paper only"
st.markdown(
    f'<div class="scen">ENGINE — {mkt} · monitoring · '
    f'{" · ".join(engine_bits) or "paper book khaali"} · {live_txt}</div>',
    unsafe_allow_html=True)

# ---- momentum radar -------------------------------------------------------
try:
    import sectors as SEC
    rad = SEC.radar(pts, bars, dates)
    cls = {"UPTREND": "b-up", "DOWNTREND": "b-dn", "DAY-HIGH REVERSAL": "b-turn",
           "BOUNCING OFF LOW": "b-bnc", "FLAT": "b-none"}
    chips = []
    for state in ("DAY-HIGH REVERSAL", "BOUNCING OFF LOW", "UPTREND", "DOWNTREND", "FLAT"):
        n = rad["counts"].get(state, 0)
        if not n:
            continue
        ex = rad["examples"].get(state)
        who = f' &nbsp;<span style="opacity:.75">{ex[0]}</span>' if ex else ""
        chips.append(f'<span class="badge {cls[state]}">{state} {n}{who}</span>')
    st.markdown("**Momentum radar**")
    if chips:
        st.markdown(" ".join(chips), unsafe_allow_html=True)
    if rad["unjudged"]:
        st.caption(f"{rad['unjudged']} naam judge nahi ho paye — day-high reversal aur "
                   f"bounce ke liye intraday bars chahiye. Daily candle par is sawal ka "
                   f"jawab hota hi nahi, isliye khaali chhoda hai, zero nahi bhara.")
except Exception as e:      # noqa
    st.caption(f"radar nahi bana: {e}")

# ---- sector heatmap -------------------------------------------------------
st.markdown("**Sector heatmap — blended strength**")
try:
    hm = SEC.heatmap()
    if not hm:
        miss = SEC.unresolved()
        st.caption("Sector feed se kuch nahi aaya (token nahi / market band). "
                   "Khaali dikha raha hoon — zero se bhar dena jhooth hota, kyunki "
                   "0.00% ka matlab 'nahi badla' hai, 'pata nahi' nahi."
                   + (f"  Resolve nahi hue: {', '.join(miss)}." if miss else ""))
    else:
        span = max(abs(r["pct"]) for r in hm) or 1.0
        cols = st.columns(2)
        for i, r in enumerate(hm):
            f = min(1.0, abs(r["pct"]) / span)
            if r["pct"] > 0:
                bg = f"rgba(63,185,80,{0.10 + 0.30*f})"; fg = "#56d364"
            elif r["pct"] < 0:
                bg = f"rgba(248,81,73,{0.10 + 0.30*f})"; fg = "#ff7b72"
            else:
                bg = "#161b22"; fg = "#8b949e"
            tagc = "#56d364" if r["tag"] == "LEADER" else "#e3b341"
            c = cols[i % 2]
            c.markdown(
                f'<div class="hm" style="background:{bg}">'
                f'<div class="hm-r">#{r["rank"]}</div>'
                f'<div class="hm-n">{r["name"]}</div>'
                f'<div class="hm-p" style="color:{fg}">{r["pct"]:+.2f}%</div>'
                + (f'<div class="hm-t" style="color:{tagc}">{r["tag"]}</div>'
                   if r["tag"] else "")
                + '</div>', unsafe_allow_html=True)
            if c.button(f"{r['name']} ke naam  →", key=f"sec_{r['name']}",
                        use_container_width=True):
                st.session_state.sector = r["name"]
        if SEC.unresolved():
            st.caption("Ye sector resolve nahi hue aur heatmap mein nahi hain: "
                       + ", ".join(SEC.unresolved()))
    st.caption("Sector strength context hai, signal nahi — iska koi backtest nahi hai. "
               "Entry phir bhi tested gates se aati hai. Kisi bhi tile pe click kar ke "
               "us sector ke naam dekh.")
except Exception as e:      # noqa
    st.caption(f"heatmap nahi bana: {e}")


# ---- click a sector -> its names, best first -------------------------------
@st.cache_data(ttl=1800, show_spinner="Sector ke naam nikal raha hoon...")
def sector_map(_prices):
    import sectors as _S
    return _S.constituents(_prices)


if st.session_state.get("sector"):
    sec = st.session_state.sector
    hl, hr = st.columns([4, 1])
    hl.markdown(f'<div class="sec">{sec} — kaunsa naam pehle</div>',
                unsafe_allow_html=True)
    if hr.button("band karo", use_container_width=True):
        st.session_state.sector = None
        st.rerun()
    try:
        import scorecard as SC
        cmap, unclear = sector_map(prices)
        members = cmap.get(sec) or []
        if not members:
            st.caption(f"{sec} se koi naam strongly correlate nahi karta "
                       f"(ya index history nahi aayi). Isliye khaali — galat naam "
                       f"bhar dene se accha khaali hai.")
        else:
            by_name = {p["name"]: p for p in pts}
            rows = []
            for m in members:
                p = by_name.get(m["name"])
                if not p:
                    continue
                s = SC.score(p)
                f = p.get("feat") or {}
                # Which side this name suits, from the same tested conditions. Not a
                # separate opinion - a reading of the score that already exists.
                lean = ("BUY CE" if s["total"] >= 6 else
                        "BUY PE" if (s["of"] - s["total"]) >= 6 else "—")
                rows.append({
                    "#": 0, "naam": m["name"],
                    "LTP": round(p.get("close", 0), 2),
                    "trend %": p.get("abs_pct"),
                    "score": s["total"], "of": s["of"],
                    "lean": lean,
                    "VWAP": ("upar" if f.get("above_vwap") else "neeche") if f else "—",
                    "RVOL": f.get("rvol", "—"),
                    "expansion": ("HAAN" if f.get("expanding") else "nahi") if f else "—",
                    "sector fit (r)": m["corr"],
                })
            # Rank by the score first, then by how hard the name is moving. The sector
            # decides WHERE to look; the tested gates still decide WHICH name.
            rows.sort(key=lambda r: (r["score"], abs(r["trend %"] or 0)), reverse=True)
            for i, r_ in enumerate(rows):
                r_["#"] = i + 1
            clickable(rows, key="sec_rows")
            top = rows[0] if rows else None
            if top:
                st.success(
                    f"**{sec} mein pehli pasand: {top['naam']}** — score "
                    f"{top['score']}/{top['of']}, trend {top['trend %']}%, "
                    f"{top['lean']}. Ye is sector ka sabse behtar SETUP hai, "
                    f"sabse behtar company nahi — dono alag sawaal hain.")
            st.caption(
                "**Sector fit (r)** = us naam ka index ke saath correlation, pichle "
                "~120 bars pe **naapa gaya** — yaad se nahi likha. r kam matlab wo naam "
                "sector ke saath chalta hi nahi, toh sector ki chaal uspe lagana galat hai. "
                "Ranking tested gates se aati hai; sector sirf ye batata hai **kahan dekhna hai**."
                + (f"  {len(unclear)} naam kisi bhi sector se strongly nahi jude — "
                   f"unhe kisi bucket mein zabardasti nahi daala." if unclear else ""))
    except Exception as e:      # noqa
        st.caption(f"sector list nahi bani: {e}")

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

# ------------------------------------------------------------- trade cards --
# The reference lists every candidate as a card: side, grade, E / SL / T1 / T2 / T3, and
# the running points. Two deliberate differences.
#   SIDE   is LONG only. This system buys CE on tested long momentum. A SHORT card would
#          mean buying PE on a rule that was never walk-forward tested, and a card is an
#          instruction - printing one for an untested side is how it gets taken.
#   T3     is 2R, computed from THIS card's own risk (entry - stop), not a fixed number.
if longs:
    st.markdown('<div class="sec">Trade cards — har candidate, poora plan</div>',
                unsafe_allow_html=True)
    try:
        import scorecard as SC

        def grade(total):
            return ("A+" if total >= 9 else "A" if total >= 7
                    else "B" if total >= 5 else "C")

        def render(p, is_short):
            c = TC.build_card(p, prices.get(p["symbol"]) or [p["close"]],
                              expiry_label="—",
                              days_to_expiry=TC.min_days_for_thesis(),
                              capital=float(getattr(config, "CAPITAL", 200000)),
                              side="SHORT" if is_short else "LONG")
            stk = c["stock"]
            e, sl = stk.get("entry") or c["spot"], stk["stop"]
            # R is a distance. Signing it would make the short's T3 land above entry.
            r = max(0.01, abs(e - sl))
            t3 = round(e - 2 * r, 2) if is_short else round(e + 2 * r, 2)
            now_px = p.get("close") or e
            pts_now = (e - now_px) if is_short else (now_px - e)
            s = SC.score(p)
            # The scorecard is built from LONG conditions. On a short the same total means
            # the opposite thing, so it is inverted rather than reused - a short showing
            # "9/10 STRONG" because the stock is strong is the worst kind of wrong.
            total = (s["of"] - s["total"]) if is_short else s["total"]
            g = grade(total)
            gcol = {"A+": "#3fb950", "A": "#56d364", "B": "#d29922"}.get(g, "#8b949e")
            pcol = "#56d364" if pts_now >= 0 else "#ff7b72"
            _CARDS[c["name"]] = c
            side_txt = "SHORT · BUY PE" if is_short else "LONG · BUY CE"
            side_bg = ("background:#3d1519;color:#ff7b72" if is_short
                       else "background:#0d2b18;color:#56d364")
            st.markdown(
                f'<div class="card" style="border-left-color:{gcol}">'
                f'<div class="card-h"><span class="side" style="{side_bg}">{side_txt}</span>'
                f'<span class="card-n">{c["name"]}</span>'
                f'<span class="grade" style="color:{gcol}">★ {g} &nbsp;'
                f'{total}/{s["of"]}</span></div>'
                f'<div class="lv">'
                f'<div><b>E</b>{e}</div>'
                f'<div><b>SL</b><span style="color:#ff7b72">{sl}</span></div>'
                f'<div><b>T1</b><span style="color:#56d364">{stk["t1"]}</span></div>'
                f'<div><b>T2</b><span style="color:#56d364">{stk["t2"]}</span></div>'
                f'<div><b>T3 · 2R</b><span style="color:#56d364">{t3}</span></div>'
                f'<div><b>R</b>{r:.2f}</div>'
                f'<div><b>Pts ab</b><span style="color:{pcol}">{pts_now:+.2f}</span></div>'
                f'</div></div>', unsafe_allow_html=True)

        cl, cr = st.columns(2)
        with cl:
            st.markdown("**LONG — BUY CE**")
            for p in longs[:6]:
                render(p, False)
                if st.button(f"Chart — {p['name']}", key=f"ch_l_{p['name']}",
                             use_container_width=True):
                    chart_window(p["name"])
        with cr:
            st.markdown("**SHORT — BUY PE**")
            shorts = sel.get("shorts") or []
            if not shorts:
                st.caption("Aaj koi naam short rule pass nahi kar raha.")
            for p in shorts[:6]:
                render(p, True)
                if st.button(f"Chart — {p['name']}", key=f"ch_s_{p['name']}",
                             use_container_width=True):
                    chart_window(p["name"])

        if not bool(getattr(config, "TRADE_SHORTS", False)):
            st.warning(
                "**SHORT cards dikh rahe hain, par engine unhe trade nahi karega.** "
                "Short book ka mirror ban gaya aur test ho gaya (stop upar, PE, put "
                "intrinsic, weakest-first ranking) — lekin uska *edge* abhi tere data pe "
                "measure nahi hua. `Tools → Short book test` chala; agar number bane toh "
                "`TRADE_SHORTS = True` kar dunga. Dekhna aur paisa lagana alag baat hai.")
        st.caption("**Pts ab** = spot ka faasla entry se, us trade ki direction mein — "
                   "premium nahi. Score short ke liye ulta hai: mazboot stock ka matlab "
                   "kharab short.")
    except Exception as e:      # noqa
        st.caption(f"cards nahi bane: {e}")

# =================================================================== chart ==
st.markdown('<div class="sec">Chart — levels, and how often they held</div>',
            unsafe_allow_html=True)
if P:
    try:
        plan = []
        if card and card["name"] == pick:
            plan = [("STOP", card["stock"]["stop"], "#ff7b72"),
                    ("T1", card["stock"]["t1"], "#56d364"),
                    ("T2", card["stock"]["t2"], "#56d364")]
        if not BARS:
            st.caption("OHLCV bars nahi mile — sirf close line. Levels tab bhi asli hain.")
        st.plotly_chart(make_fig(pick, prices.get(SYM, []), BARS, dates, F, plan),
                        use_container_width=True)
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
    clickable(rows, key="mauke")
else:
    st.caption("koi naam nahi")

# =============================================================== scorecard ==
st.markdown('<div class="sec">Scorecard — 10-point conviction, har point ka naam</div>',
            unsafe_allow_html=True)
try:
    import scorecard as SC
    ranked = sorted(pts, key=lambda p: SC.score(p)["total"], reverse=True)[:15]
    clickable(
        [{"naam": p["name"], "LTP": round(p.get("close", 0), 2),
          "score": f"{SC.score(p)['total']}/{SC.MAX}",
          "verdict": SC.label(SC.score(p)["total"]),
          "kya-kya laga": ", ".join(h["label"] for h in SC.score(p)["hits"] if h["got"])
                          or "kuch nahi"}
         for p in ranked], key="scorecard")
    st.caption("Har point ek gate hai jo walk-forward mein test hua. **Weighting test nahi "
               "hui** — 10/10 probability nahi hai, aur quantity phir bhi 1 lot rahegi. "
               "Feature na mile toh point nahi milta: unknown ko 'haan' nahi maana jaata.")

    shock = SC.volume_shock(pts, mult=float(getattr(config, "SHOCK_RVOL", 2.5)))
    st.markdown('<div class="sec">Volume shock — apne hi norm se kai guna</div>',
                unsafe_allow_html=True)
    if shock:
        clickable([{"naam": r["name"], "RVOL": f"{r['rvol']:.2f}x",
                    "LTP": round(r["close"] or 0, 2), "trend %": r["pct"],
                    "VWAP": r["vwap"],
                    "expansion": "HAAN" if r["expanding"] else "nahi"}
                   for r in shock], key="shock")
    else:
        st.caption("Aaj koi naam apne norm se itna upar nahi hai. Chup rehna bhi ek "
                   "jawab hai.")
except Exception as e:      # noqa
    st.caption(f"scorecard nahi bana: {e}")

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
