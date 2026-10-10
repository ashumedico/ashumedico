"""The window that holds the stack (main / EQ / playlist), its menus, keys and docking."""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback

from PySide6.QtCore import QAbstractNativeEventFilter, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QFileDialog, QMenu, QMessageBox, QVBoxLayout, QWidget)

from . import __version__
from .eq_panel import EqPanel
from .main_panel import MainPanel
from .player import Player
from .playlist_panel import PlaylistPanel
from .search_window import SearchWindow
from .settings import state_dir
from .skin import C
from .youtube import Track, fmt_time, parse_link

SNAP = 10
WM_HOTKEY = 0x0312
MEDIA_KEYS = {1: 0xB3, 2: 0xB0, 3: 0xB1, 4: 0xB2}   # play/pause, next, prev, stop


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, size >= 32)
        k = size / 16
        p.setBrush(C("#2c2c45"))
        p.setPen(C("#5c5c63"))
        p.drawRoundedRect(QRect(0, 0, size - 1, size - 1), 3 * k, 3 * k)
        bolt = ["....###", "...###.", "..###..", ".######", "...###.", "..###..", ".###...", "###....", "##....."]
        ox, oy = 4.5 * k, 3.5 * k
        for yy, row in enumerate(bolt):
            for xx, ch in enumerate(row):
                if ch == "#":
                    p.fillRect(int(ox + xx * k), int(oy + yy * k), max(1, int(k + 0.5)), max(1, int(k + 0.5)),
                               C("#f0c040") if xx + yy < 8 else C("#c88a18"))
        p.end()
        icon.addPixmap(QPixmap.fromImage(img))
    return icon


class MediaKeys(QAbstractNativeEventFilter):
    """Play/Pause, Next, Previous, Stop keys reach T-Amp even when it isn't focused.

    Registered for the GUI thread rather than a window, so they keep working when Qt
    recreates the native window (always-on-top, scale changes).
    """

    def __init__(self, player: Player):
        super().__init__()
        import ctypes
        self.player = player
        self._user32 = ctypes.windll.user32
        self.ids = [hk for hk, vk in MEDIA_KEYS.items() if self._user32.RegisterHotKey(None, hk, 0x4000, vk)]
        QApplication.instance().installNativeEventFilter(self)

    def stop(self) -> None:
        for hk in self.ids:
            self._user32.UnregisterHotKey(None, hk)
        self.ids = []
        QApplication.instance().removeNativeEventFilter(self)

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            import ctypes.wintypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in self.ids:
                pl = self.player
                {1: (lambda: pl.pause() if pl.status in ("playing", "paused") else pl.play()),
                 2: pl.next, 3: pl.prev, 4: pl.stop}[msg.wParam]()
                return True, 0
        return False, 0


INSTANCE_KEY = "t-amp-single-instance"


def hand_over_to_running() -> bool:
    """If T-Amp is already open, ask it to come forward and return True."""
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


