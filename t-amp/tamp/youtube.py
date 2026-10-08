"""YouTube Music: live search (ytmusicapi) and fetching the audio (yt-dlp).

Search goes to the YouTube Music catalogue only (songs, music videos, albums), so the
results are music by construction, not general YouTube. No API key and no login.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import json
import threading
import time
from dataclasses import asdict, dataclass, field


@dataclass
class Track:
    video_id: str
    title: str
    artist: str = ""
    album: str = ""
    duration: int | None = None
    kind: str = "song"          # song | video

    @property
    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.video_id}"

    @property
    def label(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        return cls(**{k: d.get(k) for k in ("video_id", "title", "artist", "album", "duration", "kind")
                      if k in d})


@dataclass
class Album:
    browse_id: str
    title: str
    artist: str = ""
    year: str = ""
    kind: str = "album"         # album | single | ep (as YouTube Music labels it)
    tracks: list = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title


@dataclass
class Stream:
    """A song's audio as a local file in the cache - complete, or still arriving (`pending`)."""
    path: str
    duration: float | None
    abr: float | None           # kbps
    asr: int | None             # Hz
    channels: int | None
    codec: str
    pending: "Download | None" = None


def fmt_time(seconds) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _artists(item: dict) -> str:
    names = [a.get("name", "") for a in (item.get("artists") or []) if a.get("name")]
    return ", ".join(names)


def _track(item: dict, kind: str = "song", album: str = "") -> Track | None:
    vid = item.get("videoId")
    if not vid or item.get("isAvailable") is False:
        return None
    alb = item.get("album")
    alb_name = alb.get("name", "") if isinstance(alb, dict) else (alb or album or "")
    dur = item.get("duration_seconds")
    if dur is None and item.get("duration"):
        try:
            parts = [int(p) for p in str(item["duration"]).split(":")]
            dur = sum(v * 60 ** i for i, v in enumerate(reversed(parts)))
        except ValueError:
            dur = None
    return Track(video_id=vid, title=item.get("title") or vid, artist=_artists(item),
                 album=alb_name, duration=dur, kind=kind)


_VIDEO_ID = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})")
_LIST_ID = re.compile(r"[?&]list=([A-Za-z0-9_-]+)")
_BROWSE_ID = re.compile(r"/browse/(MPREb_[A-Za-z0-9_-]+)")


class NotMusicLink(ValueError):
    pass


def is_youtube_link(text: str) -> bool:
    return bool(re.match(r"^(https?://)?([a-z0-9-]+\.)*(youtube\.com|youtu\.be)/", text.strip(), re.I))


def parse_link(text: str) -> tuple[str, str] | None:
    """('video'|'playlist'|'album', id) for a YouTube *Music* link, else None.

    Plain youtube.com / youtu.be links are not accepted: T-Amp plays the YouTube Music
    catalogue only, and those links can point at any video at all.
    """
    text = text.strip()
    if not re.match(r"^(https?://)?music\.youtube\.com/", text, re.I):
        return None
    if m := _BROWSE_ID.search(text):
        return ("album", m.group(1))
    v, lst = _VIDEO_ID.search(text), _LIST_ID.search(text)
    if v:
        return ("video", v.group(1))
    if lst:
        return ("playlist", lst.group(1))
    return None


class MusicSearch:
    """Thin, typed wrapper over ytmusicapi. Not thread-safe: call from one worker thread."""

    KINDS = ("songs", "videos", "albums")

    def __init__(self, location: str = "IN", language: str = "en"):
        self.location, self.language = location, language
        self._yt = None

    def _api(self):
        if self._yt is None:
            from ytmusicapi import YTMusic
            self._yt = YTMusic(language=self.language, location=self.location)
        return self._yt

    def search(self, query: str, kind: str = "songs", limit: int = 30) -> list:
        query = query.strip()
        if not query:
            return []
        link = parse_link(query)
        if link:
            return self.from_link(*link)
        if is_youtube_link(query):
            raise NotMusicLink("only YouTube Music links (music.youtube.com) - or type the song name")
        raw = self._api().search(query, filter=kind, limit=limit)
        if kind == "albums":
            out = []
            for it in raw:
                if it.get("browseId"):
                    out.append(Album(browse_id=it["browseId"], title=it.get("title", ""),
                                     artist=_artists(it) or str(it.get("artist") or ""),
                                     year=str(it.get("year") or ""),
                                     kind=(it.get("type") or "album").lower()))
            return out
        one = "video" if kind == "videos" else "song"
        return [t for t in (_track(it, one) for it in raw) if t]

    def album_tracks(self, browse_id: str) -> list[Track]:
        alb = self._api().get_album(browse_id)
        name = alb.get("title", "")
        return [t for t in (_track(it, "song", name) for it in alb.get("tracks") or []) if t]

    def playlist_tracks(self, playlist_id: str) -> list[Track]:
        if playlist_id.startswith("OLAK5uy_"):  # an album's playlist id: ask for the album
            browse = self._api().get_album_browse_id(playlist_id)
            if browse:
                return self.album_tracks(browse)
        pl = self._api().get_playlist(playlist_id, limit=500)
        return [t for t in (_track(it) for it in pl.get("tracks") or []) if t]

    def video_track(self, video_id: str) -> list[Track]:
        song = self._api().get_song(video_id)
        d = song.get("videoDetails") or {}
        if not d.get("videoId"):
            return []
        dur = int(d["lengthSeconds"]) if str(d.get("lengthSeconds", "")).isdigit() else None
        return [Track(video_id=d["videoId"], title=d.get("title", video_id),
                      artist=d.get("author", ""), duration=dur, kind="song")]

    def from_link(self, kind: str, ident: str) -> list[Track]:
        if kind == "album":
            return self.album_tracks(ident)
        if kind == "playlist":
            return self.playlist_tracks(ident)
        return self.video_track(ident)


