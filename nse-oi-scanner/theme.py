"""
theme.py  —  the desk's look, as named tokens rather than 202 hex codes.

The palette changed twice: a GitHub-ish dark, then three neons on black, now Claude's
warm paper. Each time it meant editing colours scattered through a 1,700-line file, and
each time a few were missed - the heatmap kept its rgba() greens after everything else
had moved, because a hex-based sweep could not see them.

So the colours live here, with NAMES, and the page asks for meaning instead of for a
hex. `T["up"]` is "this went up"; what colour that is becomes a one-line decision.

THE SEMANTICS ARE FIXED, THE COLOURS ARE NOT
Whatever the palette, exactly four things carry colour on this page:

    up      the move went his way / a gate passed
    down    it went against him / a gate failed
    attn    look here - not good, not bad
    accent  the brand, and the one primary action per screen

Nothing else gets a colour. That rule is what makes a colour on this screen readable at
a glance, and it is the reason a fifth colour is a bug rather than a decoration.

    python theme.py            # print both palettes
"""

# ---------------------------------------------------------------- palettes --
# CLAUDE: warm paper, serif prose, monospace numbers, one coral accent, almost no
# borders. Quiet by default so that a colour means something when it appears.
CLAUDE = {
    "name": "claude",
    "base": "light",
    "bg": "#FAF9F5",          # warm paper
    "panel": "#FFFFFF",       # cards sit slightly above the page
    "panel2": "#F2F0E9",      # inset blocks, code, table headers
    "ink": "#1F1E1D",         # body text, near-black but warm
    "ink_soft": "#3D3B37",
    "muted": "#8C8880",       # labels, captions
    "line": "#E6E3DA",        # hairlines - this palette leans on space, not borders
    "accent": "#D97757",      # Claude coral: the brand and the ONE primary action
    "accent_soft": "#F5E3DA",
    "up": "#1B6E8C",          # blue = up / pass, as he set it
    "up_soft": "#E1EEF3",
    "down": "#B03A5B",        # rose = down / fail
    "down_soft": "#F7E3E8",
    "attn": "#2F7A46",        # green = attention
    "attn_soft": "#E3F0E7",
    "font": ('ui-serif, Georgia, "Iowan Old Style", "Palatino Linotype", '
             '"Times New Roman", serif'),
    "mono": 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
    # Claude sets PROSE in serif and the chrome - labels, tabs, buttons - in a sans.
    # Serif at 0.6rem uppercase is both wrong to the reference and wider, which is what
    # made the ticket labels wrap onto a second line.
    "ui": ('-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, '
           "system-ui, sans-serif"),
}

# NEON: three neons on black, the previous look. Kept whole so switching back is a
# choice rather than an archaeology exercise.
NEON = {
    "name": "neon",
    "base": "dark",
    "bg": "#04060A",
    "panel": "#080C12",
    "panel2": "#0A0E14",
    "ink": "#D5E6F2",
    "ink_soft": "#B8CEE0",
    "muted": "#4E6072",
    "line": "#14202C",
    "accent": "#39FF14",
    "accent_soft": "#0A2B05",
    "up": "#00E5FF",
    "up_soft": "#00222B",
    "down": "#FF2D8A",
    "down_soft": "#2B0016",
    "attn": "#39FF14",
    "attn_soft": "#0A2B05",
    "font": 'ui-monospace, Consolas, "SF Mono", monospace',
    "mono": 'ui-monospace, Consolas, "SF Mono", monospace',
    "ui": 'ui-monospace, Consolas, "SF Mono", monospace',
}

PALETTES = {"claude": CLAUDE, "neon": NEON}
DEFAULT = "claude"


def get(name=None):
    return PALETTES.get(str(name or DEFAULT).lower(), CLAUDE)


def tint(hex_colour, alpha):
    """`rgba()` from a palette colour. The heatmap needs a wash whose strength carries
    the size of the move, and writing that as a literal is how the last palette change
    left neon greens behind: a sweep for hex codes is blind to rgba(), so the orphan
    survived every check. Derive it from the token instead."""
    h = str(hex_colour).lstrip("#")
    if len(h) != 6:
        return hex_colour
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{max(0.0, min(1.0, float(alpha))):.3f})"


