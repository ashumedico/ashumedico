"""The player: playlist, transport and the glue between YouTube Music and the audio engine.

UI panels call methods here and repaint on `changed` / `tick`. All network work runs in
worker threads; results come back as queued Qt signals and are checked against a request
id, so a slow answer for an old click can never start the wrong song.
"""
from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from .dsp import PRESETS, Visualizer
from .engine import AudioEngine
from .settings import Settings, audio_cache_dir, state_dir
from .youtube import Album, AudioFetcher, MusicSearch, ResolveError, Track, find_ffmpeg, fmt_time


class _Superseded(Exception):
    """A resolve nobody is waiting for any more."""


class Player(QObject):
    changed = Signal()            # transport / track / options changed: repaint everything
    playlist_changed = Signal()
    tick = Signal()               # ~30 Hz heartbeat: time display, visualiser
    search_done = Signal(int, str, object, object)   # seq, query, results, error text
    tracks_ready = Signal(object, bool, object)      # tracks, play-now, error text
    _resolved = Signal(int, object, object, float)   # request id, track, future, start
    engine_msg = Signal(str)
    SKIP_DELAY_MS = 2500          # show a failed song's error this long before moving on

    def __init__(self, settings: Settings | None = None, engine: AudioEngine | None = None,
                 music: MusicSearch | None = None, fetcher: AudioFetcher | None = None):
        super().__init__()
        self.settings = settings or Settings()
        s = self.settings
        ffmpeg = find_ffmpeg()
        self.engine = engine or AudioEngine(ffmpeg or "ffmpeg")
        self.music = music or MusicSearch(location=s.get("region") or "IN")
        self.fetcher = fetcher or AudioFetcher(audio_cache_dir(), cookies=s.get("cookies"),
                                               cache_mb=int(s.get("cache_mb") or 1024))
        self.vis = Visualizer(self.engine.samplerate)
        self.scope = np.zeros(76)

        self.tracks: list[Track] = []
        for d in s["playlist"]:
            try:
                self.tracks.append(Track.from_dict(d))
            except TypeError:
                pass
        self.current = s["current"] if 0 <= s["current"] < len(self.tracks) else (0 if self.tracks else -1)
        self.selected: set[int] = set()
        self.status = "stopped"           # stopped | connecting | playing | paused
        self.playing: Track | None = None  # the song loaded in the engine (survives playlist edits)
        self.stream = None
        self.shuffle = bool(s["shuffle"])
        self.repeat = bool(s["repeat"])
        self.engine.volume = s["volume"] / 100.0
        self.engine.balance = s["balance"] / 100.0
        self.eq_on, self.eq_auto = bool(s["eq_on"]), bool(s["eq_auto"])
        self.eq_preamp, self.eq_gains = float(s["eq_preamp"]), [float(g) for g in s["eq_gains"]][:10]
        self._apply_eq()

        self._message = ("", 0.0)
        self._req = 0
        self._retried = False
        self._proven = False          # has this song actually played for a few seconds?
        self._orphaned = False        # the playing song was removed from the list
        self._fails = 0               # failures in a row; reset only by real playback
        self._start_at = 0.0
        self._prefetched: str | None = None
        self._played_order: list[Track] = []
        self._sseq = 0
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="t-amp-resolve")
        self._search_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="t-amp-search")
        self._bg_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="t-amp-bg")  # albums, updates
        self._resolved.connect(self._on_resolved)
        self.engine_msg.connect(lambda m: self.flash(m, 12.0))

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self.save)
        self.playlist_changed.connect(self._schedule_save)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

    # ---- read-only views ---------------------------------------------------------------------
    @property
    def track(self) -> Track | None:
        """The playlist cursor (what Play would start)."""
        return self.tracks[self.current] if 0 <= self.current < len(self.tracks) else None

    @property
    def position(self) -> float:
        if self.status in ("playing", "paused"):
            return self.engine.position
        if self.status == "connecting":
            return self._start_at
        return 0.0

    @property
    def duration(self) -> float | None:
        if self.stream and self.stream.duration:
            return float(self.stream.duration)
        t = self.playing or self.track
        return float(t.duration) if t and t.duration else None

    @property
    def buffering(self) -> bool:
        return self.status == "connecting" or (self.status == "playing" and self.engine.state == "buffering")

    @property
    def message(self) -> str:
        text, until = self._message
        return text if time.monotonic() < until else ""

    def flash(self, text: str, seconds: float = 3.0) -> None:
        """A temporary line in the song-title display (slider feedback, errors)."""
        self._message = (text, time.monotonic() + seconds)
        self.changed.emit()

    def index_of(self, t: Track | None) -> int:
        return next((i for i, x in enumerate(self.tracks) if x is t), -1) if t is not None else -1

    def title_line(self) -> str:
        t = self.playing if self.status != "stopped" else self.track
        if t is None:
            return "T-AMP - YOUTUBE MUSIC  ***  PRESS L OR EJECT TO SEARCH"
        dur = self.duration
        tail = f" ({fmt_time(dur)})" if dur else ""
        i = self.index_of(t)
        return f"{i + 1}. {t.label}{tail}" if i >= 0 else f"{t.label}{tail}"

    # ---- playlist editing ------------------------------------------------------------------------
    def add_tracks(self, tracks: list[Track], play: bool = False, at: int | None = None) -> None:
        if not tracks:
            return
        tracks = [replace(t) for t in tracks]  # own copies: the same search hit added twice is two rows
        at = len(self.tracks) if at is None else max(0, min(at, len(self.tracks)))
        self.tracks[at:at] = tracks
        if self.current == -1:
            self.current = at
        elif self.current >= at:
            self.current += len(tracks)
        self.selected = set()
        self.playlist_changed.emit()
        if play:
            self.play_index(at)
        self.changed.emit()

    def remove(self, indices) -> None:
        drop = sorted({i for i in indices if 0 <= i < len(self.tracks)})
        if not drop:
            return
        if self.current in drop:
            # The row under the cursor goes; if it is the song playing, the music carries on
            # (as in Winamp) and Next continues with the row that took its place.
            self._orphaned = self.playing is self.tracks[self.current] and self.status != "stopped"
        newcur = self.current - sum(1 for i in drop if i < self.current)
        for i in reversed(drop):
            del self.tracks[i]
        self.current = min(newcur, len(self.tracks) - 1) if self.tracks else -1
        self.selected = set()
        self.playlist_changed.emit()
        self.changed.emit()

    def crop(self) -> None:
        if not self.selected:
            self.flash("CROP: SELECT THE ROWS TO KEEP FIRST")
            return
        self.remove([i for i in range(len(self.tracks)) if i not in self.selected])

    def clear(self) -> None:
        self.stop()
        self.tracks, self.current, self.selected = [], -1, set()
        self.playlist_changed.emit()
        self.changed.emit()

    def move(self, indices, to: int) -> list[int]:
        """Move rows `indices` so the first lands at `to`; returns their new positions."""
        idx = sorted(i for i in set(indices) if 0 <= i < len(self.tracks))
        if not idx:
            return []
        cur = self.track
        moving = [self.tracks[i] for i in idx]
        rest = [t for i, t in enumerate(self.tracks) if i not in set(idx)]
        to = max(0, min(to, len(rest)))
        self.tracks = rest[:to] + moving + rest[to:]
        if cur is not None:
            self.current = self.index_of(cur)
        self.selected = set(range(to, to + len(moving)))
        self.playlist_changed.emit()
        self.changed.emit()
        return sorted(self.selected)

    def sort(self, key: str) -> None:
        cur = self.track
        keyf = {"title": lambda t: t.title.lower(), "artist": lambda t: (t.artist.lower(), t.title.lower()),
                "duration": lambda t: t.duration or 0}[key]
        self.tracks.sort(key=keyf)
        self._after_reorder(cur)

    def randomize(self) -> None:
        cur = self.track
        random.shuffle(self.tracks)
        self._after_reorder(cur)

    def reverse(self) -> None:
        cur = self.track
        self.tracks.reverse()
        self._after_reorder(cur)

    def _after_reorder(self, cur) -> None:
        if cur is not None:
            self.current = self.index_of(cur)
        self.selected = set()
        self.playlist_changed.emit()
        self.changed.emit()

    def total_seconds(self, indices=None) -> tuple[int, bool]:
        """(sum of known durations, True if some are unknown)."""
        rows = range(len(self.tracks)) if indices is None else indices
        total, unknown = 0, False
        for i in rows:
            d = self.tracks[i].duration
            if d:
                total += int(d)
            else:
                unknown = True
        return total, unknown

    # ---- transport -------------------------------------------------------------------------------
    def play_index(self, i: int, start: float = 0.0) -> None:
        if not 0 <= i < len(self.tracks):
            return
        self.current = i
        t = self.tracks[i]
        self._req += 1
        self.engine.halt()  # keep the sound device open between songs: no gap, no UI hitch
        self.status = "connecting"
        self.playing = t
        self.stream = None
        self._orphaned = False
        self._retried = False
        self._proven = False
        self._start_at = start
        self._prefetched = None
        if self.eq_auto:
            self._load_track_eq(t.video_id)
        if not self._played_order or self._played_order[-1] is not t:
            self._played_order.append(t)
            del self._played_order[:-200]
        self._submit_resolve(self._req, t, start, force=False)
        self.changed.emit()
        self.playlist_changed.emit()

    def _submit_resolve(self, req: int, t: Track, start: float, force: bool) -> None:
        def job():
            if req != self._req:
                raise _Superseded()  # the user clicked on: don't spend 3-10 s asking YouTube
            return self.fetcher.fetch(t.video_id, force)
        fut = self._pool.submit(job)
        fut.add_done_callback(lambda f: self._resolved.emit(req, t, f, start))

    def _on_resolved(self, req: int, t: Track, fut, start: float) -> None:
        if req != self._req:
            return  # the user has moved on
        try:
            stream = fut.result()
        except _Superseded:
            return
        except ResolveError as exc:
            if exc.bot_check:  # every track would fail the same way: stop and say what fixes it
                self._fail("YOUTUBE ASKS THIS CONNECTION TO SIGN IN (BOT CHECK) - "
                           "MENU > OPTIONS > YOUTUBE SIGN-IN", skip=False)
            else:
                self._fail(str(exc))
            return
        except Exception as exc:  # network down, yt-dlp internals: report, don't crash
            self._fail(f"{type(exc).__name__}: {exc}")
            return
        self.stream = stream
        if not t.duration and stream.duration:
            t.duration = int(stream.duration)
            self.playlist_changed.emit()
        self.engine.open(stream.path, None, start, self.duration, feed=stream.pending)
        self.status = "playing"
        self.changed.emit()

    def _fail(self, msg: str, skip: bool = True) -> None:
        self._log(msg)
        self._fails += 1
        self.engine.halt()
        self.status = "stopped"
        self.stream = None
        self.playing = None
        self.flash(f"ERROR: {msg}", 6.0 if skip else 15.0)
        req = self._req
        if skip and self._fails < max(2, len(self.tracks)) and len(self.tracks) > 1:
            QTimer.singleShot(self.SKIP_DELAY_MS, lambda: self._skip_after_fail(req))

    def _log(self, msg: str) -> None:
        """Full error text to playback.log - the title display only has room for the start of it."""
        t = self.playing or self.track
        try:
            with open(f"{state_dir()}/playback.log", "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {t.video_id if t else '-'}  "
                         f"{t.label if t else ''}  |  {msg}\n")
        except OSError:
            pass

    def _skip_after_fail(self, req: int) -> None:
        if req == self._req and self.status == "stopped":
            nxt = self._next_index(manual=False)
            if nxt is not None:
                self.play_index(nxt)

    def play(self) -> None:
        """Winamp's play: resume if paused, restart if playing, else start the current row."""
        if self.status == "paused":
            self.engine.resume()
            self.status = "playing"
            self.changed.emit()
        elif self.tracks:
            if self.current < 0:
                self.current = min(self.selected) if self.selected else 0
            self.play_index(self.current)

    def pause(self) -> None:
        if self.status == "playing":
            self.engine.pause()
            self.status = "paused"
        elif self.status == "paused":
            self.engine.resume()
            self.status = "playing"
        self.changed.emit()

    def stop(self) -> None:
        self._req += 1
        self.engine.stop()
        self.status = "stopped"
        self.stream = None
        self.playing = None
        self._orphaned = False
        self.changed.emit()

    def next(self) -> None:
        nxt = self._next_index(manual=True)
        if nxt is not None:
            self._go(nxt)

    def prev(self) -> None:
        if not self.tracks:
            return
        target = -1
        if self.shuffle:
            if self._played_order:
                self._played_order.pop()  # the song playing now
            while self._played_order and target < 0:
                target = self.index_of(self._played_order.pop())  # skips songs removed since
        if target < 0:
            target = (self.current - 1) % len(self.tracks)
        self._go(target)

    def _go(self, i: int) -> None:
        if self.status in ("playing", "paused", "connecting"):
            self.play_index(i)
        else:
            self.current = i
            self._orphaned = False
            self.changed.emit()
            self.playlist_changed.emit()

    def _next_index(self, manual: bool) -> int | None:
        n = len(self.tracks)
        if n == 0:
            return None
        if self.shuffle and n > 1:
            recent = {id(t) for t in self._played_order[-max(1, n - 1):]}
            here = self.playing or self.track
            pool = [i for i, t in enumerate(self.tracks) if id(t) not in recent and t is not here]
            if not pool:
                if not (self.repeat or manual):
                    return None
                pool = [i for i, t in enumerate(self.tracks) if t is not here]
            return random.choice(pool)
        if self._orphaned:  # the playing song was removed: its successor already sits at `current`
            nxt = self.current
        else:
            nxt = self.current + 1
        if not 0 <= nxt < n:
            return 0 if (self.repeat or manual) else None
        return nxt

    def seek(self, seconds: float) -> None:
        if self.status in ("playing", "paused"):
            self.engine.seek(seconds)
            self.changed.emit()

    def seek_rel(self, delta: float) -> None:
        if self.status in ("playing", "paused"):
            self.seek(max(0.0, self.position + delta))

    # ---- levels, EQ, options -------------------------------------------------------------------
    def set_volume(self, v: float) -> None:
        v = max(0, min(100, round(v)))
        self.settings["volume"] = v
        self.engine.volume = v / 100.0
        self._schedule_save()
        self.changed.emit()

    def set_balance(self, b: float) -> None:
        b = max(-100, min(100, round(b)))
        self.settings["balance"] = b
        self.engine.balance = b / 100.0
        self._schedule_save()
        self.changed.emit()

    def set_eq(self, on: bool | None = None, preamp: float | None = None, gains=None, band: int | None = None,
               value: float | None = None) -> None:
        if on is not None:
            self.eq_on = on
        if preamp is not None:
            self.eq_preamp = max(-12.0, min(12.0, preamp))
        if gains is not None:
            self.eq_gains = [max(-12.0, min(12.0, float(g))) for g in gains][:10]
        if band is not None and value is not None:
            self.eq_gains[band] = max(-12.0, min(12.0, value))
        self._apply_eq()
        t = self.playing or self.track
        if self.eq_auto and t and (gains is not None or band is not None or preamp is not None):
            self.settings["eq_per_track"][t.video_id] = [self.eq_preamp, list(self.eq_gains)]
        self._schedule_save()
        self.changed.emit()

    def load_preset(self, name: str) -> None:
        pre, gains = PRESETS[name]
        self.set_eq(on=True, preamp=pre, gains=gains)
        self.flash(f"EQ PRESET: {name}")

    def _load_track_eq(self, video_id: str) -> None:
        saved = self.settings["eq_per_track"].get(video_id)
        if saved:
            self.eq_preamp, self.eq_gains = float(saved[0]), [float(g) for g in saved[1]]
            self.eq_on = True
            self._apply_eq()

    def _apply_eq(self) -> None:
        self.engine.eq.set(self.eq_on, self.eq_preamp, self.eq_gains)
        s = self.settings
        s.update(eq_on=self.eq_on, eq_auto=self.eq_auto, eq_preamp=self.eq_preamp, eq_gains=list(self.eq_gains))

    def set_cookies(self, cookies: str | None) -> None:
        """YouTube sign-in for yt-dlp: None, "browser:<name>", or a cookies.txt path."""
        self.settings["cookies"] = cookies
        if hasattr(self.fetcher, "set_cookies"):
            self.fetcher.set_cookies(cookies)
        self._schedule_save()
        self.flash("YOUTUBE SIGN-IN: " + ("OFF" if not cookies else
                   cookies[len("browser:"):].upper() + " COOKIES" if cookies.startswith("browser:") else "COOKIES.TXT"))

    def toggle(self, what: str) -> None:
        if what == "shuffle":
            self.shuffle = not self.shuffle
            self.settings["shuffle"] = self.shuffle
        elif what == "repeat":
            self.repeat = not self.repeat
            self.settings["repeat"] = self.repeat
        elif what == "eq_auto":
            self.eq_auto = not self.eq_auto
            self.settings["eq_auto"] = self.eq_auto
        self._schedule_save()
        self.changed.emit()

    # ---- search ------------------------------------------------------------------------------
    def search(self, query: str, kind: str) -> int:
        self._sseq += 1
        seq = self._sseq
        self._search_pool.submit(self._do_search, seq, query, kind)
        return seq

    def _do_search(self, seq: int, query: str, kind: str) -> None:
        if seq != self._sseq:
            return  # a newer keystroke already superseded this one
        try:
            res, err = self.music.search(query, kind), None
        except Exception as exc:  # network / API change: show it in the search window
            res, err = [], f"{type(exc).__name__}: {exc}"
        self.search_done.emit(seq, query, res, err)

    def expand_and_add(self, items, play: bool) -> None:
        """Add tracks and albums; albums are fetched in the background, in order."""
        def work():
            out = []
            try:
                for it in items:
                    out.extend(self.music.album_tracks(it.browse_id) if isinstance(it, Album) else [it])
                self.tracks_ready.emit(out, play, None)
            except Exception as exc:  # album fetch failed: say so, add what we have
                self.tracks_ready.emit(out, play, f"{type(exc).__name__}: {exc}")
        if all(isinstance(it, Track) for it in items):
            self.add_tracks(list(items), play=play)
        else:
            self._bg_pool.submit(work)

    # ---- keeping yt-dlp current -----------------------------------------------------------------
    def update_engine(self, manual: bool = False) -> None:
        """Refresh yt-dlp / ytmusicapi from PyPI in the background (see updater.py)."""
        from . import updater

        def work():
            try:
                changed = updater.update()
                self.settings["engine_checked"] = time.time()
                if changed:
                    self.engine_msg.emit("YOUTUBE ENGINE UPDATED - RESTART T-AMP TO USE IT: "
                                         + "; ".join(changed))
                elif manual:
                    self.engine_msg.emit("YOUTUBE ENGINE IS UP TO DATE")
            except Exception as exc:  # offline, PyPI down: try again next start
                if manual:
                    self.engine_msg.emit(f"ENGINE UPDATE FAILED: {type(exc).__name__}: {exc}")
        if manual:
            self.flash("CHECKING FOR A NEWER YOUTUBE ENGINE...", 10.0)
        self._bg_pool.submit(work)

    # ---- heartbeat ---------------------------------------------------------------------------
    def _on_tick(self) -> None:
        for ev in self.engine.poll():
            if ev[0] == "finished":
                nxt = self._next_index(manual=False)
                if nxt is None:
                    self.stop()
                else:
                    self.play_index(nxt)
            elif ev[0] == "error" and self.status == "playing":
                self._log(f"playback: {ev[1]} (at {fmt_time(ev[2])})")
                if not self._retried and self.playing is not None:
                    self._retried = True  # most often an expired URL: fetch a fresh one, carry on
                    self._req += 1
                    self.engine.halt()
                    self.status = "connecting"
                    self._start_at = ev[2]
                    self._submit_resolve(self._req, self.playing, ev[2], force=True)
                else:
                    self._fail(ev[1])
            elif ev[0] == "device":
                self.stop()
                self.flash(f"AUDIO DEVICE: {ev[1]}", 10.0)
        if self.status == "playing":
            mono = self.engine.audible_samples(2048)
            if not self._proven and self.engine.state == "playing" and self.position > self._start_at + 3:
                self._proven = True
                self._fails = 0  # audio really came out: the failure streak is over
            self._prefetch_next()
        else:
            mono = None
        mode = self.settings["vis_mode"]
        if mode == "spectrum":
            self.vis.step(mono, 75 if self.settings["vis_thin"] else 19)
        elif mode == "scope":
            self.scope = Visualizer.scope(mono)
        self.tick.emit()

    def _prefetch_next(self) -> None:
        dur = self.duration
        if not dur or self.position < min(dur * 0.5, dur - 40):
            return
        nxt = self._next_index(manual=False) if not self.shuffle else None
        if nxt is None:
            return
        vid = self.tracks[nxt].video_id
        if self._prefetched != vid:
            self._prefetched = vid
            self._pool.submit(self.fetcher.fetch, vid, False)  # download it in the background

    # ---- persistence -------------------------------------------------------------------------
    def _schedule_save(self) -> None:
        self._save_timer.start()

    def save(self) -> None:
        s = self.settings
        s["playlist"] = [t.to_dict() for t in self.tracks]
        s["current"] = self.current
        s.save()

    def shutdown(self) -> None:
        self.timer.stop()
        self.save()
        self.engine.close()
        for pool in (self._pool, self._search_pool, self._bg_pool):
            pool.shutdown(wait=False, cancel_futures=True)
