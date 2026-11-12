"""
test_pine.py  —  the Pine scripts must state the same rules as the Python system.

Pine cannot be compiled or run here; that needs TradingView. So this does not claim the
scripts work - it checks the one thing that can be checked from outside, and the one that
actually rots: whether the two halves still agree on the numbers.

The failure this prevents is quiet. Someone raises the RVOL minimum in the Python system,
the chart keeps screening on the old value, and for weeks the table on the screen and the
engine placing orders disagree about which names qualified. Nothing errors. The numbers
just stop meaning the same thing.

    python test_pine.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def pine_inputs(src):
    """{label: default} for every input.* in a Pine file."""
    out = {}
    for m in re.finditer(r'input\.(?:int|float|bool)\(\s*([^,]+),\s*"([^"]+)"', src):
        val, label = m.group(1).strip(), m.group(2).strip()
        out[label] = val
    return out


def py_default(fn, arg):
    import inspect
    return inspect.signature(fn).parameters[arg].default


def main():
    import indicators as I

    scr = os.path.join(HERE, "tradingview", "AashishScreener.pine")
    mom = os.path.join(HERE, "tradingview", "AashishMomentum.pine")
    for p in (scr, mom):
        if not os.path.exists(p):
            print(f"  FAIL  missing {os.path.basename(p)}")
            return 1
    s_src = open(scr).read()
    m_src = open(mom).read()

    print("\n  PINE  <->  PYTHON")
    print("  " + "-" * 62)
    print("  (Pine yahan compile nahi ho sakta - TradingView chahiye. Ye sirf ye "
          "check karta\n   hai ki dono jagah ke numbers ek jaise hain.)\n")

    si = pine_inputs(s_src)

    # squeeze windows and the coil threshold
    check("squeeze short window matches",
          si.get("Squeeze - short TR window") == str(py_default(I.squeeze, "short")),
          f"pine {si.get('Squeeze - short TR window')} vs py {py_default(I.squeeze, 'short')}")
    check("squeeze long window matches",
          si.get("Squeeze - long TR window") == str(py_default(I.squeeze, "long")),
          f"pine {si.get('Squeeze - long TR window')} vs py {py_default(I.squeeze, 'long')}")
    check("coil threshold matches",
          float(si.get("Coil threshold", -1)) == float(py_default(I.expansion, "coil")),
          f"pine {si.get('Coil threshold')} vs py {py_default(I.expansion, 'coil')}")
    check("RVOL lookback matches",
          si.get("RVOL lookback") == str(py_default(I.rvol, "n")),
          f"pine {si.get('RVOL lookback')} vs py {py_default(I.rvol, 'n')}")

    # the coiled-then-wide definition. Reading both off the same bar asks the break to
    # have happened before it happened - the bug this phrasing exists to prevent.
    check("expansion is 'coiled on the PREVIOUS bar, wide on this one'",
          re.search(r"sq\[1\]\s*<\s*coil\s+and\s+tr\s*>\s*trL", s_src) is not None)
    check("the momentum script says the same thing",
          re.search(r"squeeze\[1\]\s*<\s*coil\s+and\s+tr\s*>\s*trL", m_src) is not None)

    # the screener must not silently show fewer names than it claims
    n_syms = len(re.findall(r"input\.symbol\(", s_src))
    n_calls = len(re.findall(r"request\.security\(", s_src))
    check("every symbol slot is actually requested", n_syms == n_calls,
          f"{n_syms} inputs, {n_calls} security calls")
    check("stays inside TradingView's 40-call cap", n_calls <= 40, f"{n_calls} calls")
    n_counted = len(re.findall(r"p\d\d\[off\] \? 1 : 0", s_src))
    check("the PASS count covers every slot", n_counted == n_syms,
          f"{n_counted} of {n_syms} counted")

    # Pine functions cannot assign to a global. The obvious way to write the row
    # renderer - mutating a counter inside the function - does not compile.
    check("the row renderer returns its counter instead of mutating a global",
          "nxt := i + 1" in s_src and "    nxt" in s_src)

    # honesty markers that must survive edits
    check("repainting is stated, not buried",
          "REPAINTING" in s_src and "confirmed bars only" in s_src)
    check("it says what it is not",
          "It is not the scanner" in s_src and "never means" in s_src.replace('"', ''))
    check("not financial advice", "NOT financial advice" in s_src)

    # ---- the exporter must put TODAY'S names in, not a list someone picked once ----
    import re as _re
    import pine_export as PX
    check("NSE:X-EQ becomes the symbol TradingView understands",
          PX.tv_symbol("NSE:RELIANCE-EQ") == "NSE:RELIANCE"
          and PX.tv_symbol("RELIANCE") == "NSE:RELIANCE"
          and PX.tv_symbol("") == "",
          "a symbol TradingView cannot resolve makes request.security throw, not skip")

    rows = [{"tv": f"NSE:T{i}", "name": f"T{i}", "side": "LONG", "close": 1, "pct": 1}
            for i in range(3)]
    out, err = PX.write_pine(rows, demo=True)
    check("exporter writes a Pine file", err is None and out and os.path.exists(out), err or "")
    if out and os.path.exists(out):
        gen = open(out, encoding="utf-8").read()
        got = _re.findall(r'input\.symbol\("([^"]*)"', gen)
        check("today's names land in the first slots",
              got[:3] == ["NSE:T0", "NSE:T1", "NSE:T2"], f"{got[:3]}")
        check("unused slots are blanked, not left as someone's old picks",
              all(g == "" for g in got[3:]), f"{[g for g in got[3:] if g][:3]}")
        check("the snapshot says when it was made",
              "GENERATED" in gen and "SNAPSHOT" in gen)
        check("demo data is marked as demo", "DEMO DATA" in gen)
        # the gates must survive the rewrite untouched - only symbols may change
        check("only the symbols were rewritten",
              gen.count("ta.ema(close, emaFast)") == s_src.count("ta.ema(close, emaFast)")
              and "sq[1] < coil and tr > trL" in gen)
        os.remove(out)

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - dono jagah ke rules ek hain\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
