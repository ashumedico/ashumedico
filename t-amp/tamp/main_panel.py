"""The main window: LCD, visualiser, song title, sliders, transport. Plus its windowshade strip."""
from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter

from . import skin
from .skin import C
from .ui_base import SkinPanel
from .youtube import fmt_time

VOL_X, VOL_W, VOL_THUMB = 107, 68, 14
BAL_X, BAL_W, BAL_THUMB = 177, 38, 14
POS_X, POS_W, POS_THUMB = 16, 248, 29
TITLE_BOX = QRect(111, 27, 154, 6)
SCROLL_STEP_S = 0.22  # one character every 220 ms, as the original did


class MainPanel(SkinPanel):
    SLIDERS = ("volume", "balance", "pos", "s_pos")

    def __init__(self, shell, player):
        super().__init__(shell, player)
        self._seek_preview: float | None = None
        self._marquee_text = ""
        self._marquee_t0 = time.monotonic()
        self._ttf = QFont("Arial")
        self._ttf.setPixelSize(10)
        self._ttf.setStyleStrategy(QFont.PreferAntialias)

    @property
    def shaded(self) -> bool:
        return bool(self.player.settings["shade"])

    def logical_height(self) -> int:
        return 14 if self.shaded else 116

    # ---- layout --------------------------------------------------------------------------
    def regions(self) -> dict[str, QRect]:
        if self.shaded:
            return {
                "menu": QRect(6, 3, 9, 9), "min": QRect(244, 3, 9, 9), "shade": QRect(254, 3, 9, 9),
                "close": QRect(264, 3, 9, 9),
                "s_prev": QRect(169, 2, 8, 10), "s_play": QRect(177, 2, 10, 10), "s_pause": QRect(187, 2, 9, 10),
                "s_stop": QRect(196, 2, 9, 10), "s_next": QRect(205, 2, 8, 10), "s_eject": QRect(215, 2, 9, 10),
                "s_pos": QRect(226, 4, 17, 7), "time": QRect(127, 3, 30, 8), "vis": QRect(79, 5, 38, 5),
            }
        return {
            "menu": QRect(6, 3, 9, 9), "min": QRect(244, 3, 9, 9), "shade": QRect(254, 3, 9, 9),
            "close": QRect(264, 3, 9, 9),
            "cb_o": QRect(10, 22, 8, 8), "cb_a": QRect(10, 30, 8, 8), "cb_i": QRect(10, 38, 8, 8),
            "cb_d": QRect(10, 46, 8, 8), "cb_v": QRect(10, 54, 8, 9),
            "time": QRect(36, 26, 63, 13), "vis": QRect(24, 43, 76, 16),
            "marquee": QRect(109, 24, 157, 12),
            "volume": QRect(VOL_X, 57, VOL_W, 13), "balance": QRect(BAL_X, 57, BAL_W, 13),
            "eq": QRect(219, 58, 23, 12), "pl": QRect(242, 58, 23, 12),
            "pos": QRect(POS_X, 72, POS_W, 10),
            "prev": QRect(16, 88, 23, 18), "play": QRect(39, 88, 23, 18), "pause": QRect(62, 88, 23, 18),
            "stop": QRect(85, 88, 23, 18), "next": QRect(108, 88, 22, 18), "eject": QRect(136, 89, 22, 16),
            "shuffle": QRect(164, 89, 47, 15), "repeat": QRect(210, 89, 28, 15),
            "about": QRect(253, 91, 13, 15),
            "title": QRect(0, 0, 275, 14),
        }

    # ---- painting --------------------------------------------------------------------------
    def render(self, p: QPainter) -> None:
        if self.shaded:
            self._render_shade(p)
            return
        pl, s = self.player, self.player.settings
        skin.window_frame(p, 275, 116)
        skin.titlebar(p, 275, "T-AMP", self.active(), down=self.down)
        # LCD block, clutterbar
        skin.lcd_dots(p, 12, 23, 91, 41)
        skin.hline(p, 11, 102, 22, skin.LCD_EDGE_DARK)
        skin.vline(p, 11, 22, 63, skin.LCD_EDGE_DARK)
        skin.hline(p, 11, 103, 64, skin.LCD_EDGE_LIGHT)
        skin.vline(p, 103, 23, 64, skin.LCD_EDGE_LIGHT)
        p.fillRect(10, 22, 8, 43, C("#0a0a12"))
        lit = {"cb_o": False, "cb_a": bool(s["always_on_top"]), "cb_i": False,
               "cb_d": self.scale > 1, "cb_v": False}
        for i, (name, ch) in enumerate(zip(("cb_o", "cb_a", "cb_i", "cb_d", "cb_v"), "OAIDV")):
            col = C("#c8c8dc") if (self.down == name or lit[name]) else C("#40405a")
            skin.draw_text(p, 12, 24 + 8 * i, ch, col)
        self._render_status(p)
        self._render_time(p, 48, 26)
        self._render_vis(p, 24, 43, 76, 16)
        # song title, kbps / kHz, mono / stereo
        skin.inset(p, 109, 24, 157, 12)
        if skin.bitmap_ok(self._title_text()):
            self._render_marquee(p)
        skin.inset(p, 109, 41, 18, 10)
        skin.inset(p, 156, 41, 13, 10)
        skin.draw_text(p, 131, 43, "KBPS", skin.LABEL)
        skin.draw_text(p, 172, 43, "KHZ", skin.LABEL)
        st = pl.stream if pl.status in ("playing", "paused") else None
        if st is not None:
            if st.abr:
                skin.draw_text(p, 111, 43, f"{int(round(st.abr)):>3d}"[-3:])
            if st.asr:
                skin.draw_text(p, 158, 43, f"{int(st.asr) // 1000:>2d}"[-2:])
        stereo = st is not None and (st.channels or 2) >= 2
        mono = st is not None and not stereo
        skin.draw_text(p, 213, 44, "MONO", skin.GREEN if mono else C("#3a3a54"))
        skin.draw_text(p, 240, 44, "STEREO", skin.GREEN if stereo else C("#3a3a54"))
        # volume / balance
        vol = s["volume"] / 100.0
        skin.pill(p, VOL_X, 61, VOL_W, skin.level_color(vol))
        skin.grip_thumb(p, VOL_X + round(vol * (VOL_W - VOL_THUMB)), 58, VOL_THUMB, 11, self.down == "volume")
        bal = s["balance"] / 100.0
        skin.pill(p, BAL_X, 61, BAL_W, skin.level_color(abs(bal)))
        skin.grip_thumb(p, BAL_X + round((bal + 1) / 2 * (BAL_W - BAL_THUMB)), 58, BAL_THUMB, 11,
                        self.down == "balance")
        skin.led_button(p, 219, 58, 23, 12, "EQ", self.shell.show_eq, self.down == "eq")
        skin.led_button(p, 242, 58, 23, 12, "PL", self.shell.show_pl, self.down == "pl")
        # seek bar
        skin.inset(p, POS_X, 72, POS_W - 1, 9, C("#20202f"), C("#101019"), skin.LCD_EDGE_LIGHT)
        frac = self._pos_fraction()
        if frac is not None:
            skin.position_thumb(p, POS_X + round(frac * (POS_W - POS_THUMB)), 72, self.down == "pos")
        # transport
        for name, x, w in (("prev", 16, 23), ("play", 39, 23), ("pause", 62, 23), ("stop", 85, 23),
                           ("next", 108, 22)):
            skin.icon_button(p, name, x, 88, w, 18, self.down == name)
        skin.icon_button(p, "eject", 136, 89, 22, 16, self.down == "eject")
        skin.led_button(p, 164, 89, 47, 15, "SHUFFLE", pl.shuffle, self.down == "shuffle")
        skin.button(p, 210, 89, 28, 15, self.down == "repeat")
        off = 1 if self.down == "repeat" else 0
        p.fillRect(213 + off, 92 + off, 5, 4, skin.LED_ON if pl.repeat else skin.LED_OFF)
        skin.repeat_glyph(p, 221 + off, 93 + off, C("#2f374d"))
        self._render_logo(p, 254, 91)

    def _render_status(self, p: QPainter) -> None:
        st = self.player.status
        g = C("#00e800")
        x, y = 26, 28
        if st in ("playing", "connecting"):
            for r in range(9):
                p.fillRect(x + 3, y + r, min(r, 8 - r) + 1, 1, g)
        elif st == "paused":
            p.fillRect(x + 1, y + 1, 3, 7, g)
            p.fillRect(x + 6, y + 1, 3, 7, g)
        else:
            p.fillRect(x + 2, y + 2, 6, 6, g)
        if self.player.buffering and int(time.monotonic() * 4) % 2 == 0:
            p.fillRect(23, 33, 2, 2, C("#ff2a2a"))
        elif st == "playing":
            p.fillRect(23, 29, 2, 2, C("#00a800"))

    def _render_time(self, p: QPainter, x: int, y: int) -> None:
        pl = self.player
        p.fillRect(x + 24, y + 4, 2, 2, skin.GREEN)
        p.fillRect(x + 24, y + 8, 2, 2, skin.GREEN)
        if pl.status == "stopped":
            return
        if pl.status == "paused" and int(time.monotonic() * 2) % 2:
            return  # paused time blinks
        t = self._seek_preview if self._seek_preview is not None else pl.position
        remaining = pl.settings["time_remaining"] and pl.duration
        if remaining:
            t = max(0.0, pl.duration - t)
            p.fillRect(x - 12, y + 6, 5, 1, skin.GREEN)
        t = int(t)
        m, sec = divmod(t, 60)
        if m > 99:
            m, sec = divmod(m, 60)  # hours:minutes past the 99-minute mark
        txt = f"{m:02d}{sec:02d}"
        for i, ch in enumerate(txt):
            skin.draw_digit(p, x + (0, 12, 30, 42)[i], y, ch)

    def _render_vis(self, p: QPainter, x0: int, y0: int, w: int, h: int) -> None:
        s = self.player.settings
        mode = s["vis_mode"]
        if mode == "spectrum":
            vis = self.player.vis
            thin = s["vis_thin"]
            step, bw = (1, 1) if thin else (4, 3)
            for i, v in enumerate(vis.bars):
                bx = x0 + i * step
                if bx + bw > x0 + w:
                    break
                bh = int(round(v * h))
                for r in range(bh):
                    yy = y0 + h - 1 - r
                    p.fillRect(bx, yy, bw, 1, skin.VIS[2 + (yy - y0) * 16 // h])
                if s["vis_peaks"] and i < len(vis.peaks):
                    pk = int(round(vis.peaks[i] * h))
                    if pk > 0:
                        p.fillRect(bx, y0 + h - pk, bw, 1, skin.VIS[23])
        elif mode == "scope":
            pts = self.player.scope
            prev = None
            for i in range(min(w, len(pts))):
                yy = int(round((h - 1) / 2 - pts[i] * (h - 1) / 2))
                yy = max(0, min(h - 1, yy))
                lo, hi = (yy, yy) if prev is None else (min(prev, yy), max(prev, yy))
                for r in range(lo, hi + 1):
                    dist = abs(r - (h - 1) / 2)
                    p.fillRect(x0 + i, y0 + r, 1, 1, skin.VIS[22 - min(4, int(dist / 2))])
                prev = yy

    def _title_text(self) -> str:
        return self.player.message or self.player.title_line()

    def _scroll_offset(self, text: str, width: int, step: int) -> int:
        if text != self._marquee_text:
            self._marquee_text = text
            self._marquee_t0 = time.monotonic()
        if width <= TITLE_BOX.width():
            return 0
        n = int((time.monotonic() - self._marquee_t0) / SCROLL_STEP_S)
        return (n * step) % width

    def _render_marquee(self, p: QPainter) -> None:
        text = self._title_text()
        width = skin.text_width(text)
        if width > TITLE_BOX.width():  # long titles and long errors scroll, so all of it can be read
            text = text + "  ***  "
            width = skin.text_width(text)
        off = self._scroll_offset(text, width, skin.CHAR_W)
        p.save()
        p.setClipRect(TITLE_BOX)
        x = TITLE_BOX.x() - off
        skin.draw_text(p, x, TITLE_BOX.y(), text)
        if off:
            skin.draw_text(p, x + width, TITLE_BOX.y(), text)
        p.restore()

    def overlay(self, p: QPainter) -> None:
        """Titles the pixel font can't spell (Hindi, Tamil, Japanese...) in a real font, crisp."""
        if self.shaded:
            return
        text = self._title_text()
        if skin.bitmap_ok(text):
            return
        s = self.scale
        font = QFont(self._ttf)
        font.setPixelSize(max(9, int(9.5 * s)))
        fm = QFontMetricsF(font)
        full = text if fm.horizontalAdvance(text) <= TITLE_BOX.width() * s else text + "   ***   "
        width = fm.horizontalAdvance(full)
        off = self._scroll_offset(full, int(width), int(5 * s)) if width > TITLE_BOX.width() * s else 0
        box = QRectF(110 * s, 24 * s, 155 * s, 12 * s)
        p.save()
        p.setClipRect(box)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setFont(font)
        p.setPen(skin.TEXT_GREEN)
        base = box.y() + (box.height() + fm.ascent() - fm.descent()) / 2
        p.drawText(QPointF(box.x() + s - off, base), full)
        if off:
            p.drawText(QPointF(box.x() + s - off + width, base), full)
        p.restore()

    def _render_logo(self, p: QPainter, x: int, y: int) -> None:
        bolt = ["....###", "...###.", "..###..", ".######", "...###.", "..###..", ".###...", "###....",
                "##....."]
        for yy, row in enumerate(bolt):
            for xx, ch in enumerate(row):
                if ch == "#":
                    p.fillRect(x + xx + 1, y + yy + 3, 1, 1, C("#3a2a08"))
        for yy, row in enumerate(bolt):
            for xx, ch in enumerate(row):
                if ch == "#":
                    p.fillRect(x + xx, y + yy + 2, 1, 1, C("#f0c040") if xx + yy < 8 else C("#c88a18"))

    def _pos_fraction(self) -> float | None:
        pl = self.player
        if pl.status == "stopped" or not pl.duration:
            return None
        t = self._seek_preview if self._seek_preview is not None else pl.position
        return max(0.0, min(1.0, t / pl.duration))

    # ---- windowshade -----------------------------------------------------------------------
    def _render_shade(self, p: QPainter) -> None:
        pl = self.player
        active = self.active()
        skin.metal(p, 0, 0, 275, 14)
        skin.hline(p, 0, 274, 0, C("#0f0f17"))
        skin.hline(p, 0, 274, 1, C("#5d5d67") if active else C("#4a4a52"))
        skin.hline(p, 0, 274, 13, C("#101019"))
        skin.vline(p, 0, 0, 13, C("#0f0f17"))
        skin.vline(p, 274, 0, 13, C("#0f0f17"))
        for kind, x in (("menu", 6), ("min", 244), ("shade", 254), ("close", 264)):
            skin.titlebar_button(p, x, 3, kind, active, self.down == kind)
        # mini visualiser
        p.fillRect(79, 5, 38, 5, skin.LCD)
        bars = pl.vis.bars
        if pl.settings["vis_mode"] == "spectrum" and len(bars):
            n = 19
            for i in range(n):
                v = bars[min(len(bars) - 1, i * len(bars) // n)]
                bh = int(round(v * 5))
                for r in range(bh):
                    p.fillRect(79 + i * 2, 9 - r, 1, 1, skin.VIS[2 + (4 - r) * 3])
        # time
        if pl.status != "stopped" and not (pl.status == "paused" and int(time.monotonic() * 2) % 2):
            t = pl.position
            if pl.settings["time_remaining"] and pl.duration:
                t = max(0.0, pl.duration - t)
                skin.draw_text(p, 127, 4, "-", skin.GREEN)
            skin.draw_text(p, 132, 4, fmt_time(t).rjust(5)[-5:], skin.GREEN)
        # mini transport
        ink = C("#c8c8dc")
        for name, x in (("s_prev", 170), ("s_play", 178), ("s_pause", 188), ("s_stop", 197), ("s_next", 206),
                        ("s_eject", 216)):
            col = C("#ffffff") if self.down == name else ink
            self._mini_icon(p, name[2:], x, 4, col)
        # mini seek
        p.fillRect(226, 4, 17, 7, C("#101019"))
        frac = self._pos_fraction()
        if frac is not None:
            p.fillRect(226 + round(frac * 14), 4, 3, 7, C("#c8a858"))

    @staticmethod
    def _mini_icon(p: QPainter, kind: str, x: int, y: int, c: QColor) -> None:
        f = p.fillRect
        if kind == "prev":
            f(x, y, 1, 6, c)
            for r in range(6):
                w = min(r, 5 - r) + 1
                f(x + 1 + 3 - w, y + r, w, 1, c)
        elif kind == "play":
            for r in range(6):
                f(x, y + r, min(r, 5 - r) + 1, 1, c)
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

    # ---- behaviour -------------------------------------------------------------------------
    def click(self, name: str) -> None:
        pl, sh, s = self.player, self.shell, self.player.settings
        name = name[2:] if name.startswith("s_") and name != "s_pos" else name
        if name == "menu" or name == "cb_o":
            sh.main_menu(self.mapToGlobal(self.rect().topLeft()) + self._local(6, 13))
        elif name == "min":
            sh.showMinimized()
        elif name == "shade":
            sh.toggle_shade()
        elif name == "close":
            sh.close()
        elif name == "cb_a":
            sh.set_on_top(not s["always_on_top"])
        elif name == "cb_i":
            sh.track_info()
        elif name == "cb_d":
            sh.cycle_scale()
        elif name == "cb_v":
            sh.vis_menu(self.mapToGlobal(self._local(24, 60)))
        elif name == "time":
            s["time_remaining"] = not s["time_remaining"]
        elif name == "vis":
            order = ["spectrum", "scope", "off"]
            s["vis_mode"] = order[(order.index(s["vis_mode"]) + 1) % 3]
            pl.vis.bars[:] = 0
        elif name == "eq":
            sh.toggle_panel("eq")
        elif name == "pl":
            sh.toggle_panel("pl")
        elif name == "prev":
            pl.prev()
        elif name == "play":
            pl.play()
        elif name == "pause":
            pl.pause()
        elif name == "stop":
            pl.stop()
        elif name == "next":
            pl.next()
        elif name == "eject":
            sh.open_search()
        elif name == "shuffle":
            pl.toggle("shuffle")
        elif name == "repeat":
            pl.toggle("repeat")
        elif name == "about":
            sh.about()
        self.update()

    def _local(self, x: int, y: int) -> QPoint:
        return QPoint(x * self.scale, y * self.scale)

    def drag(self, name: str, x: int, y: int, phase: str) -> None:
        pl = self.player
        if name == "volume":
            v = (x - VOL_X - VOL_THUMB / 2) / (VOL_W - VOL_THUMB) * 100
            pl.set_volume(v)
            pl.flash(f"VOLUME: {pl.settings['volume']}%", 1.0)
        elif name == "balance":
            b = (x - BAL_X - BAL_THUMB / 2) / (BAL_W - BAL_THUMB) * 200 - 100
            if abs(b) < 12:
                b = 0  # snaps to centre, like the original
            pl.set_balance(b)
            b = pl.settings["balance"]
            side = "CENTER" if b == 0 else (f"{abs(b)}% LEFT" if b < 0 else f"{b}% RIGHT")
            pl.flash(f"BALANCE: {side}", 1.0)
        elif name in ("pos", "s_pos"):
            dur = pl.duration
            if not dur or pl.status == "stopped":
                return
            if name == "pos":
                frac = (x - POS_X - POS_THUMB / 2) / (POS_W - POS_THUMB)
            else:
                frac = (x - 226) / 16
            frac = max(0.0, min(1.0, frac))
            t = frac * dur
            if phase == "release":
                self._seek_preview = None
                pl.seek(t)
            else:
                self._seek_preview = t
                pl.flash(f"SEEK TO: {fmt_time(t)}/{fmt_time(dur)} ({int(frac * 100)}%)", 1.0)

    def double(self, name: str | None) -> None:
        if name == "title" or (self.shaded and name is None):
            self.shell.toggle_shade()
        elif name == "marquee":
            self.shell.track_info()

    def context(self, name: str | None, gpos) -> None:
        if name == "vis":
            self.shell.vis_menu(gpos)
        else:
            self.shell.main_menu(gpos)
