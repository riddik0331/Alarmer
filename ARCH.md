# Архитектура приложения «Будильник» (Budilnik)

> **Версия:** 1.0
> **Дата:** 2026-05-20
> **Стек:** Python 3.11+ | PySide6 6.x | JSON | PyInstaller

---

## 1. Общая архитектура: Model-View-Controller (MVC)

Приложение построено по классическому паттерну **MVC** с разделением на три слоя:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BudilnikApp (app.py)                        │
│                     Главный оркестратор приложения                  │
│              Инициализация, запуск, координация модулей             │
└───────┬────────────────────┬──────────────────────┬────────────────┘
        │                    │                      │
   ┌────▼────┐         ┌────▼────┐            ┌────▼────┐
   │  Model  │◄───────►│  View   │            │Controller│
   │  Слой   │  Signals│  Слой   │  Signals   │  Слой    │
   │ данных  │  /Slots │  UI     │  /Slots    │ логики   │
   └─────────┘         └─────────┘            └─────────┘
```

### Роли слоёв

| Слой | Назначение | Компоненты | Зависимости |
|------|-----------|------------|-------------|
| **Model** | Бизнес-логика, данные, внешнее хранение, звук, таймеры | `Alarm`, `AlarmManager`, `SoundManager` | Только стандартная библиотека + PySide6.QtCore |
| **View** | Отображение UI, анимации, пользовательский ввод | `MainWindow`, `AlarmCardWidget`, `AlarmFormDialog`, `AlarmPopup`, `TrayManager` | PySide6.QtWidgets, QSS |
| **Controller** | Связь Model ↔ View, обработка событий, координация | `BudilnikApp`, `AlarmController`, `TrayController` | Оба слоя (Model + View) |

### Ключевой принцип

- **View никогда не обращается к Model напрямую** — только через Controller.
- **Model не знает о существовании View** — все изменения Model сообщает через Qt signals.
- **Controller подписывается на signals Model и обновляет View**, и наоборот — signals View обрабатывает Controller.
- Все коммуникации — через **Qt Signal/Slot** механизм (событийно-ориентированная архитектура).

---

## 2. Диаграмма классов (текстовая UML)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           BudilnikApp                                  │
│─────────────────────────────────────────────────────────────────────────│
│ - alarm_controller: AlarmController                                     │
│ - tray_controller: TrayController                                       │
│ - main_window: MainWindow                                               │
│ - tray_manager: TrayManager                                             │
│─────────────────────────────────────────────────────────────────────────│
│ + run() -> None                                                         │
│ + show_window() -> None                                                 │
│ + quit_application() -> None                                            │
│ + on_alarm_triggered(alarm: Alarm) -> None                              │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│ AlarmController │ │TrayController│ │   MainWindow    │
│                 │ │             │ │   (View)        │
│ - alarm_manager │ │ - tray      │ │                 │
│ - main_window   │ │ - app_ref   │ │ - card_widgets  │
│ - popup_active  │ │             │ │ - controller    │
│                 │ │ + setup()   │ │                 │
│ + setup()       │ │ + on_show() │ │ + refresh_list()│
│ + create_alarm()│ │ + on_quit() │ │ + show_popup()  │
│ + edit_alarm()  │ │             │ │ + show_empty()  │
│ + delete_alarm()│ └─────────────┘ │                 │
│ + toggle_alarm()│                 └────────┬────────┘
│ + on_minute()   │                          │
│ + show_popup()  │              ┌────────────┼────────────┐
│ + snooze()      │              ▼            ▼            ▼
│ + dismiss()     │   ┌──────────────┐ ┌──────────┐ ┌────────────┐
└────────┬────────┘   │AlarmCardWidget│ │AlarmForm │ │AlarmPopup  │
         │            │              │ │Dialog    │ │            │
         │            │ - alarm_data │ │          │ │ - alarm    │
         ▼            │ + set_alarm()│ │ + get_data│ │ + animate()│
┌─────────────────┐   │ + animate() │ │ + validate│ │ + pulse()  │
│  AlarmManager   │   │ signal:      │ │ signal:   │ │ signal:    │
│   (Model)       │   │ toggled      │ │ saved     │ │ dismissed  │
│                 │   │ edit_clicked │ │ cancelled │ │ snoozed    │
│ - alarms: list  │   │ delete_clkd  │ └──────────┘ │            │
│ - timer: QTimer │   └──────────────┘              └────────────┘
│                 │
│ + load()        │           ┌─────────────────┐
│ + save()        │           │  SoundManager   │
│ + add()         │           │   (Model)       │
│ + update()      │           │                 │
│ + remove()      │           │ - player        │
│ + check_alarms()│           │ - builtin_sounds│
│ signal:          │           │ - fade_timer    │
│   alarms_changed │           │                 │
│   alarm_triggered│           │ + play_builtin()│
└─────────────────┘           │ + play_file()   │
                              │ + stop()        │
                              │ + set_volume()  │
                              │ + start_fade()  │
                              └─────────────────┘
```

---

## 3. Схема потоков данных

### 3.1. Создание будильника

```
Пользователь                 View                     Controller              Model
    │                        │                           │                     │
    ├── нажимает [+] ───────►│                           │                     │
    │                        │                           │                     │
    │                        ├── alarm_controller        │                     │
    │                        │   .create_alarm() ───────►│                     │
    │                        │                           │                     │
    │                        │                           ├── alarm_manager     │
    │                        │                           │   .add(alarm) ─────►│
    │                        │                           │                     │
    │                        │                           │                     ├── save() → JSON
    │                        │                           │                     ├── emit: alarms_changed
    │                        │                           │◄────────────────────┤
    │                        │                           │                     │
    │                        │◄──────────────────────────┤                     │
    │                        │  refresh_list()           │                     │
    │◄────── обновлён ───────┤                           │                     │
    │     список             │                           │                     │
```

### 3.2. Срабатывание будильника

```
QTimer (30s)          AlarmManager           Controller           View
    │                     │                      │                  │
    ├── tick ────────────►│                      │                  │
    │                     │                      │                  │
    │                     ├── check_alarms()     │                  │
    │                     ├── сравнение времени  │                  │
    │                     ├── emit:              │                  │
    │                     │   alarm_triggered ───►                  │
    │                     │                      │                  │
    │                     │                      ├── sound_manager  │
    │                     │                      │   .play() ──────►│ (SoundManager)
    │                     │                      │                  │
    │                     │                      ├── show_popup() ─►│ AlarmPopup
    │                     │                      │                  │    .show()
    │                     │                      │                  │    .animate()
    │                     │                      │                  │
    │                     │                      ├── tray_manager   │
    │                     │                      │   .show_toast()─►│ TrayManager
```

