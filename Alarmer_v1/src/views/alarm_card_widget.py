"""
Alarm card widget — a single alarm card displayed in the main window list.

Provides a compact visual representation of one alarm with time,
days, title, toggle switch, and delete button. Supports hover effects,
disabled dimming, and emits signals for user interactions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSignalMapper, Signal, Qt
from PySide6.QtGui import QColor, QEnterEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from src.models.alarm_model import Alarm


_DAY_NAMES_SHORT: list[str] = [
    "Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс",
]


class AlarmCardWidget(QFrame):
    """A card widget representing a single alarm in the main window list.

    Displays the alarm time prominently, along with recurrence days,
    an optional title, a toggle switch, and a delete button.
    Emits signals when the user toggles, deletes, or clicks the card.

    Signals:
        toggle_clicked(alarm_id: str, enabled: bool):
            Emitted when the toggle switch is changed.
        delete_clicked(alarm_id: str):
            Emitted when the delete button is pressed.
        card_clicked(alarm_id: str):
            Emitted when the card body is clicked (edit intent).
    """

    toggle_clicked = Signal(str, bool)  # alarm_id, enabled
    delete_clicked = Signal(str)  # alarm_id
    card_clicked = Signal(str)  # alarm_id

    def __init__(self, alarm: Alarm, parent: QWidget | None = None) -> None:
        """Initialise the card with the given alarm data.

        Args:
            alarm: The Alarm model instance to display.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._alarm_id: str = alarm.id
        self._enabled: bool = alarm.enabled

        self._setup_ui()
        self._apply_shadow()
        self._connect_signals()
        self.update_alarm(alarm)

    # ---- Public API -------------------------------------------------------

    def update_alarm(self, alarm: Alarm) -> None:
        """Refresh the card display with new alarm data.

        Args:
            alarm: The updated Alarm model instance.
        """
        self._alarm_id = alarm.id
        self._enabled = alarm.enabled

        # Time
        self._time_label.setText(alarm.time)

        # Days / once
        if alarm.once:
            days_text = "Единоразово"
        elif alarm.days:
            day_labels = [
                _DAY_NAMES_SHORT[i - 1] if (i in alarm.days) else "—"
                for i in range(1, 8)
            ]
            days_text = " ".join(day_labels)
        else:
            days_text = "—"

        self._days_label.setText(days_text)

        # Title
        if alarm.title:
            self._title_label.setText(alarm.title)
            self._title_label.show()
        else:
            self._title_label.hide()

        # Toggle state
        self._toggle_switch.setChecked(alarm.enabled)

        # Visual enabled/disabled state
        self._set_active_state(alarm.enabled)

    # ---- UI Setup ---------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the card widget layout."""
        self.setObjectName("alarmCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # ---- Left info block ----
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self._time_label = QLabel()
        self._time_label.setObjectName("timeLabel")
        self._time_label.setStyleSheet("font-size: 36px; font-weight: 300; color: #e2e8f0;")
        self._time_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        info_layout.addWidget(self._time_label)

        self._days_label = QLabel()
        self._days_label.setObjectName("secondaryLabel")
        self._days_label.setStyleSheet("font-size: 13px; color: #94a3b8;")
        info_layout.addWidget(self._days_label)

        self._title_label = QLabel()
        self._title_label.setObjectName("secondaryLabel")
        self._title_label.setStyleSheet("font-size: 13px; color: #e2e8f0; font-weight: 500;")
        info_layout.addWidget(self._title_label)

        layout.addLayout(info_layout, stretch=1)

        # ---- Right controls ----
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Toggle switch
        self._toggle_switch = QCheckBox()
        self._toggle_switch.setObjectName("toggleSwitch")
        self._toggle_switch.setCursor(Qt.CursorShape.PointingHandCursor)
        controls_layout.addWidget(self._toggle_switch)

        # Delete button
        self._delete_button = QPushButton("🗑")
        self._delete_button.setObjectName("deleteButton")
        self._delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_button.setToolTip("Удалить будильник")
        controls_layout.addWidget(self._delete_button)

        layout.addLayout(controls_layout)

    def _apply_shadow(self) -> None:
        """Apply a drop-shadow effect to the card."""
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(20)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self._shadow)

    def _connect_signals(self) -> None:
        """Connect internal widget signals."""
        self._toggle_switch.toggled.connect(self._on_toggle_changed)
        self._delete_button.clicked.connect(self._on_delete_clicked)

    # ---- State helpers ----------------------------------------------------

    def _set_active_state(self, enabled: bool) -> None:
        """Visually enable or dim the card.

        Args:
            enabled: True for full opacity, False for dimmed.
        """
        opacity = 1.0 if enabled else 0.5
        style = self.styleSheet() or ""
        # Apply inline opacity via a semi-transparent overlay approach:
        # We override the widget's alpha indirectly.
        self.setGraphicsEffect(None if enabled else self._shadow)

        # Re-apply shadow for enabled
        if enabled:
            self._apply_shadow()

        self._update_opacity(self, opacity)

    @staticmethod
    def _update_opacity(widget: QWidget, opacity: float) -> None:
        """Recursively set the opacity of a widget and its children.

        Args:
            widget: The widget to affect.
            opacity: A float between 0.0 and 1.0.
        """
        prop = widget.property("opacity_override")
        if prop is None or prop != opacity:
            widget.setProperty("opacity_override", opacity)
            # Force style refresh
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    # ---- Event overrides --------------------------------------------------

    def enterEvent(self, event: QEnterEvent) -> None:
        """Animate shadow lift on mouse enter."""
        if self._enabled:
            self._shadow.setBlurRadius(30)
            self._shadow.setOffset(0, 6)
            self._shadow.setColor(QColor(124, 58, 237, 60))
        super().enterEvent(event)

    def leaveEvent(self, event: QEnterEvent) -> None:
        """Restore shadow on mouse leave."""
        if self._enabled:
            self._shadow.setBlurRadius(20)
            self._shadow.setOffset(0, 4)
            self._shadow.setColor(QColor(0, 0, 0, 80))
        super().leaveEvent(event)

    def mousePressEvent(self, event: QEnterEvent) -> None:
        """Emit card_clicked on any mouse press (except on controls)."""
        # Only emit if the click wasn't on the toggle or delete button
        child = self.childAt(event.position().toPoint())
        if child not in (self._toggle_switch, self._delete_button):
            self.card_clicked.emit(self._alarm_id)
        super().mousePressEvent(event)

    # ---- Internal slots ---------------------------------------------------

    def _on_toggle_changed(self, checked: bool) -> None:
        """Handle toggle switch state change.

        Args:
            checked: New toggle state.
        """
        self._enabled = checked
        self._set_active_state(checked)
        self.toggle_clicked.emit(self._alarm_id, checked)

    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        self.delete_clicked.emit(self._alarm_id)

