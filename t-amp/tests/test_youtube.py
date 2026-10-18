"""YouTube-side parsing, offline: links, result shapes (as ytmusicapi documents them), the updater."""
import hashlib
import io
import json
import os
import sys
import urllib.request
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tamp import updater  # noqa: E402
from tamp.youtube import Album, MusicSearch, NotMusicLink, _clean_error, _track, fmt_time, parse_link  # noqa: E402,E501

# Shapes copied from ytmusicapi's own search() docstring.
SONG = {"category": "Songs", "resultType": "song", "videoId": "ZrOKjDZOtkA", "title": "Wonderwall",
        "artists": [{"name": "Oasis", "id": "UCmMUZbaYdNH0bEd1PAlAqsA"}],
        "album": {"name": "(What's The Story) Morning Glory? (Remastered)", "id": "MPREb_9nqEki4ZDpp"},
        "duration": "4:19", "duration_seconds": 259, "isAvailable": True, "isExplicit": False}
VIDEO = {"category": "Videos", "resultType": "video", "videoId": "bx1Bh8ZvH84", "title": "Wonderwall",
         "artists": [{"name": "Oasis", "id": "UCmMUZbaYdNH0bEd1PAlAqsA"}], "views": "386M",
         "duration": "4:38", "duration_seconds": 278, "isAvailable": True}
ALBUM_DOC = {"category": "Albums", "resultType": "album", "browseId": "MPREb_IInSY5QXXrW",
             "playlistId": "OLAK5uy_kunInnOpcKECWIBQGB0Qj6ZjquxDvfckg",
             "title": "(What's The Story) Morning Glory?", "type": "Album", "artist": "Oasis", "year": "1995"}
ALBUM_NEW = dict(ALBUM_DOC, artists=[{"name": "Oasis", "id": "x"}])
del ALBUM_NEW["artist"]


class FakeYT:
    def __init__(self, rows):
        self.rows = rows

    def search(self, q, filter=None, limit=30):
        return self.rows


def test_song_and_video_parse():
    t = _track(SONG)
    assert (t.video_id, t.title, t.artist, t.duration) == ("ZrOKjDZOtkA", "Wonderwall", "Oasis", 259)
    assert t.album.startswith("(What's The Story)")
    v = _track(VIDEO, "video")
    assert v.kind == "video" and v.duration == 278


def test_duration_from_text_when_seconds_missing():
    row = dict(SONG)
    del row["duration_seconds"]
    assert _track(row).duration == 259
    row["duration"] = "1:02:03"
    assert _track(row).duration == 3723


def test_greyed_out_and_idless_rows_are_dropped():
    assert _track(dict(SONG, isAvailable=False)) is None
    assert _track(dict(SONG, videoId=None)) is None


@pytest.mark.parametrize("row", [ALBUM_DOC, ALBUM_NEW])
def test_album_artist_in_either_shape(row):
    ms = MusicSearch()
    ms._yt = FakeYT([row])
    [alb] = ms.search("oasis", "albums")
    assert isinstance(alb, Album)
    assert (alb.browse_id, alb.artist, alb.year, alb.kind) == ("MPREb_IInSY5QXXrW", "Oasis", "1995", "album")


@pytest.mark.parametrize("text,expect", [
    ("https://music.youtube.com/watch?v=ZrOKjDZOtkA&si=abc", ("video", "ZrOKjDZOtkA")),
    ("music.youtube.com/watch?v=ZrOKjDZOtkA&list=RDAMVM", ("video", "ZrOKjDZOtkA")),
    ("https://music.youtube.com/playlist?list=OLAK5uy_kunInnOpcKECWIBQGB0Qj6ZjquxDvfckg",
     ("playlist", "OLAK5uy_kunInnOpcKECWIBQGB0Qj6ZjquxDvfckg")),
    ("https://music.youtube.com/browse/MPREb_IInSY5QXXrW", ("album", "MPREb_IInSY5QXXrW")),
    # plain YouTube can point at any video at all: not accepted
    ("https://www.youtube.com/watch?v=ZrOKjDZOtkA", None),
    ("https://youtu.be/ZrOKjDZOtkA?t=30", None),
    ("youtube.com/shorts/ZrOKjDZOtkA", None),
    ("wonderwall oasis", None),
    ("beautifully", None),
    ("https://example.com/watch?v=ZrOKjDZOtkA", None),
])
def test_parse_link(text, expect):
    assert parse_link(text) == expect


