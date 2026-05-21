"""
System tray manager — application icon, context menu and toast notifications.

Provides a QSystemTrayIcon with a context menu (Show, Settings, Quit)
and methods to update the icon based on active alarms state.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayManager(QObject):
    """Manages the system tray icon, context menu and notifications.

    Provides a coloured bell icon when alarms are active and a greyed-out
    version when all alarms are disabled. Emits signals when the user
    interacts with the tray menu.

    Signals:
        show_window_requested():
            Emitted when the user selects "Показать" from the tray menu.
        quit_requested():
            Emitted when the user selects "Выход" from the tray menu.
    """

    show_window_requested = Signal()
    show_requested = Signal()  # alias used by existing tray_controller
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialise the tray manager.

        Args:
            parent: Optional parent QObject.
        """
        super().__init__(parent)

        self._tray_icon: QSystemTrayIcon | None = None
        self._menu: QMenu | None = None

        self._setup_tray_icon()
        self._setup_menu()

    # ---- Public API -------------------------------------------------------

    def show_notification(self, title: str, message: str) -> None:
        """Display a toast notification from the system tray.

        Args:
            title: Notification title text.
            message: Notification body text.
        """
        if self._tray_icon is not None and self._tray_icon.isSystemTrayAvailable():
            self._tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    def set_active_icon(self, active: bool | None = None) -> None:
        """Set the tray icon according to the active state.

        If *active* is ``None`` the icon is always set to coloured.
        If *active* is ``True`` the coloured bell is shown; otherwise the
        greyed-out bell is shown.

        Args:
            active: Whether any alarm is active, or None for always coloured.
        """
        if active is None or active:
            self._set_icon_coloured(True)
        else:
            self._set_icon_coloured(False)

    def set_inactive_icon(self) -> None:
        """Set the tray icon to the greyed-out (inactive) bell."""
        self._set_icon_coloured(False)

    def update_icon(self, has_active: bool) -> None:
        """Update the tray icon based on whether any alarm is active.

        Args:
            has_active: True if at least one alarm is enabled and active.
        """
        self.set_active_icon(has_active)

    # ---- Setup ------------------------------------------------------------

    def _setup_tray_icon(self) -> None:
        """Create the system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            # Tray not available on this system — create a dummy for safety
            self._tray_icon = None
            return

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setToolTip("⏰ Будильник")
        self._set_icon_coloured(False)
        self._tray_icon.show()

    def _setup_menu(self) -> None:
        """Build the tray context menu."""
        if self._tray_icon is None:
            return

        self._menu = QMenu()

        # Show action
        show_action = QAction("🔔 Показать", self._menu)
        show_action.triggered.connect(self.show_window_requested.emit)
        show_action.triggered.connect(self.show_requested.emit)
        self._menu.addAction(show_action)

        # Quit action
        quit_action = QAction("🚪 Выход", self._menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)

        self._tray_icon.setContextMenu(self._menu)

    # ---- Icon helpers -----------------------------------------------------

    def _set_icon_coloured(self, coloured: bool) -> None:
        """Render and set a bell icon in coloured or greyed-out style.

        Args:
            coloured: True for coloured (active) bell, False for grey.
        """
        if self._tray_icon is None:
            return

        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Bell body colour
        if coloured:
            body_color = QColor(124, 58, 237)  # #7c3aed
            highlight_color = QColor(236, 72, 153)  # #ec4899
        else:
            body_color = QColor(100, 100, 120)
            highlight_color = QColor(80, 80, 100)

        # Draw a simple bell shape
        painter.setPen(Qt.PenStyle.NoPen)

        # Bell body (arc)
        painter.setBrush(body_color)
        bell_rect = (12, 16, 40, 32)
        painter.drawRoundedRect(*bell_rect, 8, 8)

        # Bell top (smaller rounded rect / dome)
        top_rect = (20, 8, 24, 16)
        painter.drawRoundedRect(*top_rect, 6, 6)

        # Bell bottom rim
        rim_rect = (16, 44, 32, 6)
        painter.drawRoundedRect(*rim_rect, 3, 3)

        # Clapper circle
        clapper_color = highlight_color if coloured else QColor(80, 80, 100)
        painter.setBrush(clapper_color)
        painter.drawEllipse(28, 48, 8, 8)

        # Highlight dot
        if coloured:
            painter.setBrush(QColor(255, 255, 255, 60))
            painter.drawEllipse(24, 20, 6, 6)

        painter.end()

        self._tray_icon.setIcon(QIcon(pixmap))