class Shell(QWidget):
    def __init__(self, player: Player):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        self.player = player
        s = player.settings
        self.setWindowTitle("T-Amp")
        self.setWindowIcon(app_icon())
        self.setFocusPolicy(Qt.StrongFocus)
        self.scale = s["scale"] or self._auto_scale()
        self.main = MainPanel(self, player)
        self.eq = EqPanel(self, player)
        self.pl = PlaylistPanel(self, player)
        self.focused_panel = self.main
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.setSizeConstraint(QVBoxLayout.SetFixedSize)
        for panel in (self.main, self.eq, self.pl):
            lay.addWidget(panel)
            panel.set_scale(self.scale)
        self.search = SearchWindow(self, player)
        self._search_docked = True
        self._move_from: tuple[QPoint, QPoint] | None = None
        self.media_keys: MediaKeys | None = None
        self.eq.setVisible(bool(s["show_eq"]))
        self.pl.setVisible(bool(s["show_pl"]))
        if s["always_on_top"]:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        player.changed.connect(self.update_all)
        player.playlist_changed.connect(self._title)
        player.tick.connect(self._on_tick)
        self._ticks = 0
        self.relayout()
        self._restore_position()

    # ---- geometry, scale, panels ---------------------------------------------------------------
    def _auto_scale(self) -> int:
        scr = QGuiApplication.primaryScreen()
        if scr is None:
            return 2
        h = scr.availableGeometry().height()
        return 3 if h >= 1500 else 2 if h >= 720 else 1

    @property
    def show_eq(self) -> bool:
        return self.eq.isVisible() if self.isVisible() else bool(self.player.settings["show_eq"])

    @property
    def show_pl(self) -> bool:
        return self.pl.isVisible() if self.isVisible() else bool(self.player.settings["show_pl"])

    def relayout(self) -> None:
        for panel in (self.main, self.eq, self.pl):
            panel.set_scale(self.scale)
        self.layout().activate()
        self.adjustSize()
        self.update_all()

    def set_scale(self, s: int) -> None:
        self.scale = s
        self.player.settings["scale"] = s
        self.relayout()
        self.search.apply_scale(s)
        if self._search_docked:
            self._dock_search()
        self.player._schedule_save()

    def cycle_scale(self) -> None:
        self.set_scale(1 if self.scale > 1 else 2)

    def toggle_panel(self, which: str) -> None:
        panel = self.eq if which == "eq" else self.pl
        panel.setVisible(not panel.isVisible())
        self.player.settings["show_" + which] = panel.isVisible()
        self.relayout()
        self.player._schedule_save()

    def toggle_shade(self) -> None:
        s = self.player.settings
        s["shade"] = not s["shade"]
        self.main.relayout()
        self.relayout()
        self.player._schedule_save()

    def set_on_top(self, on: bool) -> None:
        self.player.settings["always_on_top"] = on
        pos = self.pos()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.move(pos)
        self.show()
        self.search.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.player._schedule_save()
        self.update_all()

    def focus_panel(self, panel) -> None:
        if self.focused_panel is not panel:
            self.focused_panel = panel
            self.update_all()

    def update_all(self) -> None:
        for panel in (getattr(self, n, None) for n in ("main", "eq", "pl")):
            if panel is not None:
                panel.update()

    def _on_tick(self) -> None:
        if self.isMinimized():
            return
        self.main.update()
        self._ticks += 1
        if self._ticks % 8 == 0 and self.pl.isVisible():
            self.pl.update()

    def _title(self) -> None:
        t = self.player.track
        self.setWindowTitle(f"{self.player.current + 1}. {t.label} - T-Amp" if t else "T-Amp")

    # ---- moving, snapping, docking ---------------------------------------------------------------
    def begin_move(self, gpos: QPoint) -> None:
        self._move_from = (gpos, self.pos())

    def move_to(self, gpos: QPoint) -> None:
        if not self._move_from:
            return
        start, pos = self._move_from
        target = pos + (gpos - start)
        scr = QGuiApplication.screenAt(gpos) or QGuiApplication.primaryScreen()
        if scr is not None:
            a = scr.availableGeometry()
            x, y = target.x(), target.y()
            if abs(x - a.left()) < SNAP:
                x = a.left()
            if abs(x + self.width() - a.right() - 1) < SNAP:
                x = a.right() + 1 - self.width()
            if abs(y - a.top()) < SNAP:
                y = a.top()
            if abs(y + self.height() - a.bottom() - 1) < SNAP:
                y = a.bottom() + 1 - self.height()
            target = QPoint(x, y)
        self.move(target)

    def end_move(self) -> None:
        self._move_from = None
        self.player.settings["pos"] = [self.x(), self.y()]
        self.player._schedule_save()

    def moveEvent(self, e) -> None:
        if self._search_docked and self.search.isVisible():
            self._dock_search()
        super().moveEvent(e)

    def resizeEvent(self, e) -> None:
        if self._search_docked and self.search.isVisible():
            self._dock_search()
        super().resizeEvent(e)

    def _dock_search(self) -> None:
        self.search.move(self.x() + self.width(), self.y())

    def snap_search(self, pos: QPoint, size: QSize) -> QPoint:
        """Search window snaps flush to the player's right or left edge, tops aligned."""
        x, y = pos.x(), pos.y()
        right, left = self.x() + self.width(), self.x() - size.width()
        if abs(x - right) < SNAP and y < self.y() + self.height() and y + size.height() > self.y():
            x = right
            if abs(y - self.y()) < SNAP:
                y = self.y()
        elif abs(x - left) < SNAP and y < self.y() + self.height() and y + size.height() > self.y():
            x = left
            if abs(y - self.y()) < SNAP:
                y = self.y()
        return QPoint(x, y)

    def search_moved(self) -> None:
        sp = self.search.pos()
        self._search_docked = sp == QPoint(self.x() + self.width(), self.y())
        self.player.settings["search_pos"] = None if self._search_docked else [sp.x(), sp.y()]
        self.player._schedule_save()

    def _restore_position(self) -> None:
        s = self.player.settings
        scr = QGuiApplication.primaryScreen()
        avail = scr.availableGeometry() if scr else QRect(0, 0, 1920, 1080)
        pos = s.get("pos")
        if pos and any(sc.availableGeometry().contains(QPoint(pos[0] + 20, pos[1] + 7))
                       for sc in QGuiApplication.screens()):
            self.move(pos[0], pos[1])
        else:
            self.move(avail.x() + max(0, (avail.width() - self.width() - self.search.width()) // 2),
                      avail.y() + max(0, (avail.height() - self.height()) // 3))
        sp = s.get("search_pos")
        if sp:
            self._search_docked = False
            self.search.move(sp[0], sp[1])
        else:
            self._dock_search()

    def open_search(self, text: str | None = None) -> None:
        if self._search_docked:
            self._dock_search()
        self.search.open(text)

    # ---- menus & dialogs -------------------------------------------------------------------------
    def main_menu(self, gpos: QPoint) -> None:
        pl, s = self.player, self.player.settings
        m = QMenu(self)
        m.addAction("Search YouTube Music...\tL", self.open_search)
        m.addSeparator()
        for label, fn, key in (("Previous", pl.prev, "Z"), ("Play", pl.play, "X"), ("Pause", pl.pause, "C"),
                               ("Stop", pl.stop, "V"), ("Next", pl.next, "B")):
            m.addAction(f"{label}\t{key}", fn)
        m.addSeparator()
        a = m.addAction("Shuffle\tS", lambda: pl.toggle("shuffle"))
        a.setCheckable(True)
        a.setChecked(pl.shuffle)
        a = m.addAction("Repeat\tR", lambda: pl.toggle("repeat"))
        a.setCheckable(True)
        a.setChecked(pl.repeat)
        m.addSeparator()
        opts = m.addMenu("Options")
        a = opts.addAction("Always on top\tCtrl+A", lambda: self.set_on_top(not s["always_on_top"]))
        a.setCheckable(True)
        a.setChecked(bool(s["always_on_top"]))
        size = opts.addMenu("Size")
        for k in (1, 2, 3):
            a = size.addAction(f"{k}x" + ("\tCtrl+D" if k == 2 else ""), lambda k=k: self.set_scale(k))
            a.setCheckable(True)
            a.setChecked(self.scale == k)
        a = opts.addAction("Time remaining", self._toggle_time)
        a.setCheckable(True)
        a.setChecked(bool(s["time_remaining"]))
        a = opts.addAction("Windowshade mode\tCtrl+W", self.toggle_shade)
        a.setCheckable(True)
        a.setChecked(bool(s["shade"]))
        a = opts.addAction("Media keys control T-Amp", self._toggle_media_keys)
        a.setCheckable(True)
        a.setChecked(bool(s["media_keys"]))
        signin = opts.addMenu("YouTube sign-in")
        cur = s.get("cookies")
        for label, value in (("Off (default)", None), ("Cookies from Firefox", "browser:firefox"),
                             ("Cookies from Edge", "browser:edge"), ("Cookies from Chrome", "browser:chrome"),
                             ("Cookies from Brave", "browser:brave")):
            a = signin.addAction(label, lambda v=value: pl.set_cookies(v))
            a.setCheckable(True)
            a.setChecked(cur == value)
        a = signin.addAction("cookies.txt file...", self._pick_cookie_file)
        a.setCheckable(True)
        a.setChecked(bool(cur) and not cur.startswith("browser:"))
        vis = m.addMenu("Visualization")
        self._fill_vis_menu(vis)
        m.addSeparator()
        a = m.addAction("Equalizer\tAlt+G", lambda: self.toggle_panel("eq"))
        a.setCheckable(True)
        a.setChecked(self.eq.isVisible())
        a = m.addAction("Playlist editor\tAlt+E", lambda: self.toggle_panel("pl"))
        a.setCheckable(True)
        a.setChecked(self.pl.isVisible())
        m.addSeparator()
        m.addAction("Track info...\tAlt+3", self.track_info)
        m.addAction("Update YouTube engine (yt-dlp)", lambda: self.player.update_engine(manual=True))
        m.addAction("About T-Amp...", self.about)
        m.addSeparator()
        m.addAction("Exit", self.close)
        m.exec(gpos)
        m.deleteLater()
        self.update_all()

    def vis_menu(self, gpos: QPoint) -> None:
        m = QMenu(self)
        self._fill_vis_menu(m)
        m.exec(gpos)
        m.deleteLater()

    def _fill_vis_menu(self, m: QMenu) -> None:
        s = self.player.settings
        for mode, label in (("spectrum", "Spectrum analyzer"), ("scope", "Oscilloscope"), ("off", "Off")):
            a = m.addAction(label, lambda mode=mode: s.__setitem__("vis_mode", mode))
            a.setCheckable(True)
            a.setChecked(s["vis_mode"] == mode)
        m.addSeparator()
        a = m.addAction("Thin bands", lambda: s.__setitem__("vis_thin", not s["vis_thin"]))
        a.setCheckable(True)
        a.setChecked(bool(s["vis_thin"]))
        a = m.addAction("Peaks", lambda: s.__setitem__("vis_peaks", not s["vis_peaks"]))
        a.setCheckable(True)
        a.setChecked(bool(s["vis_peaks"]))

    def _pick_cookie_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "YouTube cookies.txt (Netscape format)", "",
                                              "Cookies (*.txt);;All files (*)")
        if path:
            self.player.set_cookies(path)

    def _toggle_time(self) -> None:
        s = self.player.settings
        s["time_remaining"] = not s["time_remaining"]

    def _toggle_media_keys(self) -> None:
        s = self.player.settings
        s["media_keys"] = not s["media_keys"]
        self._register_media_keys(s["media_keys"])
        self.player._schedule_save()

    def track_info(self, index: int | None = None) -> None:
        pl = self.player
        i = pl.current if index is None else index
        if not 0 <= i < len(pl.tracks):
            return
        t = pl.tracks[i]
        lines = [f"<b>{t.title}</b>", f"Artist: {t.artist or '-'}", f"Album: {t.album or '-'}",
                 f"Length: {fmt_time(t.duration) or 'unknown'}", f"Type: {t.kind}"]
        st = pl.stream if i == pl.current else None
        if st is not None:
            lines.append(f"Stream: {st.codec or '?'} · {round(st.abr or 0)} kbps · "
                         f"{(st.asr or 0) / 1000:g} kHz · {st.channels or 2} ch")
        lines.append(f'<a href="{t.url}">{t.url}</a>')
        box = QMessageBox(self)
        box.setWindowTitle("Track info")
        box.setTextFormat(Qt.RichText)
        box.setText("<br>".join(lines))
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()
        box.deleteLater()

    def about(self) -> None:
        QMessageBox.about(
            self, "About T-Amp",
            f"<b>T-Amp {__version__}</b><br>A classic-style player for YouTube Music.<br><br>"
            "Search: YouTube Music catalogue (ytmusicapi) · Streams: yt-dlp · Decoding: FFmpeg · "
            "Output: PortAudio<br>EQ and visualiser run on the real audio.<br><br>"
            "Inspired by Winamp 2. Not affiliated with Winamp or YouTube.")

    def load_list(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load playlist", "", "Playlists (*.m3u8 *.m3u);;All files (*)")
        if not path:
            return
        tracks, title, dur = [], None, None
        try:
            with open(path, encoding="utf-8-sig") as fh:
                lines = fh.read().splitlines()
        except OSError as exc:
            self.player.flash(f"ERROR: {exc}")
            return
        for line in lines:
            line = line.strip()
            if line.startswith("#EXTINF:"):
                head, _, title = line[8:].partition(",")
                try:
                    dur = int(float(head)) if float(head) > 0 else None
                except ValueError:
                    dur = None
            elif line and not line.startswith("#"):
                link = parse_link(line)
                if link and link[0] == "video":
                    artist, _, name = (title or "").partition(" - ")
                    if not name:
                        artist, name = "", title or link[1]
                    tracks.append(Track(video_id=link[1], title=name, artist=artist, duration=dur))
                title, dur = None, None
        self.player.add_tracks(tracks)
        self.player.flash(f"LOADED {len(tracks)} TRACKS")

    def save_list(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save playlist", "playlist.m3u8", "Playlists (*.m3u8)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("#EXTM3U\n")
                for t in self.player.tracks:
                    fh.write(f"#EXTINF:{t.duration or -1},{t.label}\n{t.url}\n")
        except OSError as exc:
            self.player.flash(f"ERROR: {exc}")
            return
        self.player.flash(f"SAVED {len(self.player.tracks)} TRACKS")

    # ---- keyboard (Winamp's own map) -----------------------------------------------------------
    def keyPressEvent(self, e) -> None:
        pl, k, mods = self.player, e.key(), e.modifiers()
        ctrl, alt = bool(mods & Qt.ControlModifier), bool(mods & Qt.AltModifier)
        if ctrl and k == Qt.Key_D:
            self.cycle_scale()
        elif ctrl and k == Qt.Key_W:
            self.toggle_shade()
        elif ctrl and k == Qt.Key_A:
            self.set_on_top(not pl.settings["always_on_top"])
        elif alt and k == Qt.Key_G:
            self.toggle_panel("eq")
        elif alt and k == Qt.Key_E:
            self.toggle_panel("pl")
        elif alt and k == Qt.Key_3:
            self.track_info()
        elif k == Qt.Key_Z:
            pl.prev()
        elif k == Qt.Key_X:
            pl.play()
        elif k == Qt.Key_C:
            pl.pause()
        elif k == Qt.Key_V:
            pl.stop()
        elif k == Qt.Key_B:
            pl.next()
        elif k in (Qt.Key_L, Qt.Key_J, Qt.Key_Insert):
            self.open_search()
        elif k == Qt.Key_S:
            pl.toggle("shuffle")
        elif k == Qt.Key_R:
            pl.toggle("repeat")
        elif k == Qt.Key_Left:
            pl.seek_rel(-5)
        elif k == Qt.Key_Right:
            pl.seek_rel(5)
        elif k == Qt.Key_Up:
            pl.set_volume(pl.settings["volume"] + 2)
        elif k == Qt.Key_Down:
            pl.set_volume(pl.settings["volume"] - 2)
        elif k in (Qt.Key_MediaPlay, Qt.Key_MediaTogglePlayPause):
            pl.pause() if pl.status in ("playing", "paused") else pl.play()
        elif k == Qt.Key_MediaNext:
            pl.next()
        elif k == Qt.Key_MediaPrevious:
            pl.prev()
        elif k == Qt.Key_MediaStop:
            pl.stop()
        else:
            super().keyPressEvent(e)
            return
        self.update_all()

    # ---- global media keys (Windows) -------------------------------------------------------------
    def showEvent(self, e) -> None:
        super().showEvent(e)
        if self.player.settings["media_keys"] and self.media_keys is None:
            self._register_media_keys(True)

    def _register_media_keys(self, on: bool) -> None:
        if self.media_keys is not None:
            self.media_keys.stop()
            self.media_keys = None
        if on and sys.platform == "win32":
            self.media_keys = MediaKeys(self.player)
            if len(self.media_keys.ids) < len(MEDIA_KEYS):
                self.player.flash("SOME MEDIA KEYS ARE HELD BY ANOTHER APP - CLOSE IT AND TOGGLE "
                                  "OPTIONS > MEDIA KEYS", 8.0)

    # ---- lifecycle -------------------------------------------------------------------------------
    def changeEvent(self, e) -> None:
        self.update_all()
        super().changeEvent(e)

    def closeEvent(self, e) -> None:
        self._register_media_keys(False)
        s = self.player.settings
        s["pos"] = [self.x(), self.y()]
        s["scale"] = self.scale
        self.player.shutdown()
        self.search.close()
        super().closeEvent(e)
        QApplication.instance().quit()


def _install_crash_log() -> str:
    """pythonw and the windowed .exe have no console: unhandled errors go to crash.log instead."""
    path = os.path.join(state_dir(), "crash.log")

    def write(exc_type, exc, tb):
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} T-Amp {__version__} ---\n")
                traceback.print_exception(exc_type, exc, tb, file=fh)
        except OSError:
            pass
    sys.excepthook = write
    threading.excepthook = lambda a: write(a.exc_type, a.exc_value, a.exc_traceback)
    return path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    from . import updater
    updater.activate()  # newer yt-dlp / ytmusicapi fetched earlier win over the bundled ones
    if "--selftest" in argv:
        from .selftest import run
        return run(argv)
    if "--make-icon" in argv:
        out = argv[argv.index("--make-icon") + 1]
        app = QApplication.instance() or QApplication(argv[:1])
        app_icon().pixmap(256, 256).toImage().save(out)
        return 0
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Floor)
    if sys.platform == "win32":
        try:  # own taskbar group + icon instead of python.exe's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TBone.TAmp")
        except Exception:  # very old Windows: cosmetic only
            pass
    crash_log = _install_crash_log()
    app = QApplication(argv[:1])
    app.setApplicationName("T-Amp")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    if hand_over_to_running():
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_KEY)  # a crashed run can leave a stale socket behind
    server.listen(INSTANCE_KEY)
    try:
        player = Player()
        shell = Shell(player)
    except Exception as exc:  # say why on screen; a windowed app that silently vanishes helps no one
        sys.excepthook(type(exc), exc, exc.__traceback__)
        QMessageBox.critical(None, "T-Amp could not start", f"{type(exc).__name__}: {exc}\n\nDetails: {crash_log}")
        return 1

    def bring_forward():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.deleteLater()
        shell.showNormal()
        shell.raise_()
        shell.activateWindow()
    server.newConnection.connect(bring_forward)
    shell.show()
    if not player.tracks:
        QTimer.singleShot(300, shell.open_search)
    if updater.due(player.settings):
        QTimer.singleShot(4000, player.update_engine)
    code = app.exec()
    # Everything is saved by now (closeEvent). Don't let a yt-dlp request still in flight keep
    # an invisible T-Amp.exe alive for its 20-second timeout.
    os._exit(code)
