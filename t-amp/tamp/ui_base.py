"""Shared panel machinery: 1x rendering, nearest-neighbour scale-up, hit regions, drags."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget


class SkinPanel(QWidget):
    """A fixed-size panel drawn on the 275-pixel grid and blown up `scale` times.

    Subclasses implement `render(p)` (skin pixels), `regions()` (name -> QRect),
    `click(name)`, and optionally `drag(name, x, y, phase)` for sliders.
    """

    W, H = 275, 116
    SLIDERS: tuple[str, ...] = ()

    def __init__(self, shell, player):
        super().__init__(shell)
        self.shell, self.player = shell, player
        self.scale = 2
        self.down: str | None = None      # region under a held mouse button
        self.dragging: str | None = None  # slider being dragged
        self.moving = False               # dragging the whole window by its body
        self._buf = QImage(self.W, self.H, QImage.Format_ARGB32_Premultiplied)
        self.setMouseTracking(False)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    # ---- geometry --------------------------------------------------------------------------
    def logical_height(self) -> int:
        return self.H

    def set_scale(self, s: int) -> None:
        self.scale = s
        self.relayout()

    def relayout(self) -> None:
        h = self.logical_height()
        if self._buf.height() != h:
            self._buf = QImage(self.W, h, QImage.Format_ARGB32_Premultiplied)
        self.setFixedSize(self.W * self.scale, h * self.scale)
        self.update()

    def lpos(self, e) -> tuple[int, int]:
        pt = e.position()
        return int(pt.x() // self.scale), int(pt.y() // self.scale)

    def regions(self) -> dict[str, QRect]:
        return {}

    def hit(self, x: int, y: int) -> str | None:
        for name, r in self.regions().items():
            if r.contains(x, y):
                return name
        return None

    def active(self) -> bool:
        return self.shell.isActiveWindow() and self.shell.focused_panel is self

    # ---- painting ----------------------------------------------------------------------------
    def render(self, p: QPainter) -> None:
        raise NotImplementedError

    def overlay(self, p: QPainter) -> None:
        """Drawn after scaling, in device pixels (for TrueType text)."""

    def paintEvent(self, _e) -> None:
        self._buf.fill(Qt.black)
        bp = QPainter(self._buf)
        self.render(bp)
        bp.end()
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QRect(0, 0, self.width(), self.height()), self._buf)
        self.overlay(p)
        p.end()

    # ---- mouse -------------------------------------------------------------------------------
    def click(self, name: str) -> None:
        pass

    def drag(self, name: str, x: int, y: int, phase: str) -> None:
        pass

    def context(self, name: str | None, gpos: QPoint) -> None:
        self.shell.main_menu(gpos)

    def double(self, name: str | None) -> None:
        pass

    def wheel(self, steps: int) -> None:
        self.player.set_volume(self.player.settings["volume"] + 4 * steps)

    def mousePressEvent(self, e) -> None:
        self.shell.focus_panel(self)
        x, y = self.lpos(e)
        name = self.hit(x, y)
        if e.button() == Qt.RightButton:
            self.context(name, e.globalPosition().toPoint())
            return
        if e.button() != Qt.LeftButton:
            return
        if name in self.SLIDERS:
            self.dragging = name
            self.down = name
            self.drag(name, x, y, "press")
        elif name is None or name == "title":
            self.down = None
            self.moving = True
            self.shell.begin_move(e.globalPosition().toPoint())
        else:
            self.down = name
        self.update()

    def mouseMoveEvent(self, e) -> None:
        if self.moving:
            self.shell.move_to(e.globalPosition().toPoint())
            return
        if self.dragging:
            x, y = self.lpos(e)
            self.drag(self.dragging, x, y, "move")
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        x, y = self.lpos(e)
        if self.moving:
            self.moving = False
            self.shell.end_move()
        elif self.dragging:
            name, self.dragging, self.down = self.dragging, None, None
            self.drag(name, x, y, "release")
        elif self.down:
            name, self.down = self.down, None
            if self.hit(x, y) == name:
                self.click(name)
        self.update()

    def mouseDoubleClickEvent(self, e) -> None:
        x, y = self.lpos(e)
        name = self.hit(x, y)
        if name in self.SLIDERS:
            self.mousePressEvent(e)
            return
        self.double(name)

    def wheelEvent(self, e) -> None:
        steps = e.angleDelta().y() // 120 or (1 if e.angleDelta().y() > 0 else -1 if e.angleDelta().y() < 0 else 0)
        if steps:
            self.wheel(steps)
