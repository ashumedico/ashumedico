"""The graphic equaliser window: ON / AUTO / PRESETS, response graph, preamp + 10 bands."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QMenu

from . import skin
from .dsp import EQ_FREQS, EQ_LABELS, PRESETS
from .skin import C
from .ui_base import SkinPanel

SLIDER_Y, SLIDER_H, THUMB = 38, 63, 11
PREAMP_X = 21
BAND_X = [78 + 18 * i for i in range(10)]
GRAPH = QRect(86, 17, 113, 19)


def _y_for(db: float) -> int:
    return SLIDER_Y + round((1 - (db + 12) / 24) * (SLIDER_H - THUMB))


def _db_for(y: int) -> float:
    frac = 1 - (y - SLIDER_Y - THUMB / 2) / (SLIDER_H - THUMB)
    db = max(-12.0, min(12.0, frac * 24 - 12))
    return 0.0 if abs(db) < 0.7 else round(db, 1)  # a little detent at 0 dB


class EqPanel(SkinPanel):
    SLIDERS = ("preamp",) + tuple(f"band{i}" for i in range(10))

    def regions(self) -> dict[str, QRect]:
        r = {"close": QRect(264, 3, 9, 9),
             "on": QRect(14, 18, 25, 12), "auto": QRect(39, 18, 33, 12), "presets": QRect(217, 18, 44, 12),
             "preamp": QRect(PREAMP_X, SLIDER_Y, 14, SLIDER_H)}
        for i, x in enumerate(BAND_X):
            r[f"band{i}"] = QRect(x, SLIDER_Y, 14, SLIDER_H)
        r["title"] = QRect(0, 0, 275, 14)
        return r

    def render(self, p: QPainter) -> None:
        pl = self.player
        skin.window_frame(p, 275, 116)
        skin.titlebar(p, 275, "EQUALIZER", self.active(), buttons=("close",), down=self.down)
        skin.led_button(p, 14, 18, 25, 12, "ON", pl.eq_on, self.down == "on")
        skin.led_button(p, 39, 18, 33, 12, "AUTO", pl.eq_auto, self.down == "auto")
        skin.led_button(p, 217, 18, 44, 12, "PRESETS", False, self.down == "presets", led=False)
        self._render_graph(p)
        # dB scale and the tick dashes between sliders
        skin.draw_text(p, 44, 37, "+12DB", skin.GOLD)
        skin.draw_text(p, 49, 66, "+0DB", skin.GOLD)
        skin.draw_text(p, 44, 96, "-12DB", skin.GOLD)
        dash = C("#d0d0dc")
        for x in [PREAMP_X - 5, PREAMP_X + 15] + [bx - 4 for bx in BAND_X] + [BAND_X[-1] + 15]:
            for y in (39, 69, 99):
                skin.hline(p, x, x + 2, y, dash)
        self._slider(p, "preamp", PREAMP_X, pl.eq_preamp)
        for i, x in enumerate(BAND_X):
            self._slider(p, f"band{i}", x, pl.eq_gains[i])
        skin.draw_text(p, PREAMP_X + 7 - skin.text_width("PREAMP") // 2, 104, "PREAMP", skin.LABEL)
        for x, lab in zip(BAND_X, EQ_LABELS):
            skin.draw_text(p, x + 7 - skin.text_width(lab) // 2, 104, lab, skin.LABEL)

    def _slider(self, p: QPainter, name: str, x: int, db: float) -> None:
        skin.vpill(p, x + 4, SLIDER_Y, SLIDER_H, skin.level_color((db + 12) / 24))
        skin.eq_thumb(p, x + 1, _y_for(db), self.down == name)

    def _render_graph(self, p: QPainter) -> None:
        g = GRAPH
        p.fillRect(g, C("#1b1b2b"))
        skin.outline(p, g.x(), g.y(), g.width(), g.height(), C("#3e3e56"))
        for i in range(10):
            skin.vline(p, g.x() + 4 + i * 12, g.y() + 1, g.bottom() - 1, C("#2a2a40"))
        mid = g.y() + g.height() // 2
        skin.hline(p, g.x() + 1, g.right() - 1, mid, C("#2a2a40"))
        pl = self.player
        if pl.eq_on:
            py = mid - round(pl.eq_preamp / 12 * 8)
            skin.hline(p, g.x() + 1, g.right() - 1, py, C("#8a8aa0"))
        # the real response of the filters, log-frequency across the box
        freqs = np.geomspace(40, min(18000, pl.engine.samplerate * 0.45), g.width() - 2)
        resp = pl.engine.eq.response_db(freqs) if pl.eq_on else np.zeros(len(freqs))
        prev = None
        for i, db in enumerate(resp):
            y = mid - int(round(max(-12, min(12, db)) / 12 * 8))
            lo, hi = (y, y) if prev is None else (min(prev, y), max(prev, y))
            for yy in range(lo, hi + 1):
                p.fillRect(g.x() + 1 + i, yy, 1, 1, skin.level_color((mid + 8 - yy) / 16))
            prev = y

    def click(self, name: str) -> None:
        pl = self.player
        if name == "close":
            self.shell.toggle_panel("eq")
        elif name == "on":
            pl.set_eq(on=not pl.eq_on)
        elif name == "auto":
            pl.toggle("eq_auto")
        elif name == "presets":
            self.presets_menu(self.mapToGlobal(QPoint(217 * self.scale, 30 * self.scale)))
        self.update()

    def presets_menu(self, gpos: QPoint) -> None:
        m = QMenu(self)
        for name in PRESETS:
            m.addAction(name, lambda n=name: self.player.load_preset(n))
        m.addSeparator()
        m.addAction("Reset to flat", lambda: self.player.set_eq(preamp=0.0, gains=[0.0] * 10))
        m.exec(gpos)
        m.deleteLater()
        self.update()

    def drag(self, name: str, x: int, y: int, phase: str) -> None:
        pl = self.player
        db = _db_for(y)
        if name == "preamp":
            pl.set_eq(preamp=db)
            pl.flash(f"EQ: PREAMP: {db:+.1f} DB", 1.0)
        else:
            i = int(name[4:])
            pl.set_eq(band=i, value=db)
            hz = EQ_FREQS[i]
            label = f"{hz // 1000}KHZ" if hz >= 1000 else f"{hz}HZ"
            pl.flash(f"EQ: {label}: {db:+.1f} DB", 1.0)
