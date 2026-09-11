"""The Black Voice mark, drawn with QPainter.

Painting the icon instead of shipping a PNG keeps it crisp on every HiDPI scale
and avoids depending on PyQt6's SVG module. The shape matches ``assets/logo.svg``:
a white plate with a black waveform.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

WHITE = QColor("#FFFFFF")
BLACK = QColor("#0A0A0A")
GREY = QColor("#6B6B6B")
ACCENT = QColor("#1F1F1F")

#: relative bar heights of the waveform, as a fraction of the plate
_BARS = (0.30, 0.62, 0.92, 0.52)


def _paint_mark(pixmap: QPixmap, plate: QColor, ink: QColor) -> None:
    size = pixmap.width()
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    radius = size * 0.22
    painter.setBrush(plate)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    painter.setBrush(ink)
    bar_width = size * 0.085
    gap = size * 0.055
    total = len(_BARS) * bar_width + (len(_BARS) - 1) * gap
    x = (size - total) / 2

    for fraction in _BARS:
        height = size * 0.62 * fraction
        y = (size - height) / 2
        painter.drawRoundedRect(
            QRectF(x, y, bar_width, height), bar_width / 2, bar_width / 2
        )
        x += bar_width + gap

    painter.end()


def mark_pixmap(size: int = 256, listening: bool = False) -> QPixmap:
    """The plate mark. While listening the plate inverts to black."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if listening:
        _paint_mark(pixmap, BLACK, WHITE)
    else:
        _paint_mark(pixmap, WHITE, BLACK)
    return pixmap


def tray_icon(listening: bool = False) -> QIcon:
    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(mark_pixmap(size, listening))
    return icon


def app_icon() -> QIcon:
    return tray_icon(listening=False)