def css(T):
    """The whole style block, built from the palette. One f-string, no stray hexes."""
    return f"""
<style>
  /* ==================================================================== */
  /*  {T['name'].upper()} — up={T['up']}  down={T['down']}  attn={T['attn']}      */
  /*  Four meanings carry colour. A fifth colour is a bug.                */
  /* ==================================================================== */
  .stApp {{background:{T['bg']}; color:{T['ink']};}}
  html, body, [class*="css"] {{font-family:{T['font']};}}

  /* ONE LANDSCAPE PAGE, 21 inches: full width, tight vertical rhythm, type
     left alone. On a trading screen you shrink the margins, never the numbers. */
  .block-container {{padding:.55rem 1.2rem 3.2rem 1.2rem; max-width:100%;
                    position:relative; z-index:1;}}
  [data-testid="stVerticalBlock"] {{gap:.34rem;}}
  [data-testid="stHorizontalBlock"] {{gap:.6rem;}}
  hr {{margin:.45rem 0; border-color:{T['line']};}}
  /* Streamlit's toolbar is a FIXED bar the default top padding exists to clear.
     Cutting that padding without removing the bar puts the header underneath it. */
  [data-testid="stHeader"], [data-testid="stToolbar"] {{display:none;}}

  /* numbers are monospace everywhere - a price that changes width as it ticks is
     harder to read at a glance than one that does not */
  [data-testid="stMetricValue"] {{font-size:1.3rem; color:{T['ink']};
      font-family:{T['mono']};}}
  [data-testid="stMetricLabel"] {{font-size:.7rem; color:{T['muted']};
      letter-spacing:.4px; text-transform:uppercase; font-family:{T['ui']};}}
  [data-testid="stMetricDelta"] {{font-family:{T['mono']};}}

  code, pre, .stCode {{background:{T['panel2']} !important; border:1px solid {T['line']};
      color:{T['ink']} !important; font-family:{T['mono']};}}
  ::selection {{background:{T['accent_soft']}; color:{T['ink']};}}

  /* Controls are quiet pills. Exactly ONE primary action per screen carries the
     accent - that is the whole hierarchy, and a second one destroys it. */
  .stButton > button {{background:{T['panel']}; color:{T['ink_soft']};
      border:1px solid {T['line']}; border-radius:9px; font-weight:600;
      letter-spacing:.2px; font-size:.8rem; font-family:{T['ui']};
      padding:.24rem .7rem; min-height:0; line-height:1.5; transition:all .12s ease;}}
  .stButton > button:hover {{border-color:{T['accent']}; color:{T['accent']};}}
  .stButton > button[kind="primary"] {{background:{T['accent']}; color:#FFFFFF;
      border-color:{T['accent']};}}
  .stButton > button[kind="primary"]:hover {{filter:brightness(1.06); color:#FFFFFF;}}

  [data-testid="stDataFrame"] {{border:1px solid {T['line']}; border-radius:9px;}}
  [data-testid="stDataFrame"] * {{font-family:{T['mono']} !important;}}

  /* tabs: the six screens, each sized to fit one screen */
  [data-testid="stTabs"] [data-baseweb="tab-list"] {{gap:2px; background:{T['panel2']};
      border:1px solid {T['line']}; border-radius:10px; padding:3px;}}
  [data-testid="stTabs"] [data-baseweb="tab"] {{height:30px; background:transparent;
      color:{T['muted']}; font-family:{T['ui']}; font-size:.78rem; font-weight:600;
      letter-spacing:.3px; border-radius:8px; padding:0 14px;}}
  [data-testid="stTabs"] [aria-selected="true"] {{background:{T['panel']};
      color:{T['ink']}; box-shadow:0 1px 2px rgba(0,0,0,.06);}}
  [data-testid="stTabs"] [data-baseweb="tab-highlight"],
  [data-testid="stTabs"] [data-baseweb="tab-border"] {{display:none;}}

  .tag {{display:inline-block; padding:3px 10px; border-radius:20px; margin-right:6px;
        font-size:.7rem; font-weight:600; letter-spacing:.2px; font-family:{T['ui']};}}
  .ok   {{background:{T['up_soft']};   color:{T['up']};}}
  .warn {{background:{T['attn_soft']}; color:{T['attn']};}}
  .bad  {{background:{T['down_soft']}; color:{T['down']};}}
  .muted{{background:{T['panel2']};    color:{T['muted']};}}
  .up   {{color:{T['up']};}} .dn {{color:{T['down']};}}

  .scen {{background:{T['panel2']}; border-left:2px solid {T['accent']};
         border-radius:8px; padding:9px 14px; font-size:.82rem; color:{T['ink_soft']};
         margin:.2rem 0 .6rem 0;}}

  .sec {{font-size:.72rem; letter-spacing:1.4px; text-transform:uppercase;
        color:{T['muted']}; border-bottom:1px solid {T['line']}; padding-bottom:4px;
        margin:.5rem 0 .45rem 0; font-family:{T['ui']}; font-weight:600;}}

  /* heatmap tiles, radar badges */
  .hm {{border-radius:9px; padding:10px 13px; margin-bottom:8px; position:relative;
       border:1px solid {T['line']}; background:{T['panel']};
       transition:border-color .12s ease;}}
  .hm:hover {{border-color:{T['accent']};}}
  .hm-n {{font-size:.68rem; letter-spacing:.6px; color:{T['muted']};
         text-transform:uppercase; font-weight:600;}}
  .hm-p {{font-size:1.4rem; font-weight:700; font-family:{T['mono']};}}
  .hm-r {{position:absolute; top:8px; right:11px; font-size:.62rem; color:{T['muted']};}}
  .hm-t {{font-size:.6rem; letter-spacing:.8px; font-weight:700;}}

  .badge {{display:inline-block; padding:5px 12px; border-radius:20px; margin:0 7px 7px 0;
          font-size:.7rem; font-weight:600; letter-spacing:.2px; font-family:{T['ui']};}}
  .b-up   {{background:{T['up_soft']};   color:{T['up']};}}
  .b-dn   {{background:{T['down_soft']}; color:{T['down']};}}
  .b-turn {{background:{T['attn_soft']}; color:{T['attn']};}}
  .b-bnc  {{background:{T['up_soft']};   color:{T['up']};}}
  .b-none {{background:{T['panel2']};    color:{T['muted']};}}

  /* ---- the order ticket. ONE number dominates (what you pay), ONE primary
     action, everything else quieter and out of the way. ---- */
  .ticket {{background:{T['panel']}; border:1px solid {T['line']}; border-radius:12px;
           padding:11px 14px 9px; margin-bottom:6px;}}
  .tk-head {{display:flex; align-items:center; gap:10px; margin-bottom:5px;}}
  .tk-name {{font-size:1.05rem; font-weight:700; color:{T['ink']}; letter-spacing:.2px;}}
  .tk-grade {{font-size:.72rem; font-weight:700; color:{T['muted']}; margin-left:auto;
             font-family:{T['mono']};}}
  .tk-act {{font-size:.62rem; font-weight:700; letter-spacing:.4px; padding:2px 8px;
           border-radius:20px; background:{T['panel2']}; color:{T['ink_soft']};
           white-space:nowrap;}}
  .tk-big {{font-size:1.7rem; font-weight:700; letter-spacing:-.2px; line-height:1.25;
           font-family:{T['mono']}; padding:0 0 3px;}}
  .tk-sub {{font-size:.72rem; font-weight:500; color:{T['muted']}; letter-spacing:.1px;}}
  /* auto-fit, not a fixed column count: the buyer's numbers took the ticket from 11
     cells to 16, and a hard grid turned that into a third row on every ticket */
  .tk-grid {{display:grid; grid-template-columns:repeat(auto-fit, minmax(84px, 1fr));
            gap:6px 12px; margin-top:6px; font-family:{T['mono']}; font-size:.8rem;
            color:{T['ink']};}}
  .tk-grid b {{display:block; color:{T['muted']}; font-weight:600; font-size:.6rem;
              letter-spacing:.4px; text-transform:uppercase; margin-bottom:1px;
              font-family:{T['ui']}; white-space:nowrap;}}

  .card {{background:{T['panel']}; border:1px solid {T['line']};
         border-left:3px solid {T['up']}; border-radius:10px; padding:11px 15px;
         margin-bottom:9px;}}
  .card-h {{display:flex; align-items:center; gap:10px; margin-bottom:6px;}}
  .side {{font-size:.64rem; font-weight:700; letter-spacing:.4px; padding:3px 10px;
         border-radius:20px; background:{T['up_soft']}; color:{T['up']};}}
  .grade {{font-size:.72rem; font-weight:700; color:{T['muted']};}}
  .card-n {{font-size:1rem; font-weight:700; color:{T['ink']};}}
  .lv {{display:flex; flex-wrap:wrap; gap:20px; font-family:{T['mono']};
       font-size:.82rem;}}
  .lv b {{color:{T['muted']}; font-weight:600; font-size:.66rem; letter-spacing:.3px;
         text-transform:uppercase; display:block; font-family:{T['ui']};}}

  .banner {{padding:10px 15px; border-radius:9px; font-weight:600; font-size:.9rem;
           margin:.2rem 0 .5rem 0;}}
  .banner-ok  {{background:{T['up_soft']};   color:{T['up']};}}
  .banner-mid {{background:{T['attn_soft']}; color:{T['attn']};}}
  .banner-bad {{background:{T['down_soft']}; color:{T['down']};}}

  /* the status strip: one line, pills, no wrapping. A header that changes height
     moves the whole page. */
  .strip {{display:flex; align-items:center; gap:7px; overflow-x:auto; padding:3px 0;
          font-family:{T['ui']}; white-space:nowrap;}}
  .strip > span {{display:inline-flex; align-items:baseline; gap:6px; padding:4px 11px;
          border:1px solid {T['line']}; border-radius:20px; background:{T['panel']};}}
  .strip i {{font-style:normal; font-size:.6rem; letter-spacing:.5px;
            color:{T['muted']}; text-transform:uppercase;}}
  .strip b {{font-size:.82rem; font-weight:700; color:{T['ink']};
            font-family:{T['mono']};}}
  .strip .radar-dish {{flex:none; display:inline-block; width:9px; height:9px;
            border-radius:50%; background:{T['accent']};}}
  .verdict {{font-size:.74rem; font-weight:700; letter-spacing:.1px; padding:5px 13px;
            border-radius:20px;}}
  .verdict.banner-ok  {{background:{T['up_soft']};   color:{T['up']};}}
  .verdict.banner-mid {{background:{T['attn_soft']}; color:{T['attn']};}}
  .verdict.banner-bad {{background:{T['down_soft']}; color:{T['down']};}}

  .radar {{display:flex; align-items:center; gap:10px; padding:6px 12px;
          border:1px solid {T['line']}; border-radius:20px; background:{T['panel']};
          font-size:.7rem; color:{T['muted']};}}
  .radar b {{color:{T['ink']}; font-weight:700;}}

  .hazard {{margin:.2rem 0 .6rem 0; border:1px solid {T['down']}; border-radius:9px;
           padding:9px 14px; font-weight:700; letter-spacing:.2px; font-size:.82rem;
           color:{T['down']}; background:{T['down_soft']};}}

  .callsign {{font-size:.68rem; letter-spacing:1.2px; color:{T['muted']};
             text-transform:uppercase; font-weight:600; margin:.35rem 0 .3rem 0;}}

  .mark {{display:flex; align-items:baseline; gap:10px; margin:0; padding:2px 0;}}
  .mark-name {{font-size:1.4rem; font-weight:700; letter-spacing:-.2px;
              color:{T['ink']};}}
  .mark-sub {{font-size:.8rem; color:{T['muted']}; letter-spacing:.2px;}}
  .reticle {{color:{T['accent']};}}

  .disclaim {{position:fixed; left:0; right:0; bottom:0; z-index:99;
             background:{T['panel2']}; color:{T['muted']};
             border-top:1px solid {T['line']}; text-align:center; padding:7px 10px;
             font-size:.72rem; font-weight:500;}}
  section[data-testid="stSidebar"] {{border-right:1px solid {T['line']};
             background:{T['panel2']};}}
</style>
"""


def main():
    for k, T in PALETTES.items():
        print(f"\n  {k.upper()}  ({T['base']})")
        for n in ("bg", "panel", "ink", "muted", "line", "accent", "up", "down", "attn"):
            print(f"    {n:<8} {T[n]}")
    print()


if __name__ == "__main__":
    main()