def test_fmt_time_and_error_cleaning():
    assert fmt_time(59) == "0:59" and fmt_time(3723) == "1:02:03" and fmt_time(None) == ""
    raw = "\x1b[0;31mERROR:\x1b[0m [youtube] ZrOKjDZOtkA: Sign in to confirm you're not a bot\nmore"
    assert _clean_error(raw) == "Sign in to confirm you're not a bot"


def _wheel(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_wheel_install_replaces_old_copy(tmp_path):
    updater._install_wheel(_wheel({"pkg/__init__.py": "v = 1", "pkg/old.py": "",
                                   "pkg-1.0.dist-info/METADATA": ""}), str(tmp_path))
    updater._install_wheel(_wheel({"pkg/__init__.py": "v = 2", "pkg-2.0.dist-info/METADATA": ""}), str(tmp_path))
    assert (tmp_path / "pkg" / "__init__.py").read_text() == "v = 2"
    assert not (tmp_path / "pkg" / "old.py").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pkg", "pkg-2.0.dist-info"]


def test_wheel_install_refuses_path_traversal(tmp_path):
    with pytest.raises(RuntimeError, match="unsafe"):
        updater._install_wheel(_wheel({"../evil.py": "x"}), str(tmp_path / "lib"))
    assert not (tmp_path / "evil.py").exists()


def _pypi_reachable() -> bool:
    try:
        urllib.request.urlopen("https://pypi.org/pypi/yt-dlp-ejs/json", timeout=10).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _pypi_reachable(), reason="PyPI not reachable")
def test_update_fetches_verifies_and_activates(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "pylib_dir", lambda: str(tmp_path))
    monkeypatch.setattr(updater, "PACKAGES", ("yt-dlp-ejs",))
    monkeypatch.setattr(updater, "_bundled", lambda pkg: "0")
    changed = updater.update()
    assert changed and changed[0].startswith("yt-dlp-ejs 0 -> ")
    man = json.loads((tmp_path / "versions.json").read_text())
    assert man["yt-dlp-ejs"]["version"] == changed[0].split(" -> ")[1]
    assert "yt_dlp_ejs" in man["yt-dlp-ejs"]["paths"]
    assert (tmp_path / "yt_dlp_ejs").is_dir()
    assert updater.update() == []  # second run: already current
    info = json.load(urllib.request.urlopen("https://pypi.org/pypi/yt-dlp-ejs/json", timeout=10))
    whl = next(f for f in info["urls"] if f["filename"].endswith("-py3-none-any.whl"))
    assert len(whl["digests"]["sha256"]) == len(hashlib.sha256().hexdigest())


def test_bot_check_is_recognised():
    from tamp.youtube import ResolveError
    assert ResolveError("Sign in to confirm you’re not a bot. Use --cookies-from-browser").bot_check
    assert ResolveError("Sign in to confirm you're not a bot").bot_check
    assert not ResolveError("Video unavailable").bot_check


def test_cookies_reach_yt_dlp(tmp_path):
    from tamp.youtube import AudioFetcher, Download
    f = AudioFetcher(str(tmp_path / "cache"), cookies="browser:firefox")
    assert f._opts(Download("x"))["cookiesfrombrowser"] == ("firefox",)
    jar = tmp_path / "cookies.txt"
    jar.write_text("# Netscape HTTP Cookie File\n")
    f.set_cookies(str(jar))
    opts = f._opts(Download("x"))
    assert opts["cookiefile"] == str(jar) and "cookiesfrombrowser" not in opts
    f.set_cookies(None)
    assert "cookiefile" not in f._opts(Download("x"))
    assert f._opts(Download("x"))["nopart"] is True, "the file must be written in place to play while arriving"


