"""
risk_gate.py  —  Stage 5 of the universal-trading pipeline, as code.

A HARD gate that sizes a trade and can BLOCK it. Any single failed check → BLOCK.
Defaults are conservative (0.5% risk/trade, 2% daily stop). Tune in config.py.

    from risk_gate import check
    verdict = check(trade, portfolio, config)   # -> {"ok":bool,"qty":int,"failed":[...],"notes":[...]}

NOT financial advice. This protects capital; it does not promise profit.
"""
import math


def _cfg(config, key, default):
    return getattr(config, key, default)


def check(trade, portfolio, config):
    """
    trade     = {symbol, underlying, side('BUY'/'SELL'), kind('CE'/'PE'/'FUT'),
                 entry, stop, target, lot_size}
    portfolio = {capital, realized_pnl_today, open_positions:[{underlying, deployed}], ...}
    """
    capital   = float(portfolio.get("capital", _cfg(config, "CAPITAL", 100000)))
    risk_pct  = _cfg(config, "RISK_PCT", 0.005)          # 0.5% per trade
    max_expo  = _cfg(config, "MAX_EXPOSURE", 0.40)
    max_name  = _cfg(config, "MAX_PER_NAME", 0.15)
    day_dd    = _cfg(config, "DAY_DD", 0.02)             # 2% daily stop
    max_loss  = _cfg(config, "MAX_LOSS", capital * 0.01) # hard rupee cap / trade
    lot       = max(1, int(trade.get("lot_size", 1)))

    entry = float(trade["entry"]); stop = float(trade["stop"])
    stop_dist = abs(entry - stop)
    failed, notes = [], []

    # ---- 3. Drawdown control (check first: if the day is done, nothing else matters) ----
    realized = float(portfolio.get("realized_pnl_today", 0))
    if realized <= -day_dd * capital:
        failed.append(f"daily drawdown hit ({realized:.0f} <= -{day_dd*100:.1f}% of capital)")

    # ---- 1. Position size (from risk-per-trade) ----
    qty = 0
    if stop_dist <= 0:
        failed.append("no stop distance (entry == stop) — cannot size")
    else:
        risk_amount = capital * risk_pct
        raw_units = risk_amount / stop_dist
        lots = int(math.floor(raw_units / lot))
        qty = lots * lot
        if lots < 1:
            failed.append(f"stop too wide for {risk_pct*100:.2f}% risk "
                          f"(need >= 1 lot of {lot}, budget {risk_amount:.0f})")
        else:
            notes.append(f"size {lots} lot(s) = {qty} @ risk {risk_amount:.0f} "
                         f"({stop_dist:.2f} pt stop)")

    # ---- 2. Exposure limits (options tie up premium; futures tie up margin, not notional) ----
    margin_pct = float(trade.get("margin_pct", 1.0))     # options 1.0 (premium), futures ~0.2
    deployed_new = qty * entry * margin_pct
    total_deployed = sum(p.get("deployed", 0) for p in portfolio.get("open_positions", [])) + deployed_new
    if total_deployed > max_expo * capital:
        failed.append(f"total exposure {total_deployed:.0f} > {max_expo*100:.0f}% cap")
    name_deployed = deployed_new + sum(
        p.get("deployed", 0) for p in portfolio.get("open_positions", [])
        if p.get("underlying") == trade.get("underlying"))
    if name_deployed > max_name * capital:
        failed.append(f"{trade.get('underlying')} exposure {name_deployed:.0f} > {max_name*100:.0f}% per-name cap")

    # ---- 4. Volatility check (hook: caller supplies vol_ok / iv; default pass) ----
    if trade.get("vol_ok") is False:
        failed.append("volatility unacceptable for this setup")

    # ---- 5. Max loss (worst case incl. gap to invalidation if given) ----
    invalidation = trade.get("invalidation", stop)
    worst_dist = max(stop_dist, abs(entry - float(invalidation)))
    worst_case = qty * worst_dist
    # option buyers: worst case can't exceed premium paid
    if trade.get("kind") in ("CE", "PE") and trade.get("side", "BUY") == "BUY":
        worst_case = min(worst_case, qty * entry)
    if worst_case > max_loss:
        failed.append(f"worst-case {worst_case:.0f} > max-loss cap {max_loss:.0f}")

    ok = not failed and qty >= lot
    return {"ok": ok, "qty": qty if ok else 0, "failed": failed, "notes": notes,
            "worst_case": round(worst_case, 2), "deployed": round(deployed_new, 2)}


def render(verdict, trade):
    tag = "PASS ✅" if verdict["ok"] else "BLOCK ⛔"
    print(f"  RISK {tag}  {trade.get('symbol','?')}  qty={verdict['qty']}")
    for n in verdict["notes"]:
        print(f"     · {n}")
    for f in verdict["failed"]:
        print(f"     ✗ {f}")


if __name__ == "__main__":
    class C:
        CAPITAL = 500000; RISK_PCT = 0.005; MAX_EXPOSURE = 0.40
        MAX_PER_NAME = 0.15; DAY_DD = 0.02; MAX_LOSS = 5000
    port = {"capital": 500000, "realized_pnl_today": 0, "open_positions": []}
    t = {"symbol": "NSE:RELIANCE-FUT", "underlying": "RELIANCE", "side": "BUY",
         "kind": "FUT", "entry": 2994.0, "stop": 2962.4, "target": 3074.2, "lot_size": 250}
    render(check(t, port, C()), t)
