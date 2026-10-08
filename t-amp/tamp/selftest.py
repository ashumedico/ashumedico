"""`T-Amp --selftest`: prove every moving part works on this machine, with real data.

Checks, in order: ffmpeg (and that it speaks https), the JavaScript runtime yt-dlp needs,
the sound device, a live YouTube Music search, resolving a stream, and decoding three
seconds of it. Writes the report to stdout and to selftest.txt in the state folder.
Exit code 0: all passed; 3: only YouTube's bot check stood in the way; 1: something failed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback

import numpy as np

from .engine import CREATE_NO_WINDOW, ffmpeg_command
from .settings import state_dir
from .youtube import MusicSearch, ResolveError, StreamResolver, find_deno, find_ffmpeg


def _run(cmd: list[str], timeout: float = 20) -> str:
    out = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
    return (out.stdout or b"").decode("utf-8", "replace") + (out.stderr or b"").decode("utf-8", "replace")


def run(argv: list[str]) -> int:
    query = "Kesariya Arijit Singh"
    if "--query" in argv:
        query = argv[argv.index("--query") + 1]
    lines: list[str] = []
    ok_all = True
    blocked = False

    def check(name: str, fn):
        nonlocal ok_all, blocked
        t0 = time.monotonic()
        try:
            detail = fn()
            lines.append(f"[PASS] {name}: {detail}  ({time.monotonic() - t0:.1f}s)")
            return detail
        except ResolveError as exc:
            if not exc.bot_check:
                ok_all = False
                lines.append(f"[FAIL] {name}: {exc}")
                return None
            blocked = True
            lines.append(f"[BLOCKED] {name}: YouTube asked this connection to sign in (bot check). "
                         "It does this to datacenter and VPN addresses; on a home connection T-Amp normally "
                         "plays without it. If you see this at home: menu > Options > YouTube sign-in.")
            return None
        except Exception as exc:  # report every failure, keep checking the rest
            ok_all = False
            lines.append(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
            if "--verbose" in argv:
                lines.append(traceback.format_exc())
            return None

    from . import __version__
    lines.append(f"T-Amp {__version__} self-test · Python {sys.version.split()[0]} · {sys.platform}"
                 f"{' · frozen' if getattr(sys, 'frozen', False) else ''}")

    ffmpeg = find_ffmpeg()

    def t_ffmpeg():
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found (imageio-ffmpeg missing?)")
        ver = _run([ffmpeg, "-hide_banner", "-version"]).splitlines()[0]
        protos = _run([ffmpeg, "-hide_banner", "-protocols"])
        if "https" not in protos.split():
            raise RuntimeError(f"{ver} has no https protocol")
        return f"{ver} · https ok · {ffmpeg}"
    check("ffmpeg", t_ffmpeg)

    def t_deno():
        d = find_deno()
        if not d:
            raise RuntimeError("deno not found - yt-dlp cannot unlock YouTube audio formats without it")
        return f"{_run([d, '--version']).splitlines()[0]} · {d}"
    check("javascript runtime", t_deno)

    def t_audio():
        """Open the real output device and prove PortAudio calls us back (silence, nothing audible)."""
        import sounddevice as sd
        dev = sd.query_devices(kind="output")
        rate = int(dev["default_samplerate"])
        calls = []

        def cb(outdata, frames, t, status):
            outdata.fill(0)
            calls.append(frames)
        with sd.OutputStream(samplerate=rate, channels=2, dtype="float32", latency="high", callback=cb) as st:
            time.sleep(0.5)
            latency = st.latency
        if not calls:
            raise RuntimeError("the device opened but never asked for audio")
        return f"{dev['name']} · {rate} Hz · {len(calls)} callbacks in 0.5 s · latency {latency * 1000:.0f} ms"
    if "--no-audio" in argv:
        lines.append("[SKIP] sound device: --no-audio")
    else:
        check("sound device", t_audio)

    music = MusicSearch()
    results = check(f"YouTube Music search '{query}'",
                    lambda: _search(music, query))
    first = results[1] if results else None

    stream = None
    if first is not None:
        from .settings import Settings
        resolver = StreamResolver(cache_dir=os.path.join(state_dir(), "yt-dlp-cache"),
                                  cookies=Settings().get("cookies"))
        stream = check(f"resolve stream for '{first.label}'",
                       lambda: _resolve(resolver, first.video_id))
    if stream is not None and ffmpeg:
        check("decode 3 s of real audio", lambda: _decode(ffmpeg, stream[1]))
        if "--no-audio" not in argv:
            check("play 3 s through the speakers (you should hear the song)",
                  lambda: _play(ffmpeg, stream[1]))

    lines.append("RESULT: " + ("FAILED" if not ok_all else "BLOCKED BY YOUTUBE BOT CHECK" if blocked else "ALL PASS"))
    report = "\n".join(lines)
    try:
        with open(os.path.join(state_dir(), "selftest.txt"), "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
    except OSError:
        pass
    try:
        print(report, flush=True)
    except (OSError, ValueError, AttributeError):  # windowed exe: no console attached
        pass
    return 1 if not ok_all else 3 if blocked else 0


class _Detail(tuple):
    """(text, payload) that prints as its text in the report."""

    def __str__(self) -> str:
        return self[0]


def _search(music: MusicSearch, query: str):
    res = music.search(query, "songs")
    if not res:
        raise RuntimeError("no songs returned")
    return _Detail((f"{len(res)} songs · first: {res[0].label} ({res[0].duration}s)", res[0]))


def _resolve(resolver: StreamResolver, vid: str):
    st = resolver.resolve(vid)
    return _Detail((f"{st.codec} · {round(st.abr or 0)} kbps · {st.asr} Hz · {st.duration}s · "
                    f"expires in {int((st.expires - time.time()) / 60)} min", st))


def _play(ffmpeg: str, st) -> str:
    """The app's own engine on the real device: what the player does when you press Play."""
    from .engine import AudioEngine
    eng = AudioEngine(ffmpeg)
    eng.volume = 0.5
    try:
        t0 = time.monotonic()
        eng.open(st.url, st.headers, 30.0, st.duration)
        started = None
        while time.monotonic() - t0 < 25:
            for ev in eng.poll():
                if ev[0] in ("error", "device"):
                    raise RuntimeError(ev[1])
            if started is None and eng.state == "playing":
                started = time.monotonic() - t0
            if eng.position >= 33.0:
                return (f"{eng.position - 30:.1f} s played at {eng.samplerate} Hz · "
                        f"sound started {started:.1f} s after Play")
            time.sleep(0.05)
        raise RuntimeError(f"only reached {eng.position:.1f} s in 25 s (state: {eng.state})")
    finally:
        eng.close()


def _decode(ffmpeg: str, st) -> str:
    cmd = ffmpeg_command(ffmpeg, st.url, 48000, 30.0, st.headers)
    cmd = cmd[:-1] + ["-t", "3", "pipe:1"]
    out = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW)
    pcm = np.frombuffer(out.stdout[: len(out.stdout) // 8 * 8], dtype="<f4").reshape(-1, 2)
    if len(pcm) < 48000 * 2.5:
        raise RuntimeError(f"only {len(pcm)} frames; ffmpeg said: {out.stderr.decode('utf-8', 'replace')[-300:]}")
    rms = float(np.sqrt(np.mean(pcm ** 2)))
    if rms < 1e-3:
        raise RuntimeError(f"decoded audio is silent (rms {rms:.5f})")
    return f"{len(pcm)} frames from 0:30 · rms {rms:.3f} · peak {float(np.abs(pcm).max()):.2f}"
