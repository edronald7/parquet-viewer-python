"""Centered "please wait" overlay shown during long operations.

A semi-transparent layer covers its parent widget (blocking clicks on it)
and shows a card with a message, an animated progress bar, the elapsed
time and an optional Cancel button (also Esc). It only appears if the operation lasts
longer than a short delay, so quick operations don't flicker.
"""

import time
from typing import Callable, Optional

from PyQt5 import QtWidgets
from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPalette


class BusyOverlay(QtWidgets.QWidget):
    """Overlay covering *parent* with a centered progress card."""

    SHOW_DELAY_MS = 300

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.hide()
        self.setFocusPolicy(Qt.StrongFocus)  # keep key presses off the UI below
        parent.installEventFilter(self)

        self._card = QtWidgets.QFrame(self)
        self._card.setObjectName("busyCard")
        self._card.setFixedWidth(380)
        self._card.setAutoFillBackground(True)
        self._card.setFrameShape(QtWidgets.QFrame.StyledPanel)
        pal = self._card.palette()
        pal.setColor(QPalette.Window, pal.color(QPalette.Base))
        self._card.setPalette(pal)

        layout = QtWidgets.QVBoxLayout(self._card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        self._title = QtWidgets.QLabel()
        font = self._title.font()
        font.setPointSizeF(font.pointSizeF() * 1.2)
        font.setBold(True)
        self._title.setFont(font)
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._detail = QtWidgets.QLabel()
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        self._bar = QtWidgets.QProgressBar()
        self._bar.setRange(0, 0)  # indeterminate (animated)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)

        bottom = QtWidgets.QHBoxLayout()
        self._elapsed = QtWidgets.QLabel()
        bottom.addWidget(self._elapsed)
        bottom.addStretch()
        self._btn_cancel = QtWidgets.QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self._on_cancel)
        bottom.addWidget(self._btn_cancel)
        layout.addLayout(bottom)

        self._on_cancel_cb: Optional[Callable[[], None]] = None
        self._start = 0.0
        self._previous_focus: Optional[QtWidgets.QWidget] = None

        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._reveal)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._update_elapsed)

    # --- public API ----------------------------------------------------------

    def start(self, title: str, detail: str = "",
              on_cancel: Optional[Callable[[], None]] = None) -> None:
        """Show the overlay (after a short delay) with the given texts.

        If *on_cancel* is given a Cancel button calls it and hides the
        overlay.
        """
        self._title.setText(title)
        self._detail.setText(detail)
        self._detail.setVisible(bool(detail))
        self._on_cancel_cb = on_cancel
        self._btn_cancel.setVisible(on_cancel is not None)
        self._bar.setRange(0, 0)  # indeterminate until set_progress()
        self._start = time.monotonic()
        self._update_elapsed()
        if not self.isVisible():
            self._show_timer.start(self.SHOW_DELAY_MS)

    def set_progress(self, percent: int) -> None:
        """Switch the bar to a determinate 0-100 % value."""
        self._bar.setRange(0, 100)
        self._bar.setValue(percent)

    def stop(self) -> None:
        """Hide the overlay (or prevent it from appearing)."""
        self._show_timer.stop()
        self._tick_timer.stop()
        self._on_cancel_cb = None
        if self.isVisible():
            self.hide()
            if self._previous_focus is not None:
                self._previous_focus.setFocus()
        self._previous_focus = None

    # --- internals -----------------------------------------------------------

    def _reveal(self) -> None:
        self._previous_focus = QtWidgets.QApplication.focusWidget()
        self._fit_parent()
        self.show()
        self.raise_()
        self.setFocus()
        self._tick_timer.start()

    def _on_cancel(self) -> None:
        callback = self._on_cancel_cb
        self.stop()
        if callback is not None:
            callback()

    def _update_elapsed(self) -> None:
        seconds = int(time.monotonic() - self._start)
        minutes, seconds = divmod(seconds, 60)
        text = f"{minutes} min {seconds:02d} s" if minutes else f"{seconds} s"
        self._elapsed.setText(f"Elapsed: {text}")

    def _fit_parent(self) -> None:
        self.setGeometry(self.parentWidget().rect())
        self._card.adjustSize()
        card = self._card.rect()
        card.moveCenter(self.rect().center())
        self._card.move(card.topLeft())

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.parentWidget() and event.type() == QEvent.Resize \
                and self.isVisible():
            self._fit_parent()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape and self._on_cancel_cb is not None:
            self._on_cancel()
        event.accept()  # swallow everything else while busy

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