def find_deno() -> str | None:
    """yt-dlp needs a JavaScript runtime to unlock YouTube's audio formats."""
    names = ["deno.exe", "deno"] if sys.platform == "win32" else ["deno"]
    roots = []
    if getattr(sys, "frozen", False):
        roots += [os.path.join(getattr(sys, "_MEIPASS", ""), "deno"), os.path.dirname(sys.executable)]
    for root in roots:
        for n in names:
            p = os.path.join(root, n)
            if os.path.isfile(p):
                return p
    try:
        import deno
        p = deno.find_deno_bin()
        if p and os.path.isfile(p):
            return p
    except Exception:  # package missing or binary not installed for this platform
        pass
    return shutil.which("deno")


def find_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # package missing: fall back to one on PATH
        return shutil.which("ffmpeg")


BOT_CHECK = re.compile(r"confirm you.?re not a bot|sign in to confirm", re.I)


class ResolveError(RuntimeError):
    @property
    def bot_check(self) -> bool:
        """YouTube wants a signed-in session from this connection (datacenter IPs, VPNs, heavy use)."""
        return bool(BOT_CHECK.search(str(self)))


def _clean_error(msg: str) -> str:
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(msg))
    msg = re.sub(r"^ERROR:\s*(\[[^\]]+\]\s*)?([A-Za-z0-9_-]{11}:\s*)?", "", msg)
    return msg.split("\n")[0].strip()


class _Log:
    """yt-dlp talks to stderr by default; a windowed .exe has none. Keep its messages here."""

    def __init__(self):
        self.last_error = ""

    def debug(self, msg):
        pass

    info = warning = debug

    def error(self, msg):
        self.last_error = _clean_error(msg)


class Download:
    """One song being written into the cache by yt-dlp. Readable while it grows.

    The engine plays it through `chunks()` as the bytes land, so a song starts within
    a second of the first bytes instead of after the whole file.
    """

    def __init__(self, video_id: str):
        self.video_id = video_id
        self.path: str | None = None
        self.info: dict | None = None
        self.bytes = 0
        self.total: int | None = None
        self.error: str | None = None
        self.started = threading.Event()    # the file exists and the format is known
        self.finished = threading.Event()   # yt-dlp returned (check `error`)

    def done(self) -> bool:
        return self.finished.is_set() and self.error is None

    def chunks(self, stop: threading.Event, size: int = 65536):
        """The file's bytes in order, waiting for more until the download ends (or `stop`)."""
        while not self.started.wait(0.1):
            if stop.is_set() or self.finished.is_set():
                return
        with open(self.path, "rb") as fh:
            while not stop.is_set():
                data = fh.read(size)
                if data:
                    yield data
                    continue
                if self.finished.is_set():
                    rest = fh.read()
                    if rest:
                        yield rest
                    return  # complete - or failed, which the player sees as a song cut short
                time.sleep(0.05)


