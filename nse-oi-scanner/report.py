"""
report.py  —  EVERYTHING in one webpage.

Builds a single self-contained HTML dashboard (charts embedded, no server, no
internet) from the whole stack: OI buildup + option chain + the 3 revalidated
trade ideas (1 CE / 1 PE / 1 Future) with their annotated charts, and the RRG.

    python report.py --dry-run      # demo data -> report.html, then open it
    python report.py                # live (needs Fyers token) -> report.html

Open report.html by double-click. NOT financial advice.
"""
import os, base64, argparse, webbrowser
from datetime import datetime, timezone, timedelta

import scanner
import option_chain as oc
import signal_engine as se
import charts as ch
import rrg

IST = timezone(timedelta(hours=5, minutes=30))
OUT = "report.html"


def _b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


# ---------- gather everything ----------
def gather(dry):
    # buildup table
    if dry:
        baseline, curr = scanner.fetch_dry()
    else:
        curr = scanner.fetch_live()
        baseline = scanner.load_baseline() or curr
        if scanner.load_baseline() is None:
            scanner.save_baseline(curr)
    rows = scanner.build_rows(baseline, curr, scanner.config.MIN_OI_CHANGE_PCT)

    # market option-chain context (NIFTY)
    try:
        chain, spot = oc.fetch_dry() if dry else oc.fetch_live("NSE:NIFTY50-INDEX")
        market = oc.analyse(chain, spot)
    except Exception:
        market = None

    # the 3 revalidated ideas + their charts
    verdicts = se.dry_verdicts() if dry else se.live_verdicts()
    ideas = se.build_ideas(verdicts) if verdicts else {}
    os.makedirs("charts", exist_ok=True)
    idea_imgs = {}
    for key, idea in ideas.items():
        p = ch.render_idea(idea, f"charts/rep_{key}.png")
        idea_imgs[key] = _b64(p)

    # RRG — full F&O universe + OI-buildup overlay
    try:
        if dry:
            rpoints = rrg.dry_points_large()
        else:
            from fno_universe import fno_stocks
            rp, rb = rrg.fetch_prices_live(fno_stocks(),
                                           getattr(scanner.config, "RRG_BENCHMARK", "NSE:NIFTY50-INDEX"))
            buildup = {}
            try:
                buildup = rrg.fetch_buildup_live(getattr(scanner.config, "FUT_EXPIRY", None))
            except Exception:
                buildup = {}
            rpoints = rrg.analyse(rp, rb, buildup) if rp else []
        rcounts = {q: sum(1 for p in rpoints if p["quadrant"] == q) for q in rrg.QUAD_COLOR}
        rconf = rrg.confluence(rpoints) if rpoints else {"fresh_longs": [], "fresh_shorts": []}
        rrg_img = _b64(rrg.render_chart(rpoints, "charts/rep_rrg.png")) if rpoints else None
    except Exception as e:      # noqa
        rpoints, rcounts, rconf, rrg_img = [], {}, {"fresh_longs": [], "fresh_shorts": []}, None

    return {"asof": datetime.now(IST).strftime("%a %d %b %Y · %H:%M IST"),
            "mode": "DEMO (synthetic data)" if dry else "LIVE (Fyers)",
            "rows": rows, "market": market, "ideas": ideas, "idea_imgs": idea_imgs,
            "rpoints": rpoints, "rcounts": rcounts, "rconf": rconf, "rrg_img": rrg_img}


# ---------- render ----------
SIG_CLASS = {"LONG BUILDUP": "bull", "SHORT COVERING": "bull",
             "SHORT BUILDUP": "bear", "LONG UNWINDING": "bear"}
QUAD_CLASS = {"LEADING": "bull", "IMPROVING": "info", "WEAKENING": "warn", "LAGGING": "bear"}


