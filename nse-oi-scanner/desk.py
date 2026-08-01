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
  /* ONE LANDSCAPE PAGE, 21 inches.
     The cap was 1500px, so a 1920 screen threw away a fifth of its width and then made
     up for it by scrolling - the worst trade available. Full width, tight vertical
     rhythm, and the type size left alone: on a trading screen you shrink the margins,
     never the numbers. */
  .block-container {padding: .55rem 1.1rem 3.2rem 1.1rem; max-width: 100%;
                    position:relative; z-index:1;}
  /* Streamlit's own toolbar is a FIXED bar ~45px tall, and the default top padding of
     the container exists to clear it. Cutting that padding without removing the bar put
     the wordmark and the scan button underneath it - a screenshot showed a blank strip
     where the header should be, while AppTest happily reported both elements present.
     Rendered and visible are different claims. The toolbar carries Deploy and a menu
     neither of which this desk uses, so it goes, and its 45px go to the page. */
  [data-testid="stHeader"] {display:none;}
  [data-testid="stToolbar"] {display:none;}
  /* Streamlit's default gaps are generous for documents and wasteful for a desk */
  [data-testid="stVerticalBlock"] {gap: .32rem;}
  [data-testid="stHorizontalBlock"] {gap: .55rem;}
  [data-testid="stElementContainer"]:has(> .stMarkdown p:empty) {display:none;}
  hr {margin: .45rem 0;}

  /* tabs: the five screens. Each one is meant to fit without scrolling. */
  [data-testid="stTabs"] [data-baseweb="tab-list"] {gap:2px; background:#080C12;
      border:1px solid #14202C; border-radius:5px; padding:3px;}
  [data-testid="stTabs"] [data-baseweb="tab"] {height:30px; background:transparent;
      color:#4E6072; font-family: ui-monospace, Consolas, monospace; font-size:.7rem;
      font-weight:800; letter-spacing:1.3px; border-radius:3px; padding:0 14px;}
  [data-testid="stTabs"] [aria-selected="true"] {background:#00222B; color:#00E5FF;
      box-shadow:0 0 14px rgba(0,229,255,.25);}
  [data-testid="stTabs"] [data-baseweb="tab-highlight"],
  [data-testid="stTabs"] [data-baseweb="tab-border"] {display:none;}

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
      border-radius:4px; font-weight:700; letter-spacing:.6px; font-size:.74rem;
      text-transform:uppercase; transition:all .12s ease;
      /* a live ticket stacks three button rows; the default height put two tickets a
         side past one screen on their own */
      padding:.18rem .55rem; min-height:0; line-height:1.5;}
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
        border-bottom:1px solid #14202C; padding-bottom:4px; margin:.5rem 0 .45rem 0;
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

  /* ---- the order ticket: broker-app hierarchy, terminal palette ----
     One number dominates (what you pay), one action is primary, everything else is
     secondary and quiet. Roomy on purpose - a confirm sheet that has to be readable
     cannot live in a crushed column. */
  .ticket {background:#080C12; border:1px solid #14202C; border-radius:6px;
           padding:8px 12px 7px; margin-bottom:4px;}
  .tk-head {display:flex; align-items:center; gap:10px; margin-bottom:5px;}
  .tk-name {font-size:1.02rem; font-weight:800; color:#D5E6F2; letter-spacing:1.4px;
            font-family: ui-monospace, Consolas, monospace;}
  .tk-grade {font-size:.7rem; font-weight:800; color:#7CFF5E; margin-left:auto;
             font-family: ui-monospace, Consolas, monospace;}
  /* the verdict was a grid cell, and "WAIT FOR PULLBACK" wrapped to two lines and grew
     every ticket by a row. It is one chip in the head now, and it does not wrap. */
  .tk-act {font-size:.6rem; font-weight:800; letter-spacing:1px; padding:2px 7px;
           border-radius:3px; background:#0A0E14; color:#7CFF5E; border:1px solid #1E6610;
           white-space:nowrap; font-family: ui-monospace, Consolas, monospace;}
  .tk-big {font-size:1.6rem; font-weight:800; letter-spacing:1px; line-height:1.25;
           font-family: ui-monospace, Consolas, monospace; padding:0 0 3px;
           text-shadow:0 0 18px currentColor;}
  .tk-sub {font-size:.7rem; font-weight:600; color:#4E6072; letter-spacing:.3px;
           text-shadow:none;}
  /* six across: the whole plan - entry, stop, three targets, R - on two tight rows */
  .tk-grid {display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); gap:5px 10px;
            margin-top:5px; font-family: ui-monospace, Consolas, monospace;
            font-size:.78rem; color:#D5E6F2;}
  .tk-grid b {display:block; color:#3E5060; font-weight:600; font-size:.62rem;
              letter-spacing:.8px; text-transform:uppercase; margin-bottom:1px;}

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
  .mark {display:flex; align-items:baseline; gap:10px; margin:0; padding:2px 0;
         overflow:visible;}
  .mark-name {font-size:1.5rem; font-weight:800; letter-spacing:5px;
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
  /* the status strip: one line, pills, no wrapping. Scrolls sideways rather than
     growing a second row - a header that changes height moves the whole page. */
  .strip {display:flex; align-items:center; gap:7px; overflow-x:auto; padding:3px 0;
          font-family: ui-monospace, Consolas, monospace; white-space:nowrap;}
  .strip > span {display:inline-flex; align-items:baseline; gap:6px; padding:4px 10px;
          border:1px solid #14202C; border-radius:3px; background:#080C12;}
  .strip i {font-style:normal; font-size:.6rem; letter-spacing:1.2px; color:#3E5060;}
  .strip b {font-size:.82rem; font-weight:800; color:#5CF2FF; letter-spacing:.6px;}
  .strip .radar-dish {flex:none; display:inline-block; width:18px; height:18px;}
  /* the verdict, folded into the same line as the numbers that justify it */
  .verdict {font-size:.72rem; font-weight:800; letter-spacing:.6px; padding:5px 12px;
            border-radius:3px; font-family: ui-monospace, Consolas, monospace;}
  .verdict.banner-ok  {background:#00222B; color:#5CF2FF; border:1px solid #00E5FF;}
  .verdict.banner-mid {background:#0A2B05; color:#7CFF5E; border:1px solid #39FF14;}
  .verdict.banner-bad {background:#2B0016; color:#FF6BB0; border:1px solid #FF2D8A;}

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


@st.cache_data(ttl=180, show_spinner=False)
def chain_for(symbol, min_days):
    """(chain, expiry_label, days, lot, error) for one underlying.

    THIS IS WHY EVERY ORDER BUTTON WAS DEAD. The tickets called build_card() with no
    chain at all, so option_from_chain() had nothing to search, tradingsymbol came back
    None, and order_button's own guard greyed out all three buttons on every card - BUY,
    SET STOP and EXIT - for every name, always. The guard was right; there genuinely was
    no contract to send. Nobody had ever fetched one.

    Fetching it here also fixes the quantity: the live chain carries the real lot size,
    which is the one number the symbol-master parser keeps confusing with freeze quantity.

    The error is returned, not swallowed. "No contract" and "your token expired" and
    "this name has no F&O series" are three different problems with three different
    fixes, and a button that greys out identically for all three teaches nothing.
    """
    if DEMO:
        return None, None, None, None, "no token — DEMO data cannot produce a real contract"
    try:
        import option_chain as OC
        ch, lbl, days, lot = OC.tradeable_chain(symbol, min_days)
        if not ch:
            return None, None, None, None, "chain came back empty for this symbol"
        return ch, lbl, days, lot, None
    except Exception as e:      # noqa
        return None, None, None, None, str(e)[:160]


@st.cache_data(ttl=900, show_spinner="Fetching daily bars for the gap screen...")
def daily_bars(symbols, need):
    """{symbol: daily candles} — the DAILY series, whatever the desk itself runs on.

    The screen is written in daily terms: daily open, daily close, previous close, a
    20-DAY mean. Running it on the 15-minute bars the rest of the desk uses would compute
    a 20-BAR mean over five hours and call it a 20-day average - a different test wearing
    the same name, and one that would pass and fail on the wrong names all morning.

    In swing mode the loaded bars are already daily, so nothing is refetched. In intraday
    mode this is a separate pull, cached on disk per day by the engine underneath.
    """
    if int(getattr(config, "BAR_MINUTES", 375)) >= 375:
        return None          # the caller already holds daily bars; do not spend a fetch
    try:
        import rrg_engine as E
        E.fetch_history(list(symbols), resolution="D", days=max(90, need * 3))
        return dict(E.LAST_BARS or {})
    except Exception as e:      # noqa
        return {"__error__": str(e)[:200]}


@st.cache_data(ttl=120, show_spinner=False)
def exchange_quotes(symbols):
    """The exchange's own open / prev close / LTP, which is what decides this screen.

    Three of the four clauses are two numbers - today's OPEN and YESTERDAY'S CLOSE - and
    reading them off a derived daily candle instead of the published quote is the single
    biggest reason two screeners with identical rules return different names.

    Short TTL because the LTP inside it is "Daily Close" while the session runs.
    """
    if DEMO:
        return {}
    try:
        import rrg_engine as E
        return E.live_ohlc(list(symbols))
    except Exception:      # noqa - the caller falls back to candles and says so
        return {}


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
# --- end of sector helpers ---


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


def make_fig(name, closes, bars_, dates_, feat, plan=None, height=330):
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


def order_button(label, key, payload, fire, blocked=None, explain=True,
                 colour="#00E5FF", no_contract_why=None):
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
    # This guard existed and did nothing, because the caller passed `sym or "-"` for
    # display and "-" is truthy. The button armed, showed symbol=-, and only the broker
    # stopped it. A guard defeated by its own placeholder is worse than no guard: it reads
    # as protection on the screen and is not.
    if not payload.get("symbol") or payload["symbol"] in ("-", "None"):
        st.button(f"{label} · NO CONTRACT", key=key, disabled=True,
                  use_container_width=True)
        # Once per ticket, not once per button: the same sentence three times reads as
        # three problems and buries the one that matters.
        if explain:
            st.caption(f"**No contract:** "
                       f"{no_contract_why or 'the chain returned no tradeable symbol'}.")
        return
    if blocked:
        st.button(f"{label} · BLOCKED", key=key, disabled=True, use_container_width=True)
        if explain:
            st.error(blocked)
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
                                 height=300),
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

    # ---- the Chartink screen, with its numbers where he can reach them --------
    # A screener whose thresholds live in the source is a screener he has to ask me to
    # change. The band is the whole idea here - below 1% is noise, above 2% has already
    # moved - so the band is a control, not a constant.
    st.markdown('<div class="sec">Gap-up screen</div>', unsafe_allow_html=True)
    GAP_MIN = st.number_input("Gap at least (x prev close)", 1.000, 1.100,
                              float(getattr(config, "GAP_MIN", 1.01)), 0.001,
                              format="%.3f")
    GAP_MAX = st.number_input("Gap under (x prev close)", 1.001, 1.200,
                              float(getattr(config, "GAP_MAX", 1.02)), 0.001,
                              format="%.3f")
    GAP_SMA = int(st.number_input("SMA length (daily)", 5, 200,
                                  int(getattr(config, "GAP_SMA", 20)), 1))
    GAP_GATE = st.checkbox("Also require: 15-min close > day's open",
                           value=bool(getattr(config, "GAP_INTRADAY_GATE", False)))
    st.caption("Off by default because it is off on your Chartink. With it on, a name "
               "with no intraday bar **fails** rather than being skipped.")

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
# The wordmark and the scanner strip share ONE row. They used to take three rows between
# them - a title, a subtitle, and a strip of metrics - which is a hundred and forty pixels
# of a nine-hundred-pixel screen spent on saying whose desk this is.
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
if "last_scan" not in st.session_state:
    st.session_state.last_scan = None
#
# Six columns of st.metric next to a 2rem wordmark do not share a row: the metrics stack
# label-over-value, the row grows to the tallest of them, and the button gets pushed off
# the right edge - which is exactly what a screenshot showed. So the status is ONE strip
# of pills, laid out by CSS that knows they are on a line together, and the only widget in
# the row is the button.
sc = st.columns([2.5, 6.1, 1.4], vertical_alignment="center")
sc[0].markdown('<div class="mark"><span class="mark-name">AASHISH</span>'
               '<span class="mark-sub">Trading Desk</span></div>',
               unsafe_allow_html=True)
# filled after the data loads - the universe size is not known yet
STRIP = sc[1].empty()
if sc[2].button("⟳  RUN SCAN NOW", use_container_width=True, type="primary"):
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
STRIP.markdown(
    f'<div class="strip">'
    f'<span class="radar-dish"></span>'
    f'<span><i>SCAN</i><b>{"ARMED" if not DEMO else "DEMO"}</b></span>'
    f'<span><i>IST</i><b>{datetime.now(IST):%H:%M:%S}</b></span>'
    f'<span><i>LAST SCAN</i><b>{st.session_state.last_scan or "—"}</b></span>'
    f'<span><i>UNIVERSE</i><b>{len(pts)}</b></span>'
    f'<span><i>PASSING</i><b>{len(longs)}</b></span>'
    f'<span><i>BAR</i><b>{int(getattr(config, "BAR_MINUTES", 375))}min</b></span>'
    f'</div>', unsafe_allow_html=True)
# ---- the drawdown halt, where he can see it before he presses anything -------
# A halt that only announces itself at the moment an order is refused is a surprise. It
# belongs above the tabs, beside the tape, all day.
try:
    import risk_limits as RL
    RISK = RL.state()
    if RISK.get("halted"):
        st.markdown(f'<div class="hazard">⚠ RISK HALT — {RISK["reason"]}</div>',
                    unsafe_allow_html=True)
    if RISK.get("not_enforced"):
        st.caption(f"**Not enforced:** {', '.join(RISK['not_enforced'])} — not set in "
                   f"`config.py`, so they are not limits. Run `0 - UPDATE` to add them.")
except Exception as e:      # noqa
    RISK = None
    st.caption(f"risk limits unavailable: {e}")

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

# ================================================================== ribbon ==
# The verdict and the numbers behind it used to be two stacked blocks - a 45px banner and
# a 70px ribbon - repeated above all five tabs. That is 115px of every screen spent twice.
# One line of pills carries the same eight facts in 37px, and the verdict is the pill on
# the left, colour-coded exactly as the banner was. Nothing was dropped; it was folded.
if P:
    px = P.get("close", 0)
    chg = P.get("abs_pct")
    rv = F.get("rvol")
    vw = F.get("above_vwap")
    cells = [
        ("SPOT", f"{px:,.2f}"),
        ("TREND", f'<span class="{"up" if (chg or 0) >= 0 else "dn"}">{chg:+.2f}%</span>'
         if chg is not None else "—"),
        ("VS VWAP", f'<span class="{"up" if vw else "dn"}">{"ABOVE" if vw else "BELOW"}</span>'
         if F else "—"),
        ("RVOL", f"{rv:.2f}x" if rv else "—"),
        ("ATR", F.get("atr", "—")),
        ("SQUEEZE", f'{F.get("squeeze","—")}{" · COILED" if F.get("coiled") else ""}'),
        ("EXPANSION", '<span class="up">YES</span>' if F.get("expanding") else "no"),
    ]
    st.markdown(
        f'<div class="strip hud"><span class="verdict {cls}">{msg}</span>'
        f'<span><i>NAME</i><b class="reticle">{pick}</b></span>'
        + "".join(f'<span><i>{k}</i><b>{v}</b></span>' for k, v in cells)
        + '</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="strip hud"><span class="verdict {cls}">{msg}</span></div>',
                unsafe_allow_html=True)

# ===================================================================== tabs ==
# ONE LANDSCAPE PAGE
#
# A 21-inch screen is about 1900x950 of usable browser. The page used to run past six
# thousand pixels of scroll, which meant the ticket he is about to press BUY on and the
# heatmap that justifies it could never be on screen together - and a decision made by
# scrolling back and forth is a decision made from memory.
#
# So: tabs, each sized to fit one screen without scrolling, plus a status strip that
# stays above all of them. Tabs rather than a smaller font, because shrinking type on a
# trading screen is how a 5418 gets read as a 5413.
T_DECK, T_SIG, T_GAP, T_CHART, T_SCREEN, T_SCORE = st.tabs(
    ["◈  COMMAND DECK", "◈  SIGNALS & TICKETS", "◈  GAP-UP", "◈  CHART",
     "◈  SCREENER", "◈  SCORE"])

with T_DECK:
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

with T_SIG:
    # ============================================================ aaj ka trade ==
    # The top pick's card is still built here - the chart tab draws its stop and targets,
    # and `card` is what it reads. What is NOT drawn any more is the metric row that used
    # to sit above the tickets: name, strike, premium, qty, cost, stop, targets. Every one
    # of those numbers is on the first LONG ticket below, in more detail and with the
    # buttons attached, so the row was three hundred pixels of a nine-hundred-pixel screen
    # spent saying the same thing twice. Its warnings print on that ticket too.
    card = None
    if not longs:
        st.info("No name passes the setup. Not taking one is also a position.")
    else:
        top = longs[0]
        closes = prices.get(top["symbol"]) or [top["close"]]
        card = TC.build_card(top, closes, expiry_label="—",
                             days_to_expiry=TC.min_days_for_thesis(),
                             capital=float(getattr(config, "CAPITAL", 200000)))

    # ------------------------------------------------------------- trade cards --
    # Every candidate as a ticket: side, grade, entry / stop / TP1 / TP2 / TP3, the option leg,
    # and three order buttons.
    #   SIDE   LONG buys CE, SHORT buys PE. Short tickets are drawn but the engine will not
    #          trade them until the short book's edge is measured - a card is an instruction,
    #          so the untested side says so on its face.
    #   LEVELS all come off the card, and the card measures every one of them from the ENTRY.
    #          TP1/TP2/TP3 are 1.5R / 3R / 4R. Nothing here recomputes them; recomputing is
    #          exactly how the desk and the card drifted apart before.
    if longs:
        try:
            import scorecard as SC

            def grade(total):
                return ("A+" if total >= 9 else "A" if total >= 7
                        else "B" if total >= 5 else "C")

            def signal_block(p, is_short):
                """One position ticket, laid out the way a broker app lays one out.

                Robinhood's lesson is not the colour, it is the hierarchy: ONE number you are
                about to pay, ONE primary action, and everything else quieter and out of the
                way. The old version put three equal buttons in a narrow half-width column, so
                "CANCEL" wrapped to three lines and the confirm sheet was unreadable at the
                moment it mattered most. Full width, one action, the rest secondary.
                """
                need = TC.min_days_for_thesis()
                ch, lbl, days, chlot, cherr = chain_for(p["symbol"], need)
                c = TC.build_card(p, prices.get(p["symbol"]) or [p["close"]],
                                  chain=ch,
                                  expiry_label=lbl or "—",
                                  days_to_expiry=days if days is not None else need,
                                  lot=chlot,
                                  capital=float(getattr(config, "CAPITAL", 200000)),
                                  side="SHORT" if is_short else "LONG")
                _CARDS[c["name"]] = c
                o = c.get("option") or {}
                stk, sz = c["stock"], c["size"]
                # Take these from the card. Recomputing R and a third target here is exactly
                # how the two halves drifted before: the card measured from spot, the desk
                # measured from entry, and the R:R on screen belonged to neither.
                e, sl = stk["entry_px"], stk["stop"]
                r, t3 = stk["risk_pts"], stk["t3"]
                prem, qty = o.get("premium"), sz["qty"]
                sym = o.get("tradingsymbol")
                outlay = (prem or 0) * qty

                import scorecard as SC
                sc_ = SC.score(p)
                total = (sc_["of"] - sc_["total"]) if is_short else sc_["total"]
                g = grade(total)
                side_txt = "SHORT · BUY PE" if is_short else "LONG · BUY CE"
                acc = "#FF2D8A" if is_short else "#00E5FF"

                # A lot that implies an absurd contract value is not a display problem, it is
                # a wrong quantity - and a wrong quantity one confirm away from the exchange.
                blocked = None
                if sz.get("lot_absurd"):
                    blocked = (f"Quantity refused. {sz['lot_warning']}  "
                               f"Fix with Tools → Lot Audit before ordering this name.")
                # MAX_LOSS is an absolute cap, so it BLOCKS the ticket rather than
                # printing beside it. A cap that only warns is not a cap.
                elif sz.get("max_loss_breach"):
                    blocked = f"Over your MAX_LOSS cap — {sz['max_loss_breach']}."
                # The CONTRACT's own gates. Everything above this line judged the stock;
                # for a buyer the contract is the trade, and a strike nobody can exit at
                # a fair price is not tradeable however good the name looks.
                elif o.get("quality_fails"):
                    blocked = ("Contract fails its own checks — "
                               + "; ".join(o["quality_fails"]) + ".")

                # THE BUYER'S OWN NUMBERS. Until now the ticket showed what the STOCK
                # would do and priced the option off it. It never said what holding the
                # option costs per day, nor whether the premium was fair against what the
                # name has actually been moving — the two questions a buyer lives or dies
                # on. Built here rather than inline: nested quotes inside an f-string are
                # a syntax error waiting for the one edit that trips it.
                q = o.get("quality") or {}
                # Record today's implied vol so an IV RANK becomes possible with time.
                # Naming a store in a docstring and never writing to it is a limitation
                # that never expires, because nothing ever starts collecting. Once per
                # name per day - the desk reruns on every click, and observing on each
                # rerun would weight a day he browsed a lot above one he did not.
                if q.get("iv") and not DEMO:
                    try:
                        import iv_history as IVH
                        IVH.record(p["symbol"], q["iv"], spot=c.get("spot"),
                                   dte=o.get("days_to_expiry"))
                        rk, rk_note = IVH.rank(p["symbol"], q["iv"])
                        q["iv_rank"], q["iv_rank_note"] = rk, rk_note
                    except Exception:      # noqa - never let bookkeeping break a ticket
                        pass
                qcells = ""
                if q:
                    vv = q.get("vol") or {}
                    ratio = f'{vv["ratio"]}x' if vv.get("ratio") else "—"
                    vcol = "#FF6BB0" if vv.get("verdict") == "EXPENSIVE" else "#5CF2FF"
                    spread = (f'{q["spread_pct"] * 100:.1f}%'
                              if q.get("spread_pct") else "—")
                    oi_txt = f'{int(q["oi"]):,}' if q.get("oi") else "—"
                    theta = o.get("theta_rs_day")
                    theta_txt = f'₹{theta:,}' if theta is not None else "—"
                    qcells = (
                        f'<div><b>IV vs realised</b><span style="color:{vcol}">'
                        f'{ratio} {vv.get("verdict", "")}</span></div>'
                        f'<div><b>Theta / day</b>'
                        f'<span style="color:#FF6BB0">{theta_txt}</span></div>'
                        f'<div><b>Delta</b>{q.get("delta", "—")}</div>'
                        f'<div><b>Spread</b>{spread}</div>'
                        f'<div><b>Strike OI</b>{oi_txt}</div>')

                st.markdown(
                    f'<div class="ticket hud">'
                    f'<div class="tk-head">'
                    f'<span class="side" style="background:{acc}22;color:{acc}">{side_txt}</span>'
                    f'<span class="tk-name">{c["name"]}</span>'
                    f'<span class="tk-act">{c["action"]}</span>'
                    f'<span class="tk-grade">★ {g} &nbsp;{total}/{sc_["of"]}</span></div>'
                    f'<div class="tk-big" style="color:{acc}">₹{prem if prem is not None else "—"}'
                    f'<span class="tk-sub">&nbsp;per unit &nbsp;·&nbsp; {o.get("strike","?")} '
                    f'{o.get("type","")} {o.get("expiry","")} &nbsp;·&nbsp; '
                    f'{"LIVE CHAIN" if o.get("premium_source") == "live chain" else "ESTIMATED"}'
                    f' &nbsp;·&nbsp; {qty} qty &nbsp;·&nbsp; '
                    f'<b style="color:#D5E6F2">₹{outlay:,.0f} to buy</b></span></div>'
                    f'<div class="tk-grid">'
                    f'<div><b>Stock entry</b>{e}</div>'
                    f'<div><b>Stock SL</b><span style="color:#FF6BB0">{sl}</span></div>'
                    f'<div><b>TP1 · {stk["rr1"]}R</b>{stk["t1"]}</div>'
                    f'<div><b>TP2 · {stk["rr2"]}R</b>{stk["t2"]}</div>'
                    f'<div><b>TP3 · {stk["rr3"]}R</b>{t3}</div>'
                    f'<div><b>Option SL</b><span style="color:#FF6BB0">{o.get("stop","—")}</span></div>'
                    f'<div><b>Option TP1</b>{o.get("t1","—")}</div>'
                    f'<div><b>Option TP2</b>{o.get("t2","—")}</div>'
                    f'<div><b>Option TP3</b>{o.get("t3","—")}</div>'
                    f'<div><b>R (points)</b>{r}</div>'
                    f'<div><b>R:R at TP1</b>{stk["rr1"]} : 1</div>'
                    + qcells
                    + '</div></div>', unsafe_allow_html=True)

                for w in (o.get("premium_reject"), o.get("expiry_warning"),
                          sz.get("cost_warning"), c.get("afford_note")):
                    if w:
                        st.warning(w)
                # "extended 2.9x vol above its 10-day mean - don't chase". It used to
                # print only for the top pick; it is per-card, so it belongs per card.
                if c.get("entry_note"):
                    st.caption(c["entry_note"])

                nm = c["name"]
                order_button(
                    f"BUY {qty} @ market  ·  ₹{outlay:,.0f}", f"buy_{nm}",
                    {"symbol": sym, "side": "BUY", "qty": qty, "type": "MARKET",
                     "premium~": prem, "outlay~": round(outlay)},
                    lambda sym=sym, qty=qty, nm=nm: __import__("broker").buy(
                        sym, qty, tag=f"desk:buy:{nm}"),
                    blocked=blocked, no_contract_why=cherr)
                b1, b2 = st.columns(2)
                with b1:
                    trig = o.get("stop")
                    order_button(
                        f"Set stop @ {trig}", f"sl_{nm}",
                        {"symbol": sym, "side": "SELL", "qty": qty, "type": "SL-M",
                         "trigger": trig},
                        lambda sym=sym, qty=qty, trig=trig, nm=nm:
                            __import__("broker").stop_loss(sym, qty, trig,
                                                           tag=f"desk:sl:{nm}"),
                        blocked=blocked, explain=False, no_contract_why=cherr)
                with b2:
                    order_button(
                        f"Exit {qty} @ market", f"exit_{nm}",
                        {"symbol": sym, "side": "SELL", "qty": qty, "type": "MARKET"},
                        lambda sym=sym, qty=qty, nm=nm: __import__("broker").sell(
                            sym, qty, tag=f"desk:exit:{nm}"),
                        blocked=blocked, explain=False, no_contract_why=cherr)
                if st.button(f"Chart — {nm}", key=f"ch_{nm}", use_container_width=True):
                    chart_window(nm)
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            # LONG on the left, SHORT on the right - the two sides of the book side by
            # side, three deep each, so the whole tradeable set is on one landscape screen
            # instead of twelve tickets deep in a scroll.
            #
            # This is NOT the layout that crushed the confirm sheet. That one put three
            # equal buttons inside a half-width column of a 1500px page - 250px each, and
            # "CANCEL" wrapped to three lines. The page is now full-width, so a column here
            # is ~900px and the confirm sheet has more room than the old single column had
            # buttons. The rule was never "one column", it was "the confirm sheet has to be
            # readable"; width is what that needs, and width is what it now has.
            TICKETS_PER_SIDE = 2
            shorts = sel.get("shorts") or []
            L, R = st.columns(2, gap="medium")
            with L:
                st.markdown('<div class="callsign">// LONG — BUY CE</div>',
                            unsafe_allow_html=True)
                if not longs:
                    st.caption("No name passes the long rule right now.")
                for p in longs[:TICKETS_PER_SIDE]:
                    signal_block(p, False)
                if len(longs) > TICKETS_PER_SIDE:
                    # one line, not three: this caption was 45px of a tab that was 29px
                    # over, which made it the most expensive sentence on the page
                    st.caption(f"+{len(longs) - TICKETS_PER_SIDE} more longs — see **SCREENER**.")
            with R:
                st.markdown('<div class="callsign">// SHORT — BUY PE</div>',
                            unsafe_allow_html=True)
                if not shorts:
                    st.caption("No name passes the short rule today.")
                for p in shorts[:TICKETS_PER_SIDE]:
                    signal_block(p, True)
                if len(shorts) > TICKETS_PER_SIDE:
                    st.caption(f"+{len(shorts) - TICKETS_PER_SIDE} more shorts — see **SCREENER**.")

            # Two hundred pixels of prose he has already read, on the tab where space is
            # scarcest. Collapsed, not deleted - the caveats are the reason the buttons
            # are safe to press, so they stay one click away rather than gone.
            with st.expander("How to read this tab — stops, shorts, and what the numbers mean"):
                st.caption("**SET STOP rests at the exchange.** That is the difference "
                           "between it and the trailing stop in the session loop: the "
                           "trail ratchets but dies with the window, this one survives a "
                           "closed laptop and cannot trail. Place both — the trail for "
                           "when you are watching, the resting stop for when you are not.")
                if not bool(getattr(config, "TRADE_SHORTS", False)):
                    st.warning(
                        "**SHORT tickets are shown, but the engine will not trade them.** "
                        "The short book is mirrored and tested — stop above, PE, put "
                        "intrinsic, weakest-first ranking — but its *edge* has not been "
                        "measured on your data yet. Run `Tools → Short book test`; if the "
                        "number holds up I will set `TRADE_SHORTS = True`. Looking at "
                        "something and funding it are different decisions.")
                st.caption("The score is inverted for shorts: a strong stock makes a poor "
                           "short. TP1/TP2/TP3 are 1.5R / 3R / 4R measured from the entry "
                           "on the ticket, and R is that ticket's own entry-to-stop "
                           "distance.")
        except Exception as e:      # noqa
            st.caption(f"cards failed: {e}")

with T_GAP:
    # ================================================================== gap-up ==
    # THE CHARTINK SCREEN, run on our own bars.
    #
    #     Daily Close  >  1 day ago Sma(1 day ago Close, 20)
    #     Daily Open   >  1 day ago Close * 1.01
    #     Daily Open   <  1 day ago Close * 1.02
    #     [0] 15 minute Close > Daily Open        <- off there, off here
    #
    # It is deliberately its OWN tab and not a filter over the signal book. The two ask
    # different questions - the ticket book asks "what does the tested rule say", this
    # asks "what gapped and held" - and quietly intersecting them would produce a list
    # that is neither, with the authority of both.
    #
    # Nothing here is walk-forward tested. That sentence is on the screen too.
    st.markdown('<div class="sec">Gap-up screen — Chartink filter, our bars</div>',
                unsafe_allow_html=True)
    try:
        import gapup as GU

        GAP_CFG = {"sma_len": GAP_SMA, "gap_min": GAP_MIN, "gap_max": GAP_MAX,
                   "use_intraday_gate": GAP_GATE}
        st.markdown(
            f'<div class="scen">Close &gt; SMA{GAP_SMA} (ending yesterday) &nbsp;·&nbsp; '
            f'Open &gt; prev close x {GAP_MIN:g} &nbsp;·&nbsp; '
            f'Open &lt; prev close x {GAP_MAX:g}'
            + (' &nbsp;·&nbsp; 15-min close &gt; day open' if GAP_GATE else '')
            + ' &nbsp;·&nbsp; F&amp;O segment</div>', unsafe_allow_html=True)

        syms = [p["symbol"] for p in pts if p.get("symbol")]
        db = daily_bars(tuple(syms), GAP_SMA)
        src = "a separate daily pull"
        if db is None:                    # swing mode: the loaded bars ARE daily
            db, src = bars or {}, "the bars already loaded (this desk runs daily)"
        if isinstance(db, dict) and db.get("__error__"):
            st.error(f"Daily bars did not load: {db['__error__']}  "
                     f"The screen needs daily candles and will not guess at them from "
                     f"15-minute ones.")
            db = {}

        # the [0] 15-minute clause reads the desk's own intraday closes
        last_i = {p["symbol"]: (prices.get(p["symbol"]) or [None])[-1] for p in pts} \
            if GAP_GATE else None
        qs = exchange_quotes(tuple(syms))
        rows = GU.scan(db, pts, GAP_CFG, last_i, qs)

        # WHICH FEED DECIDED THIS. Not decoration: a screen that silently swaps its
        # input source between runs produces two different lists from one rule and gives
        # no way to tell which run was which.
        # A name cannot pass a screen it was never shown to. If the universe came from a
        # stale cache or the hard-coded fallback, every name NSE has added since is
        # missing - and a missing name looks exactly like a name that did not qualify.
        try:
            import fno_universe as _U
            u_src, u_note = _U.source()
            if u_src in ("stale cache", "fallback"):
                st.error(f"**Universe is {u_src}** — {u_note}  "
                         f"Run `python fno_universe.py` on a machine with internet, or "
                         f"`0 - UPDATE`, before trusting this list is complete.")
        except Exception:      # noqa
            pass

        src_txt = ("exchange quotes — the same open and previous close every other "
                   "screener reads" if qs else
                   "daily candles — no live quote feed, so open and previous close are "
                   "taken off the last candle and may differ from Chartink's by a few "
                   "paise at the band edge")
        st.caption(f"Prices from **{src_txt}**. The {GAP_SMA}-day mean always comes from "
                   f"daily candles — there is no quote for an average.")

        # A prev close the two feeds disagree about is a corporate action one of them has
        # applied. The mean is rescaled onto the quote's basis rather than left to
        # compare an adjusted price against unadjusted history - but the repair is stated,
        # because a number that was silently corrected is still a number he did not
        # choose.
        for r in [x for x in rows if x.get("conflict")]:
            st.info(f"**{r['name']}** — {r['conflict']}")

        g1, g2 = st.columns([2.1, 1], gap="medium")
        with g1:
            if rows:
                clickable([{k: v for k, v in r.items()
                            if k not in ("clauses", "conflict")} for r in rows],
                          key="gapup")
                st.caption(f"{len(rows)} of {len(db)} names pass · sorted by how much of "
                           f"the gap they have **held** since the open — the gap is the "
                           f"entry condition, what happened after it is the only new "
                           f"information the morning has produced. Click a row for its "
                           f"chart.")
            elif db:
                # "nobody gapped into the band" and "this data has no gaps at all" look
                # identical as an empty list and are completely different claims. The
                # demo used to open every session exactly at the previous close, which
                # made this screen structurally incapable of returning anything, and the
                # empty list read as an observation. So the count is stated.
                gapped = sum(1 for b in db.values()
                             if len(b) > 2 and abs(float(b[-1][1]) - float(b[-2][4])) > 1e-9)
                st.info(f"No name passes the gap screen right now, out of {len(db)} "
                        f"checked — {gapped} of them gapped in any direction at all. "
                        f"Empty is an answer; a screen that always returns something is "
                        f"not a screen.")
            else:
                st.caption("No daily bars — nothing to screen.")
        with g2:
            st.markdown('<div class="callsign">// WHY IT PASSED</div>',
                        unsafe_allow_html=True)
            if rows:
                who = st.selectbox("Name", [r["name"] for r in rows],
                                   label_visibility="collapsed")
                r = next((x for x in rows if x["name"] == who), None)
                for c in (r or {}).get("clauses", []):
                    st.markdown(
                        f'<div class="hm" style="border-color:'
                        f'{"#0A6675" if c["ok"] else "#7A0B3D"}">'
                        f'<div class="hm-n">{"✓" if c["ok"] else "✗"} {c["clause"]}</div>'
                        f'<div style="font-family:ui-monospace,Consolas,monospace;'
                        f'font-size:.8rem;color:#D5E6F2">{c["detail"]}</div></div>',
                        unsafe_allow_html=True)
            else:
                st.caption("Nothing to explain yet.")

        # WHY THIS LIST DIFFERS FROM CHARTINK'S
        # Two screens running the same four clauses disagree at the BAND EDGES, because
        # a 0.98% gap and a 1.02% gap are the same event on opposite sides of a
        # threshold - and the two feeds do not agree to the paisa on yesterday's close
        # (corporate-action adjustments land on different days). A name missing here is
        # usually not a bug, it is a number differing in the second decimal. Showing the
        # near-misses turns "the lists are different" into "this figure is different".
        with st.expander("Near misses — names that failed exactly one clause "
                         "(this is usually where a Chartink disagreement lives)"):
            nm_rows = GU.near_misses(db, pts, GAP_CFG, last_i, quotes=qs)
            if nm_rows:
                st.dataframe(nm_rows, use_container_width=True, hide_index=True)
                st.caption("`missed_by_pct` is measured on the clause that actually "
                           "failed — distance outside the band for a gap clause, "
                           "distance below the mean for the SMA clause. A name Chartink "
                           "shows and this does not will almost always be near the top "
                           "here; run `python gapup.py --explain NAME` and compare the "
                           "previous close before assuming either screen is wrong.")
            else:
                st.caption("Nothing failed on a single clause.")

        st.warning(
            "**This screen is not backtested.** It is the Chartink filter, computed on "
            "your bars so the numbers can be checked — a name here means *worth opening "
            "the ticket for*, never *place this*. The tested rule is on **SIGNALS & "
            "TICKETS**; that is the one with an edge measured on your data. The last "
            "untested thing that reached a main window (RRG) cost −6.3% after costs.")
    except Exception as e:      # noqa
        st.error(f"gap screen failed: {e}")

with T_CHART:
    # =================================================================== chart ==
    # The chart is the tall element on the page, so nothing else may sit under it -
    # the list and the links go beside it, in the width that was being wasted.
    CH_L, CH_R = st.columns([3.1, 1.15], gap="medium")
    CHART_SIDE = CH_R
    with CH_L:
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

with T_SCREEN:
    # =================================================================== mauke ==
    # Two tables stacked ran the page 455px past one screen. Side by side they fit, and
    # the comparison they invite - who passes vs who scores - is the reason to look at
    # both at once anyway.
    SC_L, SC_R = st.columns([1.55, 1], gap="medium")
    with SC_L:
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

    with SC_R:
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

with CHART_SIDE:
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

with T_SCORE:
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
