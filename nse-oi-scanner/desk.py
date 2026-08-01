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
  /* ===================================================================== */
  /*  Three neons on black. Blue = up / pass. Pink = down / fail.           */
  /*  Green = attention, headers, borders. Nothing else gets a colour, so   */
  /*  a colour on this screen always means something.                       */
  /* ===================================================================== */
  .stApp {background:#04060A;}
  /* faint grid, the way a terminal sits on one. Fixed, so it does not      */
  /* scroll with content and turn into visual noise.                        */
  .stApp::before {content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
      background-image:
        linear-gradient(rgba(57,255,20,.030) 1px, transparent 1px),
        linear-gradient(90deg, rgba(57,255,20,.030) 1px, transparent 1px);
      background-size: 44px 44px;}
  .block-container {padding-top: 1rem; padding-bottom: 4.5rem; max-width: 1500px;
                    position:relative; z-index:1;}

  /* numbers are monospace everywhere - a price that shifts width as it     */
  /* ticks is harder to read at a glance than one that does not.            */
  [data-testid="stMetricValue"] {font-size: 1.35rem; color:#D5E6F2;
      font-family: ui-monospace, Consolas, "SF Mono", monospace;
      text-shadow: 0 0 14px rgba(0,229,255,.30);}
  [data-testid="stMetricLabel"] {font-size: .72rem; color: #4E6072; letter-spacing:.4px;
                                 text-transform: uppercase;}
  [data-testid="stMetricDelta"] {font-family: ui-monospace, Consolas, monospace;}

  code, pre, .stCode {background:#080C12 !important; border:1px solid #14202C;
      color:#39FF14 !important;}
  ::selection {background:#39FF14; color:#04060A;}

  /* buttons read as terminal keys, and light up on hover */
  .stButton > button {background:#080C12; color:#5CF2FF; border:1px solid #0A6675;
      border-radius:4px; font-weight:700; letter-spacing:.6px; font-size:.78rem;
      text-transform:uppercase; transition:all .12s ease;}
  .stButton > button:hover {border-color:#39FF14; color:#39FF14;
      box-shadow:0 0 12px rgba(57,255,20,.35); background:#0A0E14;}
  .stButton > button[kind="primary"] {background:#00222B; color:#00E5FF;
      border-color:#00E5FF; box-shadow:0 0 14px rgba(0,229,255,.28);}

  /* tables: black rows, neon rules */
  [data-testid="stDataFrame"] {border:1px solid #14202C; border-radius:6px;}
  [data-testid="stDataFrame"] * {font-family: ui-monospace, Consolas, monospace !important;}

  /* the pill tags used for mode / state */
  .tag {display:inline-block; padding:3px 10px; border-radius:3px; margin-right:6px;
        font-size:.71rem; font-weight:700; letter-spacing:.8px;
        font-family: ui-monospace, Consolas, monospace;}
  .ok   {background:#00222B; color:#00E5FF; border:1px solid #0A6675;}
  .warn {background:#0A2B05; color:#39FF14; border:1px solid #1E6610;}
  .bad  {background:#2B0016; color:#FF2D8A; border:1px solid #7A0B3D;}
  .muted{background:#0A0E14; color:#4E6072; border:1px solid #14202C;}

  /* green status banner - the one-line "is this thing trending" read */
  .banner {padding:11px 16px; border-radius:4px; font-weight:700; font-size:.92rem;
           margin:.35rem 0 .8rem 0; display:flex; align-items:center; gap:10px;
           letter-spacing:.6px; font-family: ui-monospace, Consolas, monospace;}
  .banner-ok  {background:#00222B; color:#5CF2FF; border:1px solid #00E5FF;
               box-shadow:0 0 18px rgba(0,229,255,.22) inset, 0 0 10px rgba(0,229,255,.18);}
  .banner-mid {background:#0A2B05; color:#7CFF5E; border:1px solid #39FF14;
               box-shadow:0 0 18px rgba(57,255,20,.20) inset;}
  .banner-bad {background:#2B0016; color:#FF6BB0; border:1px solid #FF2D8A;
               box-shadow:0 0 18px rgba(255,45,138,.20) inset;}

  /* blue ribbon carrying the live numbers for the selected name */
  .ribbon {background:linear-gradient(90deg,#00131A 0%,#002230 60%,#00131A 100%);
           border:1px solid #0A6675; border-radius:4px; padding:10px 16px;
           box-shadow:0 0 22px rgba(0,229,255,.10);
           display:flex; flex-wrap:wrap; gap:26px; align-items:center; margin-bottom:.9rem;}
  .rb-k {color:#4DE8FF; font-size:.66rem; letter-spacing:.6px; text-transform:uppercase;}
  .rb-v {color:#D5E6F2; font-size:1.02rem; font-weight:700;
         font-family: ui-monospace, Consolas, monospace;}
  .up   {color:#5CF2FF;} .dn {color:#FF6BB0;}

  /* the "SCENARIO ANALYSIS [...] — rules used" strip */
  .scen {background:#080C12; border-left:3px solid #39FF14; border-radius:4px;
         padding:9px 14px; font-size:.8rem; color:#8FA9BF; margin:.2rem 0 .7rem 0;
         font-family: ui-monospace, SFMono-Regular, Menlo, monospace;}

  .sec {font-size:.72rem; letter-spacing:2px; text-transform:uppercase; color:#39FF14;
        border-bottom:1px solid #14202C; padding-bottom:5px; margin:1.4rem 0 .7rem 0;
        font-family: ui-monospace, Consolas, monospace;
        text-shadow:0 0 12px rgba(57,255,20,.40);}
  .sec::before {content:"> "; color:#1E6610;}

  /* --- command deck: heatmap tiles, radar badges, trade cards --- */
  .hm {border-radius:4px; padding:10px 13px; margin-bottom:8px; position:relative;
       border:1px solid #14202C; transition:border-color .12s ease;}
  .hm:hover {border-color:#39FF14;}
  .hm-n {font-size:.68rem; letter-spacing:1.1px; color:#B8CEE0; text-transform:uppercase;
         font-weight:700;}
  .hm-p {font-size:1.5rem; font-weight:800; font-family:ui-monospace,Consolas,monospace;
         text-shadow:0 0 16px currentColor;}
  .hm-r {position:absolute; top:8px; right:11px; font-size:.62rem; color:#3E5060;}
  .hm-t {font-size:.6rem; letter-spacing:1.4px; font-weight:800;}

  .badge {display:inline-block; padding:5px 12px; border-radius:3px; margin:0 7px 7px 0;
          font-size:.7rem; font-weight:800; letter-spacing:1px;
          font-family: ui-monospace, Consolas, monospace;
          text-shadow:0 0 10px currentColor;}
  .b-up   {background:#00222B; color:#5CF2FF; border:1px solid #0A6675;}
  .b-dn   {background:#2B0016; color:#FF6BB0; border:1px solid #7A0B3D;}
  .b-turn {background:#0A2B05; color:#7CFF5E; border:1px solid #1E6610;}
  .b-bnc  {background:#00222B; color:#22D3EE; border:1px solid #0A6675;}
  .b-none {background:#0A0E14; color:#4E6072; border:1px solid #14202C;}

  .card {background:#080C12; border:1px solid #14202C; border-left:3px solid #00E5FF;
         border-radius:4px; padding:11px 15px; margin-bottom:9px;
         transition:box-shadow .12s ease;}
  .card:hover {box-shadow:0 0 18px rgba(0,229,255,.16);}
  .card-h {display:flex; align-items:center; gap:10px; margin-bottom:6px;}
  .side {font-size:.64rem; font-weight:800; letter-spacing:1.2px; padding:3px 9px;
         border-radius:3px; background:#00222B; color:#5CF2FF;
         font-family: ui-monospace, Consolas, monospace;}
  .grade {font-size:.72rem; font-weight:800; color:#7CFF5E;}
  .card-n {font-size:1.02rem; font-weight:800; color:#D5E6F2; letter-spacing:1.2px;
           font-family: ui-monospace, Consolas, monospace;}
  .lv {display:flex; flex-wrap:wrap; gap:20px; font-family:ui-monospace,Consolas,monospace;
       font-size:.82rem;}
  .lv b {color:#3E5060; font-weight:600; font-size:.66rem; letter-spacing:.6px;
         text-transform:uppercase; display:block;}

  /* the wordmark - his desk, with his name on it */
  /* A glow spreads in every direction, including above the cap height, so the letters
     need vertical room of their own - the container will happily clip whatever sticks
     out. line-height does that; padding alone did not, because the line box itself was
     still only as tall as the text. */
  .mark {display:flex; align-items:baseline; gap:12px; margin:.2rem 0 .35rem 0;
         padding:.45rem 0 .25rem 0; overflow:visible;}
  .mark-name {font-size:2.0rem; font-weight:800; letter-spacing:6px;
              font-family: ui-monospace, Consolas, monospace; color:#39FF14;
              line-height:1.5; display:inline-block; padding:2px 0;
              /* the RGB split stays horizontal; the soft halo is kept tight so it does
                 not need more headroom than the line box has */
              text-shadow: 0 0 6px rgba(57,255,20,.80),
                           2px 0 0 rgba(255,45,138,.50),
                          -2px 0 0 rgba(0,229,255,.50);}
  .mark-sub {font-size:.82rem; color:#3E5060; letter-spacing:2.6px;
             text-transform:uppercase;}

  /* the disclaimer the reference keeps nailed to the bottom, and so does this */
  .disclaim {position:fixed; left:0; right:0; bottom:0; z-index:99;
             background:#2B0016; color:#FF8FC5; border-top:1px solid #FF2D8A;
             text-align:center; padding:7px 10px; font-size:.74rem; font-weight:700;
             letter-spacing:.6px; font-family: ui-monospace, Consolas, monospace;
             box-shadow:0 0 22px rgba(255,45,138,.30);}
  section[data-testid="stSidebar"] {border-right:1px solid #14202C; background:#06090E;}

  /* ===================================================================== */
  /*  SWAT KATS HUD                                                        */
  /*  Borrowed from the Turbokat cockpit, not from its colours: angular cut */
  /*  corners, corner brackets, a radar block, hazard stripes on an alert,  */
  /*  and a targeting reticle on whatever is selected. The palette stays    */
  /*  the three neons - a fourth colour would be a meaning nobody defined.  */
  /*  Decoration never covers a number; every frame here sits behind one.   */
  /* ===================================================================== */

  /* angular corners, the way a cockpit panel is cut */
  .hud {position:relative; clip-path: polygon(
        14px 0, 100% 0, 100% calc(100% - 14px), calc(100% - 14px) 100%, 0 100%, 0 14px);}
  /* corner brackets - drawn, not an image, so they scale with the panel */
  .hud::before, .hud::after {content:""; position:absolute; width:16px; height:16px;
        pointer-events:none;}
  .hud::before {top:0; right:0; border-top:2px solid #39FF14; border-right:2px solid #39FF14;}
  .hud::after  {bottom:0; left:0; border-bottom:2px solid #39FF14; border-left:2px solid #39FF14;}

  /* the radar block on the scan strip */
  .radar {display:flex; align-items:center; gap:10px; padding:6px 12px;
          border:1px solid #14202C; border-radius:3px; background:#080C12;
          font-family: ui-monospace, Consolas, monospace; font-size:.68rem;
          color:#4E6072; letter-spacing:1.4px;}
  .radar-dish {width:22px; height:22px; border-radius:50%; position:relative;
        border:1px solid #1E6610; box-shadow:0 0 10px rgba(57,255,20,.25) inset;}
  .radar-dish::after {content:""; position:absolute; inset:0; border-radius:50%;
        background: conic-gradient(from 0deg, rgba(57,255,20,.55), transparent 70deg);
        animation: sweep 2.4s linear infinite;}
  @keyframes sweep {to {transform: rotate(360deg);}}
  .radar b {color:#39FF14; font-weight:800;}

  /* hazard stripes - only ever used for a state that stops trading */
  .hazard {margin:.2rem 0 .8rem 0; border:1px solid #FF2D8A; border-radius:3px;
           padding:9px 14px; font-family: ui-monospace, Consolas, monospace;
           font-weight:800; letter-spacing:2px; font-size:.78rem; color:#FF6BB0;
           background: repeating-linear-gradient(45deg,
                 #2B0016 0 14px, #3A001F 14px 28px);
           box-shadow:0 0 20px rgba(255,45,138,.25);}

  /* targeting reticle on the selected name */
  .reticle {position:relative; padding-left:22px;}
  .reticle::before {content:""; position:absolute; left:0; top:50%; width:13px; height:13px;
        margin-top:-7px; border:1px solid #39FF14; border-radius:50%;
        box-shadow:0 0 8px rgba(57,255,20,.6);}
  .reticle::after {content:""; position:absolute; left:6px; top:50%; width:1px; height:19px;
        margin-top:-10px; background:#39FF14; opacity:.55;}

  /* callsign tag for the deck sub-blocks */
  .callsign {display:inline-block; font-family: ui-monospace, Consolas, monospace;
        font-size:.64rem; letter-spacing:2.4px; font-weight:800; color:#39FF14;
        border-left:3px solid #39FF14; padding:1px 0 1px 8px; margin:.2rem 0 .5rem 0;
        text-shadow:0 0 10px rgba(57,255,20,.45);}

  /* Streamlit's own alert colours are its palette, not this one - an olive warning box
     next to neon pink and blue reads as a fourth meaning nobody defined. Repainted so
     error=pink, warning=green, info/success=blue, same as everywhere else. */
  [data-testid="stAlert"] {border-radius:4px; border-width:1px; border-style:solid;
      font-family: ui-monospace, Consolas, monospace; font-size:.84rem;}
  [data-testid="stAlert"] p {font-family: ui-monospace, Consolas, monospace;}
  [data-testid="stAlertContentError"], div[data-baseweb="notification"][kind="negative"] {
      background:#2B0016 !important; color:#FF6BB0 !important; border-color:#FF2D8A !important;}
  [data-testid="stAlertContentWarning"] {
      background:#0A2B05 !important; color:#7CFF5E !important; border-color:#39FF14 !important;}
  [data-testid="stAlertContentInfo"] {
      background:#00222B !important; color:#5CF2FF !important; border-color:#0A6675 !important;}
  [data-testid="stAlertContentSuccess"] {
      background:#00222B !important; color:#00E5FF !important; border-color:#00E5FF !important;}
  /* The fill lives on a nested div, not on the alert itself, so setting the wrapper
     alone leaves Streamlit's maroon and olive showing through the middle. Paint the
     wrapper AND everything inside it. */
  [data-testid="stAlert"]:has([data-testid="stAlertContentError"]),
  [data-testid="stAlert"]:has([data-testid="stAlertContentError"]) > div,
  [data-testid="stAlert"]:has([data-testid="stAlertContentError"]) div[data-baseweb="notification"] {
      background:#2B0016 !important; border-color:#FF2D8A !important; color:#FF6BB0 !important;}
  [data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),
  [data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) > div,
  [data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) div[data-baseweb="notification"] {
      background:#0A2B05 !important; border-color:#39FF14 !important; color:#7CFF5E !important;}
  [data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]),
  [data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) > div,
  [data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) div[data-baseweb="notification"] {
      background:#00222B !important; border-color:#0A6675 !important; color:#5CF2FF !important;}
  [data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]),
  [data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) > div,
  [data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) div[data-baseweb="notification"] {
      background:#00222B !important; border-color:#00E5FF !important; color:#00E5FF !important;}
  /* the icon svg inherits, so it stops being Streamlit red too */
  [data-testid="stAlert"] svg {fill:currentColor !important; color:inherit !important;}

  /* inputs and the select box, so the rail matches the rest */
  [data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {
      background:#080C12 !important; border-color:#14202C !important; color:#D5E6F2 !important;
      font-family: ui-monospace, Consolas, monospace !important;}
  [data-baseweb="select"] > div:hover {border-color:#39FF14 !important;}
  .stRadio label, .stCheckbox label {font-family: ui-monospace, Consolas, monospace;}
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


@st.cache_data(ttl=120, show_spinner="Fetching data...")
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
                            name=name,
                            # up is blue, down is pink - the same two colours the rest
                            # of the page uses, so a candle means what a number means
                            increasing_line_color="#00E5FF",
                            increasing_fillcolor="#00E5FF",
                            decreasing_line_color="#FF2D8A",
                            decreasing_fillcolor="#FF2D8A")
        try:
            import indicators as I
            vwl = I.vwap_session(bars_, (dates_ or [""] * len(bars_))[-len(bars_):])
            fig.add_scatter(x=list(range(len(bars_))), y=vwl, name="VWAP",
                            line=dict(color="#39FF14", width=2))   # accent, not a signal
        except Exception:
            pass
    else:
        c = closes or []
        fig.add_scatter(x=list(range(len(c))), y=c, name=name,
                        line=dict(color="#39FF14"))
    atr = feat.get("atr")
    for nm, lvl, col in (("R2", feat.get("r2"), "#FF2D8A"),
                         ("R1", feat.get("r1"), "#FF2D8A"),
                         ("S1", feat.get("s1"), "#00E5FF"),
                         ("S2", feat.get("s2"), "#00E5FF")):
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
                      paper_bgcolor="#04060A", plot_bgcolor="#04060A",
                      font=dict(family="ui-monospace, Consolas, monospace",
                                color="#8FA9BF", size=11),
                      xaxis=dict(gridcolor="rgba(57,255,20,.07)", zeroline=False),
                      yaxis=dict(gridcolor="rgba(57,255,20,.07)", zeroline=False),
                      showlegend=False)
    return fig


# ======================================================================= orders ==
# ONE-CLICK IS NEVER ONE CLICK HERE, AND THAT IS DELIBERATE.
#
# A button that sends a real order on a single press is one stray scroll-click away from a
# position he did not choose. So every order button ARMS first and fires on the second
# press, shows the exact payload in between, and disarms itself after ARM_SECONDS. That is
# not me overriding the instruction to trade live - it is how an order ticket works
# everywhere, and it costs one extra click for the thing that cannot be undone.
#
# Everything else the broker already enforced still applies: LIVE_TRADING armed, no kill
# switch, a valid token. This layer adds intent, not permission.
ARM_SECONDS = 20


def _armed_key(k):
    import time
    a = st.session_state.get("arm") or {}
    if a.get("key") != k:
        return False
    if time.time() - a.get("at", 0) > ARM_SECONDS:
        st.session_state.arm = {}
        return False
    return True


def order_button(label, key, payload, fire, colour="#00E5FF"):
    """Two-press order control. Returns nothing; renders its own result.

    payload is shown verbatim before anything is sent - the numbers on the button and the
    numbers in the request have to be the same numbers, and the only way to be sure of
    that is to print the request.
    """
    import time
    try:
        import broker as B
        halted, live = B.killed(), B.armed()
    except Exception as e:      # noqa
        st.caption(f"broker unavailable: {e}")
        return

    if halted:
        st.button(f"{label} · KILL SWITCH ON", key=key, disabled=True,
                  use_container_width=True)
        return
    if not payload.get("symbol"):
        st.button(f"{label} · no contract", key=key, disabled=True,
                  use_container_width=True)
        st.caption("The chain did not supply a tradeable symbol, so there is nothing to "
                   "send. An order assembled by hand from strike and expiry is one typo "
                   "from a different contract.")
        return

    if _armed_key(key):
        st.code(" · ".join(f"{k}={v}" for k, v in payload.items()), language=None)
        c1, c2 = st.columns([3, 1])
        if c1.button(f"⚠ CONFIRM — {label}", key=f"{key}_go", type="primary",
                     use_container_width=True):
            st.session_state.arm = {}
            ok, detail = fire()
            (st.success if ok else st.error)(
                f"{'SENT' if ok else 'NOT SENT'} — {detail}")
            if not live and not ok:
                st.caption("LIVE_TRADING is off, so this was logged and not sent. "
                           "Arm it from the launcher or `LIVE - arm or disarm`.")
        if c2.button("cancel", key=f"{key}_no", use_container_width=True):
            st.session_state.arm = {}
            st.rerun()
        st.caption(f"Disarms in {ARM_SECONDS}s. Nothing has been sent yet.")
    else:
        if st.button(label + ("" if live else "  (paper — live is off)"),
                     key=key, use_container_width=True):
            st.session_state.arm = {"key": key, "at": time.time()}
            st.rerun()


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
        st.warning(f"{name} is not in this scan — no bars for it.")
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
    m[4].metric("vs VWAP", "ABOVE" if f.get("above_vwap") else
                ("BELOW" if f else "—"))

    plan = []
    for c in (_CARDS or {}).values():
        if c and c.get("name") == name:
            plan = [("STOP", c["stock"]["stop"], "#FF6BB0"),
                    ("T1", c["stock"]["t1"], "#5CF2FF"),
                    ("T2", c["stock"]["t2"], "#5CF2FF")]
            break
    if not b:
        st.caption("No OHLCV bars for this name — close line only. "
                   "The levels are still real.")
    try:
        st.plotly_chart(make_fig(name, _PRICES.get(sym, []), b, _DATES, f, plan,
                                 height=380),
                        use_container_width=True)
    except Exception as e:      # noqa
        st.caption(f"chart failed: {e}")

    if f.get("feature_error"):
        st.warning(f"Feature calculation fail: {f['feature_error']}")

    links = "  ·  ".join(f'<a href="{u.format(name=name)}" target="_blank" '
                         f'style="color:#39FF14;text-decoration:none">{t} ↗</a>'
                         for t, u in EXTERNAL_CHARTS)
    st.markdown(f'<div class="scen">Full chart elsewhere: {links}'
                f'<br><span style="color:#3E5060">StockCharts.com is not here — it covers '
                f'US and Canadian listings, not NSE India. Linking a source that cannot '
                f'show your names is shipping a dead link.</span>'
                f'</div>', unsafe_allow_html=True)


def clickable(rows, key, name_col="names", **kw):
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
    st.caption("Index, commodity and global feeds are not wired into this system. "
               "What does not exist gets no button — an empty button is a lie.")

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
sc[1].markdown(
    f'<div class="radar"><div class="radar-dish"></div>'
    f'<div>SCAN<br><b>{"ARMED" if not DEMO else "DEMO"}</b></div></div>',
    unsafe_allow_html=True)
sc[2].metric("Last scan", st.session_state.last_scan or "—")
if sc[4].button("⟳  RUN SCAN NOW", use_container_width=True, type="primary"):
    st.cache_data.clear()
    st.session_state.last_scan = f"{datetime.now(IST):%H:%M:%S}"
    st.rerun()

if not hasattr(config, "RESOLUTION") or not hasattr(config, "BAR_MINUTES"):
    st.error("RESOLUTION / BAR_MINUTES are not set in config — this is running SWING, "
             "not INTRADAY.  Fix:  python configure.py --mode intraday")

if DEMO:
    st.warning("No token — this is DEMO data. Not one number here is real. "
               "Run the '1 - START DAY' icon to log in.")

try:
    pts, prices, bench, bars, dates = load(DEMO)
    # The floating window is defined before the data exists, so it reads these. Module
    # globals rather than arguments because st.dialog callbacks take only what the click
    # passes - a name - and everything else has to be reachable from inside.
    _ALL_POINTS, _PRICES, _BARS, _DATES, _CARDS = pts, prices, bars, dates, {}
except Exception as e:      # noqa
    st.error(f"No data: {e}")
    st.info("Token expired? Run the '1 - START DAY' icon.")
    st.stop()

# ================================================================== regime ==
reg = None
try:
    import market_regime as MR
    reg = MR.Regime(prices, bench, dates=dates or None).at(len(bench))
except Exception as e:      # noqa
    st.caption(f"regime failed: {e}")

# ------------------------------------------------------- candidates + picks --
import rrg_strategy as S, trade_card as TC

rule, params, _ = S.load_best()
sel = S.select(pts, rule, params, max_pos=8, prices=prices)
longs = sel["longs"]
sc[3].metric("Universe", len(pts), "F&O names")
if sel.get("band"):
    b = sel["band"]
    st.info(f"Price band ON: Rs {b['min']:.0f}–{b['max']:.0f} — {b['dropped']} names fell "
            f"outside it and left the scan. This is a universe filter, not a signal, "
            f"and it has never been backtested.")

with st.sidebar:
    st.markdown('<div class="sec">Name</div>', unsafe_allow_html=True)
    names = [p["name"] for p in longs] or [p["name"] for p in pts[:25]]
    pick = st.selectbox("Name", names, label_visibility="collapsed") if names else None
    st.caption(f"{len(longs)} names pass the rule · {len(pts)} in the universe")

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
    cls, msg = "banner-mid", f"{regime_state} · {pick or '—'} {struct or 'no structure'} — Partial: one side confirms, the other does not"
else:
    cls, msg = "banner-bad", f"{regime_state} · {pick or '—'} — No trend. Not taking one is also a position."
if F.get("feature_error"):
    cls, msg = "banner-bad", f"Feature calculation fail: {F['feature_error']}"
st.markdown(f'<div class="banner hud {cls}">{msg}</div>', unsafe_allow_html=True)

# ================================================================== ribbon ==
if P:
    px = P.get("close", 0)
    chg = P.get("abs_pct")
    rv = F.get("rvol")
    vw = F.get("above_vwap")
    cells = [
        ("Name", f'<span class="reticle">{pick}</span>'),
        ("Spot", f"{px:,.2f}"),
        ("Trend", f'<span class="{"up" if (chg or 0) >= 0 else "dn"}">{chg:+.2f}%</span>'
         if chg is not None else "—"),
        ("vs VWAP", f'<span class="{"up" if vw else "dn"}">{"ABOVE" if vw else "BELOW"}</span>'
         if F else "—"),
        ("RVOL", f"{rv:.2f}x" if rv else "—"),
        ("ATR", F.get("atr", "—")),
        ("Squeeze", f'{F.get("squeeze","—")}{" · COILED" if F.get("coiled") else ""}'),
        ("Expansion", '<span class="up">YES</span>' if F.get("expanding") else "no"),
    ]
    st.markdown('<div class="ribbon hud">' + "".join(
        f'<div><div class="rb-k">{k}</div><div class="rb-v">{v}</div></div>'
        for k, v in cells) + '</div>', unsafe_allow_html=True)

# =========================================================== command deck ==
# The reference calls this the Intraday Command Deck. Everything in it is context - where
# the money is today and which names just turned. None of it is a trigger, and none of it
# has been walk-forward tested (there is no sector-index history here to test against).
st.markdown('<div class="sec">Command deck — where the money is today</div>',
            unsafe_allow_html=True)

engine_bits = []
try:
    import paper as _P
    _bk = _P.load()
    engine_bits.append(f"{len(_bk.get('open', []))} open")
    engine_bits.append(f"{len(_bk.get('closed', []))} closed")
except Exception:
    pass
mkt = "market open" if 915 <= int(f"{datetime.now(IST):%H%M}") <= 1530 else "market closed"
try:
    import broker as _B
    live_txt = ("HALTED - kill switch" if _B.killed()
                else "LIVE ARMED" if _B.armed() else "paper only")
except Exception:
    live_txt = "paper only"
if "HALTED" in live_txt:
    st.markdown(f'<div class="hazard">⚠ KILL SWITCH ON — nothing will be ordered. '
                f'{mkt} · {" · ".join(engine_bits) or "paper book empty"}</div>',
                unsafe_allow_html=True)
else:
    st.markdown(
        f'<div class="scen">ENGINE — {mkt} · monitoring · '
        f'{" · ".join(engine_bits) or "paper book empty"} · {live_txt}</div>',
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
    st.markdown('<div class="callsign">// MOMENTUM RADAR</div>', unsafe_allow_html=True)
    if chips:
        st.markdown(" ".join(chips), unsafe_allow_html=True)
    if rad["unjudged"]:
        st.caption(f"{rad['unjudged']} names could not be judged — day-high reversal "
                   f"and bounce need intraday bars. On a daily candle that question has "
                   f"no answer, so it is left empty rather than filled with a zero.")
except Exception as e:      # noqa
    st.caption(f"radar failed: {e}")

# ---- sector heatmap: two columns, advancing and declining ------------------
# Vertical, split by direction, with the names driving each sector beside it.
#
# ON THE WORD "DRIVERS"
# A true index contribution needs free-float weights, and this system has none. So these
# are NOT contributions - they are the names that (a) actually track this sector, by
# measured correlation, and (b) moved furthest in the sector's direction today. That is a
# defensible answer to "who is behind this move"; "RELIANCE contributed 43 bps" is not,
# and printing it would be inventing a number.
st.markdown('<div class="callsign">// SECTOR SCAN &nbsp;·&nbsp; ADVANCING / DECLINING &nbsp;·&nbsp; DRIVERS</div>', unsafe_allow_html=True)


@st.cache_data(ttl=1800, show_spinner="Working out sector membership...")
def sector_map(_prices):
    import sectors as _S
    return _S.constituents(_prices)


# A name has to actually track the sector before its move can be called the sector's
# doing. Weighting the move by r is NOT enough on its own - a test caught exactly that:
# 9% at r=0.30 scores 2.7 and outranks 3% at r=0.85, so the loosest-tracking name leads
# the list precisely when it has a big idiosyncratic day. That is the opposite of what
# the column is for. So r is a gate first and a weight second.
DRIVER_MIN_R = 0.50


def drivers(sec_name, direction, cmap, by_name, top=4):
    """Names that track this sector and moved furthest WITH it, biggest first."""
    out = []
    for m in (cmap.get(sec_name) or []):
        r = float(m.get("corr") or 0)
        if r < DRIVER_MIN_R:
            continue                       # does not track it - not this sector's story
        p = by_name.get(m["name"])
        if not p or p.get("abs_pct") is None:
            continue
        pct = float(p["abs_pct"])
        if direction > 0 and pct <= 0:
            continue
        if direction < 0 and pct >= 0:
            continue
        out.append({"name": m["name"], "pct": pct, "r": m["corr"],
                    "drive": abs(pct) * r})
    out.sort(key=lambda x: x["drive"], reverse=True)
    return out[:top]


try:
    hm = SEC.heatmap()
    if not hm:
        miss = SEC.unresolved()
        st.caption("Nothing came back from the sector feed (no token / market closed). "
                   "Showing it empty — filling it with zeros would be a lie, because "
                   "0.00% means 'did not move', not 'do not know'."
                   + (f"  Did not resolve: {', '.join(miss)}." if miss else ""))
    else:
        try:
            cmap, _unclear = sector_map(prices)
        except Exception:
            cmap = {}
        by_name = {p["name"]: p for p in pts}
        span = max(abs(r["pct"]) for r in hm) or 1.0
        up = [r for r in hm if r["pct"] >= 0]
        dn = [r for r in hm if r["pct"] < 0]

        def render_col(rows, direction, title, colour):
            st.markdown(f'<div style="color:{colour};font-family:ui-monospace,Consolas,'
                        f'monospace;font-size:.72rem;letter-spacing:2px;font-weight:800;'
                        f'text-shadow:0 0 10px currentColor;margin-bottom:6px">'
                        f'{title} · {len(rows)}</div>', unsafe_allow_html=True)
            if not rows:
                st.caption("none")
                return
            for r in rows:
                f = min(1.0, abs(r["pct"]) / span)
                if direction > 0:
                    bg, fg = f"rgba(0,229,255,{0.06 + 0.24*f})", "#5CF2FF"
                else:
                    bg, fg = f"rgba(255,45,138,{0.06 + 0.24*f})", "#FF6BB0"
                dr = drivers(r["name"], direction, cmap, by_name)
                chips = "".join(
                    f'<span style="display:inline-block;margin:3px 6px 0 0;padding:1px 6px;'
                    f'border:1px solid {fg}44;border-radius:3px;font-size:.66rem;'
                    f'color:{fg};font-family:ui-monospace,Consolas,monospace">'
                    f'{d["name"]} {d["pct"]:+.1f}% <span style="color:#3E5060">r{d["r"]}'
                    f'</span></span>' for d in dr)
                if not chips:
                    chips = ('<span style="font-size:.66rem;color:#3E5060;'
                             'font-family:ui-monospace,Consolas,monospace">'
                             'no tracked name moved this way</span>')
                tag = (f'<span class="hm-t" style="color:{fg};margin-left:8px">'
                       f'{r["tag"]}</span>' if r["tag"] else "")
                st.markdown(
                    f'<div class="hm" style="background:{bg}">'
                    f'<div class="hm-r">#{r["rank"]}</div>'
                    f'<div style="display:flex;align-items:baseline;gap:10px">'
                    f'<span class="hm-p" style="color:{fg};font-size:1.15rem">'
                    f'{r["pct"]:+.2f}%</span>'
                    f'<span class="hm-n">{r["name"]}</span>{tag}</div>'
                    f'<div style="margin-top:2px">{chips}</div>'
                    f'</div>', unsafe_allow_html=True)
                if st.button(f"{r['name']} names  →", key=f"sec_{r['name']}",
                             use_container_width=True):
                    st.session_state.sector = r["name"]

        cu, cd = st.columns(2)
        with cu:
            render_col(up, +1, "ADVANCING", "#00E5FF")
        with cd:
            render_col(dn, -1, "DECLINING", "#FF2D8A")

        if SEC.unresolved():
            st.caption("These sectors did not resolve and are not on the heatmap: "
                       + ", ".join(SEC.unresolved()))
    st.caption("The names beside each sector are the ones that **track** it (measured "
               "correlation, shown as r) and moved furthest **with** it today, largest "
               "first. They are NOT index contributions — that needs free-float weights, "
               "which this system does not have, so it is not claimed. Sector strength is "
               "context, not a signal, and none of it is backtested. Click a sector for "
               "its full ranked list.")
except Exception as e:      # noqa
    st.caption(f"heatmap failed: {e}")


# ---- click a sector -> its names, best first -------------------------------
if st.session_state.get("sector"):
    sec = st.session_state.sector
    hl, hr = st.columns([4, 1])
    hl.markdown(f'<div class="sec">{sec} — which name first</div>',
                unsafe_allow_html=True)
    if hr.button("close", use_container_width=True):
        st.session_state.sector = None
        st.rerun()
    try:
        import scorecard as SC
        cmap, unclear = sector_map(prices)
        members = cmap.get(sec) or []
        if not members:
            st.caption(f"No name correlates strongly with {sec} (or the index history did not "
                       f"arrive). So it is empty — empty beats filling it with the "
                       f"wrong names.")
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
                    "#": 0, "names": m["name"],
                    "LTP": round(p.get("close", 0), 2),
                    "trend %": p.get("abs_pct"),
                    "score": s["total"], "of": s["of"],
                    "lean": lean,
                    "VWAP": ("upar" if f.get("above_vwap") else "neeche") if f else "—",
                    "RVOL": f.get("rvol", "—"),
                    "expansion": ("YES" if f.get("expanding") else "no") if f else "—",
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
                    f"**First pick in {sec}: {top['name']}** — score "
                    f"{top['score']}/{top['of']}, trend {top['trend %']}%, "
                    f"{top['lean']}. This is the best SETUP in the sector, not the best "
                    f"company — those are different questions.")
            st.caption(
                "**Sector fit (r)** = that name's correlation with the index, **measured** over "
                "the last ~120 bars — not written from memory. A low r means the name does "
                "not move with its sector, so reading the sector's move onto it is wrong. "
                "Ranking comes from the tested gates; the sector only says **where to look**."
                + (f"  {len(unclear)} names do not track any sector strongly — none of them were "
                   f"forced into a bucket." if unclear else ""))
    except Exception as e:      # noqa
        st.caption(f"sector list failed: {e}")

# ================================================================== maahol ==
st.markdown('<div class="sec">Market — is the tape worth trading</div>', unsafe_allow_html=True)
if reg:
    cols = st.columns(5)
    cols[0].metric("Regime", reg["state"], f"{reg['passed']}/{reg['of']} checks")
    if reg.get("breadth") is not None:
        cols[1].metric("Breadth", f"{reg['breadth']*100:.0f}%", "names trending")
    if reg.get("drawdown") is not None:
        cols[2].metric("Index", f"-{reg['drawdown']*100:.1f}%", "off its high")
    if reg.get("vol_ratio"):
        cols[3].metric("Vol", f"{reg['vol_ratio']:.2f}x", "of normal")
    cols[4].metric("Universe", len(pts), "names")
    if reg["state"] == "RISK-OFF":
        st.markdown('<div class="hazard">⚠ RISK-OFF — TAPE IS POOR. The trade below '
                    'still shows; size it down or skip it.</div>',
                    unsafe_allow_html=True)

# ============================================================ aaj ka trade ==
st.markdown('<div class="sec">Today\'s trade — the ticket</div>', unsafe_allow_html=True)
card = None
if not longs:
    st.info("No name passes the setup. Not taking one is also a position.")
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
    k[3].metric("Cost", f"Rs {s.get('cost_per_lot', 0) * s['lots']:,.0f}",
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
    st.markdown('<div class="sec">Trade cards — every candidate, the whole plan</div>',
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
            gcol = {"A+": "#00E5FF", "A": "#5CF2FF", "B": "#39FF14"}.get(g, "#4E6072")
            pcol = "#5CF2FF" if pts_now >= 0 else "#FF6BB0"
            _CARDS[c["name"]] = c
            side_txt = "SHORT · BUY PE" if is_short else "LONG · BUY CE"
            side_bg = ("background:#2B0016;color:#FF6BB0" if is_short
                       else "background:#00222B;color:#5CF2FF")
            st.markdown(
                f'<div class="card" style="border-left-color:{gcol}">'
                f'<div class="card-h"><span class="side" style="{side_bg}">{side_txt}</span>'
                f'<span class="card-n">{c["name"]}</span>'
                f'<span class="grade" style="color:{gcol}">★ {g} &nbsp;'
                f'{total}/{s["of"]}</span></div>'
                f'<div class="lv">'
                f'<div><b>E</b>{e}</div>'
                f'<div><b>SL</b><span style="color:#FF6BB0">{sl}</span></div>'
                f'<div><b>T1</b><span style="color:#5CF2FF">{stk["t1"]}</span></div>'
                f'<div><b>T2</b><span style="color:#5CF2FF">{stk["t2"]}</span></div>'
                f'<div><b>T3 · 2R</b><span style="color:#5CF2FF">{t3}</span></div>'
                f'<div><b>R</b>{r:.2f}</div>'
                f'<div><b>Pts now</b><span style="color:{pcol}">{pts_now:+.2f}</span></div>'
                f'</div></div>', unsafe_allow_html=True)

        def signal_block(p, is_short):
            """The plan in BOTH languages - the stock's levels and the option's - plus the
            three things he can actually do about it.

            Both matter and they are not interchangeable. The stock levels are where the
            thesis lives (stop below structure, targets at ATR multiples). The option
            levels are what the account will actually see, because the premium moves by
            delta and not one-for-one. Showing only one of them is how a trader ends up
            watching the wrong number."""
            c = TC.build_card(p, prices.get(p["symbol"]) or [p["close"]],
                              expiry_label="—",
                              days_to_expiry=TC.min_days_for_thesis(),
                              capital=float(getattr(config, "CAPITAL", 200000)),
                              side="SHORT" if is_short else "LONG")
            _CARDS[c["name"]] = c
            render(p, is_short)
            o = c.get("option") or {}
            stk, sz = c["stock"], c["size"]
            e, sl = stk.get("entry") or c["spot"], stk["stop"]
            r = max(0.01, abs(e - sl))
            t3 = round(e - 2 * r, 2) if is_short else round(e + 2 * r, 2)

            und = (f'UNDERLYING &nbsp; E <b>{e}</b> &nbsp; SL <b>{sl}</b> &nbsp; '
                   f'TP1 <b>{stk["t1"]}</b> &nbsp; TP2 <b>{stk["t2"]}</b> &nbsp; '
                   f'TP3 <b>{t3}</b>')
            opt = (f'OPTION {o.get("strike","?")} {o.get("type","")} &nbsp; '
                   f'BUY <b>{o.get("premium","?")}</b> &nbsp; '
                   f'SL <b>{o.get("stop","?")}</b> &nbsp; '
                   f'TP1 <b>{o.get("t1","?")}</b> &nbsp; TP2 <b>{o.get("t2","?")}</b> '
                   f'&nbsp; qty <b>{sz["qty"]}</b>')
            st.markdown(
                f'<div class="scen" style="margin-top:-4px">{und}<br>{opt}</div>',
                unsafe_allow_html=True)

            sym, qty = o.get("tradingsymbol"), sz["qty"]
            prem = o.get("premium")
            b1, b2, b3 = st.columns(3)
            nm = c["name"]
            with b1:
                order_button(
                    f"BUY {qty} @ mkt", f"buy_{nm}",
                    {"symbol": sym or "-", "side": "BUY", "qty": qty,
                     "type": "MARKET", "premium~": prem},
                    lambda sym=sym, qty=qty, nm=nm: __import__("broker").buy(
                        sym, qty, tag=f"desk:buy:{nm}"))
            with b2:
                trig = o.get("stop")
                order_button(
                    f"SET SL @ {trig}", f"sl_{nm}",
                    {"symbol": sym or "-", "side": "SELL", "qty": qty,
                     "type": "SL-M", "trigger": trig},
                    lambda sym=sym, qty=qty, trig=trig, nm=nm:
                        __import__("broker").stop_loss(sym, qty, trig,
                                                       tag=f"desk:sl:{nm}"))
            with b3:
                order_button(
                    f"EXIT {qty} @ mkt", f"exit_{nm}",
                    {"symbol": sym or "-", "side": "SELL", "qty": qty,
                     "type": "MARKET"},
                    lambda sym=sym, qty=qty, nm=nm: __import__("broker").sell(
                        sym, qty, tag=f"desk:exit:{nm}"))
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        cl, cr = st.columns(2)
        with cl:
            st.markdown('<div class="callsign">// LONG — BUY CE</div>',
                        unsafe_allow_html=True)
            for p in longs[:6]:
                signal_block(p, False)
                if st.button(f"Chart — {p['name']}", key=f"ch_l_{p['name']}",
                             use_container_width=True):
                    chart_window(p["name"])
        with cr:
            st.markdown('<div class="callsign">// SHORT — BUY PE</div>',
                        unsafe_allow_html=True)
            shorts = sel.get("shorts") or []
            if not shorts:
                st.caption("No name passes the short rule today.")
            for p in shorts[:6]:
                signal_block(p, True)
                if st.button(f"Chart — {p['name']}", key=f"ch_s_{p['name']}",
                             use_container_width=True):
                    chart_window(p["name"])

        st.caption("**SET SL rests at the exchange.** That is the difference between it "
                   "and the trailing stop in the session loop: the trail ratchets but "
                   "dies with the window, this one survives a closed laptop and cannot "
                   "trail. Place both — the trail for when you are watching, the resting "
                   "SL for when you are not.")

        if not bool(getattr(config, "TRADE_SHORTS", False)):
            st.warning(
                "**SHORT cards are shown, but the engine will not trade them.** "
                "The short book is mirrored and tested — stop above, PE, put intrinsic, "
                "weakest-first ranking — but its *edge* has not been measured on your "
                "data yet. Run `Tools → Short book test`; if the number holds up I will "
                "set `TRADE_SHORTS = True`. Looking at something and funding it are "
                "different decisions.")
        st.caption("**Pts now** = distance of spot from entry, in that trade's direction — not the "
                   "premium. The score is inverted for shorts: a strong stock makes a "
                   "poor short.")
    except Exception as e:      # noqa
        st.caption(f"cards failed: {e}")

# =================================================================== chart ==
st.markdown('<div class="sec">Chart — levels, and how often they held</div>',
            unsafe_allow_html=True)
if P:
    try:
        plan = []
        if card and card["name"] == pick:
            plan = [("STOP", card["stock"]["stop"], "#FF6BB0"),
                    ("T1", card["stock"]["t1"], "#5CF2FF"),
                    ("T2", card["stock"]["t2"], "#5CF2FF")]
        if not BARS:
            st.caption("No OHLCV bars — close line only. The levels are still real.")
        st.plotly_chart(make_fig(pick, prices.get(SYM, []), BARS, dates, F, plan),
                        use_container_width=True)
    except Exception as e:      # noqa
        st.caption(f"chart failed: {e}")

    # ------------------------------------------------------------ scenarios --
    st.markdown(
        f'<div class="scen">SCENARIO ANALYSIS [{pick} · NSE F&O] — support/resistance '
        f'+ 3-5 candle continuation + 60% body breakout rule</div>',
        unsafe_allow_html=True)

    r1, r2, s1, s2 = F.get("r1"), F.get("r2"), F.get("s1"), F.get("s2")
    if not (r1 and s1):
        st.caption("No levels — too little history for this name. No scenario either.")
    else:
        which = st.radio("Scenario", ["Bullish", "Sideways", "Bearish"],
                         horizontal=True, label_visibility="collapsed")
        cont = f"{F.get('cont_up', 0)}/5 up-candles"
        if which == "Bullish":
            st.success(
                f"**If** {pick} closes above {r1} on a **60%-body candle** with RVOL "
                f"{F.get('rvol','—')}x → **target {r2}**, **invalidation {s1}** "
                f"(below that the thesis is dead — flatten). Right now: {cont}, "
                f"{'expansion bar YES' if F.get('expanding') else 'no expansion bar yet'}."
                + ("" if F.get("room_up") else
                   f"  ⚠ R1 is only {F.get('to_resistance_atr')} ATR away — little room above."))
        elif which == "Bearish":
            st.error(
                f"**If** {pick} breaks {s1} on a 60% body → **target {s2}**, "
                f"**invalidation {r1}**. This system is long-only — this scenario is an "
                f"exit, not a trade. If a position is open, the stop is "
                f"{card['stock']['stop'] if card and card['name']==pick else s1}.")
        else:
            st.info(
                f"**If** {pick} stays between {s1}–{r1} → no trade. "
                f"Squeeze {F.get('squeeze','—')}"
                f"{' (COILED — waiting for the expansion bar)' if F.get('coiled') else ''}. "
                f"In a range, theta eats the premium; for a buyer this is the most "
                f"expensive scenario of the three.")
        st.caption("This is 'if X then Y', not a prediction. The levels come from the "
                   "bars, and the invalidation is written before the trade.")

# =================================================================== mauke ==
st.markdown('<div class="sec">Opportunities — names that pass the rule</div>', unsafe_allow_html=True)
st.caption("An empty feature means too little history for that name — and empty is never "
           "read as yes. **thesis** = the Q1 watchlist's fundamental trigger, if the name "
           "is on that list. It is a bias, not a signal, and none of it is backtested.")
WM = watch_map()
rows = []
for p in longs:
    f = p.get("feat") or {}
    rows.append({
        "names": p["name"],
        "thesis": (WM.get(p["name"]) or ("", ""))[0] or "—",
        "close": round(p.get("close", 0), 2),
        "trend %": p.get("abs_pct"),
        "VWAP": ("upar" if f.get("above_vwap") else "neeche") if f else "—",
        "RVOL": f.get("rvol", "—"),
        "squeeze": f.get("squeeze", "—"),
        "expansion": ("YES" if f.get("expanding") else "no") if f else "—",
        "structure": f.get("trend_struct", "—"),
        "R1 tak (ATR)": f.get("to_resistance_atr", "—"),
        "room": ("yes" if f.get("room_up") else "no") if f else "—",
        "OI": p.get("signal") or "—",
        "freshness": p.get("freshness"),
    })
if rows:
    clickable(rows, key="mauke")
else:
    st.caption("no names")

# =============================================================== scorecard ==
st.markdown('<div class="sec">Scorecard — 10-point conviction, every point named</div>',
            unsafe_allow_html=True)
try:
    import scorecard as SC
    ranked = sorted(pts, key=lambda p: SC.score(p)["total"], reverse=True)[:15]
    clickable(
        [{"names": p["name"], "LTP": round(p.get("close", 0), 2),
          "score": f"{SC.score(p)['total']}/{SC.MAX}",
          "verdict": SC.label(SC.score(p)["total"]),
          "what fired": ", ".join(h["label"] for h in SC.score(p)["hits"] if h["got"])
                          or "nothing"}
         for p in ranked], key="scorecard")
    st.caption("Every point is a gate that survived the walk-forward. **The weighting "
               "between them is not tested** — 10/10 is not a probability, and the size is "
               "still one lot. A missing feature scores nothing: unknown is never a yes.")

    shock = SC.volume_shock(pts, mult=float(getattr(config, "SHOCK_RVOL", 2.5)))
    st.markdown('<div class="sec">Volume shock — multiples of a name\'s own norm</div>',
                unsafe_allow_html=True)
    if shock:
        clickable([{"names": r["name"], "RVOL": f"{r['rvol']:.2f}x",
                    "LTP": round(r["close"] or 0, 2), "trend %": r["pct"],
                    "VWAP": r["vwap"],
                    "expansion": "YES" if r["expanding"] else "no"}
                   for r in shock], key="shock")
    else:
        st.caption("No name is running that far above its own norm today. Silence is "
                   "an answer too.")
except Exception as e:      # noqa
    st.caption(f"scorecard failed: {e}")

# ========================================================== chart list ==
st.markdown('<div class="sec">Chart list — names passing right now</div>',
            unsafe_allow_html=True)
st.caption("The 20 symbols in the Pine screener were picked by hand — those are the "
           "wrong 20. These came out of today's scan. Paste them into a TradingView "
           "watchlist and click through the names.")
try:
    import pine_export as PX
    picks = ([(p, "LONG") for p in longs] +
             [(p, "SHORT") for p in (sel.get("shorts") or [])])
    tv, seen = [], set()
    for p, sd in picks:
        t = PX.tv_symbol(p.get("symbol"))
        if t and t not in seen:
            seen.add(t)
            tv.append(t)
    if tv:
        st.code("\n".join(tv[:20]), language=None)
        st.caption(f"{len(tv[:20])} names · this scan. It is a **snapshot** — the next "
                   f"candle can change it. To write the Pine file: "
                   f"`python pine_export.py` (Tools → Chart list).")
    else:
        st.caption("Nothing passes right now. An empty list is an answer too — leaving "
                   "yesterday's list on the chart is worse, because it looks current.")
except Exception as e:      # noqa
    st.caption(f"list failed: {e}")

# =================================================================== score ==
st.markdown('<div class="sec">Score — paper vs what the backtest claimed</div>',
            unsafe_allow_html=True)
try:
    import paper as PB
    bk = PB.load()
    closed, open_ = bk.get("closed", []), bk.get("open", [])
    if not closed and not open_:
        st.caption("The paper book is empty. Run the '4 - PAPER LIVE' icon.")
    else:
        wins = [t for t in closed if t.get("pnl", 0) > 0]
        pnl = sum(t.get("pnl", 0) for t in closed)
        cap = float(getattr(config, "CAPITAL", 200000))
        m = st.columns(4)
        m[0].metric("Open", len(open_))
        m[1].metric("Closed", len(closed),
                    f"{100*len(wins)/len(closed):.0f}% won" if closed else "")
        m[2].metric("P&L", f"Rs {pnl:+,.0f}", f"{pnl/cap*100:+.1f}% capital")
        exp = PB.expectation()
        if exp and closed:
            band = PB.binomial_band(len(closed), exp["win_rate"] / 100.0)
            m[3].metric("Backtest claimed", f"{exp['win_rate']}%",
                        f"{band[0]:.0f}-{band[1]:.0f} wins expected")
            if band[0] <= len(wins) <= band[1]:
                st.caption("Inside the normal range — neither proof nor problem. Keep going.")
        if closed:
            st.dataframe([{k: t.get(k) for k in
                           ("name", "premium_in", "premium_out", "reason", "pnl")}
                          for t in closed[-15:]],
                         use_container_width=True, hide_index=True)
except Exception as e:      # noqa
    st.caption(f"paper book not found: {e}")

st.markdown(
    '<div class="disclaim">NOT FINANCIAL ADVICE — signals are inputs, the decision is yours. '
    'Options can lose 100% of the premium. Levels are computed from past bars and can fail.</div>',
    unsafe_allow_html=True)
