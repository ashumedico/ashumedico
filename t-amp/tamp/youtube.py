"""YouTube Music: live search (ytmusicapi) and stream resolution (yt-dlp).

Search goes to the YouTube Music catalogue only (songs, music videos, albums), so the
results are music by construction, not general YouTube. No API key and no login.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import threading
import time
import urllib.parse
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
    url: str
    headers: dict
    duration: float | None
    abr: float | None           # kbps
    asr: int | None             # Hz
    channels: int | None
    codec: str
    expires: float              # epoch seconds


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


def parse_link(text: str) -> tuple[str, str] | None:
    """('video'|'playlist'|'album', id) for a YouTube / YouTube Music link, else None."""
    text = text.strip()
    if not re.match(r"^(https?://)?([a-z0-9-]+\.)*(youtube\.com|youtu\.be)/", text, re.I):
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


class StreamResolver:
    """videoId -> a direct audio URL (plus headers, bitrate, rate). Cached until it expires."""

    def __init__(self, cache_dir: str | None = None, cookies: str | None = None):
        self.cache_dir = cache_dir
        self.cookies = cookies      # None | "browser:<name>" | path to a cookies.txt
        self._ydl = None
        self._cache: dict[str, Stream] = {}
        self._lock = threading.Lock()

    def _make(self):
        from yt_dlp import YoutubeDL
        opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "cachedir": self.cache_dir or False,
            "logger": _Log(),
        }
        deno = find_deno()
        if deno:
            opts["js_runtimes"] = {"deno": {"path": deno}}
        if self.cookies and self.cookies.startswith("browser:"):
            opts["cookiesfrombrowser"] = (self.cookies[len("browser:"):],)
        elif self.cookies:
            opts["cookiefile"] = self.cookies
        return YoutubeDL(opts)

    def set_cookies(self, cookies: str | None) -> None:
        with self._lock:
            self.cookies = cookies
            self._ydl = None        # rebuilt with the new sign-in on the next resolve
            self._cache.clear()

    def resolve(self, video_id: str, force: bool = False) -> Stream:
        with self._lock:  # one YoutubeDL instance, one caller at a time
            hit = self._cache.get(video_id)
            if hit and not force and hit.expires - time.time() > 300:
                return hit
            if self._ydl is None:
                self._ydl = self._make()
            try:
                info = self._ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            except Exception as exc:  # yt-dlp raises DownloadError/ExtractorError with the reason
                raise ResolveError(_clean_error(exc)) from exc
            if info.get("requested_formats"):
                fmt = next((f for f in info["requested_formats"] if f.get("acodec") not in (None, "none")),
                           info["requested_formats"][0])
            else:
                fmt = info
            url = fmt.get("url")
            if not url:
                raise ResolveError("no playable audio format for this track")
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            try:
                expires = float(q.get("expire", [0])[0]) or time.time() + 3600
            except ValueError:
                expires = time.time() + 3600
            stream = Stream(
                url=url,
                headers=dict(fmt.get("http_headers") or info.get("http_headers") or {}),
                duration=info.get("duration"),
                abr=fmt.get("abr") or fmt.get("tbr"),
                asr=fmt.get("asr"),
                channels=fmt.get("audio_channels"),
                codec=fmt.get("acodec") or "",
                expires=expires,
            )
            self._cache[video_id] = stream
            return stream
