"""The popup overlay.

A frameless card that appears near the bottom of the primary screen when Black
Voice is listening, shows what it heard and what it answered, and fades out
again. It also carries a text box, so every voice command can be typed instead.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QPushButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .icons import ACCENT, BLACK, GREY, WHITE

log = logging.getLogger(__name__)

CARD_WIDTH = 520
BAR_COUNT = 28

#: Platform plugins that cannot set per-window opacity. Qt prints
#: "This plugin does not support setting window opacity" on every attempt,
#: which floods the journal because the overlay fades on each activation.
#: The fade is decoration, so it is simply skipped there.
_NO_OPACITY_PLATFORMS = ("wayland", "offscreen", "minimal", "vnc", "linuxfb", "eglfs")


def _supports_window_opacity() -> bool:
    name = (QGuiApplication.platformName() or "").lower()
    return not any(p in name for p in _NO_OPACITY_PLATFORMS)


_STATE_LABEL = {
    "idle": "ready",
    "listening": "listening…",
    "thinking": "thinking…",
    "speaking": "speaking",
    "asleep": "asleep",
    "setup": "first run — downloading speech models…",
}


class Waveform(QWidget):
    """A simple level meter drawn as symmetric bars."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._levels: List[float] = [0.0] * BAR_COUNT
        self._active = False

        self._decay = QTimer(self)
        self._decay.setInterval(60)
        self._decay.timeout.connect(self._fade)

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self._decay.start()
        else:
            self._decay.stop()
            self._levels = [0.0] * BAR_COUNT
            self.update()

    def push(self, level: float) -> None:
        # Speech RMS sits well below 1.0, so scale it into something visible.
        scaled = min(1.0, max(0.0, level * 8.0))
        self._levels = self._levels[1:] + [scaled]
        self.update()

    def _fade(self) -> None:
        if not any(self._levels):
            return
        self._levels = [max(0.0, v - 0.06) for v in self._levels]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLACK if self._active else QColor("#D8D8D8"))

        width = self.width() / BAR_COUNT
        bar_width = max(2.0, width * 0.42)
        centre = self.height() / 2
        minimum = 3.0

        for index, level in enumerate(self._levels):
            height = max(minimum, level * (self.height() - 6))
            x = index * width + (width - bar_width) / 2
            painter.drawRoundedRect(
                QRectF(x, centre - height / 2, bar_width, height),
                bar_width / 2,
                bar_width / 2,
            )


class Card(QFrame):
    """White rounded plate that everything sits on."""

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 18, 18)
        painter.fillPath(path, WHITE)
        painter.setPen(QPen(QColor(0, 0, 0, 28), 1.5))
        painter.drawPath(path)


