"""
rrg_view.py  —  the interactive RRG main window (Plotly), shared by the app and HTML export.

One figure builder so the Streamlit app and the standalone page can never drift apart.
Encodes three things at once on every dot:
  position  = rotation quadrant (RS-Ratio x, RS-Momentum y)
  shape     = OI buildup intent (▲ fresh buying / ▼ fresh selling)
  ring      = a live trade candidate under the validated setup (gold halo)
Hover shows the full metric set; tails show where each name came from.
"""
import math
import plotly.graph_objects as go

QUAD_COLOR = {"LEADING": "#1f9d63", "WEAKENING": "#e0a11b",
              "LAGGING": "#d1495b", "IMPROVING": "#2f6fed"}
BUILDUP_SYMBOL = {
    "LONG BUILDUP":   ("triangle-up", True),
    "SHORT COVERING": ("triangle-up", False),
    "SHORT BUILDUP":  ("triangle-down", True),
    "LONG UNWINDING": ("triangle-down", False),
    None:             ("circle", True),
}


def _hover(p):
    sig = p.get("signal") or "—"
    tr = {1: "UP", -1: "DOWN", 0: "flat"}.get(p.get("abs_trend", 0), "?")
    return (f"<b>{p['name']}</b><br>"
            f"Quadrant: {p['quadrant']}"
            + (f"  (from {p['prev_quadrant']})" if p.get("crossed") else "") + "<br>"
            f"RS-Ratio: {p['x']:.2f}   RS-Mom: {p['y']:.2f}<br>"
            f"Distance: {p['distance']:.2f}   Velocity: {p['velocity']:.2f}<br>"
            f"Heading: {p['heading']:.0f}°<br>"
            f"Own trend: {tr} ({p.get('abs_pct',0):+.1f}% vs MA)<br>"
            f"OI: {sig}<extra></extra>")


def rrg_figure(points, picks=None, show_tails=True, dark=True, title=None):
    """points: from rrg_engine.build_points. picks: names to highlight as candidates."""
    picks = set(picks or [])
    if not points:
        return go.Figure()

    span = max(2.5, max(max(abs(p["x"] - 100), abs(p["y"] - 100)) for p in points) * 1.15)
    lo, hi = 100 - span, 100 + span
    ink = "#e6edf3" if dark else "#161b22"
    grid = "rgba(255,255,255,0.06)" if dark else "rgba(0,0,0,0.06)"
    paper = "#0e1116" if dark else "#ffffff"

    fig = go.Figure()

    # quadrant washes
    for q, (x0, x1, y0, y1) in {
        "LEADING":   (100, hi, 100, hi), "WEAKENING": (100, hi, lo, 100),
        "LAGGING":   (lo, 100, lo, 100), "IMPROVING": (lo, 100, 100, hi),
    }.items():
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, layer="below",
                      fillcolor=QUAD_COLOR[q], opacity=0.07, line_width=0)
        fig.add_annotation(
            x=(x0 + x1) / 2, y=y1 if y1 > 100 else y0,
            text=f"<b>{q}</b> · {sum(1 for p in points if p['quadrant']==q)}",
            showarrow=False, font=dict(size=13, color=QUAD_COLOR[q]),
            yanchor="top" if y1 > 100 else "bottom", opacity=0.85)

    fig.add_hline(y=100, line_color="#7d8590", line_width=1)
    fig.add_vline(x=100, line_color="#7d8590", line_width=1)

    # tails
    if show_tails:
        tx, ty = [], []
        for p in points:
            t = p.get("tail") or []
            if len(t) > 1:
                tx += [a for a, _ in t] + [None]
                ty += [b for _, b in t] + [None]
        if tx:
            fig.add_trace(go.Scatter(x=tx, y=ty, mode="lines", hoverinfo="skip",
                                     line=dict(color="rgba(125,133,144,0.35)", width=1),
                                     showlegend=False))

    # dots grouped by (symbol, filled) so each trace is one marker style
    groups = {}
    for p in points:
        sym, filled = BUILDUP_SYMBOL.get(p.get("signal"), BUILDUP_SYMBOL[None])
        groups.setdefault((sym, filled), []).append(p)

    label_names = {"LONG BUILDUP": "Long buildup (fresh buy)", "SHORT COVERING": "Short covering",
                   "SHORT BUILDUP": "Short buildup (fresh sell)", "LONG UNWINDING": "Long unwinding",
                   None: "No OI read"}
    for (sym, filled), ps in groups.items():
        colors = [QUAD_COLOR[p["quadrant"]] for p in ps]
        legend = label_names.get(ps[0].get("signal"), "—")
        fig.add_trace(go.Scatter(
            x=[p["x"] for p in ps], y=[p["y"] for p in ps], mode="markers",
            name=legend,
            marker=dict(symbol=sym, size=11,
                        color=colors if filled else paper,
                        line=dict(color=colors, width=1.6)),
            customdata=[p["name"] for p in ps],
            hovertemplate=[_hover(p) for p in ps]))

    # candidate halos + labels
    cand = [p for p in points if p["name"] in picks]
    if cand:
        fig.add_trace(go.Scatter(
            x=[p["x"] for p in cand], y=[p["y"] for p in cand], mode="markers+text",
            name="Trade candidate",
            marker=dict(symbol="circle-open", size=22, line=dict(color="#f0b429", width=2.4)),
            text=[p["name"] for p in cand], textposition="top center",
            textfont=dict(size=10, color="#f0b429"),
            hovertemplate=[_hover(p) for p in cand]))

    fig.update_layout(
        title=dict(text=title or f"Relative Rotation — {len(points)} F&O names vs NIFTY",
                   font=dict(size=17, color=ink)),
        xaxis=dict(title="RS-Ratio  (relative strength →)", range=[lo, hi],
                   gridcolor=grid, zeroline=False, color=ink),
        yaxis=dict(title="RS-Momentum  (strength rising ↑)", range=[lo, hi],
                   gridcolor=grid, zeroline=False, color=ink, scaleanchor="x"),
        paper_bgcolor=paper, plot_bgcolor=paper, font=dict(color=ink),
        legend=dict(orientation="h", y=-0.13, font=dict(size=10)),
        margin=dict(l=60, r=20, t=55, b=70), height=680, hovermode="closest")
    return fig


def export_html(points, path="rrg_live.html", picks=None, title=None):
    fig = rrg_figure(points, picks=picks, title=title)
    fig.write_html(path, include_plotlyjs="inline", full_html=True)
    return path