### 3.3. Обработка откладывания (Snooze)

```
Пользователь          AlarmPopup         Controller        AlarmManager
    │                     │                  │                  │
    ├── нажимает ────────►│                  │                  │
    │   "Отложить 5"     │                  │                  │
    │                     ├── emit:          │                  │
    │                     │   snoozed(5) ───►│                  │
    │                     │                  │                  │
    │                     │                  ├── stop() (звук)  │
    │                     │                  ├── alarm.         │
    │                     │                  │   snoozed_until  │
    │                     │                  │   = now + 5min ──►│
    │                     │                  │                  ├── save()
    │                     │                  │                  ├── emit:
    │                     │                  │◄─────────────────│   alarms_changed
    │                     │◄─────────────────┤                  │
    │◄── popup closed ────┤                  │                  │
```

### 3.4. Поток данных JSON

```
┌──────────┐     load()     ┌──────────┐     save()     ┌───────────┐
│  App     │───────────────►│  Manager │───────────────►│  JSON     │
│ Startup  │                │          │                │  File     │
│          │◄───────────────┤          │◄───────────────┤           │
└──────────┘    list[Alarm] └──────────┘    json.dump   └───────────┘
                                                              │
                                                         Атомарная
                                                         запись:
                                                         1. temp.json
                                                         2. rename
```

---

## 4. Детальное описание модулей и классов

### 4.1. `src/main.py` — Точка входа

Назначение: создание `QApplication`, загрузка QSS-темы, запуск `BudilnikApp`.

```python
def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Budilnik")
    app.setOrganizationName("Budilnik")
    app.setQuitOnLastWindowClosed(False)  # Важно: не выходим при закрытии окна

    # Загрузка тёмной темы
    with open(theme_path, "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    budilnik = BudilnikApp()
    budilnik.run()

    sys.exit(app.exec())
```

**Ключевые моменты:**
- `setQuitOnLastWindowClosed(False)` — чтобы приложение оставалось в трее после закрытия окна.
- QSS загружается до создания окон, чтобы избежать flicker.
- Обработка исключений на верхнем уровне (`sys.excepthook`).

---

### 4.2. `src/app.py` — BudilnikApp (главный контроллер)

**Назначение:** Оркестратор приложения. Инициализирует все компоненты, устанавливает связи между ними.

**Атрибуты:**

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `alarm_manager` | `AlarmManager` | Модель — управление будильниками |
| `sound_manager` | `SoundManager` | Модель — воспроизведение звуков |
| `main_window` | `MainWindow` | View — главное окно |
| `tray_manager` | `TrayManager` | View — системный трей |
| `alarm_controller` | `AlarmController` | Контроллер — связь Model ↔ View |
| `tray_controller` | `TrayController` | Контроллер — обработка действий трея |

**Методы:**

| Метод | Описание |
|-------|----------|
| `run()` | Инициализация компонентов, загрузка данных, запуск |
| `_init_controllers()` | Создание контроллеров и связывание Model ↔ View |
| `_connect_signals()` | Подписка на signals (alarm_triggered → show_popup, и т.д.) |
| `show_window()` | Показать/развернуть главное окно |
| `quit_application()` | Завершить приложение (остановить звук, сохранить, выйти) |

**Логика инициализации (`run`):**

```
1. Создать SoundManager
2. Создать AlarmManager → load() из JSON
3. Создать MainWindow
4. Создать TrayManager
5. Создать AlarmController(alarm_manager, main_window, sound_manager)
6. Создать TrayController(tray_manager, app_ref)
7. Connect signals:
   - alarm_manager.alarm_triggered → BudilnikApp.on_alarm_triggered
   - alarm_manager.alarms_changed → main_window.refresh_list
   - tray_controller.show_signal → BudilnikApp.show_window
   - tray_controller.quit_signal → BudilnikApp.quit_application
8. main_window.show()
9. alarm_manager.start_timer()
```

---

### 4.3. Модели (`src/models/`)

#### 4.3.1. `alarm_model.py` — Класс Alarm

```python
@dataclass
class Alarm:
    id: str               # UUID v4
    enabled: bool         # True — активен
    title: str            # Название (метка), может быть пустым
    time: str             # "ЧЧ:ММ"
    days: list[int]       # [1..7] или []
    once: bool            # True — единоразовый
    sound_source: str     # "builtin" | "file"
    sound_name: str       # Имя встроенного звука (если builtin)
    sound_file: str | None  # Путь к файлу (если file)
    volume: int           # 0–100
    fade_in: bool         # True — плавное увеличение
    snoozed_until: str | None  # ISO datetime или None
```

**Методы:**

| Метод | Описание |
|-------|----------|
| `to_dict() -> dict` | Сериализация в dict для JSON |
| `from_dict(data: dict) -> Alarm` | Десериализация из dict |
| `is_active() -> bool` | Проверка: enabled и не просрочен snooze |
| `is_recurring() -> bool` | `not once and len(days) > 0` |
| `get_display_days() -> str` | "Пн Вт Ср ..." или "Единоразово" |
| `get_sort_key() -> str` | Для сортировки по времени |

#### 4.3.2. `alarm_manager.py` — AlarmManager

**Назначение:** CRUD-операции над будильниками, JSON I/O, фоновый таймер проверки.

**Атрибуты:**

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `_alarms` | `list[Alarm]` | Внутренний список (всегда отсортирован по времени) |
| `_timer` | `QTimer` | Таймер проверки каждые 30 секунд |
| `_snooze_timer` | `QTimer` | Таймер для обработки snoozed (каждые 10 сек) |
| `_file_path` | `str` | Путь к `alarms.json` |
| `_storage` | `Storage` | Утилита для работы с файловой системой |

**Сигналы:**

| Сигнал | Тип данных | Описание |
|--------|-----------|----------|
| `alarms_changed` | `()` | Список изменился (add/update/delete/toggle) |
| `alarm_triggered` | `(Alarm)` | Будильник сработал |

**Методы:**

| Метод | Описание |
|-------|----------|
| `load() -> None` | Загрузить JSON, распарсить, восстановить snoozed |
| `save() -> None` | Атомарная запись (temp + rename), форматирование JSON |
| `get_all() -> list[Alarm]` | Получить копию списка (отсортированную) |
| `get_by_id(id: str) -> Alarm \| None` | Найти по UUID |
| `add(alarm: Alarm) -> None` | Добавить, сохранить, emit |
| `update(alarm: Alarm) -> None` | Обновить, сохранить, emit |
| `remove(alarm_id: str) -> None` | Удалить, сохранить, emit |
| `toggle(alarm_id: str) -> None` | Переключить enabled, сохранить, emit |
| `check_alarms() -> None` | Проверить все активные на совпадение времени → emit alarm_triggered |
| `snooze(alarm_id: str, minutes: int) -> None` | Установить snoozed_until, сохранить |
| `start_timer() -> None` | Запустить `_timer` (30 сек) |
| `stop_timer() -> None` | Остановить `_timer` |
| `_handle_snoozed() -> None` | Проверить истекшие snoozed будильники |

