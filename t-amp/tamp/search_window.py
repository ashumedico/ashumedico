"""Live YouTube Music search, in a skinned window that docks beside the player.

Type and the results follow you (280 ms after the last key). Up/Down walk the list
without leaving the box, Enter plays, Shift+Enter enqueues, Ctrl+Enter adds them all.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import QLineEdit, QMenu, QWidget

from . import skin
from .skin import C
from .youtube import Album, Track, fmt_time

KIND_LABELS = (("songs", "SONGS"), ("videos", "VIDEOS"), ("albums", "ALBUMS"))
ROW_H = 15
KIND_W = 45
DEBOUNCE_MS = 280


class ResultList(QWidget):
    def __init__(self, win: "SearchWindow"):
        super().__init__(win)
        self.win = win
        self.items: list = []
        self.sel = -1
        self.hover = -1
        self.top = 0
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)
        self._font = QFont("Arial")
        self._font.setStyleStrategy(QFont.PreferAntialias)

    @property
    def s(self) -> int:
        return self.win.scale

    @property
    def rows(self) -> int:
        return max(1, self.height() // (ROW_H * self.s))

    def set_items(self, items: list) -> None:
        self.items = items
        self.sel = 0 if items else -1
        self.top = 0
        self.update()

    def move_sel(self, d: int) -> None:
        if not self.items:
            return
        self.sel = max(0, min(len(self.items) - 1, self.sel + d))
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + self.rows:
            self.top = self.sel - self.rows + 1
        self.update()

    def paintEvent(self, _e) -> None:
        s = self.s
        p = QPainter(self)
        p.fillRect(self.rect(), skin.PL_BG)
        font = QFont(self._font)
        font.setPixelSize(round(9.5 * s))
        small = QFont(self._font)
        small.setPixelSize(round(8.5 * s))
        fm, fms = QFontMetricsF(font), QFontMetricsF(small)
        rh = ROW_H * s
        w = self.width()
        for k in range(self.rows + 1):
            i = self.top + k
            if i >= len(self.items):
                break
            it = self.items[i]
            y = k * rh
            if i == self.sel:
                p.fillRect(QRectF(0, y, w, rh), skin.PL_SELECTED)
            elif i == self.hover:
                p.fillRect(QRectF(0, y, w, rh), C("#10202a"))
            base = y + (rh + fm.ascent() - fm.descent()) / 2
            if isinstance(it, Album):
                main = it.title
                sub = " · ".join(x for x in (it.artist, it.year, it.kind.upper()) if x)
                right = "ALBUM"
            else:
                main = it.title
                sub = " · ".join(x for x in (it.artist, it.album) if x)
                right = fmt_time(it.duration)
            rw = fms.horizontalAdvance(right) + 6 * s
            p.setFont(font)
            p.setPen(skin.PL_CURRENT if i == self.sel else skin.PL_NORMAL)
            col = (w - rw) * 0.5  # fixed column: titles left, artist / album right
            p.save()
            p.setClipRect(QRectF(0, y, col - 4 * s, rh))
            p.drawText(QPointF(4 * s, base), main)
            p.restore()
            p.setFont(small)
            p.setPen(C("#9adf9a") if i == self.sel else C("#00a800"))
            p.save()
            p.setClipRect(QRectF(col, y, w - rw - col, rh))
            p.drawText(QPointF(col, base), sub)
            p.restore()
            p.setPen(skin.PL_NORMAL)
            p.drawText(QPointF(w - rw + 2 * s, base), right)
        if not self.items and self.win.hint:
            p.setFont(small)
            p.setPen(C("#00a000"))
            p.drawText(self.rect().adjusted(8 * s, 8 * s, -8 * s, -8 * s), Qt.AlignLeft | Qt.TextWordWrap,
                       self.win.hint)
        p.end()

    def _index_at(self, y: float) -> int:
        i = self.top + int(y // (ROW_H * self.s))
        return i if 0 <= i < len(self.items) else -1

    def mouseMoveEvent(self, e) -> None:
        i = self._index_at(e.position().y())
        if i != self.hover:
            self.hover = i
            self.update()

    def leaveEvent(self, _e) -> None:
        self.hover = -1
        self.update()

    def mousePressEvent(self, e) -> None:
        i = self._index_at(e.position().y())
        if i >= 0:
            self.sel = i
            self.update()
            if e.button() == Qt.RightButton:
                m = QMenu(self)
                m.addAction("Play now\tEnter", lambda: self.win.take(play=True))
                m.addAction("Enqueue\tShift+Enter", lambda: self.win.take(play=False))
                m.addAction("Enqueue all results\tCtrl+Enter", lambda: self.win.take(play=False, every=True))
                m.exec(e.globalPosition().toPoint())
                m.deleteLater()

    def mouseDoubleClickEvent(self, e) -> None:
        if self._index_at(e.position().y()) >= 0:
            self.win.take(play=True)

    def wheelEvent(self, e) -> None:
        d = -3 if e.angleDelta().y() > 0 else 3
        self.top = max(0, min(self.top + d, max(0, len(self.items) - self.rows)))
        self.update()


class SearchBox(QLineEdit):
    def __init__(self, win: "SearchWindow"):
        super().__init__(win)
        self.win = win

    def keyPressEvent(self, e) -> None:
        k, mods = e.key(), e.modifiers()
        lst = self.win.results
        if k == Qt.Key_Down:
            lst.move_sel(1)
        elif k == Qt.Key_Up:
            lst.move_sel(-1)
        elif k == Qt.Key_PageDown:
            lst.move_sel(lst.rows)
        elif k == Qt.Key_PageUp:
            lst.move_sel(-lst.rows)
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            if self.win.timer.isActive():  # Enter before the debounce fired: search now, act on arrival
                self.win.enter_pending = (not bool(mods & Qt.ShiftModifier), bool(mods & Qt.ControlModifier))
                self.win.run_search()
                return
            self.win.take(play=not (mods & Qt.ShiftModifier) and not (mods & Qt.ControlModifier),
                          every=bool(mods & Qt.ControlModifier))
        elif k == Qt.Key_Escape:
            if self.text():
                self.clear()
            else:
                self.win.hide()
        elif k == Qt.Key_Tab:
            self.win.cycle_kind()
        else:
            super().keyPressEvent(e)


class SearchWindow(QWidget):
    MIN_W, MIN_H = 275, 140

    def __init__(self, shell, player):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.shell, self.player = shell, player
        self.setWindowTitle("T-Amp - YouTube Music search")
        self.scale = shell.scale
        self.kind = player.settings.get("search_kind") or "songs"
        self.down: str | None = None
        self.hint = ("Type an artist, a song or an album - results appear as you type.\n\n"
                     "Paste a YouTube Music link to add a song, an album or a whole playlist.\n\n"
                     "Enter plays  ·  Shift+Enter enqueues  ·  Ctrl+Enter enqueues everything  ·  "
                     "Tab switches Songs / Videos / Albums")
        self.status = "YOUTUBE MUSIC"
        self.enter_pending: tuple[bool, bool] | None = None
        self._seq = 0
        self._t0 = 0.0
        self._cache: dict[tuple[str, str], list] = {}
        self._move_from: tuple[QPoint, QPoint] | None = None
        self._resize_from: tuple[QPoint, QSize] | None = None
        self.box = SearchBox(self)
        self.box.setPlaceholderText("Search YouTube Music")
        self.box.textChanged.connect(self._typed)
        self.results = ResultList(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(DEBOUNCE_MS)
        self.timer.timeout.connect(self.run_search)
        player.search_done.connect(self._on_results)
        player.tracks_ready.connect(self._on_tracks_ready)
        size = player.settings.get("search_size") or [330, 300]
        self.logical = QSize(max(self.MIN_W, size[0]), max(self.MIN_H, size[1]))
        self.apply_scale(self.scale)

    # ---- layout ------------------------------------------------------------------------------
    def apply_scale(self, s: int) -> None:
        self.scale = s
        self.resize(self.logical.width() * s, self.logical.height() * s)
        f = QFont("Arial")
        f.setPixelSize(round(10 * s))
        self.box.setFont(f)
        self.box.setStyleSheet(
            "QLineEdit { background: #000; color: #00ff00; border: none; padding: 0 %dpx;"
            " selection-background-color: #0000c6; selection-color: #fff; }" % (2 * s))
        self._place()

    def _lw(self) -> int:
        return self.width() // self.scale

    def _lh(self) -> int:
        return self.height() // self.scale

    def _place(self) -> None:
        s, w, h = self.scale, self._lw(), self._lh()
        kinds_w = 3 * KIND_W + 4
        self.box.setGeometry(13 * s, 21 * s, (w - 26 - kinds_w) * s, 13 * s)
        self.results.setGeometry(13 * s, 40 * s, (w - 26) * s, (h - 40 - 30) * s)
        self.update()

    def regions(self) -> dict[str, QRect]:
        w, h = self._lw(), self._lh()
        r = {"close": QRect(w - 11, 3, 9, 9)}
        x = w - 13 - 3 * KIND_W
        for i, (k, _) in enumerate(KIND_LABELS):
            r[f"kind_{k}"] = QRect(x + i * KIND_W + 2, 21, KIND_W - 2, 13)
        r["play"] = QRect(w - 13 - 3 * 44 + 2, h - 24, 42, 16)
        r["enqueue"] = QRect(w - 13 - 2 * 44 + 2, h - 24, 42, 16)
        r["all"] = QRect(w - 13 - 44 + 2, h - 24, 42, 16)
        r["grip"] = QRect(w - 12, h - 12, 12, 12)
        return r

    def resizeEvent(self, _e) -> None:
        self._place()

    # ---- painting ----------------------------------------------------------------------------
    def paintEvent(self, _e) -> None:
        s, w, h = self.scale, self._lw(), self._lh()
        p = QPainter(self)
        p.scale(s, s)
        skin.metal(p, 0, 0, w, h)
        skin.outline(p, 0, 0, w, h, C("#0d0d14"))
        skin.vline(p, 1, 1, h - 2, skin.FRAME_LIGHT)
        skin.titlebar(p, w, "YOUTUBE MUSIC SEARCH", self.isActiveWindow(), buttons=("close",), down=self.down)
        # the search field's well
        bw = w - 26 - 3 * KIND_W - 4
        skin.inset(p, 13, 21, bw, 13)
        for i, (k, label) in enumerate(KIND_LABELS):
            x = w - 13 - 3 * KIND_W + i * KIND_W + 2
            skin.led_button(p, x, 21, KIND_W - 2, 13, label, self.kind == k, self.down == f"kind_{k}")
        skin.inset(p, 13, 40, w - 26, h - 70, None)
        # status + actions
        skin.draw_text(p, 13, h - 19, self.status[: max(0, (w - 13 - 3 * 44 - 18) // skin.CHAR_W)], skin.TEXT_GREEN)
        for name, label in (("play", "PLAY"), ("enqueue", "ENQUEUE"), ("all", "ADD ALL")):
            r = self.regions()[name]
            skin.led_button(p, r.x(), r.y(), r.width(), r.height(), label, False, self.down == name, led=False)
        for a in range(3):
            for b in range(3 - a):
                p.fillRect(w - 4 - a * 3, h - 4 - b * 3, 2, 2, C("#6a6a80"))
        p.end()

    # ---- search flow ------------------------------------------------------------------------
    def open(self, text: str | None = None) -> None:
        if text is not None:
            self.box.setText(text)
        self.show()
        self.raise_()
        self.activateWindow()
        self.box.setFocus()
        self.box.selectAll()

    def _typed(self, _text: str) -> None:
        self.enter_pending = None
        self.timer.start()

    def run_search(self) -> None:
        self.timer.stop()
        q = self.box.text().strip()
        if len(q) < 2:
            self.enter_pending = None
            self._seq = -1  # an answer still in flight must not refill the list
            self.results.set_items([])
            self.status = "YOUTUBE MUSIC"
            self.update()
            return
        hit = self._cache.get((self.kind, q.lower()))
        if hit is not None:
            self._seq = -1
            self._show(hit, q, 0.0)
            return
        self._t0 = time.monotonic()
        self.status = "SEARCHING..."
        self._seq = self.player.search(q, self.kind)
        self._pending_q = q
        self.update()

    def _on_results(self, seq: int, query: str, results, err) -> None:
        if seq != self._seq:
            return  # an older keystroke's answer: ignore
        if err:
            self.status = f"ERROR: {err}"
            self.results.set_items([])
            self.update()
            return
        self._cache[(self.kind, query.lower())] = results
        self._show(results, query, time.monotonic() - self._t0)

    def _show(self, results: list, query: str, secs: float) -> None:
        self.results.set_items(results)
        noun = {"songs": "SONG", "videos": "VIDEO", "albums": "ALBUM"}[self.kind]
        n = len(results)
        if n:
            self.status = f"{n} {noun}{'S' if n != 1 else ''}" + (f" IN {secs:.1f}S" if secs else "")
        else:
            self.status = "NO RESULTS"
        self.update()
        if self.enter_pending is not None and results:
            play, every = self.enter_pending
            self.enter_pending = None
            self.take(play=play and not every, every=every)

    def cycle_kind(self) -> None:
        order = [k for k, _ in KIND_LABELS]
        self.set_kind(order[(order.index(self.kind) + 1) % len(order)])

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.player.settings["search_kind"] = kind
        self.run_search()
        self.update()

    def take(self, play: bool, every: bool = False) -> None:
        lst = self.results
        if every:
            items = list(lst.items)
        elif 0 <= lst.sel < len(lst.items):
            items = [lst.items[lst.sel]]
        else:
            return
        if not items:
            return
        has_album = any(isinstance(it, Album) for it in items)
        if has_album:
            self.status = "LOADING ALBUM..."
            self.update()
        self.player.expand_and_add(items, play=play)
        if not has_album:
            self._confirm(items, play)

    def _on_tracks_ready(self, tracks, play: bool, err) -> None:
        self.player.add_tracks(list(tracks), play=play)
        if err:
            self.status = f"ERROR: {err}"
        else:
            self._confirm(tracks, play)
        self.update()

    def _confirm(self, items, play: bool) -> None:
        n = sum(1 for it in items if isinstance(it, Track))
        self.status = ("PLAYING" if play else "ADDED") + (f" {n} TRACKS" if n != 1 else "")
        self.update()

    # ---- mouse: buttons, move, resize -----------------------------------------------------------
    def _hit(self, e) -> tuple[str | None, int, int]:
        x, y = int(e.position().x() // self.scale), int(e.position().y() // self.scale)
        for name, r in self.regions().items():
            if r.contains(x, y):
                return name, x, y
        return None, x, y

    def mousePressEvent(self, e) -> None:
        name, x, y = self._hit(e)
        if e.button() != Qt.LeftButton:
            return
        if name == "grip":
            self._resize_from = (e.globalPosition().toPoint(), self.size())
        elif name is None:
            self._move_from = (e.globalPosition().toPoint(), self.pos())
        else:
            self.down = name
        self.update()

    def mouseMoveEvent(self, e) -> None:
        g = e.globalPosition().toPoint()
        if self._move_from:
            start, pos = self._move_from
            self.move(self.shell.snap_search(pos + (g - start), self.size()))
        elif self._resize_from:
            start, size = self._resize_from
            d = g - start
            s = self.scale
            lw = max(self.MIN_W, (size.width() + d.x()) // s)
            lh = max(self.MIN_H, (size.height() + d.y()) // s)
            self.logical = QSize(lw, lh)
            self.resize(lw * s, lh * s)

    def mouseReleaseEvent(self, e) -> None:
        if self._move_from:
            self._move_from = None
            self.shell.search_moved()
        elif self._resize_from:
            self._resize_from = None
            self.player.settings["search_size"] = [self.logical.width(), self.logical.height()]
        elif self.down:
            name, self.down = self.down, None
            hit, _, _ = self._hit(e)
            if hit == name:
                if name == "close":
                    self.hide()
                elif name.startswith("kind_"):
                    self.set_kind(name[5:])
                elif name == "play":
                    self.take(play=True)
                elif name == "enqueue":
                    self.take(play=False)
                elif name == "all":
                    self.take(play=False, every=True)
        self.update()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape:
            self.hide()
        else:
            self.box.setFocus()
            self.box.keyPressEvent(e)

    def changeEvent(self, e) -> None:
        self.update()
        super().changeEvent(e)
