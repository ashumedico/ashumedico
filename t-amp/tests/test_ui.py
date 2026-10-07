"""The whole app, driven offscreen: clicks, keys, search flow, and screenshots to look at.

YouTube is replaced by a local audio file (the network is the one thing a test can't own),
but everything after the URL is real: ffmpeg decodes it, the EQ filters it, the
visualiser analyses it. Screenshots land in $T_AMP_SHOTS (default: a temp folder).
"""
import os
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tamp.app import Shell  # noqa: E402
from tamp.engine import AudioEngine  # noqa: E402
from tamp.player import Player  # noqa: E402
from tamp.settings import Settings  # noqa: E402
from tamp.youtube import Album, Stream, Track, find_ffmpeg  # noqa: E402

SR = 48000
FFMPEG = find_ffmpeg()
SHOTS = os.environ.get("T_AMP_SHOTS") or tempfile.mkdtemp(prefix="t-amp-shots-")
os.makedirs(SHOTS, exist_ok=True)
_alive = []


class Device:
    latency = 0.0
    closed = False

    def __init__(self, engine):
        self.engine, self.active = engine, True
        self._stop = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self._stop.is_set():
            buf = np.zeros((1024, 2), np.float32)
            self.engine._callback(buf, 1024, None, None)
            time.sleep(1024 / SR)

    def close(self):
        self._stop.set()
        self.active = False


class LocalResolver:
    """Stands in for yt-dlp: every video id resolves to the same local file."""

    def __init__(self, path):
        self.path, self.calls = path, []

    def resolve(self, video_id, force=False):
        self.calls.append((video_id, force))
        return Stream(url=self.path, headers={}, duration=20.0, abr=129.6, asr=48000, channels=2,
                      codec="opus", expires=time.time() + 3600)


class CannedSearch:
    """Stands in for ytmusicapi with a fixed catalogue; records what was asked."""

    def __init__(self):
        self.queries = []

    def search(self, query, kind="songs", limit=30):
        self.queries.append((query, kind))
        if kind == "albums":
            return [Album(browse_id="MPREb_test", title="Test Album", artist="Test Artist", year="2022")]
        return [Track(video_id=f"vid{i:08d}"[:11], title=f"{query.title()} Song {i}", artist="Test Artist",
                      album="Test Album", duration=180 + i) for i in range(12)]

    def album_tracks(self, browse_id):
        return [Track(video_id=f"alb{i:08d}"[:11], title=f"Album Track {i}", artist="Test Artist",
                      album="Test Album", duration=200) for i in range(5)]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def audio_file():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "music.wav")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.25:sample_rate=48000:duration=20",
                    "-f", "lavfi", "-i", "sine=frequency=80:sample_rate=48000:duration=20",
                    "-filter_complex", "[0][1]amix=inputs=2:weights=1 0.6,volume=2", "-ac", "2", p], check=True)
    return p


@pytest.fixture()
def rig(app, audio_file, tmp_path):
    settings = Settings(str(tmp_path / "state.json"))
    settings["scale"] = 2
    engine = AudioEngine(FFMPEG, samplerate=SR, output=lambda e: Device(e))
    resolver = LocalResolver(audio_file)
    music = CannedSearch()
    player = Player(settings, engine=engine, music=music, resolver=resolver)
    shell = Shell(player)
    shell.show()
    app.processEvents()
    yield app, player, shell, resolver, music
    shell.close()
    app.processEvents()
    _alive.append((shell, player, engine))  # never let the GC free Qt objects from another thread


def pump(app, seconds=0.2, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.01)
    return until() if until else True


def click(widget, x, y, scale=2, button=Qt.LeftButton, double=False):
    pos = QPointF(x * scale + scale / 2, y * scale + scale / 2)
    gpos = QPointF(widget.mapToGlobal(QPoint(int(pos.x()), int(pos.y()))))
    press = QMouseEvent(QMouseEvent.MouseButtonPress, pos, gpos, button, button, Qt.NoModifier)
    release = QMouseEvent(QMouseEvent.MouseButtonRelease, pos, gpos, button, Qt.NoButton, Qt.NoModifier)
    widget.mousePressEvent(press)
    widget.mouseReleaseEvent(release)
    if double:
        dbl = QMouseEvent(QMouseEvent.MouseButtonDblClick, pos, gpos, button, button, Qt.NoModifier)
        widget.mouseDoubleClickEvent(dbl)
        widget.mouseReleaseEvent(release)


def shot(widget, name):
    path = os.path.join(SHOTS, name)
    widget.grab().save(path)
    return path


def tracks(n=6):
    names = [("Arijit Singh", "Kesariya"), ("A.R. Rahman", "Kun Faya Kun"), ("Daft Punk", "Get Lucky"),
             ("Shreya Ghoshal", "Teri Ore"), ("The Weeknd", "Blinding Lights"), ("Lata Mangeshkar", "लग जा गले")]
    return [Track(video_id=f"id{i:09d}", title=t, artist=a, duration=200 + 17 * i) for i, (a, t) in
            enumerate(names[:n])]


def test_empty_state_renders(rig):
    app, player, shell, *_ = rig
    pump(app, 0.1)
    assert shell.width() == 275 * 2
    shot(shell, "01-empty.png")