**Логика `check_alarms()`:**

```python
def check_alarms(self) -> None:
    now = QDateTime.currentDateTime()
    current_time = now.toString("HH:mm")
    current_day = now.date().dayOfWeek()  # 1=Пн ... 7=Вс

    for alarm in self._alarms:
        if not alarm.is_active():
            continue
        if alarm.snoozed_until is not None:
            continue

        if alarm.time != current_time:
            continue

        if alarm.once or current_day in alarm.days:
            self.alarm_triggered.emit(alarm)
            if alarm.once:
                alarm.enabled = False
                self.save()
                self.alarms_changed.emit()
```

> **Важно:** Проверка каждые 30 секунд → допуск ±30 секунд. Если пользователь
> выставил 07:30:00, а проверка может пройти в 07:30:15 или 07:30:45 —
> всё равно сработает. Это приемлемо по спецификации.

#### 4.3.3. `sound_manager.py` — SoundManager

**Назначение:** Воспроизведение звуков, управление громкостью, fade-in.

**Атрибуты:**

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `_player` | `QMediaPlayer` | Основной плеер |
| `_audio_output` | `QAudioOutput` | Выход аудио (для регулировки громкости) |
| `_builtin_sounds` | `dict[str, str]` | Карта: имя звука → путь к файлу |
| `_fade_timer` | `QTimer` | Таймер для fade-in (200ms intervals) |
| `_fade_step` | `float` | Шаг увеличения громкости |
| `_current_volume` | `float` | Текущая громкость (0.0–1.0) |
| `_target_volume` | `float` | Целевая громкость (0.0–1.0) |
| `_is_playing` | `bool` | Флаг воспроизведения |

**Методы:**

| Метод | Описание |
|-------|----------|
| `get_builtin_names() -> list[str]` | Список доступных встроенных звуков |
| `get_builtin_path(name: str) -> str \| None` | Путь к встроенному звуку |
| `play_builtin(name: str, volume: int) -> None` | Воспроизвести встроенный звук |
| `play_file(path: str, volume: int) -> None` | Воспроизвести файл |
| `play_preview(path: str, volume: int) -> None` | Предпрослушивание (без loop) |
| `stop() -> None` | Остановить воспроизведение |
| `set_volume(percent: int) -> None` | Установить громкость 0–100 |
| `start_fade(target_volume: int, duration_ms: int = 30000) -> None` | Запустить fade-in |
| `stop_fade() -> None` | Остановить fade-in |

**Логика fade-in:**

```python
def start_fade(self, target_volume: int, duration_ms: int = 30000) -> None:
    self._target_volume = target_volume / 100.0
    self._current_volume = 0.0
    self._audio_output.setVolume(0.0)

    steps = duration_ms / 200  # 150 шагов за 30 секунд
    self._fade_step = self._target_volume / steps

    self._fade_timer.timeout.connect(self._fade_tick)
    self._fade_timer.start(200)  # каждые 200ms

def _fade_tick(self) -> None:
    self._current_volume += self._fade_step
    if self._current_volume >= self._target_volume:
        self._current_volume = self._target_volume
        self._fade_timer.stop()
    self._audio_output.setVolume(self._current_volume)
```

---

### 4.4. Представления (`src/views/`)

#### 4.4.1. `main_window.py` — MainWindow

**Назначение:** QMainWindow — главное окно со списком будильников.

**Атрибуты:**

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `_alarm_list_widget` | `QScrollArea` | Область со списком карточек |
| `_add_button` | `QPushButton` | Кнопка "+" |
| `_empty_state_widget` | `QWidget` | Заглушка "нет будильников" |
| `_card_widgets` | `dict[str, AlarmCardWidget]` | id → widget |

**Сигналы:**

| Сигнал | Данные | Описание |
|--------|--------|----------|
| `add_alarm_requested` | `()` | Пользователь нажал "+" |
| `edit_alarm_requested` | `(alarm_id: str)` | Пользователь кликнул на карточку |
| `toggle_alarm_requested` | `(alarm_id: str, enabled: bool)` | Переключение toggle |
| `delete_alarm_requested` | `(alarm_id: str)` | Удаление будильника |

**Методы:**

| Метод | Описание |
|-------|----------|
| `refresh_list(alarms: list[Alarm])` | Полностью перерисовать список карточек |
| `show_empty_state()` | Показать заглушку |
| `show_alarm_popup(alarm: Alarm) -> AlarmPopup` | Показать окно срабатывания |
| `closeEvent(event)` | Переопределён: hide вместо close, emit signal в трей |

**Логика refresh_list:**

```python
def refresh_list(self, alarms: list[Alarm]) -> None:
    # Очистить текущий список виджетов
    for card in self._card_widgets.values():
        self._scroll_layout.removeWidget(card)
        card.deleteLater()
    self._card_widgets.clear()

    if not alarms:
        self.show_empty_state()
        return

    self._empty_state_widget.hide()
    for alarm in sorted(alarms, key=lambda a: a.time):
        card = AlarmCardWidget(alarm)
        self._connect_card_signals(card)
        self._scroll_layout.addWidget(card)
        self._card_widgets[alarm.id] = card
```

#### 4.4.2. `alarm_card_widget.py` — AlarmCardWidget

**Назначение:** QWidget — карточка одного будильника в списке.

**Композиция:**

| Элемент | Тип | Описание |
|---------|-----|----------|
| `_time_label` | `QLabel` | Крупное время "07:30" |
| `_days_label` | `QLabel` | Дни недели или "Единоразово" |
| `_title_label` | `QLabel` | Название (если есть) |
| `_toggle_switch` | `QCheckBox` | Стилизованный switch |
| `_delete_button` | `QPushButton` | Иконка корзины |
| `_shadow` | `QGraphicsDropShadowEffect` | Тень карточки |

**Сигналы:**

| Сигнал | Данные | Описание |
|--------|--------|----------|
| `toggled` | `(alarm_id: str, enabled: bool)` | Изменён switch |
| `edit_clicked` | `(alarm_id: str)` | Клик по карточке |
| `delete_clicked` | `(alarm_id: str)` | Клик по корзине |

**Методы:**

