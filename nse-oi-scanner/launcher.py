"""
launcher.py  —  AASHISH TRADING OS, as one window.

Everything this system does already existed as a .bat file and an icon. That is fine at
9:20am when you know the order; it is not fine when you are asked to remember which of
twenty-five icons comes first, or when a credential needs changing and the answer is
"open config.py in Notepad".

So: one window. Credentials at the top, settings under them, one green button that starts
the engine, and a log that shows what the engine is actually doing - the same output the
console shows, in the same window as the button that started it.

WHAT THIS IS NOT
It is not a second trading system. Every button here runs the same file the icon ran:
fyers_auth.py, selftest.py, paper.py, desk.py, broker.py. If the window disagrees with the
console, the console is right, because they are the same process.

Standard library only - no Tk extras, no theme packs. That keeps the packaged .exe small
and, more importantly, keeps it building on a machine that has nothing but Python.

    python launcher.py

NOT financial advice. Arming live trading is a deliberate act and it is yours.
"""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

BG      = "#0b0f14"
PANEL   = "#121821"
EDGE    = "#21262d"
TXT     = "#e6edf3"
DIM     = "#8b949e"
GREEN   = "#3fb950"
RED     = "#f85149"
BLUE    = "#58a6ff"
AMBER   = "#d29922"
MONO    = ("Consolas", 9)
UI      = ("Segoe UI", 9)
UIB     = ("Segoe UI", 9, "bold")

KILL_FILE = "STOP_TRADING.txt"


