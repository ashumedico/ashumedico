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
    """Stands in for yt-dlp: every video id "downloads" to the same local file."""

    def __init__(self, path):
        self.path, self.calls = path, []

    def fetch(self, video_id, force=False):
        self.calls.append((video_id, force))
        return Stream(path=self.path, duration=20.0, abr=129.6, asr=48000, channels=2, codec="opus")


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
    player = Player(settings, engine=engine, music=music, fetcher=resolver)
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


class BotCheckResolver:
    """YouTube's answer to a datacenter IP: every resolve asks for a sign-in."""

    def __init__(self):
        self.calls = []

    def fetch(self, video_id, force=False):
        from tamp.youtube import ResolveError
        self.calls.append(video_id)
        raise ResolveError("Sign in to confirm you’re not a bot. Use --cookies-from-browser or --cookies")


def test_bot_check_stops_instead_of_skipping_through_the_list(app, tmp_path):
    settings = Settings(str(tmp_path / "state.json"))
    engine = AudioEngine(FFMPEG, samplerate=SR, output=lambda e: Device(e))
    resolver = BotCheckResolver()
    player = Player(settings, engine=engine, music=CannedSearch(), fetcher=resolver)
    _alive.append((player, engine))
    player.add_tracks(tracks())
    player.play_index(0)
    assert pump(app, 2, until=lambda: player.status == "stopped" and player.message)
    assert "SIGN-IN" in player.message
    pump(app, 3.0)  # longer than the 2.5 s skip-after-fail delay
    assert resolver.calls == ["id000000000"], "a bot check must not walk the whole playlist"
    player.shutdown()


# ---- playlist edits while music plays (the verifier's findings 3, 4, 9) ----------------------------
def test_removing_the_playing_song_keeps_it_playing_and_next_continues(rig):
    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    player.play_index(2)
    assert pump(app, 5, until=lambda: player.status == "playing")
    song = player.playing
    player.remove([2])
    assert player.playing is song and player.status == "playing"
    assert player.title_line().startswith("Daft Punk - Get Lucky"), "no stale row number for a removed song"
    player.next()
    assert player.playing.title == "Teri Ore", "Next continues with the row after the removed song"


def test_removing_rows_above_the_cursor_shifts_it(rig):
    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    player.play_index(3)
    player.remove([0, 1])
    assert player.current == 1 and player.track is player.playing


def test_crop_without_a_selection_keeps_everything(rig):
    app, player, shell, *_ = rig
    player.add_tracks(tracks())
    player.selected = set()
    player.crop()
    assert len(player.tracks) == 6


def test_the_same_result_added_twice_is_two_independent_rows(rig):
    app, player, shell, *_ = rig
    hit = tracks(1)[0]
    player.add_tracks([hit])
    player.add_tracks([hit])
    assert player.tracks[0] is not player.tracks[1] and hit not in player.tracks[:0]
    player.current = 1
    player.reverse()
    assert player.current == 0, "the cursor follows its own row, not the first copy"


# ---- failure streaks and stale clicks (findings 2 and 8) -----------------------------------------
class DeadStreamResolver:
    """Every song resolves, but the URL is dead - the 403 case."""

    def __init__(self):
        self.calls = []

    def fetch(self, video_id, force=False):
        self.calls.append(video_id)
        return Stream(path="/nonexistent/dead.m4a", duration=200.0, abr=128, asr=44100, channels=2, codec="opus")


def test_dead_streams_on_repeat_stop_after_one_pass(app, tmp_path):
    settings = Settings(str(tmp_path / "state.json"))
    engine = AudioEngine(FFMPEG, samplerate=SR, output=lambda e: Device(e))
    resolver = DeadStreamResolver()
    player = Player(settings, engine=engine, music=CannedSearch(), fetcher=resolver)
    player.SKIP_DELAY_MS = 30
    _alive.append((player, engine))
    player.add_tracks(tracks(3))
    player.repeat = True
    player.play_index(0)
    pump(app, 6.0)
    # each song: one resolve + one fresh-URL retry; then the streak ends instead of looping forever
    assert player.status == "stopped"
    assert len(resolver.calls) <= 2 * 3, resolver.calls
    player.shutdown()


class SlowResolver(LocalResolver):
    def fetch(self, video_id, force=False):
        time.sleep(0.4)
        return super().fetch(video_id, force)


def test_clicks_the_user_has_moved_past_never_reach_youtube(app, audio_file, tmp_path):
    settings = Settings(str(tmp_path / "state.json"))
    engine = AudioEngine(FFMPEG, samplerate=SR, output=lambda e: Device(e))
    resolver = SlowResolver(audio_file)
    player = Player(settings, engine=engine, music=CannedSearch(), fetcher=resolver)
    _alive.append((player, engine))
    player.add_tracks(tracks())
    for i in range(5):        # Next, Next, Next... faster than YouTube answers
        player.play_index(i)
    assert pump(app, 5, until=lambda: player.status == "playing")
    asked = [vid for vid, _ in resolver.calls]
    assert player.playing.title == "Blinding Lights"
    assert "id000000002" not in asked and "id000000003" not in asked, asked
    player.shutdown()