| Метод | Описание |
|-------|----------|
| `set_alarm(alarm: Alarm)` | Обновить данные карточки из модели |
| `set_active(active: bool)` | Визуально включить/затемнить |
| `animate_hover_in()` | Анимация подъёма тени |
| `animate_hover_out()` | Анимация возврата тени |
| `enterEvent(event)` | Триггер `animate_hover_in()` |
| `leaveEvent(event)` | Триггер `animate_hover_out()` |
| `mousePressEvent(event)` | Триггер `edit_clicked` |

> **Стилизация:** Все визуальные элементы настраиваются через QSS-классы.
> Switch реализован через QCheckBox с кастомным QSS (псевдосостояние `::indicator`).

#### 4.4.3. `alarm_form_dialog.py` — AlarmFormDialog

**Назначение:** QDialog — форма создания или редактирования будильника.

**Атрибуты:**

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `_time_edit` | `QTimeEdit` | Выбор времени (ЧЧ:ММ) |
| `_day_checkboxes` | `list[QCheckBox]` | 7 чекбоксов для дней недели |
| `_once_checkbox` | `QCheckBox` | "Единоразово" |
| `_sound_combo` | `QComboBox` | Выбор встроенного звука |
| `_preview_play_btn` | `QPushButton` | Прослушать звук |
| `_preview_stop_btn` | `QPushButton` | Остановить предпрослушивание |
| `_file_radio` | `QRadioButton` | "Свой файл" |
| `_file_path_label` | `QLabel` | Путь к файлу |
| `_browse_button` | `QPushButton` | Выбрать файл |
| `_reset_file_button` | `QPushButton` | Сбросить на встроенный |
| `_volume_slider` | `QSlider` | Громкость |
| `_volume_label` | `QLabel` | "75%" |
| `_volume_icon` | `QLabel` | Иконка динамика |
| `_fade_in_checkbox` | `QCheckBox` | Fade-in |
| `_title_edit` | `QLineEdit` | Название |
| `_save_button` | `QPushButton` | Сохранить |
| `_cancel_button` | `QPushButton` | Отмена |
| `_editing_alarm_id` | `str \| None` | ID редактируемого (None при создании) |

**Сигналы:**

| Сигнал | Данные | Описание |
|--------|--------|----------|
| `saved` | `(alarm_data: dict)` | Форма сохранена (данные для Controller) |
| `cancelled` | `()` | Форма закрыта без сохранения |

**Методы:**

| Метод | Описание |
|-------|----------|
| `set_alarm(alarm: Alarm)` | Заполнить форму данными (режим редактирования) |
| `get_form_data() -> dict` | Собрать данные из полей формы |
| `validate() -> bool` | Валидация перед сохранением |
| `_on_once_toggled(checked: bool)` | Блокировка/разблокировка дней недели |
| `_on_day_toggled()` | Если выбран день → снять once |
| `_on_file_selected()` | QFileDialog → выбор .wav/.mp3 |
| `_on_preview_play()` | Воспроизвести звук (через контроллер) |
| `_on_preview_stop()` | Остановить предпрослушивание |
| `_update_volume_icon(value: int)` | Сменить иконку динамика |

**Логика `get_form_data()`:**

```python
def get_form_data(self) -> dict:
    return {
        "id": self._editing_alarm_id or str(uuid.uuid4()),
        "enabled": True,
        "title": self._title_edit.text().strip(),
        "time": self._time_edit.time().toString("HH:mm"),
        "days": [i+1 for i, cb in enumerate(self._day_checkboxes) if cb.isChecked()],
        "once": self._once_checkbox.isChecked(),
        "sound_source": "builtin" if not self._file_radio.isChecked() else "file",
        "sound_name": self._sound_combo.currentData() if not self._file_radio.isChecked() else "",
        "sound_file": self._file_path_label.text() if self._file_radio.isChecked() else None,
        "volume": self._volume_slider.value(),
        "fade_in": self._fade_in_checkbox.isChecked(),
        "snoozed_until": None,
    }
```

#### 4.4.4. `alarm_popup.py` — AlarmPopup

**Назначение:** QDialog — окно срабатывания будильника (поверх всех).

**Атрибуты:**

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `_alarm` | `Alarm` | Данные сработавшего будильника |
| `_title_label` | `QLabel` | Название или "Будильник!" |
| `_time_label` | `QLabel` | Крупное время |
| `_dismiss_button` | `QPushButton` | Красная кнопка "Выключить" |
| `_snooze_5_btn` | `QPushButton` | Отложить 5 мин |
| `_snooze_10_btn` | `QPushButton` | Отложить 10 мин |
| `_snooze_15_btn` | `QPushButton` | Отложить 15 мин |
| `_pulse_animation` | `QVariantAnimation` | Анимация пульсации фона |
| `_scale_animation` | `QPropertyAnimation` | Анимация появления |

**Сигналы:**

| Сигнал | Данные | Описание |
|--------|--------|----------|
| `dismissed` | `(alarm_id: str)` | Будильник выключен |
| `snoozed` | `(alarm_id: str, minutes: int)` | Отложен на N минут |

**Методы:**

| Метод | Описание |
|-------|----------|
| `set_alarm(alarm: Alarm)` | Заполнить данные |
| `start_pulse_animation()` | Циклическая анимация фона (1.5 сек период) |
| `start_scale_animation()` | Анимация появления (0.8 → 1.0 за 300ms) |
| `stop_animations()` | Остановить все анимации |
| `closeEvent(event)` | Остановить звук при закрытии |

**Анимация пульсации:**

```python
def start_pulse_animation(self) -> None:
    self._pulse_animation = QVariantAnimation(self)
    self._pulse_animation.setDuration(1500)  # 1.5 сек
    self._pulse_animation.setStartValue(QColor("#1a1a2e"))
    self._pulse_animation.setEndValue(QColor("#2d004d"))
    self._pulse_animation.setLoopCount(-1)  # бесконечно
    self._pulse_animation.valueChanged.connect(
        lambda color: self.setStyleSheet(
            f"background-color: {color.name()};"
        )
    )
    self._pulse_animation.start()
```

#### 4.4.5. `tray_manager.py` — TrayManager

**Назначение:** QSystemTrayIcon — иконка в трее, контекстное меню, toast-уведомления.

**Атрибуты:**

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `_tray_icon` | `QSystemTrayIcon` | Иконка в трее |
| `_menu` | `QMenu` | Контекстное меню |
| `_show_action` | `QAction` | "Показать" |
| `_settings_action` | `QAction` | "Настройки" |
| `_quit_action` | `QAction` | "Выход" |

**Сигналы:**

| Сигнал | Описание |
|--------|----------|
| `show_requested` | Пользователь выбрал "Показать" |
| `settings_requested` | Пользователь выбрал "Настройки" |
| `quit_requested` | Пользователь выбрал "Выход" |

**Методы:**

