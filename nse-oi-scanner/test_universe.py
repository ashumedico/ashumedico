"""
test_universe.py  —  a name cannot pass a screen it was never shown to.

The F&O list changes every month. `fno_stocks()` computed where its list came from and
then threw that away, and the cache had NO expiry - a file written in March was still
the universe in August. Every name NSE added since was invisible on every screen, and a
missing name looks exactly like a name that did not qualify. That is the worst failure
shape available: silent, plausible, and indistinguishable from a correct answer.

So: the cache expires, an expired-but-usable cache is labelled as stale rather than
passed off as current, and the source is readable by anything that draws a list.

    python test_universe.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def main():
    import fno_universe as U

    print("\n  F&O UNIVERSE")
    print("  " + "-" * 62)

    check("the cache has an expiry at all", hasattr(U, "CACHE_MAX_AGE_DAYS"),
          "a cache with no expiry is used forever")
    check("and it is short enough to catch a monthly list change",
          0 < U.CACHE_MAX_AGE_DAYS <= 31, f"{U.CACHE_MAX_AGE_DAYS} days")

    # ---- the source is reported, whatever it turns out to be ----------------
    syms = U.fno_stocks()
    src, note = U.source()
    check("fno_stocks returns Fyers symbols", bool(syms) and syms[0].startswith("NSE:"),
          syms[0] if syms else "empty")
    check("the source of the list is knowable", src in
          ("live", "cache", "stale cache", "fallback"), str(src))
    check("and it comes with the detail needed to act on it", bool(note), str(note)[:70])

    # ---- a degraded source must NAME itself as degraded ---------------------
    # This is the whole point. "fallback" and "stale cache" have to be distinguishable
    # from "live", because only they mean names may be missing.
    if src in ("fallback", "stale cache"):
        check("a degraded universe says that names may be missing",
              "missing" in note.lower() or "cannot appear" in note.lower(), note[:80])
    else:
        check(f"universe is {src} — nothing to warn about", True, note[:60])

    # ---- an aged cache must not be treated as current ----------------------
    real = U.CACHE
    tmp = real + ".testbak"
    had = os.path.exists(real)
    if had:
        os.rename(real, tmp)
    try:
        with open(real, "w") as f:
            f.write("RELIANCE\nTCS\nSBIN\n")
        old = time.time() - (U.CACHE_MAX_AGE_DAYS + 3) * 86400
        os.utime(real, (old, old))
        U.LAST_SOURCE = None
        names, s2 = U._underlyings()
        check("a cache older than the limit is not reported as current",
              s2 != "cache", f"reported {s2!r}")
        check("but it is still USED if the refresh fails — stale beats hard-coded",
              s2 in ("stale cache", "live"),
              "falling back to the built-in list when a 10-day cache exists loses names")

        # fresh again -> straight back to "cache"
        os.utime(real, None)
        U.LAST_SOURCE = None
        _n, s3 = U._underlyings()
        check("a fresh cache is used without a refetch", s3 == "cache", f"{s3!r}")
    finally:
        if os.path.exists(real):
            os.remove(real)
        if had:
            os.rename(tmp, real)
        U.LAST_SOURCE = None

    # ---- the fallback is a last resort, and honest about it -----------------
    check("the built-in fallback is a real universe, not a token list",
          len(U.FALLBACK) > 100, f"{len(U.FALLBACK)} names")
    check("its names are plain symbols, not Fyers-prefixed",
          all(":" not in n for n in U.FALLBACK[:20]))

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - the list knows where it came from\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