class Launcher:
    def __init__(self, root):
        self.root = root
        self.proc = None            # the engine subprocess, when one is running
        self.q = queue.Queue()
        root.title("AASHISH TRADING OS — Live Launcher")
        root.configure(bg=BG)
        root.geometry("980x760")
        root.minsize(860, 620)

        self._header()
        self._credentials()
        self._settings()
        self._buttons()
        self._log()
        self._load()
        self._refresh_state()
        root.after(120, self._drain)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- chrome --
    def _panel(self, title, color=BLUE):
        wrap = tk.Frame(self.root, bg=PANEL, highlightbackground=EDGE,
                        highlightthickness=1)
        wrap.pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(wrap, text=title, bg=PANEL, fg=color, font=("Segoe UI", 8, "bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(7, 2))
        body = tk.Frame(wrap, bg=PANEL)
        body.pack(fill="x", padx=10, pady=(0, 9))
        return body

    def _header(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=12, pady=(10, 8))
        tk.Label(bar, text="AASHISH", bg=BG, fg=GREEN,
                 font=("Segoe UI", 19, "bold")).pack(side="left")
        tk.Label(bar, text="  TRADING OS  ·  LIVE LAUNCHER", bg=BG, fg=DIM,
                 font=("Segoe UI", 9)).pack(side="left", pady=(8, 0))
        self.state_lbl = tk.Label(bar, text="", bg=BG, fg=DIM, font=UIB)
        self.state_lbl.pack(side="right", pady=(8, 0))

    def _row(self, parent, label, r, show=None, width=52):
        tk.Label(parent, text=label, bg=PANEL, fg=TXT, font=UI, anchor="w",
                 width=18).grid(row=r, column=0, sticky="w", pady=2)
        e = tk.Entry(parent, bg="#0d1117", fg=TXT, insertbackground=TXT, font=MONO,
                     relief="flat", width=width, show=show,
                     highlightbackground=EDGE, highlightthickness=1)
        e.grid(row=r, column=1, sticky="we", pady=2)
        parent.columnconfigure(1, weight=1)
        return e

    # ----------------------------------------------------------- credentials --
    def _credentials(self):
        b = self._panel("CREDENTIALS")
        self.e_client = self._row(b, "Fyers Client ID", 0)
        self.e_secret = self._row(b, "Fyers Secret Key", 1, show="•")
        self.e_redir  = self._row(b, "Redirect URI", 2)
        self.e_tgtok  = self._row(b, "Telegram Bot Token", 3, show="•")
        self.e_tgchat = self._row(b, "Telegram Chat ID", 4)

        opts = tk.Frame(b, bg=PANEL)
        opts.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.show_secrets = tk.BooleanVar(value=False)
        self.remember = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="show secrets", variable=self.show_secrets,
                       command=self._toggle_secrets, bg=PANEL, fg=DIM,
                       selectcolor=PANEL, activebackground=PANEL, activeforeground=TXT,
                       font=UI).pack(side="left")
        tk.Checkbutton(opts, text="remember credentials (config.py mein save)",
                       variable=self.remember, bg=PANEL, fg=DIM, selectcolor=PANEL,
                       activebackground=PANEL, activeforeground=TXT,
                       font=UI).pack(side="left", padx=14)
        tk.Label(opts, text="config.py git-ignored hai — repo public hai",
                 bg=PANEL, fg=AMBER, font=("Segoe UI", 8)).pack(side="left", padx=10)

    def _toggle_secrets(self):
        ch = "" if self.show_secrets.get() else "•"
        for e in (self.e_secret, self.e_tgtok):
            e.config(show=ch)

    # -------------------------------------------------------------- settings --
    def _settings(self):
        b = self._panel("SETTINGS")
        grid = tk.Frame(b, bg=PANEL)
        grid.pack(fill="x")

        def num(col, label, width=9):
            f = tk.Frame(grid, bg=PANEL)
            f.grid(row=0, column=col, sticky="w", padx=(0, 16))
            tk.Label(f, text=label, bg=PANEL, fg=DIM,
                     font=("Segoe UI", 8)).pack(anchor="w")
            e = tk.Entry(f, bg="#0d1117", fg=TXT, insertbackground=TXT, font=MONO,
                         relief="flat", width=width, highlightbackground=EDGE,
                         highlightthickness=1)
            e.pack()
            return e

        self.e_cap    = num(0, "Capital (Rs)", 12)
        self.e_lots   = num(1, "Lots per trade")
        self.e_target = num(2, "Target Rs (net)")
        self.e_pmin   = num(3, "Price min")
        self.e_pmax   = num(4, "Price max")

        mode = tk.Frame(grid, bg=PANEL)
        mode.grid(row=0, column=5, sticky="w")
        tk.Label(mode, text="Mode", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8)).pack(anchor="w")
        self.mode = tk.StringVar(value="intraday")
        mrow = tk.Frame(mode, bg=PANEL)
        mrow.pack()
        for txt, val in (("Intraday 15m", "intraday"), ("Swing", "swing")):
            tk.Radiobutton(mrow, text=txt, value=val, variable=self.mode, bg=PANEL,
                           fg=TXT, selectcolor=PANEL, activebackground=PANEL,
                           activeforeground=TXT, font=UI).pack(side="left")

        note = tk.Label(b, bg=PANEL, fg=DIM, font=("Segoe UI", 8), justify="left",
                        anchor="w", wraplength=900,
                        text="Price band sirf universe chhota karta hai — signal nahi hai, "
                             "aur iska walk-forward test nahi hua. 0 / 0 = band off. "
                             "Quantity hamesha 'Lots per trade' se aati hai, risk budget se nahi.")
        note.pack(fill="x", pady=(8, 0))

    # --------------------------------------------------------------- buttons --
    def _buttons(self):
        b = self._panel("ENGINE", GREEN)
        row = tk.Frame(b, bg=PANEL)
        row.pack(fill="x")

        def btn(parent, text, cmd, bg, fg="#04140a", w=17, side="left"):
            x = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, font=UIB,
                          relief="flat", width=w, pady=7, activebackground=bg,
                          cursor="hand2")
            x.pack(side=side, padx=(0, 8))
            return x

        self.b_engine = btn(row, "▶  START ENGINE", self.start_engine, GREEN)
        btn(row, "1  Fyers login", lambda: self.run(["fyers_auth.py"], "LOGIN"),
            "#1f6feb", "#ffffff", 15)
        btn(row, "Self-test", lambda: self.run(["selftest.py"], "SELF-TEST"),
            "#30363d", TXT, 12)
        btn(row, "Check-in", lambda: self.run(["checkin.py"], "CHECK-IN"),
            "#30363d", TXT, 12)
        btn(row, "Desk (website)", self.open_desk, "#30363d", TXT, 14)
        self.b_kill = btn(row, "■  KILL SWITCH", self.toggle_kill, RED, "#ffffff", 15,
                          side="right")

        row2 = tk.Frame(b, bg=PANEL)
        row2.pack(fill="x", pady=(8, 0))
        self.live = tk.BooleanVar(value=False)
        tk.Checkbutton(row2, text="LIVE TRADING — asli order Fyers pe jayenge",
                       variable=self.live, command=self.toggle_live, bg=PANEL, fg=RED,
                       selectcolor=PANEL, activebackground=PANEL, activeforeground=RED,
                       font=UIB).pack(side="left")
        tk.Label(row2, text="  Paper hamesha chalta hai. Ye sirf live leg on/off karta hai.",
                 bg=PANEL, fg=DIM, font=("Segoe UI", 8)).pack(side="left")

    # ------------------------------------------------------------------- log --
    def _log(self):
        wrap = tk.Frame(self.root, bg=PANEL, highlightbackground=EDGE,
                        highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        head = tk.Frame(wrap, bg=PANEL)
        head.pack(fill="x", padx=10, pady=(7, 2))
        tk.Label(head, text="ENGINE LOG", bg=PANEL, fg=BLUE,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(head, text="clear", command=lambda: self._clear(), bg=PANEL, fg=DIM,
                  relief="flat", font=("Segoe UI", 8), cursor="hand2").pack(side="right")
        self.log = scrolledtext.ScrolledText(wrap, bg="#0d1117", fg=TXT, font=MONO,
                                             relief="flat", height=14, wrap="word",
                                             insertbackground=TXT)
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 9))
        for tag, col in (("ok", GREEN), ("bad", RED), ("warn", AMBER), ("sys", BLUE),
                         ("dim", DIM)):
            self.log.tag_config(tag, foreground=col)

        tk.Label(self.root, bg=BG, fg="#ff7b72", font=("Segoe UI", 8, "bold"),
                 text="NOT FINANCIAL ADVICE — signals are inputs, the decision is yours. "
                      "Options can lose 100% of the premium."
                 ).pack(fill="x", pady=(0, 8))

    def _clear(self):
        self.log.delete("1.0", "end")

    def say(self, text, tag="dim"):
        self.log.insert("end", text.rstrip() + "\n", tag)
        self.log.see("end")

    # ------------------------------------------------------------ config i/o --
    def _load(self):
        try:
            import configure as C
            cred = C.read_credentials()
            cur = C.read_current()
        except Exception as e:      # noqa
            cred, cur = {}, {}
            self.say(f"config padha nahi gaya: {e}", "warn")
        for e, k in ((self.e_client, "CLIENT_ID"), (self.e_secret, "SECRET_KEY"),
                     (self.e_redir, "REDIRECT_URI"), (self.e_tgtok, "TELEGRAM_TOKEN"),
                     (self.e_tgchat, "TELEGRAM_CHAT")):
            e.insert(0, cred.get(k, ""))
        if not cred.get("REDIRECT_URI"):
            self.e_redir.insert(0, "https://127.0.0.1")

        def put(entry, key, default):
            raw = (cur.get(key) or "").strip().strip("'\"")
            entry.insert(0, raw if raw else str(default))
        put(self.e_cap, "CAPITAL", 200000)
        put(self.e_lots, "LOTS_PER_TRADE", 1)
        put(self.e_target, "TARGET_RUPEES", 500)
        put(self.e_pmin, "PRICE_MIN", 0)
        put(self.e_pmax, "PRICE_MAX", 0)
        bm = (cur.get("BAR_MINUTES") or "15").strip()
        self.mode.set("swing" if bm.isdigit() and int(bm) >= 375 else "intraday")
        try:
            import config
            self.live.set(bool(getattr(config, "LIVE_TRADING", False)))
        except Exception:
            pass

    def save(self, announce=True):
        """Write the form back. Credentials only when 'remember' is ticked - an unticked
        box must not quietly persist a secret the user chose not to store."""
        try:
            import configure as C
            if self.remember.get():
                C.write_credentials({
                    "CLIENT_ID": self.e_client.get().strip(),
                    "SECRET_KEY": self.e_secret.get().strip(),
                    "REDIRECT_URI": self.e_redir.get().strip(),
                    "TELEGRAM_TOKEN": self.e_tgtok.get().strip(),
                    "TELEGRAM_CHAT": self.e_tgchat.get().strip(),
                })
            up = dict(C.MODES[self.mode.get()])
            def i(entry, default=0):
                try:
                    return int(float(entry.get().strip() or default))
                except ValueError:
                    return default
            up.update({"CAPITAL": i(self.e_cap, 200000),
                       "LOTS_PER_TRADE": max(1, i(self.e_lots, 1)),
                       "TARGET_RUPEES": i(self.e_target, 0),
                       "PRICE_MIN": max(0, i(self.e_pmin, 0)),
                       "PRICE_MAX": max(0, i(self.e_pmax, 0))})
            C.write({k: C.KEYS[k][0](v) for k, v in up.items() if k in C.KEYS})
            if announce:
                self.say("settings save ho gayi (config.py, backup ke saath)", "ok")
            return True
        except Exception as e:      # noqa
            self.say(f"save fail: {e}", "bad")
            return False

    # --------------------------------------------------------------- running --
    def run(self, args, label):
        """Run a python file and stream it here. One at a time, on purpose: two engines
        marking the same book would each think they own it."""
        if self.proc and self.proc.poll() is None:
            messagebox.showinfo("Pehle se chal raha hai",
                                "Ek process already chal raha hai. Pehle usse rukne do "
                                "ya STOP ENGINE dabao.")
            return
        self.save(announce=False)
        self.say(f"\n=== {label} ===", "sys")
        cmd = [sys.executable, "-u"] + args
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:      # noqa
            self.say(f"start nahi hua: {e}", "bad")
            return
        threading.Thread(target=self._pump, args=(self.proc, label), daemon=True).start()
        self._refresh_state()

    def _pump(self, proc, label):
        for raw in iter(proc.stdout.readline, ""):
            self.q.put(raw)
        proc.stdout.close()
        code = proc.wait()
        self.q.put(f"\x00{label} khatam (exit {code})")

    def _drain(self):
        try:
            while True:
                line = self.q.get_nowait()
                if line.startswith("\x00"):
                    self.say(f"=== {line[1:]} ===", "sys")
                    self._refresh_state()
                    continue
                plain = _strip_ansi(line)
                low = plain.lower()
                tag = ("bad" if ("fail" in low or "error" in low or "traceback" in low)
                       else "ok" if (" ok" in low or "pass" in low or "chalu" in low)
                       else "warn" if ("skip" in low or "warn" in low or "!!" in plain)
                       else "dim")
                self.say(plain, tag)
        except queue.Empty:
            pass
        self.root.after(120, self._drain)

    def start_engine(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.say("engine ko rukne ka signal bhej diya", "warn")
            except Exception as e:      # noqa
                self.say(f"terminate fail: {e}", "bad")
            self.root.after(600, self._refresh_state)
            return
        if os.path.exists(KILL_FILE):
            messagebox.showwarning("Kill switch on",
                                   "STOP_TRADING.txt maujood hai. Pehle KILL SWITCH "
                                   "band kar, phir engine chalu hoga.")
            return
        self.run(["paper.py", "--session"], "ENGINE")

    def open_desk(self):
        """The desk is a server, not a script - it gets its own process and a browser
        tab, and it must not occupy the single engine slot."""
        self.save(announce=False)
        try:
            subprocess.Popen([sys.executable, "-m", "streamlit", "run", "desk.py"],
                             cwd=HERE,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.say("desk chalu — browser mein localhost:8501 khul jayega", "ok")
            try:
                import webbrowser
                self.root.after(3500, lambda: webbrowser.open("http://localhost:8501"))
            except Exception:
                pass
        except Exception as e:      # noqa
            self.say(f"desk start nahi hua: {e}", "bad")

    # ----------------------------------------------------------------- state --
    def toggle_kill(self):
        if os.path.exists(KILL_FILE):
            try:
                os.remove(KILL_FILE)
                self.say("kill switch hata diya — system chal sakta hai", "ok")
            except Exception as e:      # noqa
                self.say(f"hata nahi paya: {e}", "bad")
        else:
            with open(KILL_FILE, "w") as f:
                f.write("halted from launcher\n")
            self.say("KILL SWITCH ON — koi order nahi jayega", "bad")
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass
        self._refresh_state()

    def toggle_live(self):
        want = self.live.get()
        if want and not messagebox.askyesno(
                "LIVE trading chalu?",
                "Ab asli order Fyers account pe jayenge.\n\n"
                "Bhara hua order wapas nahi hota. Quantity 1 lot rahegi.\n\n"
                "Chalu karun?"):
            self.live.set(False)
            return
        try:
            import configure as C
            C.write({"LIVE_TRADING": "True" if want else "False"})
            self.say("LIVE TRADING ON — asli order jayenge" if want
                     else "LIVE off — sirf paper", "bad" if want else "ok")
        except Exception as e:      # noqa
            self.say(f"live toggle fail: {e}", "bad")
            self.live.set(not want)
        self._refresh_state()

    def _refresh_state(self):
        running = bool(self.proc and self.proc.poll() is None)
        killed = os.path.exists(KILL_FILE)
        self.b_engine.config(text="■  STOP ENGINE" if running else "▶  START ENGINE",
                             bg=AMBER if running else GREEN)
        self.b_kill.config(text="KILL SWITCH ON" if killed else "■  KILL SWITCH",
                           bg="#8b0000" if killed else RED)
        bits = []
        bits.append("ENGINE CHAL RAHA HAI" if running else "idle")
        if killed:
            bits.append("HALTED")
        if self.live.get():
            bits.append("LIVE ARMED")
        else:
            bits.append("paper only")
        self.state_lbl.config(
            text="   ·   ".join(bits),
            fg=RED if (killed or self.live.get()) else (GREEN if running else DIM))

    def _on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno(
                    "Engine chal raha hai",
                    "Engine abhi chal raha hai. Window band karne se wo bhi ruk jayega, "
                    "aur khuli position ko koi dekhne wala nahi bachega.\n\n"
                    "Phir bhi band karun?"):
                return
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.root.destroy()


def _strip_ansi(s):
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)


def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default=os.path.join(HERE, "tbone.ico"))
    except Exception:
        pass                      # no icon file is not a reason to fail to start
    Launcher(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