| Метод | Описание |
|-------|----------|
| `setup()` | Создание иконки, меню, подключение signals |
| `set_active_icon(active: bool)` | Цветная / серая иконка |
| `show_toast(title: str, message: str)` | Системное уведомление (QSystemTrayIcon.showMessage) |
| `update_menu(alarms_count: int)` | Обновить меню (добавить/убрать пункты) |

---

### 4.5. Контроллеры (`src/controllers/`)

#### 4.5.1. `alarm_controller.py` — AlarmController

**Назначение:** Центральный контроллер — связывает AlarmManager, MainWindow, SoundManager и AlarmPopup.

**Атрибуты:**

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `_alarm_manager` | `AlarmManager` | Модель |
| `_main_window` | `MainWindow` | View |
| `_sound_manager` | `SoundManager` | Модель звука |
| `_active_popup` | `AlarmPopup \| None` | Текущее окно срабатывания (только одно) |

**Методы:**

| Метод | Описание |
|-------|----------|
| `setup()` | Подключить сигналы View → Controller → Model |
| `on_add_alarm()` | Открыть AlarmFormDialog (режим создания) |
| `on_edit_alarm(alarm_id: str)` | Открыть AlarmFormDialog (режим редактирования) |
| `on_save_alarm(form_data: dict)` | Создать/обновить Alarm через AlarmManager |
| `on_delete_alarm(alarm_id: str)` | Подтверждение → удаление через AlarmManager |
| `on_toggle_alarm(alarm_id: str, enabled: bool)` | Переключение через AlarmManager |
| `on_alarm_triggered(alarm: Alarm)` | Показать AlarmPopup, запустить звук |
| `on_dismiss_alarm(alarm_id: str)` | Остановить звук, закрыть popup |
| `on_snooze_alarm(alarm_id: str, minutes: int)` | Остановить звук, установить snooze |
| `_confirm_delete(alarm) -> bool` | Диалог подтверждения удаления |

**Подключение сигналов (`setup`):**

```python
def setup(self) -> None:
    # View → Controller
    self._main_window.add_alarm_requested.connect(self.on_add_alarm)
    self._main_window.edit_alarm_requested.connect(self.on_edit_alarm)
    self._main_window.toggle_alarm_requested.connect(self.on_toggle_alarm)
    self._main_window.delete_alarm_requested.connect(self.on_delete_alarm)

    # Model → Controller
    self._alarm_manager.alarm_triggered.connect(self.on_alarm_triggered)
    self._alarm_manager.alarms_changed.connect(
        lambda: self._main_window.refresh_list(self._alarm_manager.get_all())
    )
```

#### 4.5.2. `tray_controller.py` — TrayController

**Назначение:** Контроллер для системного трея — обрабатывает действия из контекстного меню.

**Сигналы:**

| Сигнал | Описание |
|--------|----------|
| `show_signal` | Показать главное окно |
| `quit_signal` | Завершить приложение |

**Методы:**

| Метод | Описание |
|-------|----------|
| `setup()` | Подключить сигналы TrayManager → Controller → BudilnikApp |
| `on_tray_activated(reason)` | Левый клик → показать окно |
| `on_show()` | emit `show_signal` |
| `on_quit()` | emit `quit_signal` |

---

### 4.6. Утилиты (`src/utils/`)

#### 4.6.1. `constants.py` — Константы

```python
# Цветовая палитра (Material Dark)
COLOR_BG = "#1e1e2e"
COLOR_CARD_BG = "#2a2a3e"
COLOR_PRIMARY = "#7c3aed"
COLOR_ACCENT = "#ec4899"
COLOR_TEXT_PRIMARY = "#e2e8f0"
COLOR_TEXT_SECONDARY = "#94a3b8"
COLOR_SUCCESS = "#22c55e"
COLOR_DANGER = "#ef4444"

# Пути
SOUNDS_DIR = "resources/sounds"
ICONS_DIR = "resources/icons"
STYLES_DIR = "resources/styles"
ALARMS_FILE = "alarms.json"

# Встроенные звуки
BUILTIN_SOUNDS: dict[str, str] = {
    "classic": "classic.mp3",
    "gentle": "gentle.mp3",
    "nature": "nature.mp3",
    "energetic": "energetic.mp3",
    "lounge": "lounge.mp3",
}

BUILTIN_SOUND_NAMES: dict[str, str] = {
    "classic": "Классический",
    "gentle": "Нежный",
    "nature": "Природа",
    "energetic": "Энергичный",
    "lounge": "Лаунж",
}

# Таймеры
ALARM_CHECK_INTERVAL_MS = 30000  # 30 секунд
SNOOZE_CHECK_INTERVAL_MS = 10000  # 10 секунд
FADE_INTERVAL_MS = 200  # 200 мс для fade-in
FADE_DURATION_MS = 30000  # 30 секунд

# Окно срабатывания
POPUP_WIDTH = 400
POPUP_HEIGHT = 300
PULSE_DURATION_MS = 1500
SCALE_DURATION_MS = 300

# UI
CARD_SHADOW_BLUR = 20
CARD_SHADOW_OFFSET = 4
CARD_SHADOW_OPACITY = 0.3
CARD_RADIUS = 16
BUTTON_RADIUS = 12
DISABLED_OPACITY = 0.5
```

#### 4.6.2. `storage.py` — Storage

**Назначение:** Работа с файловой системой — пути, создание директорий, атомарная запись.

**Методы:**

| Метод | Описание |
|-------|----------|
| `get_data_dir() -> str` | Путь к `%APPDATA%/Budilnik/` (или `./` в dev) |
| `ensure_data_dir() -> None` | Создать директорию, если нет |
| `get_alarms_path() -> str` | Полный путь к `alarms.json` |
| `get_resource_path(relative: str) -> str` | Путь к ресурсу (учитывает PyInstaller `sys._MEIPASS`) |
| `atomic_write(filepath: str, data: str) -> None` | Запись через temp + rename |
| `read_json(filepath: str) -> dict \| list` | Безопасное чтение JSON |

**Атомарная запись:**

```python
@staticmethod
def atomic_write(filepath: str, data: str) -> None:
    """Атомарная запись: temp → rename. Предотвращает повреждение JSON."""
    dir_path = os.path.dirname(filepath)
    temp_path = os.path.join(dir_path, f".{os.path.basename(filepath)}.tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())  # Принудительная запись на диск

    os.replace(temp_path, filepath)  # Атомарно для NTFS
```

#### 4.6.3. `helpers.py` — Вспомогательные функции

**Функции:**

