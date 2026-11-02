"""
upgrade_config.py  —  add newly-added settings to an existing config.py, safely.

Why this exists: config.py is generated once by setup.py and then never touched, so a
config created before a feature shipped is silently missing that feature's keys. The
symptom is nasty — the code falls back to a default, the app still runs, and you get a
wrong number with no error. A missing DEFAULT_LOT is exactly how a quantity of "130 lot
x 1" appears for a stock whose real lot is 500.

This reads config.example.py, finds every top-level KEY = value your config.py lacks,
appends only those, and never touches your existing lines (credentials included).
A timestamped backup is written first.

    python upgrade_config.py            # show what is missing, then apply
    python upgrade_config.py --check    # report only, change nothing
"""
import os, re, shutil, sys
from datetime import datetime

TEMPLATE, TARGET = "config.example.py", "config.py"
KEY_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*=")
# never copy these from the template - they hold placeholder credentials
NEVER = {"CLIENT_ID", "SECRET_KEY", "REDIRECT_URI"}


def keys_in(path):
    found = {}
    if not os.path.exists(path):
        return found
    with open(path) as f:
        for i, line in enumerate(f):
            m = KEY_RE.match(line)
            if m:
                found[m.group(1)] = i
    return found


def blocks_for(path, wanted):
    """Grab each wanted key's line plus any comment lines directly above it."""
    with open(path) as f:
        lines = f.readlines()
    out = []
    for i, line in enumerate(lines):
        m = KEY_RE.match(line)
        if not m or m.group(1) not in wanted:
            continue
        j = i - 1
        head = []
        while j >= 0 and lines[j].lstrip().startswith("#"):
            head.insert(0, lines[j]); j -= 1
        out.append("".join(head) + line)
    return out


def main():
    check_only = "--check" in sys.argv
    if not os.path.exists(TARGET):
        print(f"  [X] {TARGET} not found. Run:  python setup.py")
        return 1
    if not os.path.exists(TEMPLATE):
        print(f"  [X] {TEMPLATE} missing - pull the latest code first.")
        return 1

    have, tmpl = keys_in(TARGET), keys_in(TEMPLATE)
    missing = [k for k in tmpl if k not in have and k not in NEVER]

    if not missing:
        print(f"  [OK] {TARGET} already has every setting ({len(have)} keys). Nothing to do.")
        return 0

    print(f"  {TARGET} is missing {len(missing)} setting(s):")
    for k in missing:
        print(f"    - {k}")
    if check_only:
        print("\n  --check given, nothing written. Re-run without --check to apply.")
        return 0

    backup = f"{TARGET}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(TARGET, backup)
    with open(TARGET, "a") as f:
        f.write(f"\n\n# ---- added by upgrade_config.py on {datetime.now():%Y-%m-%d %H:%M} ----\n")
        for block in blocks_for(TEMPLATE, set(missing)):
            f.write(block if block.endswith("\n") else block + "\n")

    print(f"\n  [OK] appended {len(missing)} setting(s) to {TARGET}")
    print(f"       backup saved as {backup}")
    print(f"       your Fyers credentials were not touched")

    # the lot table is the one that silently breaks quantities - offer to fill it now
    try:
        from fno_universe import fetch_lot_sizes
        lots = fetch_lot_sizes()
        if lots:
            print(f"  [OK] fetched real lot sizes for {len(lots)} F&O names -> fno_lots.json")
            print("       trade cards will now size in real, buyable lots")
        else:
            print("  [!] could not fetch lot sizes now; cards fall back to DEFAULT_LOT")
    except Exception as e:      # noqa
        print(f"  [!] lot-size fetch skipped: {e}")
    print("\n  Next:  open the app and check the Quantity line shows a real lot multiple.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