def _idea_card(key, idea, img):
    if not idea:
        return f'<div class="card empty"><div class="ktag">{key}</div><p>No qualifying confluence.</p></div>'
    t = idea["trade"]; L = idea["levels"]; v = idea["verdict"]
    bias = idea["bias"]; cls = "bull" if bias == "BULLISH" else "bear"
    strike = f' {idea.get("strike","")}'.rstrip()
    reasons = "".join(f"<li>{r}</li>" for r in idea["reasons"])
    return f'''
    <div class="card">
      <div class="card-h">
        <div><span class="ktag {cls}">{idea['kind']}</span>
             <span class="under">{idea['underlying'].split(':')[-1]}{strike}</span></div>
        <div class="conf {cls}">{bias} · {idea['confidence']}%</div>
      </div>
      <div class="trend">{v['chart']['trend']['combined']}</div>
      <img src="{img}" alt="{key} chart"/>
      <div class="levels">
        <span class="lv r">R2 {L['R2']:g}</span><span class="lv r">R1 {L['R1']:g}</span>
        <span class="lv s">S1 {L['S1']:g}</span><span class="lv s">S2 {L['S2']:g}</span>
      </div>
      <div class="trade-row">
        <div><span>Entry</span><b>{t['entry']:g}</b></div>
        <div><span>Stop</span><b class="bear">{t['stop']:g}</b></div>
        <div><span>Target</span><b class="bull">{t['target']:g}</b></div>
        <div><span>R:R</span><b>{t['rr']}</b></div>
      </div>
      <details><summary>Why this trade</summary><ul>{reasons}</ul></details>
    </div>'''


def _buildup_rows(rows):
    if not rows:
        return '<tr><td colspan="5" class="muted">No names over the OI-change threshold.</td></tr>'
    out = []
    for r in rows:
        cls = SIG_CLASS.get(r["signal"], "")
        vol = "✓" if r.get("conf") == "yes" else "·"
        out.append(f'<tr><td class="sym">{r["sym"]}</td>'
                   f'<td class="num {"bull" if r["px"]>=0 else "bear"}">{r["px"]:+.1f}%</td>'
                   f'<td class="num {"bull" if r["oi"]>=0 else "bear"}">{r["oi"]:+.1f}%</td>'
                   f'<td class="vol">{vol}</td>'
                   f'<td><span class="pill {cls}">{r["signal"].title()}</span></td></tr>')
    return "".join(out)


def _quad_chips(counts):
    order = [("LEADING", "Leading"), ("WEAKENING", "Weakening"),
             ("IMPROVING", "Improving"), ("LAGGING", "Lagging")]
    out = []
    for k, label in order:
        out.append(f'<div class="quad {QUAD_CLASS[k]}"><span>{label}</span>'
                   f'<b>{counts.get(k, 0)}</b></div>')
    return "".join(out)


def _conf_lists(conf):
    def chips(items, cls):
        if not items:
            return '<span class="muted">—</span>'
        return "".join(f'<span class="tk {cls}">{p["name"]}</span>' for p in items[:14])
    longs = chips(conf.get("fresh_longs", []), "bull")
    shorts = chips(conf.get("fresh_shorts", []), "bear")
    return f'''
      <div class="conf-block">
        <div class="conf-h bull">▲ Fresh longs <small>leading/improving + long buildup</small></div>
        <div class="tokens">{longs}</div>
        <div class="conf-h bear">▼ Fresh shorts <small>lagging/weakening + short buildup</small></div>
        <div class="tokens">{shorts}</div>
      </div>'''


def _market_tiles(m):
    if not m:
        return ""
    return f'''
      <div class="tile"><span>Spot</span><b>{m['spot']:g}</b></div>
      <div class="tile"><span>PCR</span><b>{m['pcr']}</b></div>
      <div class="tile"><span>Max Pain</span><b>{m['max_pain']:g}</b></div>
      <div class="tile"><span>Support</span><b class="bull">{m['support']:g}</b></div>
      <div class="tile"><span>Resistance</span><b class="bear">{m['resistance']:g}</b></div>'''