| Функция | Описание |
|---------|----------|
| `generate_id() -> str` | UUID v4 строка |
| `time_to_minutes(time_str: str) -> int` | "07:30" → 450 (для сравнения) |
| `validate_time_format(time_str: str) -> bool` | Проверка "ЧЧ:ММ" |
| `validate_alarm_data(data: dict) -> bool` | Валидация полей Alarm |
| `format_days(days: list[int]) -> str` | [1,3,5] → "Пн Ср Пт" |
| `clamp(value: int, min_v: int, max_v: int) -> int` | Ограничение значения |
| `get_today_day() -> int` | Текущий день недели (1=Пн) |
| `parse_snoozed_until(iso_str: str) -> QDateTime \| None` | Парсинг snoozed_until |
| `resource_path(relative: str) -> str` | Путь к ресурсу (PyInstaller compat) |

---

## 5. Схема сигналов и слотов (Signal/Slot Map)

### 5.1. Полная карта соединений

```
AlarmManager (Model)
├── alarms_changed() ────────────────────────────────────► MainWindow.refresh_list()
│                                                         AlarmCardWidget (пересоздаются)
│                                                         TrayManager.update_menu()
│
├── alarm_triggered(Alarm) ──────────────────────────────► AlarmController.on_alarm_triggered()
      │                                                     │
      │                                                     ├── SoundManager.play_*(alarm)
      │                                                     ├── MainWindow.show_alarm_popup()
      │                                                     └── TrayManager.show_toast()

AlarmCardWidget (View)
├── toggled(alarm_id, enabled) ──────────────────────────► AlarmController.on_toggle_alarm()
│                                                           └── AlarmManager.toggle()
│
├── edit_clicked(alarm_id) ──────────────────────────────► AlarmController.on_edit_alarm()
│                                                           └── AlarmFormDialog open
│
└── delete_clicked(alarm_id) ────────────────────────────► AlarmController.on_delete_alarm()
                                                            └── AlarmManager.remove()

AlarmFormDialog (View)
├── saved(form_data) ────────────────────────────────────► AlarmController.on_save_alarm()
│                                                           └── AlarmManager.add() / update()
│
└── cancelled() ─────────────────────────────────────────► (nothing — просто закрыть)

AlarmPopup (View)
├── dismissed(alarm_id) ─────────────────────────────────► AlarmController.on_dismiss_alarm()
│                                                           ├── SoundManager.stop()
│                                                           ├── popup.close()
│                                                           └── AlarmManager (deactivate if once)
│
└── snoozed(alarm_id, minutes) ──────────────────────────► AlarmController.on_snooze_alarm()
                                                            ├── SoundManager.stop()
                                                            ├── popup.close()
                                                            └── AlarmManager.snooze()

TrayManager (View)
├── show_requested() ────────────────────────────────────► BudilnikApp.show_window()
│                                                           └── MainWindow.show() + raise()
│
├── settings_requested() ────────────────────────────────► BudilnikApp.show_window()
│                                                           └── MainWindow.show() + raise()
│
└── quit_requested() ────────────────────────────────────► BudilnikApp.quit_application()
                                                            ├── SoundManager.stop()
                                                            ├── AlarmManager.stop_timer()
                                                            └── QApplication.quit()

MainWindow (View)
├── add_alarm_requested() ───────────────────────────────► AlarmController.on_add_alarm()
│                                                           └── AlarmFormDialog open
│
├── edit_alarm_requested(alarm_id) ──────────────────────► AlarmController.on_edit_alarm()
├── toggle_alarm_requested(id, en) ──────────────────────► AlarmController.on_toggle_alarm()
└── delete_alarm_requested(id) ────────────────────────► AlarmController.on_delete_alarm()

TrayController
├── show_signal() ───────────────────────────────────────► BudilnikApp.show_window()
└── quit_signal() ──────────────────────────────────────► BudilnikApp.quit_application()
```

### 5.2. Принципы соединений

1. **Все соединения прямые** (direct connection, т.к. всё в одном потоке Qt).
2. **Никаких callback-цепей** — только сигналы.
3. **View не знает о Model** — все сигналы View идут в Controller.
4. **Model не знает о View** — сигналы Model обрабатывает Controller.
5. **Controller может обновлять View только через публичные методы**, не через сигналы.

---

## 6. План реализации (порядок написания модулей)

### Этап 1: Каркас (Foundation)

| Шаг | Модуль | Описание | Ожидаемый результат |
|-----|--------|----------|---------------------|
| 1.1 | `utils/constants.py` | Все константы, цвета, пути, имена звуков | Единый источник констант |
| 1.2 | `utils/storage.py` | Storage: пути, атомарная запись, `resource_path` | Можно читать/писать JSON атомарно |
| 1.3 | `utils/helpers.py` | Вспомогательные функции (uuid, валидация, форматирование) | Чистые функции без зависимостей от Qt |
| 1.4 | `models/alarm_model.py` | Dataclass Alarm + `to_dict()` / `from_dict()` | Модель данных готова |
| 1.5 | `models/alarm_manager.py` | AlarmManager: load, save, CRUD, QTimer, check_alarms | Будильники живут в памяти и на диске |
| 1.6 | `models/sound_manager.py` | SoundManager: плеер, громкость, fade-in | Звук воспроизводится и регулируется |

**Проверка этапа 1:** Юнит-тесты для AlarmManager и SoundManager. Консольный скрипт, который загружает/сохраняет будильники.

### Этап 2: View — статические компоненты

| Шаг | Модуль | Описание | Ожидаемый результат |
|-----|--------|----------|---------------------|
| 2.1 | `resources/styles/theme.qss` | Полный QSS-файл тёмной темы | Тёмная тема выглядит целостно |
| 2.2 | `views/main_window.py` | MainWindow: заголовок, кнопка "+", scroll area, empty state | Главное окно отображается |
| 2.3 | `views/alarm_card_widget.py` | AlarmCardWidget: время, дни, toggle, удаление, тень, hover | Карточка отображается, toggle работает |
| 2.4 | `views/tray_manager.py` | TrayManager: иконка, контекстное меню | Иконка в трее, меню работает |
| 2.5 | `main.py` + `app.py` | Базовая инициализация, запуск окна | Приложение стартует и показывает окно |

**Проверка этапа 2:** MainWindow открывается, карточки рисуются с тестовыми данными, иконка в трее появляется.

### Этап 3: View — динамические компоненты

| Шаг | Модуль | Описание | Ожидаемый результат |
|-----|--------|----------|---------------------|
| 3.1 | `views/alarm_form_dialog.py` | Форма: время, дни, звук, громкость, fade-in, название | Можно заполнить форму, валидация работает |
| 3.2 | `views/alarm_popup.py` | Окно срабатывания: кнопки, пульсация, анимации | Окно появляется, пульсирует, анимации работают |

**Проверка этапа 3:** Форму можно открыть и заполнить. Popup показывается и анимируется.

