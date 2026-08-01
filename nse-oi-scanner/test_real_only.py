"""
test_real_only.py  —  can this desk still invent a number when nobody asked it to?

Every other test in this folder runs WITH the synthetic permission granted, because a page
with no token has nothing to render otherwise. That makes them structurally unable to check
the one thing that matters here: what happens on HIS desk, where the permission is absent
and the money is real.

So this suite does the opposite. It strips DESK_SYNTHETIC out of the environment and then
tries, deliberately, to get fabricated data out of every door that used to hand it over:
the universe loader, the option chain, the TradingView watchlist, the paper book, and the
broker itself. A door that opens is a failure. A door that refuses has to refuse with the
command that fixes it, because "no data" without "run 1 - START DAY" is a dead end.

    python test_real_only.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FAILED = []


def check(name, cond, detail=""):
    # One line per check. A multi-line subprocess dump under a PASS makes a passing suite
    # unreadable, which is the same complaint as a crowded ticket.
    d = " ".join(str(detail).split())[:120]
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + d if d else ''}")
    if not cond:
        FAILED.append(name)


def clean_env(**extra):
    """His desk: no synthetic permission, whatever this test runner happens to have set."""
    env = dict(os.environ, **extra)
    env.pop("DESK_SYNTHETIC", None)
    return env


def run(code, env=None):
    """Run a snippet in a FRESH interpreter - real_only reads the environment at call
    time, but desk.py resolves NO_TOKEN/SYNTHETIC at import, and an already-imported
    module would answer from whatever the parent process had."""
    p = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env or clean_env(),
                       capture_output=True, text=True, timeout=300)
    return (p.stdout + p.stderr).strip()


def main():
    print("\n  REAL ONLY  (no synthetic permission - his desk)")
    print("  " + "-" * 62)

    # ---- the switch itself -------------------------------------------------
    out = run("import real_only as R; print(R.allowed(), bool(R.why_no_orders()))")
    check("synthetic data is refused by default", out.startswith("False"), out)
    check("and a default process is NOT disqualified from ordering",
          out.endswith("False"), out)

    on = run("import real_only as R; print(R.allowed(), bool(R.why_no_orders()))",
             env=dict(os.environ, DESK_SYNTHETIC="1"))
    check("DESK_SYNTHETIC=1 grants it", on.startswith("True"), on)
    # THE INVARIANT. Granting permission to invent must remove permission to send, or the
    # grant is just a label and a fabricated premium has a path to a real order.
    check("and that same grant disqualifies the process from ordering",
          on.endswith("True"), on)

    # ---- the broker, which is where money leaves --------------------------
    out = run(
        "import os; os.environ['DESK_SYNTHETIC']='1'\n"
        "import broker; print(broker.place('NSE:X', 50, 'BUY'))",
        env=dict(os.environ, DESK_SYNTHETIC="1"))
    check("a synthetic process cannot place an order",
          "False" in out and "not permitted to send" in out, out[:150])

    # A missing real_only.py must CLOSE the gate, not open it. An import guard that
    # swallows the exception and carries on is how a safety check becomes decoration.
    out = run(
        "import sys, broker\n"
        "sys.modules['real_only'] = None\n"          # import returns None -> attr error
        "print(broker.place('NSE:X', 50, 'BUY'))")
    check("and a broken real_only closes the gate rather than opening it",
          "False" in out and "refusing" in out, out[:150])

    # ---- the desk ----------------------------------------------------------
    # Run the real page, the way a browser runs it, with no token and no permission. The
    # assertion is not "a warning appeared" - it is that there is NOTHING TO PRESS. A
    # banner over a board of tickets is what this whole change exists to delete.
    out = run(
        "from streamlit.testing.v1 import AppTest\n"
        "at = AppTest.from_file('desk.py', default_timeout=600).run()\n"
        "said = ' '.join(list(w.value for w in at.warning)"
        "                + list(e.value for e in at.error))\n"
        "labels = ' | '.join(b.label for b in at.button)\n"
        "print('TOLD:', 'No token' in said)\n"
        "print('FIX:', '1 - START DAY' in said)\n"
        "print('PRESSABLE:', [l for l in labels.split(' | ')\n"
        "                     if 'BUY' in l or 'Exit' in l or 'stop @' in l])",
        env=clean_env(STREAMLIT_SERVER_HEADLESS="true"))
    check("a tokenless desk says so", "TOLD: True" in out, out[:150])
    check("and names the command that fixes it", "FIX: True" in out, out[:150])
    check("and offers nothing to press - no ticket, no BUY, no stop",
          "PRESSABLE: []" in out,
          next((l for l in out.splitlines() if l.startswith("PRESSABLE")), out[:120]))

    src = open(os.path.join(HERE, "desk.py"), encoding="utf-8").read()
    check("chain_for refuses rather than building one from a spot",
          "no token, so no option chain" in src)
    check("the no-token banner carries the command that fixes it",
          "RO.FIX" in src and "No token — no numbers" in src)
    check("the synthetic banner is an error, not a caption",
          "st.error(RO.banner())" in src)

    # ---- artifacts that outlive their warning ------------------------------
    # A terminal warning scrolls away; the file it wrote does not. These two write things
    # he opens LATER - a watchlist he trades from, a book he judges the system by - so a
    # printed caveat is worth nothing and the write itself has to not happen.
    pine = open(os.path.join(HERE, "pine_export.py"), encoding="utf-8").read()
    check("no token, no TradingView watchlist",
          "RO.Synthetic(" in pine and "RO.allowed()" in pine)

    paper = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
    check("--demo is refused without permission", "--demo refused" in paper)
    check("and even when permitted it writes to a separate book",
          "paper_trades.synthetic.json" in paper and "load(a.demo)" in paper)

    out = run("import paper; print(paper.book_path(False), paper.book_path(True))")
    check("the real book is never the synthetic book",
          out.split()[0] != out.split()[-1] and "synthetic" in out.split()[-1], out)

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - nothing here invents a number he could trade on\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
