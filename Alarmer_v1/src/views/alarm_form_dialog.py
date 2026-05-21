"""AlarmFormDialog — modal dialog for creating / editing an alarm.

Provides a form with time picker, day-of-week toggles, volume slider,
fade-in option, and a title field.  Sound is always the built-in alarm_1.wav.
Emits a ``saved`` signal with the form data when the user confirms.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from src.utils.constants import SNOOZE_MINUTES
from src.utils.helpers import generate_id, validate_time


class AlarmFormDialog(QDialog):
    """Form for creating or editing an alarm.

    Signals:
        saved(alarm_data: dict):
            Emitted when the user presses "Сохранить" and validation passes.
        cancelled():
            Emitted when the user presses "Отмена".
    """

    saved = Signal(dict)  # alarm_data
    cancelled = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._editing_id: Optional[str] = None

        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_alarm(self, alarm: Any) -> None:
        """Pre-fill the form with an existing alarm's data (edit mode).

        Args:
            alarm: An ``Alarm`` instance (or duck-typed object with matching attrs).
        """
        self._editing_id = alarm.id

        # Time
        from PySide6.QtCore import QTime  # noqa: PLC0415
        hours, minutes = alarm.time.split(":")
        self._time_edit.setTime(QTime(int(hours), int(minutes)))

        # Days
        for i, cb in enumerate(self._day_checkboxes):
            cb.setChecked((i + 1) in alarm.days)
        self._once_checkbox.setChecked(alarm.once)

        # Volume
        self._volume_slider.setValue(alarm.volume)
        self._volume_value_label.setText(f"{alarm.volume}%")

        # Fade-in
        self._fade_in_checkbox.setChecked(alarm.fade_in)

        # Title
        self._title_edit.setText(alarm.title)

    def get_form_data(self) -> dict[str, Any]:
        """Collect and return the current form field values.

        Returns:
            A dictionary suitable for creating/updating an ``Alarm``.
        """
        from PySide6.QtCore import QTime  # noqa: PLC0415

        time_val: QTime = self._time_edit.time()
        selected_days = [
            i + 1
            for i, cb in enumerate(self._day_checkboxes)
            if cb.isChecked()
        ]

        return {
            "id": self._editing_id or generate_id(),
            "enabled": True,
            "title": self._title_edit.text().strip(),
            "time": time_val.toString("HH:mm"),
            "days": selected_days if not self._once_checkbox.isChecked() else [],
            "once": self._once_checkbox.isChecked(),
            "volume": self._volume_slider.value(),
            "fade_in": self._fade_in_checkbox.isChecked(),
            "snoozed_until": None,
        }

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        """Configure dialog properties."""
        self.setWindowTitle("Будильник")
        self.setObjectName("alarmFormDialog")
        self.setMinimumWidth(420)
        self.setModal(True)

    def _setup_ui(self) -> None:
        """Build the form layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ---- Time ----
        time_label = QLabel("⏰ Время")
        time_label.setObjectName("formSectionTitle")
        layout.addWidget(time_label)

        time_row = QHBoxLayout()
        self._time_edit = QTimeEdit()
        self._time_edit.setObjectName("timeEdit")
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setWrapping(True)  # 23→00, 59→00 cyclic
        self._time_edit.setStyleSheet("font-size: 32px;")
        time_row.addWidget(self._time_edit)
        time_row.addStretch()
        layout.addLayout(time_row)

        # ---- Days ----
        days_label = QLabel("📅 Дни недели")
        days_label.setObjectName("formSectionTitle")
        layout.addWidget(days_label)

        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        days_row = QHBoxLayout()
        days_row.setSpacing(6)
        self._day_checkboxes = []
        for name in day_names:
            cb = QCheckBox(name)
            cb.setObjectName("dayCheckbox")
            cb.toggled.connect(self._on_day_toggled)
            self._day_checkboxes.append(cb)
            days_row.addWidget(cb)
        days_row.addStretch()
        layout.addLayout(days_row)

        self._once_checkbox = QCheckBox("Единоразово")
        self._once_checkbox.setObjectName("onceCheckbox")
        self._once_checkbox.setChecked(True)
        self._once_checkbox.toggled.connect(self._on_once_toggled)
        layout.addWidget(self._once_checkbox)

        # ---- Volume ----
        vol_label = QLabel("🔊 Громкость")
        vol_label.setObjectName("formSectionTitle")
        layout.addWidget(vol_label)

        vol_row = QHBoxLayout()
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setObjectName("volumeSlider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self._volume_slider, stretch=1)

        self._volume_value_label = QLabel("80%")
        self._volume_value_label.setObjectName("volumeValueLabel")
        vol_row.addWidget(self._volume_value_label)

        layout.addLayout(vol_row)

        # ---- Fade-in ----
        self._fade_in_checkbox = QCheckBox("Плавно увеличивать громкость (Fade-in)")
        self._fade_in_checkbox.setObjectName("fadeInCheckbox")
        layout.addWidget(self._fade_in_checkbox)

        # ---- Title ----
        title_label = QLabel("✏️ Название")
        title_label.setObjectName("formSectionTitle")
        layout.addWidget(title_label)

        self._title_edit = QLineEdit()
        self._title_edit.setObjectName("titleEdit")
        self._title_edit.setPlaceholderText("Название будильника…")
        self._title_edit.setMaxLength(50)
        layout.addWidget(self._title_edit)

        # ---- Buttons ----
        layout.addSpacing(8)
        btn_row = QHBoxLayout()

        cancel_btn = QPushButton("ОТМЕНА")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()

        self._save_btn = QPushButton("💾 СОХРАНИТЬ")
        self._save_btn.setObjectName("primaryButton")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_once_toggled(self, checked: bool) -> None:
        """When "Единоразово" is checked, uncheck all day boxes."""
        if checked:
            for cb in self._day_checkboxes:
                cb.setChecked(False)

    def _on_day_toggled(self) -> None:
        """When any day is checked, uncheck "Единоразово"."""
        any_day = any(cb.isChecked() for cb in self._day_checkboxes)
        if any_day:
            self._once_checkbox.blockSignals(True)
            self._once_checkbox.setChecked(False)
            self._once_checkbox.blockSignals(False)

    def _on_volume_changed(self, value: int) -> None:
        """Update the volume percentage label."""
        self._volume_value_label.setText(f"{value}%")

    def _on_save(self) -> None:
        """Validate and emit ``saved`` with form data."""
        data = self.get_form_data()

        # Validate time format
        if not validate_time(data["time"]):
            QMessageBox.warning(
                self,
                "Ошибка",
                "Некорректное время. Пожалуйста, укажите время в формате HH:MM.",
            )
            return

        self.saved.emit(data)
        self.accept()

    def _on_cancel(self) -> None:
        """Emit ``cancelled`` and close."""
        self.cancelled.emit()
        self.reject()