def body_html(d):
    """Inner HTML (style + content) — used standalone and for the Artifact."""
    cards = "".join(_idea_card(k, d["ideas"].get(k), d["idea_imgs"].get(k)) for k in ("CE", "PE", "FUT"))
    rrg_block = (f'<img src="{d["rrg_img"]}" alt="RRG"/>' if d["rrg_img"]
                 else '<p class="muted">RRG needs price data.</p>')
    mode_cls = "warn" if d["mode"].startswith("DEMO") else "bull"
    return f'''<style>{CSS}</style>
<div class="wrap">
  <header>
    <div class="brand"><span class="dot"></span> NSE F&amp;O Signal Desk</div>
    <div class="meta"><span class="mode {mode_cls}">{d['mode']}</span>
      <span class="asof">{d['asof']}</span></div>
  </header>
  <p class="lede">One page: OI buildup, option chain, the three revalidated ideas
     (1&nbsp;CE&nbsp;· 1&nbsp;PE&nbsp;· 1&nbsp;Future) with levels and rationale, and the rotation map.</p>

  <section class="tiles">{_market_tiles(d['market'])}</section>

  <h2>Revalidated trade ideas <small>OI buildup × option chain × chart action</small></h2>
  <section class="cards">{cards}</section>

  <section class="panel">
    <h2>Relative Rotation <small>{len(d['rpoints'])} F&amp;O stocks vs NIFTY · position = rotation, marker = OI buildup</small></h2>
    <div class="rrg-grid">
      <div class="rrg-img">{rrg_block}</div>
      <div class="rrg-side">
        <div class="quads">{_quad_chips(d['rcounts'])}</div>
        {_conf_lists(d['rconf'])}
      </div>
    </div>
  </section>

  <section class="panel">
    <h2>OI buildup <small>futures · from day-open · sorted by |OI Δ|</small></h2>
    <table class="build">
      <thead><tr><th>Symbol</th><th>Price</th><th>OI</th><th>Vol</th><th>Signal</th></tr></thead>
      <tbody>{_buildup_rows(d['rows'])}</tbody>
    </table>
  </section>

  <footer>NOT financial advice · signals are inputs, the decision is yours ·
    generated locally, no data leaves your PC</footer>
</div>'''


