"""
test_layout.py  —  does the desk actually FIT the screen he actually owns?

Every other test in this folder asks whether an element was produced. None of them can
ask whether it was visible, and the difference is not academic: cutting the container's
top padding slid the wordmark and the RUN SCAN button underneath Streamlit's own fixed
toolbar, and AppTest reported both elements present and correct while a screenshot showed
a blank strip where the header should be. Rendered and visible are different claims.

So this one drives a real browser at the size of his desk - 21 inches, 1920x940 of usable
viewport - clicks through every tab, and measures how far each one runs past one
screen. A tab that scrolls is not a failure of taste, it is the thing he asked not to
happen: the ticket he is about to press BUY on and the evidence for it have to be visible
together, or the decision gets made from memory.

The DEMO and config banners are subtracted, because they exist only on a machine with no
token and no intraday config - neither is true on his. That subtraction is stated in the
output rather than hidden, so the raw number is always visible next to the adjusted one.

    python test_layout.py          (SKIPs cleanly if playwright or chromium is absent)
"""
import glob
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWPORT = (1920, 940)          # a 21-inch desktop, minus browser chrome
TABS = ["COMMAND DECK", "SIGNALS & TICKETS", "GAP-UP", "CHART", "SCREENER", "SCORE"]
SLACK = 24                      # px of rounding/margin we do not argue about

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def chromium():
    """The browser this environment ships, wherever it put it."""
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    for pat in (os.path.join(root, "chromium*", "chrome-linux", "chrome"),
                os.path.join(root, "chromium*", "chrome-win", "chrome.exe"),
                os.path.join(root, "chromium")):
        hit = sorted(glob.glob(pat))
        if hit:
            return hit[-1]
    return None


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def serve(port):
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "desk.py",
         "--server.port", str(port), "--server.headless", "true"],
        cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import urllib.request
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            return proc
        except Exception:
            time.sleep(1)
    proc.kill()
    raise RuntimeError("streamlit did not come up")


def measure(port):
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"], executable_path=chromium())
        pg = b.new_page(viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
        pg.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle", timeout=240000)
        pg.wait_for_selector('[data-testid="stTabs"]', timeout=240000)
        pg.wait_for_timeout(9000)
        tabs = pg.locator('[data-testid="stTabs"] [role="tab"]')
        out.append(("__tabcount__", tabs.count(), 0))
        # the header has to be ON the page, not under Streamlit's fixed toolbar
        for sel in (".mark", ".strip"):
            box = pg.locator(sel).first.bounding_box() if pg.locator(sel).count() else None
            out.append((f"__visible__{sel}", box["y"] if box else -1,
                        box["height"] if box else 0))
        for i, name in enumerate(TABS):
            if i:
                tabs.nth(i).click(timeout=30000)
                pg.wait_for_timeout(4000)
            h = pg.evaluate("""() => {
                const el = document.querySelector('[data-testid="stMainBlockContainer"]')
                        || document.querySelector('section.main');
                const s = el && (el.closest('section') || el.parentElement);
                return {content: el ? el.scrollHeight : -1,
                        view: s ? s.clientHeight : window.innerHeight};
            }""")
            demo = pg.evaluate("""() => {
                let t = 0;
                for (const a of document.querySelectorAll('[data-testid="stAlert"]')) {
                    const s = a.innerText || "";
                    if (s.includes("DEMO data") || s.includes("BAR_MINUTES"))
                        t += a.getBoundingClientRect().height + 8;
                }
                return Math.round(t);
            }""")
            out.append((name, h["content"] - h["view"], demo))
        b.close()
    return out


def main():
    print("\n  LAYOUT  (1920x940 - one landscape screen)")
    print("  " + "-" * 62)
    try:
        import playwright  # noqa
    except ImportError:
        print("  SKIP  playwright not installed\n")
        return 0
    if not chromium():
        print("  SKIP  no chromium in PLAYWRIGHT_BROWSERS_PATH\n")
        return 0

    port = free_port()
    proc = serve(port)
    try:
        rows = measure(port)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()

    for name, a, b in rows:
        if name == "__tabcount__":
            check(f"all {len(TABS)} tabs exist", a == len(TABS), f"{a} found")
        elif name.startswith("__visible__"):
            sel = name.replace("__visible__", "")
            check(f"{sel} is painted below the toolbar, not under it",
                  0 < a < 120 and b > 8, f"top={a}px height={b}px")
        else:
            over = a - b
            check(f"{name} fits one screen",
                  over <= SLACK,
                  (f"OVER by {over}px" if over > SLACK else "fits")
                  + (f"  (raw {a}px, demo-only banners {b}px)" if b else f"  (raw {a}px)"))

    print("  " + "-" * 62)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good - every tab fits the 21-inch screen\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