def test_plain_youtube_links_are_refused_not_searched():
    ms = MusicSearch()
    ms._yt = FakeYT([SONG])
    with pytest.raises(NotMusicLink, match="music.youtube.com"):
        ms.search("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_activate_uses_any_newer_package_and_prunes_stale_ones(tmp_path, monkeypatch):
    """A newer ytmusicapi alone must be loaded; a copy the shipped build has caught up with is removed."""
    monkeypatch.setattr(updater, "pylib_dir", lambda: str(tmp_path))
    bundled = {"yt-dlp": "2026.8.19", "ytmusicapi": "1.12.3", "yt-dlp-ejs": "0.8.0"}
    monkeypatch.setattr(updater, "_bundled", lambda pkg: bundled[pkg])
    (tmp_path / "ytmusicapi").mkdir()
    (tmp_path / "yt_dlp").mkdir()
    (tmp_path / "versions.json").write_text(json.dumps({
        "ytmusicapi": {"version": "1.13.0", "paths": ["ytmusicapi"]},     # newer: keep
        "yt-dlp": {"version": "2026.1.1", "paths": ["yt_dlp"]},           # older than shipped: prune
    }))
    monkeypatch.setattr(sys, "path", list(sys.path))
    updater.activate()
    assert sys.path[0] == str(tmp_path)
    assert (tmp_path / "ytmusicapi").is_dir() and not (tmp_path / "yt_dlp").exists()
    assert list(json.loads((tmp_path / "versions.json").read_text())) == ["ytmusicapi"]


# ---- the fetcher, end to end: real yt-dlp downloading from a local, deliberately slow server ----------
import http.server  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402


@pytest.fixture(scope="module")
def slow_server(tmp_path_factory):
    from tamp.youtube import find_ffmpeg
    root = tmp_path_factory.mktemp("srv")
    song = root / "abcdefghijk.webm"
    subprocess.run([find_ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=330:sample_rate=48000:duration=8", "-c:a", "libopus", "-b:a", "96k",
                    str(song)], check=True)
    data = song.read_bytes()

    class Slow(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-Type", "audio/webm")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()

        def do_GET(self):
            start = 0
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):
                start = int(rng[6:].split("-")[0] or 0)
            body = data[start:]
            self.send_response(206 if start else 200)
            self.send_header("Content-Type", "audio/webm")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            step = max(1, len(body) // 20)
            for i in range(0, len(body), step):   # ~1.5 s for the whole song
                self.wfile.write(body[i:i + step])
                self.wfile.flush()
                time.sleep(0.075)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", data
    srv.shutdown()


def test_fetcher_streams_while_downloading_then_serves_from_cache(slow_server, tmp_path):
    from tamp.youtube import AudioFetcher
    base, data = slow_server
    f = AudioFetcher(str(tmp_path / "cache"), url_for=lambda vid: f"{base}/{vid}.webm")
    t0 = time.monotonic()
    st = f.fetch("abcdefghijk")
    assert st.pending is not None and not st.pending.finished.is_set(), "returned before the download ended"
    stop = threading.Event()
    got = b"".join(st.pending.chunks(stop))          # follows the file as it grows, ends at the true end
    assert st.pending.error is None, st.pending.error
    assert got == data, "the bytes read while downloading are the whole song"
    assert time.monotonic() - t0 > 1.0
    again = f.fetch("abcdefghijk")
    assert again.pending is None and again.path == st.path, "second play comes from the cache"
    refetched = f.fetch("abcdefghijk", force=True)
    assert refetched.pending is not None
    refetched.pending.finished.wait(30)
    assert open(refetched.path, "rb").read() == data


def test_fetcher_reports_yt_dlp_errors(tmp_path):
    from tamp.youtube import AudioFetcher, ResolveError
    f = AudioFetcher(str(tmp_path / "cache"), url_for=lambda vid: "http://127.0.0.1:9/nothing-here.webm")
    with pytest.raises(ResolveError):
        f.fetch("zzzzzzzzzzz")
