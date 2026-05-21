"""MainWindow — the primary application window displaying the alarm list.

Provides a scrollable list of AlarmCardWidget instances, an empty-state
placeholder, and a floating "+" button to add new alarms.  Emits Qt signals
for user interactions that the controller layer handles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.utils.constants import APP_NAME
from src.utils.helpers import center_on_screen

if TYPE_CHECKING:
    from src.models.alarm_model import Alarm
    from src.views.alarm_card_widget import AlarmCardWidget


class MainWindow(QMainWindow):
    """Main application window.

    Displays a scrollable list of alarm cards and delegates user
    interactions through Qt signals.

    Signals:
        add_alarm_requested:   User pressed the '+' button.
        edit_alarm_requested:  User clicked on an alarm card.
        toggle_alarm_requested: User toggled the enable switch.
        delete_alarm_requested: User pressed delete on a card.
    """

    add_alarm_requested = Signal()
    edit_alarm_requested = Signal(str)  # alarm_id
    toggle_alarm_requested = Signal(str, bool)  # alarm_id, enabled
    delete_alarm_requested = Signal(str)  # alarm_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the main window.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._card_widgets: dict[str, AlarmCardWidget] = {}

        self._setup_window()
        self._setup_ui()

        # Start in empty state
        self.show_empty_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_list(self, alarms: list[Alarm]) -> None:
        """Incrementally update the card list from the given alarm collection.

        Compares the incoming alarm list with existing cards and performs
        minimal DOM mutations: removes vanished cards, updates changed ones,
        and inserts new cards in sorted order.

        Args:
            alarms: A list of Alarm instances to display.
        """
        if not alarms:
            # Remove all existing cards
            for card in self._card_widgets.values():
                self._scroll_layout.removeWidget(card)
                card.deleteLater()
            self._card_widgets.clear()
            self.show_empty_state()
            return

        self.show_alarms_list()

        sorted_alarms = sorted(alarms, key=lambda a: a.time)
        new_ids = {a.id for a in sorted_alarms}

        # 1. Remove cards for alarms that no longer exist
        vanished_ids = [aid for aid in self._card_widgets if aid not in new_ids]
        for aid in vanished_ids:
            card = self._card_widgets.pop(aid)
            self._scroll_layout.removeWidget(card)
            card.deleteLater()

        # 2. Remove trailing stretch items to re-layout cleanly
        self._remove_trailing_stretch()

        # 3. Iterate sorted alarms and update / insert cards in order
        from src.views.alarm_card_widget import AlarmCardWidget  # noqa: PLC0415

        insertion_index = 0
        for alarm in sorted_alarms:
            existing = self._card_widgets.get(alarm.id)
            if existing is not None:
                # Update existing card
                existing.update_alarm(alarm)
            else:
                # Create new card
                card = AlarmCardWidget(alarm)
                card.toggle_clicked.connect(self._on_card_toggled)
                card.delete_clicked.connect(self._on_card_deleted)
                card.card_clicked.connect(self._on_card_clicked)

                # Insert at the correct sorted position
                self._scroll_layout.insertWidget(insertion_index, card)
                self._card_widgets[alarm.id] = card
            insertion_index += 1

        # 4. Add trailing stretch
        self._scroll_layout.addStretch()

    def _remove_trailing_stretch(self) -> None:
        """Remove trailing stretch items from the scroll layout."""
        while self._scroll_layout.count() > 0:
            item = self._scroll_layout.itemAt(self._scroll_layout.count() - 1)
            if item and item.spacerItem():
                self._scroll_layout.removeItem(item)
            else:
                break

    set_alarms = refresh_list  # alias for the spec-compatible name

    def show_empty_state(self) -> None:
        """Show the empty-state placeholder and hide the scroll list."""
        self._empty_widget.show()

    def show_alarms_list(self) -> None:
        """Show the scrollable alarm list and hide the empty state."""
        self._empty_widget.hide()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle(f"⏰ {APP_NAME}")
        self.setObjectName("mainWindow")
        self.setMinimumSize(420, 500)
        self.resize(480, 640)

        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
        """)

        center_on_screen(self)

    def _setup_ui(self) -> None:
        """Build the main window layout."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Header with gradient ---
        header = QWidget()
        header.setObjectName("windowHeader")
        header.setFixedHeight(80)
        header.setStyleSheet("""
            #windowHeader {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #7c3aed, stop: 1 #1e1e2e
                );
            }
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)

        title_label = QLabel(f"⏰ {APP_NAME}")
        title_label.setObjectName("windowTitle")
        title_label.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #e2e8f0; background: transparent;"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        add_btn = QPushButton("+")
        add_btn.setObjectName("addButton")
        add_btn.setFixedSize(44, 44)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setToolTip("Добавить будильник")
        add_btn.clicked.connect(self.add_alarm_requested.emit)
        header_layout.addWidget(add_btn)

        layout.addWidget(header)

        # --- Scrollable alarm list ---
        scroll = QScrollArea()
        scroll.setObjectName("alarmScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background-color: transparent; }
        """)

        scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(16, 12, 16, 12)
        self._scroll_layout.setSpacing(12)
        self._scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # --- Empty state placeholder ---
        self._empty_widget = QWidget()
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(16)

        # Large bell-off icon (drawn via QPainter)
        empty_icon = QLabel()
        empty_icon.setPixmap(self._create_empty_icon())
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_text = QLabel(
            "Нет будильников\nНажмите [+], чтобы добавить первый"
        )
        empty_text.setObjectName("emptyStateText")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_text.setWordWrap(True)
        empty_text.setStyleSheet(
            "font-size: 16px; color: #94a3b8; background: transparent;"
        )
        empty_layout.addWidget(empty_text)

        self._empty_widget.hide()
        # Insert the empty widget into the scroll layout
        self._scroll_layout.addWidget(self._empty_widget)

    def _create_empty_icon(self) -> QPixmap:
        """Draw a large semi-transparent bell-off icon.

        Returns:
            A QPixmap suitable for the empty-state placeholder.
        """
        size = 80
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(148, 163, 184, 100)  # #94a3b8 semi-transparent
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)

        # Bell body
        painter.drawRoundedRect(18, 22, 44, 32, 8, 8)
        # Bell top
        painter.drawRoundedRect(26, 10, 28, 18, 6, 6)
        # Bell rim
        painter.drawRoundedRect(22, 48, 36, 6, 3, 3)
        # Clapper
        painter.drawEllipse(34, 52, 12, 12)

        # Cross-out line
        pen = painter.pen()
        pen.setWidthF(3.0)
        pen.setColor(QColor(239, 68, 68, 120))
        painter.setPen(pen)
        painter.drawLine(12, 12, 68, 68)

        painter.end()
        return pixmap

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_card_toggled(self, alarm_id: str, enabled: bool) -> None:
        """Forward toggle event from a card.

        Args:
            alarm_id: The alarm UUID.
            enabled: The new toggle state.
        """
        self.toggle_alarm_requested.emit(alarm_id, enabled)

    def _on_card_deleted(self, alarm_id: str) -> None:
        """Forward delete event from a card.

        Args:
            alarm_id: The alarm UUID.
        """
        self.delete_alarm_requested.emit(alarm_id)

    def _on_card_clicked(self, alarm_id: str) -> None:
        """Forward edit event from a card.

        Args:
            alarm_id: The alarm UUID.
        """
        self.edit_alarm_requested.emit(alarm_id)

    # ------------------------------------------------------------------
    # Window close → hide instead of quit
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Override close to hide instead of closing (system-tray pattern)."""
        self.hide()
        event.ignore()