class AudioFetcher:
    """videoId -> the song's audio in a local cache, fetched by yt-dlp itself.

    yt-dlp does the downloading - with its own headers, chunked requests, retries,
    cookies and your Windows proxy settings - so whatever lets it find the song also
    lets it fetch the song. ffmpeg then only ever reads a local file. Finished songs stay
    in the cache (least recently played are pruned past `cache_mb`), so replays are instant.
    """

    def __init__(self, cache_dir: str, cookies: str | None = None, cache_mb: int = 1024, url_for=None):
        self.cache_dir = cache_dir
        self.cookies = cookies      # None | "browser:<name>" | path to a cookies.txt
        self.cache_mb = cache_mb
        self.url_for = url_for or (lambda vid: f"https://www.youtube.com/watch?v={vid}")
        os.makedirs(cache_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._active: dict[str, Download] = {}
        self._index_path = os.path.join(cache_dir, "index.json")
        try:
            with open(self._index_path, encoding="utf-8") as fh:
                self._index: dict = json.load(fh)
        except (OSError, ValueError):
            self._index = {}

    def set_cookies(self, cookies: str | None) -> None:
        self.cookies = cookies      # used by every download started from now on

    # ---- the cache ---------------------------------------------------------------------------
    def _cached(self, video_id: str) -> Stream | None:
        ent = self._index.get(video_id)
        if not ent:
            return None
        path = os.path.join(self.cache_dir, ent["file"])
        if not os.path.isfile(path) or os.path.getsize(path) != ent.get("size"):
            self._index.pop(video_id, None)
            return None
        ent["used"] = time.time()
        return Stream(path=path, duration=ent.get("duration"), abr=ent.get("abr"), asr=ent.get("asr"),
                      channels=ent.get("channels"), codec=ent.get("codec", ""))

    def _save_index(self) -> None:
        tmp = self._index_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._index, fh)
            os.replace(tmp, self._index_path)
        except OSError:
            pass

    def _prune(self) -> None:
        total = sum(e.get("size", 0) for e in self._index.values())
        active = {d.path for d in self._active.values()}
        for vid, ent in sorted(self._index.items(), key=lambda kv: kv[1].get("used", 0)):
            if total <= self.cache_mb * 1024 * 1024:
                break
            path = os.path.join(self.cache_dir, ent["file"])
            if path in active:
                continue
            try:
                os.remove(path)
            except OSError:
                continue
            total -= ent.get("size", 0)
            del self._index[vid]

    def forget(self, video_id: str) -> None:
        with self._lock:
            ent = self._index.pop(video_id, None)
            if ent:
                try:
                    os.remove(os.path.join(self.cache_dir, ent["file"]))
                except OSError:
                    pass
                self._save_index()

    # ---- fetching ----------------------------------------------------------------------------
    def fetch(self, video_id: str, force: bool = False) -> Stream:
        """Returns as soon as the audio starts arriving (or at once, if it is cached)."""
        if force:
            self.forget(video_id)
        with self._lock:
            hit = None if force else self._cached(video_id)
            if hit is not None:
                return hit
            dl = self._active.get(video_id)
            if dl is None or dl.finished.is_set():
                dl = Download(video_id)
                self._active[video_id] = dl
                threading.Thread(target=self._run, args=(dl,), daemon=True,
                                 name=f"t-amp-fetch-{video_id}").start()
        while not dl.started.wait(0.1):
            if dl.finished.is_set():
                break
        if dl.error:
            raise ResolveError(dl.error)
        if not dl.path:
            raise ResolveError("yt-dlp finished without writing the audio")
        info = dl.info or {}
        return Stream(path=dl.path, duration=info.get("duration"), abr=info.get("abr") or info.get("tbr"),
                      asr=info.get("asr"), channels=info.get("audio_channels"), codec=info.get("acodec") or "",
                      pending=None if dl.done() else dl)

    def _opts(self, dl: Download) -> dict:
        def hook(d):
            path = d.get("filename") or d.get("tmpfilename")
            if path:
                dl.path = path
            if d.get("info_dict"):
                dl.info = d["info_dict"]
            dl.bytes = d.get("downloaded_bytes") or dl.bytes
            dl.total = d.get("total_bytes") or d.get("total_bytes_estimate") or dl.total
            if dl.path and os.path.exists(dl.path):
                dl.started.set()
        opts = {
            "format": "bestaudio/best",
            "outtmpl": {"default": os.path.join(self.cache_dir, "%(id)s.%(ext)s")},
            "nopart": True,             # write in place, so the song can play while it arrives
            "fixup": "never",           # no rewrite-and-replace of a file the player is reading
            "continuedl": True,
            "retries": 10,
            "fragment_retries": 10,
            "socket_timeout": 20,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [hook],
            "cachedir": os.path.join(self.cache_dir, "yt-dlp"),
            "logger": _Log(),
        }
        deno = find_deno()
        if deno:
            opts["js_runtimes"] = {"deno": {"path": deno}}
        if self.cookies and self.cookies.startswith("browser:"):
            opts["cookiesfrombrowser"] = (self.cookies[len("browser:"):],)
        elif self.cookies:
            opts["cookiefile"] = self.cookies
        return opts

    def _run(self, dl: Download) -> None:
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL(self._opts(dl)) as ydl:
                info = ydl.extract_info(self.url_for(dl.video_id), download=True)
            done = (info.get("requested_downloads") or [{}])[0]
            path = done.get("filepath") or dl.path
            if not path or not os.path.isfile(path):
                raise RuntimeError("yt-dlp reported success but wrote no file")
            fmt = done if done.get("acodec") else info
            dl.info, dl.path = {**info, **{k: fmt.get(k) for k in ("abr", "tbr", "asr", "audio_channels",
                                                                   "acodec") if fmt.get(k)}}, path
            with self._lock:
                self._index[dl.video_id] = {
                    "file": os.path.basename(path), "size": os.path.getsize(path), "used": time.time(),
                    "duration": info.get("duration"), "abr": dl.info.get("abr") or dl.info.get("tbr"),
                    "asr": dl.info.get("asr"), "channels": dl.info.get("audio_channels"),
                    "codec": dl.info.get("acodec") or ""}
                self._prune()
                self._save_index()
        except Exception as exc:  # DownloadError and friends carry yt-dlp's own reason
            dl.error = _clean_error(exc) or type(exc).__name__
        finally:
            if dl.path and os.path.exists(dl.path):
                dl.started.set()
            dl.finished.set()
            with self._lock:
                if self._active.get(dl.video_id) is dl:
                    del self._active[dl.video_id]
