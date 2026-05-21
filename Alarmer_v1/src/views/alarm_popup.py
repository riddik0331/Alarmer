"""
Alarm popup — full-screen attention dialog shown when an alarm fires.

Displays a top-most modal dialog with the alarm title, current time,
a large red dismiss button, and snooze buttons for 5, 10 and 15 minutes.
Features pulsing background animation and a scale-in appearance effect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Signal, Qt
from PySide6.QtGui import QCloseEvent, QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from src.models.alarm_model import Alarm

from src.utils.helpers import center_on_screen


class AlarmPopup(QDialog):
    """Full-attention dialog shown when an alarm triggers.

    Displays the alarm title, current time, a dismiss button and
    snooze options. Plays a pulsing background animation and a
    scale-in entrance effect.

    Signals:
        dismiss(alarm_id: str):
            Emitted when the user presses the dismiss button.
        snooze(alarm_id: str, minutes: int):
            Emitted when the user selects a snooze duration.
    """

    dismissed = Signal(str)  # alarm_id
    snoozed = Signal(str, int)  # alarm_id, minutes

    # Aliases for spec compatibility
    dismiss = dismissed
    snooze = snoozed

    # Background colour property for animation
    _bg_color: QColor = QColor("#1a1a2e")

    def __init__(self, alarm: Alarm, parent: QWidget | None = None) -> None:
        """Initialise the popup dialog for the given alarm.

        Args:
            alarm: The triggered Alarm instance.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._alarm_id: str = alarm.id
        self._alarm_title: str = alarm.title or "⏰ БУДИЛЬНИК!"

        self._setup_window()
        self._setup_ui(alarm)
        self._setup_animations()

    # ---- Public API -------------------------------------------------------

    def start_animation(self) -> None:
        """Start the pulsing background and blinking title animations."""
        self._start_pulse_animation()
        self._start_scale_animation()
        self._start_blink_animation()

    def stop_animation(self) -> None:
        """Stop all running animations."""
        if self._pulse_anim is not None:
            self._pulse_anim.stop()
            self._pulse_anim.deleteLater()
            self._pulse_anim = None

        if self._scale_anim is not None:
            self._scale_anim.stop()
            self._scale_anim.deleteLater()
            self._scale_anim = None

        if self._blink_anim is not None:
            self._blink_anim.stop()
            self._blink_anim.deleteLater()
            self._blink_anim = None

        if hasattr(self, '_opacity_effect') and self._opacity_effect is not None:
            self._title_label.setGraphicsEffect(None)
            self._opacity_effect = None

    # ---- Window setup -----------------------------------------------------

    def _setup_window(self) -> None:
        """Configure dialog window flags and appearance."""
        self.setWindowTitle("⏰ Будильник!")
        self.setObjectName("alarmPopup")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(400, 320)
        self.setStyleSheet("background-color: #1a1a2e; border-radius: 16px;")

        center_on_screen(self)

    # ---- UI setup ---------------------------------------------------------

    def _setup_ui(self, alarm: Alarm) -> None:
        """Build the dialog contents.

        Args:
            alarm: The triggered Alarm instance.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        self._title_label = QLabel(self._alarm_title)
        self._title_label.setObjectName("alarmPopupTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._title_label.font()
        font.setPointSize(20)
        font.setBold(True)
        self._title_label.setFont(font)
        self._title_label.setStyleSheet("color: #e2e8f0; background: transparent;")
        layout.addWidget(self._title_label)

        # Time
        self._time_label = QLabel(alarm.time)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_font = self._time_label.font()
        time_font.setPointSize(48)
        time_font.setWeight(QFont.Weight.Light)
        self._time_label.setFont(time_font)
        self._time_label.setStyleSheet("color: #e2e8f0; background: transparent;")
        layout.addWidget(self._time_label)

        # Spacer
        layout.addSpacing(12)

        # Dismiss button
        self._dismiss_button = QPushButton("🔴 ВЫКЛЮЧИТЬ")
        self._dismiss_button.setObjectName("dangerButton")
        self._dismiss_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._dismiss_button.setMinimumSize(120, 120)
        self._dismiss_button.setMaximumSize(120, 120)
        self._dismiss_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #ef4444, stop: 1 #dc2626);
                border: none;
                border-radius: 60px;
                color: white;
                font-size: 13px;
                font-weight: 700;
                padding: 0;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #dc2626, stop: 1 #b91c1c);
            }
            QPushButton:pressed {
                background: #b91c1c;
            }
        """)

        # Center the dismiss button
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(self._dismiss_button)
        layout.addLayout(btn_layout)

        # Spacer
        layout.addSpacing(8)

        # Snooze buttons row
        snooze_layout = QHBoxLayout()
        snooze_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        snooze_layout.setSpacing(12)

        self._snooze_5_btn = QPushButton("😴 5 мин")
        self._snooze_10_btn = QPushButton("😴 10 мин")
        self._snooze_15_btn = QPushButton("😴 15 мин")

        for btn in (self._snooze_5_btn, self._snooze_10_btn, self._snooze_15_btn):
            btn.setObjectName("snoozeButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            snooze_layout.addWidget(btn)

        layout.addLayout(snooze_layout)

        # Connect signals
        self._dismiss_button.clicked.connect(self._on_dismiss)
        self._snooze_5_btn.clicked.connect(lambda: self._on_snooze(5))
        self._snooze_10_btn.clicked.connect(lambda: self._on_snooze(10))
        self._snooze_15_btn.clicked.connect(lambda: self._on_snooze(15))

    # ---- Animations -------------------------------------------------------

    def _setup_animations(self) -> None:
        """Prepare animation objects (not started yet)."""
        self._pulse_anim: QPropertyAnimation | None = None
        self._scale_anim: QPropertyAnimation | None = None
        self._blink_anim: QPropertyAnimation | None = None

    def _start_pulse_animation(self) -> None:
        """Animate the background colour between dark and deep purple-red."""
        self._pulse_anim = QPropertyAnimation(self, b"bgColor")
        self._pulse_anim.setDuration(1500)
        self._pulse_anim.setStartValue(QColor("#1a1a2e"))
        self._pulse_anim.setKeyValueAt(0.5, QColor("#2d004d"))
        self._pulse_anim.setEndValue(QColor("#1a1a2e"))
        self._pulse_anim.setLoopCount(-1)  # infinite
        self._pulse_anim.start()

    def _start_scale_animation(self) -> None:
        """Animate the dialog scale from 0.8 to 1.0 over 300 ms."""
        self._scale_anim = QPropertyAnimation(self, b"windowOpacity")
        self._scale_anim.setDuration(300)
        self._scale_anim.setStartValue(0.0)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.start()

    def _start_blink_animation(self) -> None:
        """Animate the title label opacity (blinking effect) via opacity effect."""
        self._opacity_effect = QGraphicsOpacityEffect(self._title_label)
        self._title_label.setGraphicsEffect(self._opacity_effect)

        self._blink_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._blink_anim.setDuration(1500)
        self._blink_anim.setStartValue(0.3)
        self._blink_anim.setKeyValueAt(0.5, 1.0)
        self._blink_anim.setEndValue(0.3)
        self._blink_anim.setLoopCount(-1)  # infinite
        self._blink_anim.start()

    # ----- Background colour property for animation -----------------------

    def _get_bg_color(self) -> QColor:
        return self._bg_color

    def _set_bg_color(self, color: QColor) -> None:
        self._bg_color = color
        self.setStyleSheet(
            f"background-color: {color.name()}; border-radius: 16px;"
        )

    bgColor = Property(QColor, _get_bg_color, _set_bg_color)  # type: ignore[assignment]

    # ---- Internal slots ---------------------------------------------------

    def _on_dismiss(self) -> None:
        """Emit dismiss signal and close the popup."""
        self.stop_animation()
        self.dismiss.emit(self._alarm_id)
        self.accept()

    def _on_snooze(self, minutes: int) -> None:
        """Emit snooze signal and close the popup.

        Args:
            minutes: Number of minutes to snooze.
        """
        self.stop_animation()
        self.snooze.emit(self._alarm_id, minutes)
        self.accept()

    # ---- Event overrides --------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Ensure animations are stopped when the dialog is closed."""
        self.stop_animation()
        super().closeEvent(event)

    def showEvent(self, event: QEvent) -> None:  # noqa: N802
        """Start animations when the dialog is shown."""
        super().showEvent(event)
        self.start_animation()

