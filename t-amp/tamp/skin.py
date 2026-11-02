"""The classic look, drawn in code: palette, pixel fonts, bevels, buttons, sliders.

Everything here paints in *skin pixels* (the 275-pixel-wide Winamp grid). Panels render
at 1x and are blown up with nearest-neighbour scaling, which is exactly what Winamp's
double-size mode did. No bitmap from any Winamp skin is used.
"""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter

C = QColor

# ---- palette (measured off the 2.9x base skin) -------------------------------------------
BG_DARK = C("#191926")
BG_MID = C("#2c2c45")
BG_LIGHT = C("#39395a")
FRAME_LIGHT = C("#5c5c63")
FRAME_DARK = C("#13131e")
LCD = C("#000000")
LCD_DOT = C("#181829")
LCD_EDGE_LIGHT = C("#74738a")
LCD_EDGE_DARK = C("#161622")
GREEN = C("#00f800")
GREEN_DIM = C("#0d3a12")
TEXT_GREEN = C("#00e000")
WHITE = C("#ffffff")
LABEL = C("#e8e8f0")
GOLD = C("#e0b33a")

BTN_FACE = C("#bdced6")
BTN_HI = C("#efffff")
BTN_HI2 = C("#adb5c6")
BTN_SH1 = C("#7b8494")
BTN_SH2 = C("#4a5a6b")
BTN_SH3 = C("#2b2b44")
BTN_ICON = C("#4a5a6b")
BTN_ICON_FILL = C("#a6b5c4")
BTN_FACE_DOWN = C("#8e9eae")

LED_ON = C("#00d600")
LED_OFF = C("#1c3b26")

GRIP_ACTIVE = (C("#1e1f25"), C("#ecce7a"), C("#ffffff"), C("#45413c"), C("#a3946a"), C("#ecce7a"), C("#25262c"))
GRIP_INACTIVE = (C("#1f1f22"), C("#86774d"), C("#909090"), C("#34302c"), C("#625a45"), C("#86774d"), C("#222326"))

# playlist (pledit.txt defaults)
PL_NORMAL = C("#00ff00")
PL_CURRENT = C("#ffffff")
PL_BG = C("#000000")
PL_SELECTED = C("#0000c6")

# viscolor.txt defaults: 0 bg, 1 dots, 2..17 analyser top->bottom, 18..22 scope, 23 peaks
VIS = [C(x) for x in (
    "#000000", "#181829",
    "#ef3110", "#ce2910", "#d65a00", "#d66600", "#d67300", "#c67b08", "#dea518", "#d6b521",
    "#bdde29", "#94de21", "#29ce10", "#32be10", "#39b510", "#319c08", "#299400", "#188408",
    "#ffffff", "#d6d6de", "#b5bdbd", "#a0aaaf", "#949ca5", "#969696",
)]


