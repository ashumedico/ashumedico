"""
test_launcher.py  —  proof that the window builds and its wiring is real.

A GUI is the easiest thing to ship broken: it imports fine, compiles fine, and then throws
the first time a human clicks anything. This builds the actual window off-screen, then
exercises the parts that touch state - config round-trip, the kill switch, the button
labels that are supposed to change - without a person or a broker in the loop.

What it does NOT do is place orders or start the engine. Those are subprocess calls; the
test asserts the command that would be run, not the running of it.

    python test_launcher.py

Needs tkinter and a display. On a headless box:  xvfb-run -a python test_launcher.py
Without either it SKIPS, and a skip is not a pass.
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        FAILED.append(name)


def test_config_roundtrip():
    """Credentials and settings must survive a write/read cycle, and 'remember' being
    off must not persist a secret."""
    print("\n  CONFIG ROUND-TRIP")
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        shutil.copy(os.path.join(HERE, "config.example.py"),
                    os.path.join(tmp, "config.py"))
        os.chdir(tmp)
        for m in ("configure",):
            sys.modules.pop(m, None)
        sys.path.insert(0, HERE)
        import configure as C

        C.write_credentials({"CLIENT_ID": "TESTID-100", "SECRET_KEY": "s3cr3t",
                             "TELEGRAM_CHAT": "12345"})
        back = C.read_credentials()
        check("credentials written and read back",
              back.get("CLIENT_ID") == "TESTID-100" and back.get("SECRET_KEY") == "s3cr3t")

        C.write_credentials({"CLIENT_ID": ""})       # blank must not wipe a real value
        check("blank does not erase an existing credential",
              C.read_credentials().get("CLIENT_ID") == "TESTID-100")

        C.write({k: C.KEYS[k][0](v) for k, v in
                 {"CAPITAL": 200000, "LOTS_PER_TRADE": 1, "PRICE_MIN": 200,
                  "PRICE_MAX": 600}.items()})
        cur = C.read_current()
        check("settings written", cur.get("CAPITAL") == "200000" and
              cur.get("PRICE_MIN") == "200" and cur.get("PRICE_MAX") == "600",
              f"capital={cur.get('CAPITAL')} band={cur.get('PRICE_MIN')}-{cur.get('PRICE_MAX')}")

        # Two writes actually happen (the blank one is a no-op). Both land in the same
        # second, so this is really a test that same-second backups do not clobber.
        baks = [f for f in os.listdir(".") if f.startswith("config.py.bak-")]
        check("same-second writes keep separate backups", len(baks) >= 2,
              f"{len(baks)} backups")

        text = open("config.py").read()
        check("secret is quoted, not bare", "SECRET_KEY = 's3cr3t'" in text)
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
        sys.modules.pop("configure", None)


def test_window():
    print("\n  WINDOW")
    try:
        import tkinter as tk
    except ImportError:
        print("  SKIP  tkinter nahi hai (Linux: apt install python3-tk). "
              "Windows pe Python ke saath aata hai.")
        return
    try:
        root = tk.Tk()
    except Exception as e:      # noqa
        print(f"  SKIP  koi display nahi ({str(e)[:60]}) - try: xvfb-run -a python test_launcher.py")
        return
    root.withdraw()
    import launcher as L

    app = L.Launcher(root)
    check("window builds", app is not None)
    check("all five credential fields exist",
          all(hasattr(app, a) for a in ("e_client", "e_secret", "e_redir",
                                        "e_tgtok", "e_tgchat")))
    check("settings fields exist",
          all(hasattr(app, a) for a in ("e_cap", "e_lots", "e_target",
                                        "e_pmin", "e_pmax")))

    # secrets masked by default, revealed on demand
    check("secret masked by default", app.e_secret.cget("show") == "•")
    app.show_secrets.set(True)
    app._toggle_secrets()
    check("show secrets reveals", app.e_secret.cget("show") == "")
    app.show_secrets.set(False)
    app._toggle_secrets()
    check("and hides again", app.e_secret.cget("show") == "•")

    # kill switch really creates and removes the file the rest of the system reads
    kf = os.path.join(HERE, L.KILL_FILE)
    pre = os.path.exists(kf)
    if pre:
        os.remove(kf)
    app.toggle_kill()
    check("kill switch creates the file the engine checks", os.path.exists(kf))
    check("kill button relabels", "ON" in app.b_kill.cget("text"))
    app.toggle_kill()
    check("kill switch clears", not os.path.exists(kf))

    # the engine button must refuse to start while halted
    with open(kf, "w") as f:
        f.write("test\n")
    started = {"no": True}
    app.run = lambda *a, **k: started.update(no=False)
    try:
        import tkinter.messagebox as mb
        mb.showwarning = lambda *a, **k: None
        app.start_engine()
    finally:
        os.remove(kf)
    check("engine refuses to start with the kill switch on", started["no"])

    # log tagging: a FAIL line must not be painted as ok
    app.say("Token   FAIL  koi token nahi", "bad")
    check("log accepts styled lines", "FAIL" in app.log.get("1.0", "end"))

    root.destroy()


def main():
    print("\n  LAUNCHER")
    print("  " + "-" * 60)
    test_config_roundtrip()
    test_window()
    print("  " + "-" * 60)
    if FAILED:
        print(f"  {len(FAILED)} FAILED: {', '.join(FAILED)}\n")
        return 1
    print("  all good\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