CSS = '''
:root{
  --bg:#0e1116; --panel:#161b22; --panel2:#1b222c; --line:#232a34;
  --ink:#e6edf3; --muted:#8b98a5; --accent:#4c8dff;
  --bull:#3fb950; --bear:#f4516c; --warn:#d29922; --info:#58a6ff;
  --radius:14px;
}
@media (prefers-color-scheme: light){
  :root{ --bg:#f4f6f9; --panel:#ffffff; --panel2:#f0f3f7; --line:#e2e7ee;
    --ink:#161b22; --muted:#5b6672; --bull:#1f9d4d; --bear:#d1284a; --warn:#b7791f; --info:#2f6fed; }
}
:root[data-theme="dark"]{ --bg:#0e1116; --panel:#161b22; --panel2:#1b222c; --line:#232a34;
  --ink:#e6edf3; --muted:#8b98a5; --bull:#3fb950; --bear:#f4516c; --warn:#d29922; --info:#58a6ff; }
:root[data-theme="light"]{ --bg:#f4f6f9; --panel:#ffffff; --panel2:#f0f3f7; --line:#e2e7ee;
  --ink:#161b22; --muted:#5b6672; --bull:#1f9d4d; --bear:#d1284a; --warn:#b7791f; --info:#2f6fed; }
*{box-sizing:border-box}
body{margin:0}
.wrap{max-width:1120px;margin:0 auto;padding:28px 22px 60px;
  font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink);background:var(--bg);min-height:100vh;line-height:1.5}
.num,.tile b,.trade-row b,.lv,.levels,.build .num,table{font-variant-numeric:tabular-nums;
  font-family:ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace}
header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}
.brand{font-size:19px;font-weight:700;letter-spacing:.2px;display:flex;align-items:center;gap:9px}
.dot{width:10px;height:10px;border-radius:50%;background:var(--accent);
  box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 25%,transparent)}
.meta{display:flex;gap:10px;align-items:center;font-size:12.5px}
.mode{padding:3px 9px;border-radius:999px;font-weight:700;font-size:11px;letter-spacing:.4px;
  border:1px solid var(--line)}
.mode.warn{color:var(--warn);background:color-mix(in srgb,var(--warn) 12%,transparent)}
.mode.bull{color:var(--bull);background:color-mix(in srgb,var(--bull) 12%,transparent)}
.asof{color:var(--muted)}
.lede{color:var(--muted);max-width:64ch;margin:10px 0 22px}
h2{font-size:15px;letter-spacing:.3px;margin:30px 0 12px;text-wrap:balance;
  display:flex;align-items:baseline;gap:10px}
h2 small{font-size:12px;color:var(--muted);font-weight:500;letter-spacing:0}
.tiles{display:flex;gap:10px;flex-wrap:wrap}
.tile{flex:1;min-width:120px;background:var(--panel);border:1px solid var(--line);
  border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:3px}
.tile span{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px}
.tile b{font-size:20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:14px;display:flex;flex-direction:column;gap:10px}
.card.empty{justify-content:center;align-items:center;color:var(--muted);min-height:180px}
.card img{width:100%;border-radius:8px;background:#fff}
.card-h{display:flex;justify-content:space-between;align-items:center;gap:8px}
.ktag{font-size:11px;font-weight:800;letter-spacing:.5px;padding:3px 8px;border-radius:7px;
  background:var(--panel2);border:1px solid var(--line)}
.ktag.bull{color:var(--bull)} .ktag.bear{color:var(--bear)}
.under{font-weight:700;margin-left:8px}
.conf{font-size:12.5px;font-weight:800;letter-spacing:.3px}
.conf.bull{color:var(--bull)} .conf.bear{color:var(--bear)}
.trend{font-size:12px;color:var(--muted);margin-top:-4px}
.levels{display:flex;gap:6px;flex-wrap:wrap}
.lv{font-size:11.5px;padding:2px 7px;border-radius:6px;border:1px solid var(--line)}
.lv.r{color:var(--bear)} .lv.s{color:var(--bull)}
.trade-row{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;
  background:var(--panel2);border-radius:10px;padding:10px}
.trade-row div{display:flex;flex-direction:column;gap:2px}
.trade-row span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.trade-row b{font-size:15px}
.bull{color:var(--bull)} .bear{color:var(--bear)} .info{color:var(--info)} .warn{color:var(--warn)}
details summary{cursor:pointer;font-size:12.5px;color:var(--accent);font-weight:600}
details ul{margin:8px 0 0;padding-left:18px;font-size:12.5px;color:var(--muted);line-height:1.7}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
@media(max-width:820px){.two-col{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:16px}
.panel img{width:100%;border-radius:8px;background:#fff}
table.build{width:100%;border-collapse:collapse;font-size:13px}
.build th{text-align:left;font-size:10.5px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.6px;font-weight:600;padding:6px 8px;border-bottom:1px solid var(--line)}
.build td{padding:7px 8px;border-bottom:1px solid var(--line)}
.build tr:last-child td{border-bottom:none}
.build .sym{font-weight:700} .build .num{text-align:right} .build .vol{text-align:center;color:var(--muted)}
.pill{font-size:11px;font-weight:700;padding:2px 8px;border-radius:6px;border:1px solid var(--line)}
.pill.bull{color:var(--bull);background:color-mix(in srgb,var(--bull) 12%,transparent)}
.pill.bear{color:var(--bear);background:color-mix(in srgb,var(--bear) 12%,transparent)}
.rrg-grid{display:grid;grid-template-columns:1.55fr 1fr;gap:16px;align-items:start}
@media(max-width:820px){.rrg-grid{grid-template-columns:1fr}}
.rrg-img img{width:100%;border-radius:8px;background:#fff}
.quads{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.quad{padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--panel2);
  display:flex;flex-direction:column;gap:2px;border-left:3px solid currentColor}
.quad span{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px}
.quad b{font-size:20px;color:var(--ink);font-weight:700;font-variant-numeric:tabular-nums}
.conf-block{margin-top:14px;display:flex;flex-direction:column;gap:7px}
.conf-h{font-size:12px;font-weight:700;display:flex;align-items:baseline;gap:7px}
.conf-h small{font-size:10.5px;color:var(--muted);font-weight:500;text-transform:none;letter-spacing:0}
.tokens{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px}
.tk{font-size:11px;font-weight:600;padding:2px 7px;border-radius:6px;border:1px solid var(--line);
  background:var(--panel2);font-family:ui-monospace,Menlo,monospace}
.tk.bull{color:var(--bull);border-color:color-mix(in srgb,var(--bull) 35%,var(--line))}
.tk.bear{color:var(--bear);border-color:color-mix(in srgb,var(--bear) 35%,var(--line))}
.muted{color:var(--muted)}
footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);
  font-size:11.5px;color:var(--muted);text-align:center}
'''


def render_standalone(d):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>NSE F&O Signal Desk</title></head><body>'
            + body_html(d) + '</body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--body-only", action="store_true", help="write inner HTML (for embedding)")
    args = ap.parse_args()
    d = gather(args.dry_run)
    html = body_html(d) if args.body_only else render_standalone(d)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [OK] wrote {OUT}  ({d['mode']})")
    if not args.body_only:
        try:
            webbrowser.open("file://" + os.path.abspath(OUT))
        except Exception:
            pass


if __name__ == "__main__":
    main()