# ---- pixel font ---------------------------------------------------------------------------
# 4x6 glyphs in a 5x6 cell. Drawn for this project.
_GLYPHS = {
    "A": [".##.", "#..#", "#..#", "####", "#..#", "#..#"],
    "B": ["###.", "#..#", "###.", "#..#", "#..#", "###."],
    "C": [".###", "#...", "#...", "#...", "#...", ".###"],
    "D": ["###.", "#..#", "#..#", "#..#", "#..#", "###."],
    "E": ["####", "#...", "###.", "#...", "#...", "####"],
    "F": ["####", "#...", "###.", "#...", "#...", "#..."],
    "G": [".###", "#...", "#...", "#.##", "#..#", ".###"],
    "H": ["#..#", "#..#", "####", "#..#", "#..#", "#..#"],
    "I": ["###.", ".#..", ".#..", ".#..", ".#..", "###."],
    "J": ["..##", "...#", "...#", "...#", "#..#", ".##."],
    "K": ["#..#", "#.#.", "##..", "#.#.", "#..#", "#..#"],
    "L": ["#...", "#...", "#...", "#...", "#...", "####"],
    "M": ["#..#", "####", "####", "#..#", "#..#", "#..#"],
    "N": ["#..#", "##.#", "#.##", "#..#", "#..#", "#..#"],
    "O": [".##.", "#..#", "#..#", "#..#", "#..#", ".##."],
    "P": ["###.", "#..#", "#..#", "###.", "#...", "#..."],
    "Q": [".##.", "#..#", "#..#", "#..#", "#.#.", ".#.#"],
    "R": ["###.", "#..#", "#..#", "###.", "#.#.", "#..#"],
    "S": [".###", "#...", ".##.", "...#", "...#", "###."],
    "T": ["###.", ".#..", ".#..", ".#..", ".#..", ".#.."],
    "U": ["#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    "V": ["#..#", "#..#", "#..#", "#..#", ".##.", ".##."],
    "W": ["#..#", "#..#", "#..#", "####", "####", "#..#"],
    "X": ["#..#", "#..#", ".##.", ".##.", "#..#", "#..#"],
    "Y": ["#..#", "#..#", ".##.", ".##.", ".##.", ".##."],
    "Z": ["####", "...#", "..#.", ".#..", "#...", "####"],
    "0": [".##.", "#..#", "#.##", "##.#", "#..#", ".##."],
    "1": [".#..", "##..", ".#..", ".#..", ".#..", "###."],
    "2": [".##.", "#..#", "..#.", ".#..", "#...", "####"],
    "3": ["###.", "...#", ".##.", "...#", "...#", "###."],
    "4": ["#..#", "#..#", "####", "...#", "...#", "...#"],
    "5": ["####", "#...", "###.", "...#", "...#", "###."],
    "6": [".##.", "#...", "###.", "#..#", "#..#", ".##."],
    "7": ["####", "...#", "..#.", ".#..", ".#..", ".#.."],
    "8": [".##.", "#..#", ".##.", "#..#", "#..#", ".##."],
    "9": [".##.", "#..#", "#..#", ".###", "...#", ".##."],
    " ": ["....", "....", "....", "....", "....", "...."],
    ".": ["....", "....", "....", "....", "....", ".#.."],
    ",": ["....", "....", "....", "....", ".#..", "#..."],
    ":": ["....", ".#..", "....", "....", ".#..", "...."],
    ";": ["....", ".#..", "....", "....", ".#..", "#..."],
    "-": ["....", "....", "....", "###.", "....", "...."],
    "_": ["....", "....", "....", "....", "....", "####"],
    "'": [".#..", ".#..", "....", "....", "....", "...."],
    '"': ["#.#.", "#.#.", "....", "....", "....", "...."],
    "(": ["..#.", ".#..", ".#..", ".#..", ".#..", "..#."],
    ")": [".#..", "..#.", "..#.", "..#.", "..#.", ".#.."],
    "[": [".##.", ".#..", ".#..", ".#..", ".#..", ".##."],
    "]": [".##.", "..#.", "..#.", "..#.", "..#.", ".##."],
    "/": ["...#", "..#.", "..#.", ".#..", ".#..", "#..."],
    "\\": ["#...", ".#..", ".#..", "..#.", "..#.", "...#"],
    "!": [".#..", ".#..", ".#..", ".#..", "....", ".#.."],
    "?": [".##.", "#..#", "..#.", ".#..", "....", ".#.."],
    "&": [".#..", "#.#.", ".#..", "##.#", "#.#.", ".#.#"],
    "+": ["....", ".#..", "###.", ".#..", "....", "...."],
    "=": ["....", "###.", "....", "###.", "....", "...."],
    "#": ["#.#.", "####", "#.#.", "#.#.", "####", "#.#."],
    "%": ["#..#", "...#", "..#.", ".#..", "#...", "#..#"],
    "@": [".##.", "#..#", "#.##", "#.##", "#...", ".###"],
    "*": ["....", "#.#.", ".#..", "#.#.", "....", "...."],
    "<": ["..#.", ".#..", "#...", ".#..", "..#.", "...."],
    ">": ["#...", ".#..", "..#.", ".#..", "#...", "...."],
    "|": [".#..", ".#..", ".#..", ".#..", ".#..", ".#.."],
    "~": ["....", ".#.#", "#.#.", "....", "....", "...."],
    "$": [".###", "#.#.", ".##.", "..##", "###.", "..#."],
    "^": [".#..", "#.#.", "....", "....", "....", "...."],
}
CHAR_W, CHAR_H = 5, 6
_glyph_cache: dict[tuple[str, int], QImage] = {}


def _glyph(ch: str, color: QColor) -> QImage:
    key = (ch, color.rgba())
    img = _glyph_cache.get(key)
    if img is None:
        img = QImage(CHAR_W, CHAR_H, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        for y, row in enumerate(_GLYPHS.get(ch, _GLYPHS["?"])):
            for x, bit in enumerate(row):
                if bit == "#":
                    img.setPixelColor(x, y, color)
        _glyph_cache[key] = img
    return img


def ascii_fold(text: str) -> str:
    """'Beyoncé' -> 'BEYONCE'; anything still outside the font survives unchanged."""
    text = text.replace("…", "...").replace("–", "-").replace("—", "-").replace("’", "'")
    text = text.replace("‘", "'").replace("“", '"').replace("”", '"').replace("·", "-")
    out = []
    for ch in text:
        up = ch.upper()
        if up in _GLYPHS:
            out.append(up)
            continue
        base = unicodedata.normalize("NFKD", ch)
        base = "".join(b for b in base if not unicodedata.combining(b)).upper()
        out.append(base if base and all(b in _GLYPHS for b in base) else ch)
    return "".join(out)


def bitmap_ok(text: str) -> bool:
    """True when the whole string can be shown in the pixel font (else use a TrueType face)."""
    return all(ch in _GLYPHS for ch in ascii_fold(text))


def text_width(text: str) -> int:
    return len(ascii_fold(text)) * CHAR_W


def draw_text(p: QPainter, x: int, y: int, text: str, color: QColor = TEXT_GREEN) -> int:
    for ch in ascii_fold(text):
        p.drawImage(x, y, _glyph(ch, color))
        x += CHAR_W
    return x


def draw_text_bold(p: QPainter, x: int, y: int, text: str, color: QColor, shadow: QColor | None = None) -> int:
    """Title-bar lettering: the pixel font struck twice, one pixel apart."""
    if shadow is not None:
        draw_text_bold(p, x + 1, y + 1, text, shadow)
    for ch in ascii_fold(text):
        g = _glyph(ch, color)
        p.drawImage(x, y, g)
        p.drawImage(x + 1, y, g)
        x += CHAR_W + 1
    return x


def bold_width(text: str) -> int:
    return len(ascii_fold(text)) * (CHAR_W + 1)


# ---- seven-segment time digits (9x13) -----------------------------------------------------
_SEGS = {  # a b c d e f g = top, top-right, bottom-right, bottom, bottom-left, top-left, middle
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd",
    "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g", " ": "",
}


def draw_digit(p: QPainter, x: int, y: int, ch: str, color: QColor = GREEN) -> None:
    segs = _SEGS.get(ch, "")
    f = p.fillRect
    if "a" in segs:
        f(x + 1, y, 7, 1, color)
    if "b" in segs:
        f(x + 8, y + 1, 1, 5, color)
    if "c" in segs:
        f(x + 8, y + 7, 1, 5, color)
    if "d" in segs:
        f(x + 1, y + 12, 7, 1, color)
    if "e" in segs:
        f(x, y + 7, 1, 5, color)
    if "f" in segs:
        f(x, y + 1, 1, 5, color)
    if "g" in segs:
        f(x + 1, y + 6, 7, 1, color)


# ---- primitives ---------------------------------------------------------------------------
def hline(p: QPainter, x1: int, x2: int, y: int, c: QColor) -> None:
    p.fillRect(x1, y, x2 - x1 + 1, 1, c)


def vline(p: QPainter, x: int, y1: int, y2: int, c: QColor) -> None:
    p.fillRect(x, y1, 1, y2 - y1 + 1, c)


def outline(p: QPainter, x: int, y: int, w: int, h: int, c: QColor) -> None:
    hline(p, x, x + w - 1, y, c)
    hline(p, x, x + w - 1, y + h - 1, c)
    vline(p, x, y, y + h - 1, c)
    vline(p, x + w - 1, y, y + h - 1, c)


def inset(p: QPainter, x: int, y: int, w: int, h: int, fill: QColor | None = LCD,
          dark: QColor = LCD_EDGE_DARK, light: QColor = LCD_EDGE_LIGHT) -> None:
    """A recessed box: dark top/left edge, light bottom/right edge, `fill` inside."""
    if fill is not None:
        p.fillRect(x, y, w, h, fill)
    hline(p, x - 1, x + w - 1, y - 1, dark)
    vline(p, x - 1, y - 1, y + h - 1, dark)
    hline(p, x - 1, x + w, y + h, light)
    vline(p, x + w, y - 1, y + h, light)


def metal(p: QPainter, x: int, y: int, w: int, h: int) -> None:
    """The brushed blue-grey body: dark at the edges, lightest a little right of centre."""
    g = QLinearGradient(QPointF(x, 0), QPointF(x + w, 0))
    g.setColorAt(0.0, C("#161622"))
    g.setColorAt(0.08, C("#1d1e2e"))
    g.setColorAt(0.35, C("#2e2d48"))
    g.setColorAt(0.58, C("#39395a"))
    g.setColorAt(0.66, C("#39395a"))
    g.setColorAt(0.9, C("#2a2942"))
    g.setColorAt(1.0, C("#1c1b2b"))
    p.fillRect(x, y, w, h, g)


def window_frame(p: QPainter, w: int, h: int) -> None:
    """Body + the classic bevel: light line and dark band on the left, inner frame with a shadow."""
    metal(p, 0, 0, w, h)
    vline(p, 0, 0, h - 1, C("#101019"))
    vline(p, 1, 0, h - 1, FRAME_LIGHT)
    p.fillRect(2, 14, 4, h - 15, FRAME_DARK)
    vline(p, w - 1, 0, h - 1, C("#171724"))
    hline(p, 0, w - 1, h - 1, C("#28283f"))
    outline(p, 6, 14, w - 9, h - 17, FRAME_LIGHT)
    p.fillRect(w - 6, 15, 2, h - 19, C("#181825"))
    p.fillRect(7, h - 6, w - 13, 2, C("#28283f"))


def lcd_dots(p: QPainter, x: int, y: int, w: int, h: int) -> None:
    p.fillRect(x, y, w, h, LCD)
    for yy in range(y + 1, y + h, 2):
        for xx in range(x + 1, x + w, 2):
            p.fillRect(xx, yy, 1, 1, LCD_DOT)


# ---- buttons ------------------------------------------------------------------------------
def button(p: QPainter, x: int, y: int, w: int, h: int, down: bool = False) -> None:
    if not down:
        p.fillRect(x, y, w, h, BTN_FACE)
        hline(p, x, x + w - 1, y, BTN_HI2)
        vline(p, x, y, y + h - 1, BTN_HI2)
        hline(p, x + 1, x + w - 3, y + 1, BTN_HI)
        vline(p, x + 1, y + 1, y + h - 3, BTN_HI)
        hline(p, x + 1, x + w - 1, y + h - 1, BTN_SH3)
        vline(p, x + w - 1, y, y + h - 1, BTN_SH3)
        hline(p, x + 2, x + w - 2, y + h - 2, BTN_SH2)
        vline(p, x + w - 2, y + 1, y + h - 2, BTN_SH2)
        hline(p, x + 2, x + w - 3, y + h - 3, BTN_SH1)
        vline(p, x + w - 3, y + 2, y + h - 3, BTN_SH1)
    else:
        p.fillRect(x, y, w, h, BTN_FACE_DOWN)
        outline(p, x, y, w, h, C("#10101a"))
        hline(p, x + 1, x + w - 2, y + 1, BTN_SH2)
        vline(p, x + 1, y + 1, y + h - 2, BTN_SH2)
        hline(p, x + 2, x + w - 2, y + h - 2, BTN_FACE)
        vline(p, x + w - 2, y + 2, y + h - 2, BTN_FACE)


# Transport icons. d = outline, m = fill, w = highlight.
ICONS = {
    "prev": ["dd....d", "dw...dd", "dw..dwd", "dw.dwmd", "dwdwmmd", "dw.dwmd", "dw..dwd", "dw...dd", "dd....d"],
    "play": ["d.....", "dd....", "dwd...", "dwmd..", "dwmmd.", "dwmd..", "dwd...", "dd....", "d....."],
    "pause": ["ddd.ddd", "dwd.dwd", "dwd.dwd", "dwd.dwd", "dwd.dwd", "dwd.dwd", "dwd.dwd", "dwd.dwd", "ddd.ddd"],
    "stop": ["ddddddddd", "dwwwwwwwd", "dwmmmmmmd", "dwmmmmmmd", "dwmmmmmmd", "dwmmmmmmd", "dwmmmmmmd",
             "dwmmmmmmd", "ddddddddd"],
    "next": ["d....dd", "dd...wd", "dwd..wd", "dwmd.wd", "dwmmdwd", "dwmd.wd", "dwd..wd", "dd...wd", "d....dd"],
    "eject": ["....d....", "...dwd...", "..dwmmd..", ".dwmmmmd.", "ddddddddd", ".........",
              "ddddddddd", "dwwwwwwwd", "ddddddddd"],
}


def icon(p: QPainter, name: str, x: int, y: int, down: bool = False) -> None:
    rows = ICONS[name]
    cols = {"d": C("#1f2a38") if down else BTN_ICON,
            "m": C("#7d8d9c") if down else BTN_ICON_FILL,
            "w": C("#c3d0d8") if down else BTN_HI}
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            if ch in cols:
                p.fillRect(x + xx, y + yy, 1, 1, cols[ch])


def icon_button(p: QPainter, name: str, x: int, y: int, w: int, h: int, down: bool = False) -> None:
    button(p, x, y, w, h, down)
    rows = ICONS[name]
    iw, ih = len(rows[0]), len(rows)
    off = 1 if down else 0
    icon(p, name, x + (w - iw) // 2 + off, y + (h - ih) // 2 + off - (1 if name != "eject" else 0) + 1, down)


def led_button(p: QPainter, x: int, y: int, w: int, h: int, label: str, lit: bool,
               down: bool = False, led: bool = True) -> None:
    button(p, x, y, w, h, down)
    off = 1 if down else 0
    tx = x + 3 + off
    if led:
        p.fillRect(x + 3 + off, y + 3 + off, 5, 4, LED_ON if lit else LED_OFF)
        hline(p, x + 3 + off, x + 7 + off, y + 2 + off, BTN_SH2)
        vline(p, x + 2 + off, y + 2 + off, y + 6 + off, BTN_SH2)
        tx = x + 10 + off
    else:
        tx = x + (w - text_width(label)) // 2 + off
    draw_text(p, tx, y + (h - CHAR_H) // 2 + off, label, C("#2f374d"))


def repeat_glyph(p: QPainter, x: int, y: int, c: QColor) -> None:
    """The loop arrow on the repeat button."""
    hline(p, x + 1, x + 9, y, c)
    vline(p, x + 10, y + 1, y + 3, c)
    hline(p, x + 1, x + 9, y + 4, c)
    vline(p, x, y + 1, y + 3, c)
    p.fillRect(x + 2, y + 3, 1, 3, c)
    p.fillRect(x + 1, y + 4, 3, 1, c)


# ---- sliders ------------------------------------------------------------------------------
def level_color(t: float) -> QColor:
    """0 -> green, 0.5 -> yellow, 1 -> red: the volume / EQ bar colour ramp."""
    t = max(0.0, min(1.0, t))
    stops = [(0.0, (0x1c, 0xb0, 0x10)), (0.45, (0xb8, 0xd8, 0x20)), (0.62, (0xe0, 0xc0, 0x20)),
             (0.8, (0xe0, 0x80, 0x20)), (1.0, (0xd8, 0x20, 0x10))]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            return C(*(round(a + (b - a) * k) for a, b in zip(c0, c1)))
    return C(*stops[-1][1])


def pill(p: QPainter, x: int, y: int, w: int, color: QColor) -> None:
    """Horizontal rounded bar, 5 px tall, shaded like a tube."""
    dark = color.darker(170)
    light = color.lighter(135)
    hline(p, x + 1, x + w - 2, y, C("#0f0f17"))
    hline(p, x, x + w - 1, y + 1, dark)
    hline(p, x, x + w - 1, y + 2, light)
    hline(p, x, x + w - 1, y + 3, color)
    hline(p, x + 1, x + w - 2, y + 4, dark)
    hline(p, x + 1, x + w - 2, y + 5, C("#5a5a70"))


def vpill(p: QPainter, x: int, y: int, h: int, color: QColor) -> None:
    """Vertical rounded bar, 5 px wide (EQ sliders)."""
    dark = color.darker(170)
    light = color.lighter(135)
    vline(p, x, y + 1, y + h - 2, C("#0f0f17"))
    vline(p, x + 1, y, y + h - 1, dark)
    vline(p, x + 2, y, y + h - 1, light)
    vline(p, x + 3, y, y + h - 1, color)
    vline(p, x + 4, y + 1, y + h - 2, dark)
    vline(p, x + 5, y + 1, y + h - 2, C("#5a5a70"))


def grip_thumb(p: QPainter, x: int, y: int, w: int, h: int, down: bool = False) -> None:
    """Volume / balance knob: a small raised block with three grip lines."""
    if down:
        p.fillRect(x, y, w, h, C("#e8f3f5"))
        outline(p, x, y, w, h, C("#0b0f16"))
    else:
        p.fillRect(x, y, w, h, C("#adbcc4"))
        outline(p, x, y, w, h, C("#0b0f16"))
        hline(p, x + 1, x + w - 2, y + 1, C("#dae7ea"))
        vline(p, x + 1, y + 1, y + h - 2, C("#dae7ea"))
        hline(p, x + 1, x + w - 2, y + h - 2, BTN_SH1)
        vline(p, x + w - 2, y + 1, y + h - 2, BTN_SH1)
    cx = x + w // 2
    for dx in (-2, 0, 2):
        vline(p, cx + dx, y + 3, y + h - 4, C("#2b2b44"))


def eq_thumb(p: QPainter, x: int, y: int, down: bool = False) -> None:
    w = h = 11
    p.fillRect(x, y, w, h, C("#0b0f16") if down else C("#adbcc4"))
    outline(p, x, y, w, h, C("#0b0f16"))
    if not down:
        hline(p, x + 1, x + w - 2, y + 1, C("#dae7ea"))
        vline(p, x + 1, y + 1, y + h - 2, C("#dae7ea"))
    c = C("#e8f3f5") if down else C("#2b2b44")
    for dy in (3, 5, 7):
        hline(p, x + 3, x + 7, y + dy, c)


def position_thumb(p: QPainter, x: int, y: int, down: bool = False) -> None:
    """The gold seek knob, 29x10."""
    w, h = 29, 10
    body = C("#8d753a") if not down else C("#6c561f")
    p.fillRect(x, y, w, h, body)
    hline(p, x, x + w - 1, y, C("#dbcb9e"))
    vline(p, x, y, y + h - 1, C("#dbcb9e"))
    hline(p, x, x + w - 1, y + h - 1, C("#090202"))
    vline(p, x + w - 1, y, y + h - 1, C("#090202"))
    outline(p, x + 3, y + 2, w - 6, h - 4, C("#f4eac7") if not down else C("#c9b88a"))
    hline(p, x + 4, x + w - 5, y + 3, C("#f5f5f5") if not down else C("#d6c79a"))
    p.fillRect(x + 4, y + 4, w - 8, h - 7, C("#755b22") if not down else C("#5a4516"))


# ---- title bars ---------------------------------------------------------------------------
def _grip(p: QPainter, x1: int, x2: int, active: bool) -> None:
    if x2 - x1 < 4:
        return
    rows = GRIP_ACTIVE if active else GRIP_INACTIVE
    for i, col in enumerate(rows):
        hline(p, x1 + (1 if i in (0, 6) else 0), x2 - (1 if i in (0, 6) else 0), 4 + i, col)
    vline(p, x1 - 1, 5, 9, rows[0])
    vline(p, x2 + 1, 5, 9, rows[0])


def titlebar_button(p: QPainter, x: int, y: int, kind: str, active: bool, down: bool = False) -> None:
    """9x9 caption button: menu, min, shade, close."""
    if kind == "menu":
        c = C("#ecce7a") if active else C("#86774d")
        for (dx, dy) in ((1, 4), (2, 3), (3, 2), (3, 3), (4, 4), (4, 5), (5, 6), (6, 5), (6, 4), (7, 3), (2, 4)):
            p.fillRect(x + dx, y + dy, 1, 1, c.darker(140) if down else c)
        return
    top = C("#f0dca0") if active else C("#a8a8b0")
    bot = C("#6b5a32") if active else C("#55555f")
    if down:
        top, bot = bot, top
    g = QLinearGradient(QPointF(0, y), QPointF(0, y + 9))
    g.setColorAt(0, top)
    g.setColorAt(1, bot)
    p.fillRect(x + 1, y + 1, 7, 7, g)
    outline(p, x, y, 9, 9, C("#1a1a24"))
    ink = C("#1a1a24")
    if kind == "min":
        hline(p, x + 2, x + 6, y + 6, ink)
    elif kind == "shade":
        hline(p, x + 2, x + 6, y + 2, ink)
        hline(p, x + 2, x + 6, y + 6, ink)
    elif kind == "close":
        for i in range(5):
            p.fillRect(x + 2 + i, y + 2 + i, 1, 1, ink)
            p.fillRect(x + 6 - i, y + 2 + i, 1, 1, ink)


def titlebar(p: QPainter, w: int, title: str, active: bool, buttons=("menu", "min", "shade", "close"),
             down: str | None = None) -> dict[str, QRect]:
    """Draws the 14-px caption strip; returns the hit rects of its buttons."""
    p.fillRect(0, 0, w, 14, C("#1a1a28"))
    metal(p, 0, 1, w, 12)
    hline(p, 0, w - 1, 0, C("#0f0f17"))
    hline(p, 0, w - 1, 1, C("#5d5d67") if active else C("#4a4a52"))
    hline(p, 0, w - 1, 12, C("#101019"))
    hline(p, 0, w - 1, 13, C("#101019"))
    vline(p, 0, 0, 13, C("#0f0f17"))
    vline(p, w - 1, 0, 13, C("#0f0f17"))
    rects: dict[str, QRect] = {}
    right = w - 2
    for kind in reversed([b for b in buttons if b != "menu"]):
        bx = right - 9
        rects[kind] = QRect(bx, 3, 9, 9)
        right = bx - 1
    left = 4
    if "menu" in buttons:
        rects["menu"] = QRect(6, 3, 9, 9)
        left = 18
    for kind, r in rects.items():
        titlebar_button(p, r.x(), r.y(), kind, active, down == kind)
    tw = bold_width(title)
    tx = (w - tw) // 2
    _grip(p, left + 2, tx - 5, active)
    _grip(p, tx + tw + 3, right - 4, active)
    fg = WHITE if active else C("#9a9aa8")
    draw_text_bold(p, tx, 4, title, fg, C("#1a1a28"))
    return rects