class Overlay(QWidget):
    """The popup itself."""

    submitted = pyqtSignal(str)

    def __init__(self, timeout: float = 8.0, auto_close: bool = False) -> None:
        super().__init__()
        self._timeout_ms = int(timeout * 1000)
        self._auto_close = auto_close

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._build()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.fade_out)

        self._can_fade = _supports_window_opacity()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        if not self._can_fade:
            log.debug(
                "platform %r cannot set window opacity; showing the overlay "
                "without a fade", QGuiApplication.platformName(),
            )

    # -------------------------------------------------------------- layout
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        card = Card()
        card.setFixedWidth(CARD_WIDTH)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(38)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 90))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # Header ----------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(10)

        wordmark = QLabel("BLACK")
        font = QFont()
        font.setPointSize(15)
        font.setWeight(QFont.Weight.ExtraBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.4)
        wordmark.setFont(font)
        wordmark.setStyleSheet(f"color: {BLACK.name()};")
        header.addWidget(wordmark)

        self.state_label = QLabel("ready")
        state_font = QFont()
        state_font.setPointSize(9)
        state_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        self.state_label.setFont(state_font)
        self.state_label.setStyleSheet(f"color: {GREY.name()};")
        header.addWidget(self.state_label)
        header.addStretch(1)

        close = QPushButton("×")
        close.setFixedSize(22, 22)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setToolTip("Close")
        close.setStyleSheet(
            f"""
            QPushButton {{
                border: none; background: transparent;
                color: {GREY.name()}; font-size: 17px;
            }}
            QPushButton:hover {{ color: {BLACK.name()}; }}
            """
        )
        close.clicked.connect(self.dismiss)
        header.addWidget(close)
        layout.addLayout(header)

        # Waveform --------------------------------------------------------
        self.waveform = Waveform()
        layout.addWidget(self.waveform)

        # Transcript ------------------------------------------------------
        self.heard = QLabel("")
        self.heard.setWordWrap(True)
        heard_font = QFont()
        heard_font.setPointSize(11)
        self.heard.setFont(heard_font)
        self.heard.setStyleSheet(f"color: {GREY.name()};")
        self.heard.hide()
        layout.addWidget(self.heard)

        # Reply -----------------------------------------------------------
        self.reply = QLabel("")
        self.reply.setWordWrap(True)
        self.reply.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        reply_font = QFont()
        reply_font.setPointSize(12)
        self.reply.setFont(reply_font)
        self.reply.setStyleSheet(f"color: {BLACK.name()};")
        self.reply.hide()
        layout.addWidget(self.reply)

        # Input -----------------------------------------------------------
        self.input = QLineEdit()
        self.input.setPlaceholderText("or type a command…")
        self.input.setStyleSheet(
            f"""
            QLineEdit {{
                border: none;
                border-top: 1px solid #E6E6E6;
                padding: 9px 2px 2px 2px;
                font-size: 12px;
                color: {ACCENT.name()};
                background: transparent;
            }}
            """
        )
        self.input.returnPressed.connect(self._on_submit)
        layout.addWidget(self.input)

        self.setFixedWidth(CARD_WIDTH + 32)

    # ------------------------------------------------------------ actions
    def _on_submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.show_heard(text)
        self.submitted.emit(text)

    def position(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(
            area.center().x() - self.width() // 2,
            area.bottom() - self.height() - 90,
        )

    def pop(self) -> None:
        """Show the card (or restart its hide timer if already visible)."""
        self.adjustSize()
        self.position()
        if not self.isVisible():
            if self._can_fade:
                self.setWindowOpacity(0.0)
                self.show()
                self._fade.stop()
                self._fade.setStartValue(0.0)
                self._fade.setEndValue(1.0)
                self._fade.start()
            else:
                self.show()
        self._hide_timer.stop()

    def fade_out(self) -> None:
        if not self.isVisible():
            return
        if not self._can_fade:
            self.hide()
            return
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        try:
            self._fade.finished.disconnect()
        except TypeError:
            pass
        self._fade.finished.connect(self.hide)
        self._fade.start()

    def arm_hide(self) -> None:
        """Start the automatic close, if the user asked for one at all."""
        if not self._auto_close or self._timeout_ms <= 0:
            return
        self._hide_timer.start(self._timeout_ms)

    def dismiss(self) -> None:
        """Close the card now, whatever it was doing."""
        self._hide_timer.stop()
        self.fade_out()

    # ------------------------------------------------------------ updates
    def show_state(self, state: str) -> None:
        self.state_label.setText(_STATE_LABEL.get(state, state))
        listening = state == "listening"
        self.waveform.set_active(listening)
        if listening:
            self.heard.setText("")
            self.heard.hide()
            self.reply.hide()
            self.pop()
        elif state == "setup":
            # The first-run download takes a while; keep the card up so the
            # user can see why nothing is responding yet.
            self.pop()
        elif state in {"idle", "asleep"}:
            self.arm_hide()

    def show_level(self, level: float) -> None:
        self.waveform.push(level)

    def show_heard(self, text: str, partial: bool = False) -> None:
        if not text:
            return
        self.heard.setText(f"“{text}”" + (" …" if partial else ""))
        self.heard.show()
        self.pop()

    def show_reply(self, text: str, ok: bool = True) -> None:
        if not text:
            return
        self.reply.setText(text)
        self.reply.setStyleSheet(
            f"color: {BLACK.name() if ok else '#B3261E'};"
        )
        self.reply.show()
        self.pop()
        # Deliberately not arming the close here. The engine is very likely
        # still speaking this reply; the timer starts when it returns to idle.

    def focus_input(self) -> None:
        self.pop()
        self.activateWindow()
        self.raise_()
        self.input.setFocus()
        self._hide_timer.stop()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.fade_out()
            return
        super().keyPressEvent(event)
