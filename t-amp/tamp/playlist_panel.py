"""The playlist editor: green-on-black list, blue selection, scrollbar, the button bar."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication, QPainter
from PySide6.QtWidgets import QMenu

from . import skin
from .skin import C
from .ui_base import SkinPanel
from .youtube import fmt_time

ROW_H = 13
LIST_X, LIST_TOP = 12, 20
LIST_W = 243
BOTTOM_H = 38
SCROLL_X = 260
STEP = 29


class PlaylistPanel(SkinPanel):
    SLIDERS = ("scroll", "grip")

    def __init__(self, shell, player):
        super().__init__(shell, player)
        self.top = 0
        self._anchor: int | None = None
        self._row_drag: int | None = None    # row under the mouse when a selection drag began
        self._font = QFont("Arial")
        self._font.setStyleStrategy(QFont.PreferAntialias)
        self.setFocusPolicy(Qt.ClickFocus)
        player.playlist_changed.connect(self._clamp)

    # ---- geometry --------------------------------------------------------------------------
    def logical_height(self) -> int:
        return 116 + STEP * max(0, int(self.player.settings["pl_rows"]))

    @property
    def list_h(self) -> int:
        return self.logical_height() - LIST_TOP - BOTTOM_H

    @property
    def visible_rows(self) -> int:
        return max(1, self.list_h // ROW_H)

    def _clamp(self) -> None:
        n = len(self.player.tracks)
        self.top = max(0, min(self.top, n - self.visible_rows))
        self.update()

    def ensure_visible(self, i: int) -> None:
        if i < self.top:
            self.top = i
        elif i >= self.top + self.visible_rows:
            self.top = i - self.visible_rows + 1
        self._clamp()

    def regions(self) -> dict[str, QRect]:
        h = self.logical_height()
        b = h - 30
        return {
            "close": QRect(264, 3, 9, 9),
            "add": QRect(11, b, 25, 18), "rem": QRect(39, b, 25, 18), "sel": QRect(67, b, 25, 18),
            "misc": QRect(95, b, 25, 18), "list": QRect(228, b, 23, 18),
            "m_prev": QRect(129, h - 15, 8, 8), "m_play": QRect(138, h - 15, 8, 8),
            "m_pause": QRect(147, h - 15, 8, 8), "m_stop": QRect(156, h - 15, 8, 8),
            "m_next": QRect(165, h - 15, 8, 8), "m_eject": QRect(174, h - 15, 8, 8),
            "grip": QRect(258, h - 20, 17, 20),
            "scroll": QRect(SCROLL_X - 1, LIST_TOP, 10, self.list_h),
            "rows": QRect(LIST_X, LIST_TOP, LIST_W, self.list_h),
            "title": QRect(0, 0, 275, 20),
        }

    # ---- painting --------------------------------------------------------------------------
    def render(self, p: QPainter) -> None:
        pl = self.player
        h = self.logical_height()
        skin.metal(p, 0, 0, 275, h)
        skin.titlebar(p, 275, "PLAYLIST", self.active(), buttons=("close",), down=self.down)
        p.fillRect(0, 14, 275, 6, C("#191926"))
        skin.metal(p, 0, 14, 275, 6)
        skin.vline(p, 0, 0, h - 1, C("#101019"))
        skin.vline(p, 1, 14, h - 1, skin.FRAME_LIGHT)
        skin.vline(p, 274, 0, h - 1, C("#171724"))
        skin.hline(p, 0, 274, h - 1, C("#101019"))
        # list well
        lh = self.list_h
        p.fillRect(LIST_X, LIST_TOP, LIST_W, lh, skin.PL_BG)
        skin.hline(p, LIST_X - 1, LIST_X + LIST_W, LIST_TOP - 1, C("#0b0b12"))
        skin.vline(p, LIST_X - 1, LIST_TOP - 1, LIST_TOP + lh, C("#0b0b12"))
        skin.hline(p, LIST_X - 1, LIST_X + LIST_W, LIST_TOP + lh, skin.LCD_EDGE_LIGHT)
        skin.vline(p, LIST_X + LIST_W, LIST_TOP - 1, LIST_TOP + lh, skin.LCD_EDGE_LIGHT)
        # scrollbar
        p.fillRect(SCROLL_X, LIST_TOP, 8, lh, C("#14141f"))
        skin.vline(p, SCROLL_X - 1, LIST_TOP, LIST_TOP + lh - 1, C("#0b0b12"))
        ty = self._thumb_y()
        skin.button(p, SCROLL_X, ty, 8, 18, self.down == "scroll")
        for k in (6, 8, 10):
            skin.hline(p, SCROLL_X + 2, SCROLL_X + 5, ty + k, C("#4a5a6b"))
        # bottom bar
        b = h - BOTTOM_H
        skin.hline(p, 2, 272, b + 1, C("#101019"))
        for name, label, x in (("add", "ADD", 11), ("rem", "REM", 39), ("sel", "SEL", 67), ("misc", "MISC", 95)):
            skin.button(p, x, h - 30, 25, 18, self.down == name)
            o = 1 if self.down == name else 0
            skin.draw_text(p, x + (25 - skin.text_width(label)) // 2 + o, h - 24 + o, label, C("#2f374d"))
        skin.button(p, 228, h - 30, 23, 18, self.down == "list")
        o = 1 if self.down == "list" else 0
        skin.draw_text(p, 230 + o, h - 28 + o, "LIST", C("#2f374d"))
        skin.draw_text(p, 230 + o, h - 21 + o, "OPTS", C("#2f374d"))
        # info LCD: selected length / total length, then mini transport + time
        skin.inset(p, 127, h - 33, 96, 11)
        sel = sorted(pl.selected)
        st, su = pl.total_seconds(sel) if sel else (0, False)
        tt, tu = pl.total_seconds()
        info = f"{fmt_time(st) if sel else '0:00'}{'+' if su else ''}/{fmt_time(tt)}{'+' if tu else ''}"
        skin.draw_text(p, 129, h - 30, info[:18], skin.TEXT_GREEN)
        for name, x in (("prev", 129), ("play", 138), ("pause", 147), ("stop", 156), ("next", 165), ("eject", 174)):
            col = C("#ffffff") if self.down == f"m_{name}" else C("#c0c0d0")
            self._mini(p, name, x + 1, h - 14, col)
        skin.inset(p, 190, h - 16, 33, 9)
        if pl.status != "stopped":
            skin.draw_text(p, 192, h - 15, fmt_time(pl.position).rjust(6)[-6:], skin.TEXT_GREEN)
        # resize grip
        for a in range(4):
            for b in range(4 - a):
                p.fillRect(270 - a * 3, h - 5 - b * 3, 2, 2, C("#6a6a80"))

    @staticmethod
    def _mini(p: QPainter, kind: str, x: int, y: int, c) -> None:
        f = p.fillRect
        if kind == "prev":
            f(x, y, 1, 6, c)
            for r in range(6):
                w = min(r, 5 - r) + 1
                f(x + 1 + 3 - w, y + r, w, 1, c)
        elif kind == "play":
            for r in range(6):
                f(x + 1, y + r, min(r, 5 - r) + 1, 1, c)
        elif kind == "pause":
            f(x, y, 2, 6, c)
            f(x + 4, y, 2, 6, c)
        elif kind == "stop":
            f(x, y, 6, 6, c)
        elif kind == "next":
            for r in range(6):
                f(x, y + r, min(r, 5 - r) + 1, 1, c)
            f(x + 4, y, 1, 6, c)
        elif kind == "eject":
            for r in range(3):
                f(x + 2 - r, y + r, 1 + 2 * r, 1, c)
            f(x, y + 4, 5, 2, c)

    def _thumb_y(self) -> int:
        n = len(self.player.tracks)
        span = self.list_h - 18
        if n <= self.visible_rows:
            return LIST_TOP
        return LIST_TOP + round(self.top / (n - self.visible_rows) * span)

    def overlay(self, p: QPainter) -> None:
        pl, s = self.player, self.scale
        font = QFont(self._font)
        font.setPixelSize(max(8, round(9.5 * s)))
        fm = QFontMetricsF(font)
        p.setFont(font)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        area = QRectF(LIST_X * s, LIST_TOP * s, LIST_W * s, self.list_h * s)
        p.save()
        p.setClipRect(area)
        rh = ROW_H * s
        for k in range(self.visible_rows + 1):
            i = self.top + k
            if i >= len(pl.tracks):
                break
            t = pl.tracks[i]
            y = area.y() + k * rh
            if i in pl.selected:
                p.fillRect(QRectF(area.x(), y, area.width(), rh), skin.PL_SELECTED)
            p.setPen(skin.PL_CURRENT if i == pl.current else skin.PL_NORMAL)
            dur = fmt_time(t.duration)
            dw = fm.horizontalAdvance(dur) if dur else 0
            base = y + (rh + fm.ascent() - fm.descent()) / 2
            p.save()
            p.setClipRect(QRectF(area.x(), y, area.width() - dw - 6 * s, rh))
            p.drawText(QPointF(area.x() + 2 * s, base), f"{i + 1}. {t.label}")
            p.restore()
            if dur:
                p.drawText(QPointF(area.right() - dw - 3 * s, base), dur)
        if not pl.tracks:
            p.setPen(C("#00a000"))
            p.drawText(area.adjusted(6 * s, 6 * s, -6 * s, -6 * s), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                       "Empty playlist.\n\nPress L, the ADD button or EJECT to search YouTube Music.\n"
                       "Paste a YouTube Music link into the search box to add a song, album or playlist.")
        p.restore()

    # ---- mouse -------------------------------------------------------------------------------
    def _row_at(self, y: int) -> int | None:
        k = (y - LIST_TOP) // ROW_H
        i = self.top + k
        return i if 0 <= k and i < len(self.player.tracks) else None

    def mousePressEvent(self, e) -> None:
        x, y = self.lpos(e)
        if self.hit(x, y) == "rows" and e.button() in (Qt.LeftButton, Qt.RightButton):
            self.shell.focus_panel(self)
            self.setFocus()
            pl = self.player
            i = self._row_at(y)
            mods = e.modifiers()
            if i is None:
                if e.button() == Qt.LeftButton:
                    pl.selected = set()
            elif e.button() == Qt.RightButton:
                if i not in pl.selected:
                    pl.selected = {i}
                    self._anchor = i
                self.update()
                self.row_menu(e.globalPosition().toPoint())
                return
            elif mods & Qt.ShiftModifier and self._anchor is not None:
                lo, hi = sorted((self._anchor, i))
                pl.selected = set(range(lo, hi + 1))
            elif mods & Qt.ControlModifier:
                pl.selected ^= {i}
                self._anchor = i
            else:
                if i not in pl.selected:
                    pl.selected = {i}
                self._anchor = i
                self._row_drag = i
            self.update()
            self.shell.update_all()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._row_drag is not None:
            x, y = self.lpos(e)
            k = (y - LIST_TOP) // ROW_H
            i = max(0, min(len(self.player.tracks) - 1, self.top + k))
            delta = i - self._row_drag
            if delta:
                sel = sorted(self.player.selected)
                if sel:
                    first = max(0, min(sel[0] + delta, len(self.player.tracks) - len(sel)))
                    if first != sel[0]:
                        self.player.move(sel, first)
                        self._row_drag += first - sel[0]
                self.update()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._row_drag is not None:
            x, y = self.lpos(e)
            i = self._row_at(y)
            if i is not None and not (e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)) \
                    and i == self._row_drag and len(self.player.selected) > 1:
                self.player.selected = {i}
            self._row_drag = None
            self.update()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:
        x, y = self.lpos(e)
        if self.hit(x, y) == "rows":
            i = self._row_at(y)
            if i is not None:
                self.player.selected = {i}
                self.player.play_index(i)
            return
        super().mouseDoubleClickEvent(e)

    def wheel(self, steps: int) -> None:
        self.top -= 3 * steps
        self._clamp()

    def drag(self, name: str, x: int, y: int, phase: str) -> None:
        if name == "scroll":
            n = len(self.player.tracks)
            span = self.list_h - 18
            if n > self.visible_rows and span > 0:
                frac = (y - LIST_TOP - 9) / span
                self.top = round(max(0.0, min(1.0, frac)) * (n - self.visible_rows))
                self._clamp()
        elif name == "grip":
            rows = max(0, min(24, round((y - 116 + 10) / STEP)))
            if rows != self.player.settings["pl_rows"]:
                self.player.settings["pl_rows"] = rows
                self.relayout()
                self._clamp()
                self.shell.relayout()

    def click(self, name: str) -> None:
        pl, sh = self.player, self.shell
        at = lambda x, y: self.mapToGlobal(QPoint(x * self.scale, y * self.scale))  # noqa: E731
        h = self.logical_height()
        if name == "close":
            sh.toggle_panel("pl")
        elif name == "add":
            m = QMenu(self)
            m.addAction("Search YouTube Music...\tL", sh.open_search)
            m.addAction("Add link from clipboard", self.add_clipboard)
            m.exec(at(11, h - 30))
            m.deleteLater()
        elif name == "rem":
            m = QMenu(self)
            m.addAction("Remove selected\tDel", lambda: pl.remove(pl.selected))
            m.addAction("Crop (keep selected)", pl.crop)
            m.addAction("Remove duplicates", self.remove_duplicates)
            m.addSeparator()
            m.addAction("Remove all", pl.clear)
            m.exec(at(39, h - 30))
            m.deleteLater()
        elif name == "sel":
            m = QMenu(self)
            m.addAction("Select all\tCtrl+A", self.select_all)
            m.addAction("Select none", self.select_none)
            m.addAction("Invert selection", self.select_invert)
            m.exec(at(67, h - 30))
            m.deleteLater()
        elif name == "misc":
            m = QMenu(self)
            m.addAction("Sort by title", lambda: pl.sort("title"))
            m.addAction("Sort by artist", lambda: pl.sort("artist"))
            m.addAction("Sort by length", lambda: pl.sort("duration"))
            m.addAction("Reverse list", pl.reverse)
            m.addAction("Randomize list", pl.randomize)
            m.addSeparator()
            m.addAction("Track info...", sh.track_info)
            m.exec(at(95, h - 30))
            m.deleteLater()
        elif name == "list":
            m = QMenu(self)
            m.addAction("New list", pl.clear)
            m.addAction("Load list (.m3u8)...", sh.load_list)
            m.addAction("Save list (.m3u8)...", sh.save_list)
            m.exec(at(200, h - 30))
            m.deleteLater()
        elif name.startswith("m_"):
            {"prev": pl.prev, "play": pl.play, "pause": pl.pause, "stop": pl.stop, "next": pl.next,
             "eject": sh.open_search}[name[2:]]()
        self.update()

    def row_menu(self, gpos) -> None:
        pl, sh = self.player, self.shell
        m = QMenu(self)
        sel = sorted(pl.selected)
        if sel:
            m.addAction("Play", lambda: pl.play_index(sel[0]))
            m.addAction("Remove\tDel", lambda: pl.remove(sel))
            m.addAction("Crop", pl.crop)
            m.addSeparator()
            m.addAction("Copy YouTube Music link", lambda: QGuiApplication.clipboard().setText(
                "\n".join(pl.tracks[i].url for i in sel)))
            m.addAction("Track info...", lambda: sh.track_info(sel[0]))
        m.exec(gpos)
        m.deleteLater()
        self.update()

    def add_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        self.shell.open_search(text)

    def remove_duplicates(self) -> None:
        seen, drop = set(), []
        for i, t in enumerate(self.player.tracks):
            if t.video_id in seen:
                drop.append(i)
            seen.add(t.video_id)
        self.player.remove(drop)

    def select_all(self) -> None:
        self.player.selected = set(range(len(self.player.tracks)))
        self.shell.update_all()

    def select_none(self) -> None:
        self.player.selected = set()
        self.shell.update_all()

    def select_invert(self) -> None:
        self.player.selected = set(range(len(self.player.tracks))) - self.player.selected
        self.shell.update_all()

    def keyPressEvent(self, e) -> None:
        pl = self.player
        n = len(pl.tracks)
        key = e.key()
        if key in (Qt.Key_Delete, Qt.Key_Backspace) and pl.selected:
            pl.remove(pl.selected)
        elif key in (Qt.Key_Return, Qt.Key_Enter) and pl.selected:
            pl.play_index(min(pl.selected))
        elif key == Qt.Key_A and e.modifiers() & Qt.ControlModifier:
            self.select_all()
        elif key in (Qt.Key_Up, Qt.Key_Down) and n:
            cur = (min(pl.selected) if key == Qt.Key_Up else max(pl.selected)) if pl.selected else pl.current
            nxt = max(0, min(n - 1, (cur if cur >= 0 else 0) + (-1 if key == Qt.Key_Up else 1)))
            if e.modifiers() & Qt.AltModifier and pl.selected:
                sel = sorted(pl.selected)
                first = max(0, min(sel[0] + (-1 if key == Qt.Key_Up else 1), n - len(sel)))
                pl.move(sel, first)
                self.ensure_visible(first)
            else:
                pl.selected = {nxt}
                self._anchor = nxt
                self.ensure_visible(nxt)
        elif key == Qt.Key_PageDown:
            self.top += self.visible_rows
            self._clamp()
        elif key == Qt.Key_PageUp:
            self.top -= self.visible_rows
            self._clamp()
        else:
            self.shell.keyPressEvent(e)
            return
        self.update()
