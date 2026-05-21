"""Alarm controller — bridges AlarmManager (Model) with MainWindow (View)."""

import logging
from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from src.models.alarm_model import Alarm
from src.models.alarm_manager import AlarmManager
from src.models.sound_manager import SoundManager
from src.views.main_window import MainWindow
from src.views.alarm_form_dialog import AlarmFormDialog
from src.views.alarm_popup import AlarmPopup
from src.views.tray_manager import TrayManager

logger = logging.getLogger(__name__)


class AlarmController(QObject):
    """Main controller that connects alarm Model and View layers.

    Handles alarm CRUD operations, alarm triggering, snooze, and dismiss.
    Acts as the mediator between AlarmManager/SoundManager (Model) and
    MainWindow/AlarmFormDialog/AlarmPopup (View).
    """

    def __init__(
        self,
        alarm_manager: AlarmManager,
        sound_manager: SoundManager,
    ) -> None:
        """Initialize the controller with model instances.

        Args:
            alarm_manager: The alarm data manager (model).
            sound_manager: The sound playback manager (model).
        """
        super().__init__()
        self._alarm_manager: AlarmManager = alarm_manager
        self._sound_manager: SoundManager = sound_manager
        self._main_window: Optional[MainWindow] = None
        self._tray_manager: Optional[TrayManager] = None
        self._active_popup: Optional[AlarmPopup] = None

    # ── Connection methods ─────────────────────────────────────────────

    def connect_view(self, main_window: MainWindow) -> None:
        """Connect main window signals to controller slots.

        Subscribes to user-initiated signals from MainWindow
        and forwards them to the appropriate model methods.
        Also connects model signals back to view updates.

        Args:
            main_window: The main application window (view).
        """
        self._main_window = main_window

        # View → Controller: user actions
        main_window.add_alarm_requested.connect(self._on_add_alarm)
        main_window.edit_alarm_requested.connect(self._on_edit_alarm)
        main_window.delete_alarm_requested.connect(self._on_delete_alarm)
        main_window.toggle_alarm_requested.connect(self._on_toggle_alarm)

        # Model → View: data changes (via controller)
        self._alarm_manager.alarms_changed.connect(self._refresh_view)
        self._alarm_manager.alarm_triggered.connect(self._on_alarm_triggered)

    def connect_tray(self, tray_manager: TrayManager) -> None:
        """Connect tray icon updates to alarm state changes.

        Whenever the alarms list changes, the tray icon is updated
        to reflect whether any alarms are active (coloured icon)
        or all are disabled (grey icon).

        Args:
            tray_manager: The system tray manager (view).
        """
        self._tray_manager = tray_manager
        self._alarm_manager.alarms_changed.connect(self._update_tray_icon)

    # ── View event handlers ────────────────────────────────────────────

    def _on_add_alarm(self) -> None:
        """Open the alarm form dialog in create mode.

        Creates a new AlarmFormDialog instance and connects its
        ``saved`` signal to handle form submission.
        """
        if self._main_window is None:
            logger.warning("Cannot open add form: main_window is None")
            return

        dialog = AlarmFormDialog(self._main_window)
        dialog.saved.connect(self._on_alarm_saved)
        dialog.open()

    def _on_edit_alarm(self, alarm_id: str) -> None:
        """Open the alarm form dialog in edit mode for the given alarm.

        Loads the existing alarm data from AlarmManager and pre-fills
        the form. Connects the ``saved`` signal to handle updates.

        Args:
            alarm_id: UUID of the alarm to edit.
        """
        if self._main_window is None:
            logger.warning("Cannot open edit form: main_window is None")
            return

        alarm = self._alarm_manager.get_by_id(alarm_id)
        if alarm is None:
            logger.warning("Tried to edit unknown alarm: %s", alarm_id)
            return

        dialog = AlarmFormDialog(self._main_window)
        dialog.set_alarm(alarm)
        dialog.saved.connect(self._on_alarm_saved)
        dialog.open()

    def _on_delete_alarm(self, alarm_id: str) -> None:
        """Ask for user confirmation and delete the alarm.

        Displays a QMessageBox confirmation dialog. If the user
        confirms, removes the alarm via AlarmManager.

        Args:
            alarm_id: UUID of the alarm to delete.
        """
        if self._main_window is None:
            return

        alarm = self._alarm_manager.get_by_id(alarm_id)
        if alarm is None:
            return

        title: str = alarm.title if alarm.title else alarm.time
        reply = QMessageBox.question(
            self._main_window,
            "Удаление будильника",
            f'Удалить будильник "{title}" ({alarm.time})?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._alarm_manager.remove(alarm_id)
            logger.info("Deleted alarm: %s (%s)", alarm_id, alarm.time)

    def _on_toggle_alarm(self, alarm_id: str, enabled: bool) -> None:
        """Set the enabled state of an alarm to the requested value.

        Delegates to AlarmManager.toggle_alarm() which sets the state
        directly and persists the change.

        Args:
            alarm_id: UUID of the alarm to toggle.
            enabled: The desired enabled state (True = active, False = disabled).
        """
        self._alarm_manager.toggle_alarm(alarm_id, enabled)

    def _on_alarm_saved(self, alarm_data: dict) -> None:
        """Create or update an alarm from validated form data.

        If the alarm ID already exists in AlarmManager, it is updated.
        Otherwise, a new alarm is created.

        Args:
            alarm_data: Dictionary with alarm fields from AlarmFormDialog.
        """
        alarm = Alarm.from_dict(alarm_data)
        existing = self._alarm_manager.get_by_id(alarm.id)

        if existing is not None:
            self._alarm_manager.update(alarm)
            logger.info("Updated alarm: %s", alarm.id)
        else:
            self._alarm_manager.add(alarm)
            logger.info("Created new alarm: %s", alarm.id)

    # ── Alarm trigger handling ─────────────────────────────────────────

    def _on_alarm_triggered(self, alarm: Alarm) -> None:
        """Handle an alarm firing — play sound and show the alarm popup.

        Determines the sound source (built-in or custom file), starts
        playback (with optional fade-in), and opens the AlarmPopup
        window on top of all other windows.

        Args:
            alarm: The alarm that was triggered.
        """
        if self._main_window is None:
            logger.warning("Cannot show popup: main_window is None")
            return

        # Play appropriate sound
        if alarm.sound_source == "file" and alarm.sound_file:
            self._sound_manager.play_file(alarm.sound_file, alarm.volume)
        else:
            self._sound_manager.play_builtin(alarm.sound_name, alarm.volume)

        # Start fade-in if enabled
        if alarm.fade_in:
            self._sound_manager.start_fade(alarm.volume)

        # Create and show the popup window
        from PySide6.QtCore import Qt  # noqa: PLC0415
        from src.views.alarm_popup import AlarmPopup  # noqa: PLC0415

        popup = AlarmPopup(alarm, self._main_window)
        popup.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        popup.dismissed.connect(self._on_dismiss)
        popup.snoozed.connect(self._on_snooze)
        popup.show()
        self._active_popup = popup

        logger.info("Alarm triggered: %s at %s", alarm.id, alarm.time)

    def _on_dismiss(self, alarm_id: str) -> None:
        """Dismiss the alarm — stop sound and close the popup.

        Args:
            alarm_id: UUID of the alarm being dismissed.
        """
        self._sound_manager.stop()

        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None

        logger.info("Alarm dismissed: %s", alarm_id)

    def _on_snooze(self, alarm_id: str, minutes: int) -> None:
        """Snooze the alarm — stop sound and reschedule via AlarmManager.

        Args:
            alarm_id: UUID of the alarm to snooze.
            minutes: Number of minutes to snooze for.
        """
        self._sound_manager.stop()
        self._alarm_manager.snooze(alarm_id, minutes)

        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None

        logger.info("Alarm snoozed: %s for %d minutes", alarm_id, minutes)

    # ── Internal helpers ───────────────────────────────────────────────

    def _refresh_view(self) -> None:
        """Refresh the alarm list in the main window.

        Called whenever AlarmManager emits ``alarms_changed``.
        Fetches the latest sorted list and passes it to MainWindow.
        """
        if self._main_window is not None:
            alarms = self._alarm_manager.get_all()
            self._main_window.refresh_list(alarms)

    def _update_tray_icon(self) -> None:
        """Update the tray icon based on whether any alarms are active."""
        if self._tray_manager is None:
            return
        alarms = self._alarm_manager.get_all()
        has_active: bool = any(a.enabled for a in alarms)
        self._tray_manager.set_active_icon(has_active)