### Этап 4: Контроллеры — связка Model + View

| Шаг | Модуль | Описание | Ожидаемый результат |
|-----|--------|----------|---------------------|
| 4.1 | `controllers/alarm_controller.py` | Подключение сигналов, CRUD-операции, popup, snooze/dismiss | Полный цикл создания → срабатывания |
| 4.2 | `controllers/tray_controller.py` | Обработка действий трея, show/quit | Трей управляет окном и выходом |
| 4.3 | `app.py` (финальная версия) | Полная инициализация всех связей | Приложение работает целиком |

**Проверка этапа 4:** Создание → сохранение → срабатывание → отложить/выключить. Закрытие окна → трей. Выход через трей.

### Этап 5: Полировка и сборка

| Шаг | Модуль | Описание | Ожидаемый результат |
|-----|--------|----------|---------------------|
| 5.1 | Анимации | Все hover, transition, scale, pulse | Плавные анимации везде |
| 5.2 | Toast-уведомления | Системные уведомления при срабатывании | Toast при скрытом окне |
| 5.3 | Иконки | Все SVG-иконки, иконка приложения | Все иконки на месте |
| 5.4 | Fade-in | Тестирование 30-секундного fade-in | Громкость растёт плавно |
| 5.5 | `pyproject.toml` | Конфигурация проекта | Зависимости, метаданные |
| 5.6 | PyInstaller | `Budilnik.spec`, сборка, тестирование .exe | Работающий .exe |
| 5.7 | Тесты | Юнит-тесты для моделей | >70% покрытие моделей |

---

## 7. Рекомендации по стилю кода и архитектурные паттерны

### 7.1. Naming conventions

| Элемент | Стиль | Пример |
|---------|-------|--------|
| Классы | PascalCase | `AlarmManager`, `AlarmCardWidget`, `MainWindow` |
| Методы и функции | snake_case | `check_alarms()`, `get_form_data()`, `start_fade()` |
| Атрибуты (private) | `_` prefix | `_alarms`, `_timer`, `_current_volume` |
| Константы | UPPER_CASE | `COLOR_BG`, `ALARM_CHECK_INTERVAL_MS` |
| Переменные | snake_case | `alarm_list`, `form_data`, `active_popup` |
| Типы | PascalCase | `Alarm`, `QTimer`, `QMediaPlayer` |
| Сигналы | snake_case | `alarm_triggered`, `alarms_changed`, `snoozed` |
| UI текст | Русский | `"Будильники"`, `"Сохранить"`, `"Выключить"` |
| Комментарии | English | `# Atomic write: temp + rename` |
| Docstrings | Google-style | `"""Load alarms from JSON file."""` |

### 7.2. Обязательные паттерны

#### Паттерн 1: Атомарное сохранение

```python
# Везде, где пишем в JSON — только через Storage.atomic_write()
self._storage.atomic_write(path, json_data)
```

#### Паттерн 2: Единый источник истины (Single Source of Truth)

```python
# AlarmManager._alarms — единственное хранилище данных.
# Нигде больше не хранятся копии списка будильников.
# View получает данные через get_all() и перерисовывается.
```

#### Паттерн 3: Controller как посредник

```python
# Controller НЕ содержит бизнес-логики.
# Он только: получает сигнал → вызывает метод Model → обновляет View.
# Пример ПРАВИЛЬНО:
def on_toggle_alarm(self, alarm_id: str, enabled: bool) -> None:
    self._alarm_manager.toggle(alarm_id)

# Пример НЕПРАВИЛЬНО (логика в контроллере):
def on_toggle_alarm(self, alarm_id: str, enabled: bool) -> None:
    alarm = self._alarm_manager.get_by_id(alarm_id)
    alarm.enabled = enabled  # Логика изменения — в Model!
    self._alarm_manager.save()
```

#### Паттерн 4: Qt Signal/Slot для всех cross-layer коммуникаций

```python
# Model → View через сигналы, НЕ через прямые вызовы:
class AlarmManager(QObject):
    alarms_changed = Signal()

    def add(self, alarm: Alarm) -> None:
        self._alarms.append(alarm)
        self.save()
        self.alarms_changed.emit()  # Controller подхватит
```

#### Паттерн 5: RAII для ресурсов

```python
# SoundManager гарантирует освобождение QMediaPlayer при завершении.
# Все таймеры останавливаются в деструкторе.
def stop_all(self) -> None:
    self.stop()
    self._fade_timer.stop()
```

### 7.3. Рекомендации по PySide6

1. **Никогда не храните ссылки на QWidget, которые удалены** — используйте `deleteLater()` и очищайте `_card_widgets` словарь.
2. **Используйте `QObject` как базовый класс для всех классов, испускающих сигналы** — это обязательное требование Qt.
3. **Не создавайте виджеты в глобальной области видимости** — только как атрибуты классов.
4. **Для анимаций используйте `QPropertyAnimation` и `QVariantAnimation`** — они работают в главном потоке Qt и не требуют threading.
5. **Не блокируйте главный поток** — звук воспроизводится асинхронно через `QMediaPlayer`, таймеры — через `QTimer`.
6. **Для иконок используйте SVG** — они масштабируются без потери качества. PySide6 поддерживает `QIcon` из `.svg` файлов.

### 7.4. Структура импортов

```python
# Порядок (разделены пустой строкой):
# 1. Стандартная библиотека
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Optional

# 2. PySide6
from PySide6.QtCore import (
    QObject, Signal, QTimer, QDateTime, QPropertyAnimation,
    QVariantAnimation, QEasingCurve, QPoint, QSize, Qt,
)
from PySide6.QtGui import QColor, QIcon, QFont, QAction, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QComboBox, QSlider, QLineEdit,
    QTimeEdit, QSpinBox, QScrollArea, QDialog, QFileDialog,
    QSystemTrayIcon, QMenu, QMessageBox, QGraphicsDropShadowEffect,
)

# 3. Внутренние модули
from models.alarm_model import Alarm
from models.alarm_manager import AlarmManager
from models.sound_manager import SoundManager
from utils.constants import COLOR_BG, ALARM_CHECK_INTERVAL_MS
```

### 7.5. Обработка ошибок

```python
# При загрузке JSON — игнорировать повреждённые записи:
def load(self) -> None:
    try:
        data = self._storage.read_json(self._file_path)
        self._alarms = [Alarm.from_dict(item) for item in data.get("alarms", [])
                       if self._validate_alarm_dict(item)]
    except (FileNotFoundError, json.JSONDecodeError):
        self._alarms = []  # Новый файл, если нет
    except Exception as e:
        logger.error(f"Failed to load alarms: {e}")
        self._alarms = []

# Валидация каждого будильника при загрузке
@staticmethod
def _validate_alarm_dict(data: dict) -> bool:
    required = {"id", "enabled", "time", "days", "once",
                "sound_source", "volume", "fade_in"}
    if not required.issubset(data.keys()):
        return False
    if not isinstance(data.get("time"), str) or ":" not in data["time"]:
        return False
    return True
```