def test_play_from_playlist_runs_real_audio_and_vis(rig):
    app, player, shell, resolver, _ = rig
    player.add_tracks(tracks())
    shell.pl.ensure_visible(0)
    # double-click row 3 in the playlist
    click(shell.pl, 40, 20 + 2 * 13 + 5, double=True)
    assert pump(app, 5, until=lambda: player.status == "playing" and player.position > 1.5)
    assert resolver.calls[0] == ("id000000002", False)
    assert ("id000000003", False) in resolver.calls, "next track should be prefetched"
    assert player.current == 2
    assert player.vis.bars.max() > 0.3, "visualiser should be moving on real audio"
    shell.toggle_panel("eq")
    player.load_preset("Rock")
    pump(app, 0.6)
    shot(shell, "02-playing-eq-playlist.png")
    shell.toggle_panel("eq")


def test_transport_buttons_and_time(rig):
    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    click(shell.main, 50, 96)                       # play
    assert pump(app, 5, until=lambda: player.position > 1.0)
    click(shell.main, 70, 96)                       # pause
    assert player.status == "paused"
    p = player.position
    pump(app, 0.4)
    assert abs(player.position - p) < 0.05
    click(shell.main, 70, 96)                       # pause again = resume
    assert player.status == "playing"
    click(shell.main, 118, 96)                      # next
    assert player.current == 1
    click(shell.main, 26, 96)                       # prev
    assert player.current == 0
    click(shell.main, 95, 96)                       # stop
    assert player.status == "stopped"
    assert player.position == 0.0


def test_sliders_volume_balance_seek(rig):
    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    player.play_index(0)
    assert pump(app, 5, until=lambda: player.status == "playing" and player.engine.state == "playing")
    click(shell.main, 107 + 2, 63)                  # far left of volume
    assert player.settings["volume"] == 0
    click(shell.main, 107 + 66, 63)                 # far right
    assert player.settings["volume"] == 100
    click(shell.main, 177 + 19, 63)                 # balance centre detent
    assert player.settings["balance"] == 0
    click(shell.main, 16 + 124, 76)                 # seek to ~half of 20 s
    assert pump(app, 3, until=lambda: 8.0 < player.position < 13.0), player.position


def test_shade_mode_and_scale(rig):
    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    player.play_index(1)
    pump(app, 1.5, until=lambda: player.position > 0.8)
    shell.toggle_shade()
    pump(app, 0.2)
    assert shell.main.height() == 14 * 2
    shot(shell.main, "03-shade.png")
    shell.toggle_shade()
    shell.set_scale(1)
    pump(app, 0.1)
    assert shell.main.width() == 275
    shot(shell, "04-scale-1x.png")
    shell.set_scale(2)


def test_live_search_debounces_and_plays(rig):
    app, player, shell, resolver, music = rig
    shell.open_search()
    box = shell.search.box
    for ch in "kesar":           # typed fast: one search, not five
        box.setText(box.text() + ch)
        pump(app, 0.03)
    assert pump(app, 2, until=lambda: len(shell.search.results.items) == 12)
    assert music.queries == [("kesar", "songs")]
    shot(shell.search, "05-search.png")
    shell.search.results.move_sel(2)
    shell.search.take(play=True)
    assert pump(app, 5, until=lambda: player.status == "playing")
    assert player.track.title == "Kesar Song 2"
    # albums expand into their tracks
    shell.search.set_kind("albums")
    assert pump(app, 2, until=lambda: shell.search.results.items and
                isinstance(shell.search.results.items[0], Album))
    n = len(player.tracks)
    shell.search.take(play=False)
    assert pump(app, 2, until=lambda: len(player.tracks) == n + 5)


def test_unicode_title_uses_truetype(rig):
    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    player.play_index(5)                       # Devanagari title
    assert pump(app, 5, until=lambda: player.position > 0.5)
    shot(shell, "06-devanagari.png")


def test_playlist_keyboard_and_reorder(rig):
    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    first = player.tracks[0]
    player.selected = {0}
    player.move([0], 3)
    assert player.tracks[3] is first
    player.remove([3])
    assert first not in player.tracks
    assert player.total_seconds()[0] == sum(t.duration for t in player.tracks)


def test_state_persists(rig, tmp_path):
    app, player, shell, *_ = rig
    player.add_tracks(tracks(3))
    player.set_volume(42)
    player.set_eq(on=True, band=0, value=6.0)
    player.save()
    again = Settings(player.settings.path)
    assert again["volume"] == 42 and again["eq_gains"][0] == 6.0
    assert [d["title"] for d in again["playlist"]][:3] == ["Kesariya", "Kun Faya Kun", "Get Lucky"]


def test_full_desk_screenshot(rig):
    """Main + EQ + playlist with the search window docked on the right, as one picture."""
    from PySide6.QtGui import QColor, QImage, QPainter

    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    shell.toggle_panel("eq")
    player.load_preset("Pop")
    player.play_index(0)
    shell.open_search()
    shell.search.box.setText("arijit singh")
    assert pump(app, 5, until=lambda: player.position > 1.2 and len(shell.search.results.items) == 12)
    shell.search.results.move_sel(3)
    pump(app, 0.3)
    left, right = shell.grab().toImage(), shell.search.grab().toImage()
    assert shell.search.pos().x() == shell.x() + shell.width(), "search window should dock flush right"
    img = QImage(left.width() + right.width(), max(left.height(), right.height()), QImage.Format_ARGB32)
    img.fill(QColor("#101018"))
    p = QPainter(img)
    p.drawImage(0, 0, left)
    p.drawImage(left.width(), 0, right)
    p.end()
    img.save(os.path.join(SHOTS, "00-desk.png"))
    shell.toggle_panel("eq")