---

## 8. Ключевые архитектурные решения и их обоснование

| Решение | Выбор | Альтернативы | Почему |
|---------|-------|-------------|--------|
| **Архитектура** | MVC (Model-View-Controller) | MVVM, MVP | MVC — простейший паттерн для PySide6. Qt спроектирован под сигналы/слоты, что идеально ложится на MVC. MVVM добавил бы лишнюю прослойку для такого простого приложения. |
| **Хранение** | JSON | SQLite, YAML, pickle | JSON — человекочитаемый, не требует схемы, легко дебажить. SQLite избыточен для 10–50 будильников. |
| **Атомарная запись** | temp + rename | Прямая запись | Предотвращает повреждение JSON при аварийном завершении. Для NTFS `os.replace` — атомарная операция. |
| **Аудио** | QMediaPlayer + QAudioOutput | QSoundEffect, winsound, pygame | QMediaPlayer поддерживает MP3 и WAV, loop, регулировку громкости. QSoundEffect — только WAV, без loop. |
| **Таймер проверки** | QTimer (30 сек) | Threading.Timer, sched | QTimer работает в главном потоке Qt — не нужно синхронизировать доступ к данным. 30 сек — оптимальный баланс точности и производительности. |
| **Сборка** | PyInstaller (onefile) | Nuitka, cx_Freeze | PyInstaller — стандарт для PySide6, поддержка onefile, иконки, UPX. |
| **Тёмная тема** | QSS-файл | QPalette, qt-material | QSS — декларативный, легко менять, отдельный файл. Palette не даёт такой гибкости. |
| **Анимации** | QPropertyAnimation | QML, CSS animations | QPropertyAnimation — встроенный в PySide6, не требует QML. Достаточно для hover, пульсации, scale. |
| **Иконки** | SVG + PNG fallback | Только PNG | SVG — векторные, масштабируются. Для .exe иконки — .ico. Для трея на Windows лучше .png 32×32. |

---

## 9. Компромиссы (Trade-offs)

| Компромисс | Принятое решение | Последствия |
|------------|------------------|-------------|
| **Точность срабатывания** | Проверка каждые 30 сек (QTimer) | Будильник может сработать с задержкой до 30 секунд. Это приемлемо для будильника. Более частые проверки (1 сек) — лишняя нагрузка на CPU. |
| **Только один звук одновременно** | Один QMediaPlayer | Если сработают два будильника одновременно — звук будет только от последнего. Вероятность низкая. В будущем можно queue. |
| **Одно окно popup** | Только один AlarmPopup активен | Второй будильник не откроет второе окно, но звук переключится. Можно улучшить до стека popup'ов. |
| **Только Windows** | WinAPI для поведения трея | Нет кроссплатформенности. Но SPEC требует только Windows. |
| **JSON в памяти** | Весь список загружается в RAM | Для 100+ будильников — ~50 KB, что ничтожно. Масштабируется. |
| **Нет шины событий** | Прямые сигналы через Controller | При 5+ контроллерах сложнее расширять. Для текущего объёма — оптимально. |

---

## 10. Тестирование

### Модули для unit-тестирования

```
tests/
├── test_alarm_model.py        # Alarm dataclass: to_dict/from_dict, is_active
├── test_alarm_manager.py      # CRUD, save/load, check_alarms, snooze
├── test_sound_manager.py      # (требует аудиоустройства — интеграционные)
├── test_storage.py            # Атомарная запись, пути, валидация
└── test_helpers.py            # validate, format, generate_id
```

### Интеграционное тестирование

- Главный экран: создание, редактирование, удаление будильников (через QTest)
- Срабатывание: подмена `QDateTime.currentDateTime()` для теста
- Трей: проверка создания иконки и меню
- JSON: загрузка/сохранение с реальными данными

---

## 11. Диаграмма последовательности (Sequence) — ключевой сценарий

### Сценарий "Срабатывание повторяющегося будильника → Отложить"

```
QTimer      AlarmManager   AlarmController  SoundManager   AlarmPopup    MainWindow
  │              │               │               │            │             │
  ├─tick(30s)───►│               │               │            │             │
  │              │               │               │            │             │
  │              ├─check_alarms()│               │            │             │
  │              │─сравнить time │               │            │             │
  │              │─day in days  │               │            │             │
  │              │               │               │            │             │
  │              ├─alarm_triggered(alarm)───────►│            │             │
  │              │               │               │            │             │
  │              │               ├─play_builtin(name, vol)──►│             │
  │              │               │               │  play()   │             │
  │              │               │               │  (loop)   │             │
  │              │               │               │            │             │
  │              │               ├─show_alarm_popup(alarm)───►│             │
  │              │               │               │            │             │
  │              │               │               │            ├─animate()   │
  │              │               │               │            ├─pulse()     │
  │              │               │               │            │             │
  │              │               │               │     [Пользователь         │
  │              │               │               │      нажимает             │
  │              │               │               │      "Отложить 5"]       │
  │              │               │               │            │             │
  │              │               │               │◄───────────┤             │
  │              │               │◄─snoozed──────┤            │             │
  │              │               │  (id, 5)      │            │             │
  │              │               │               │            │             │
  │              │               ├─stop()───────►│  stop()    │             │
  │              │               │               │            │             │
  │              │               ├─snooze(id,5)─►│            │             │
  │              │               │               │            │             │
  │              │               │               │  ── 5 мин ──│             │
  │              │               │               │            │             │
  │              │  [timer tick] │               │            │             │
  │              │─check_alarms()│               │            │             │
  │              │─alarm.snoozed_until < now     │            │             │
  │              │─reset snooze, срабатывает     │            │             │
  │              │                               │            │             │
```

---

## 12. Заключение

Предложенная архитектура обеспечивает:

- **Чёткое разделение ответственности** между Model, View и Controller.
- **Событийно-ориентированную коммуникацию** через Qt Signal/Slot.
- **Надёжное хранение данных** с атомарной записью.
- **Плавный UX** с анимациями через QPropertyAnimation.
- **Лёгкую расширяемость** — добавление новых типов будильников или звуков не требует перестройки архитектуры.
- **Возможность тестирования** каждого слоя независимо.
- **Соответствие SPEC** по всем функциональным и нефункциональным требованиям.

Реализация разделена на 5 этапов (см. раздел 6), каждый из которых даёт работающий инкремент продукта.
