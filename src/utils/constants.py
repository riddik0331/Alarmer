"""Application-wide constants: colors, paths, sounds, and configuration values.

All UI-facing strings are in Russian as required by the specification.
All code-level identifiers are in English.
"""

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
APP_NAME: str = "Будильник"
ORGANIZATION: str = "Budilnik"
JSON_VERSION: int = 1

# ---------------------------------------------------------------------------
# Color palette — Material Dark theme
# ---------------------------------------------------------------------------
BACKGROUND: str = "#1e1e2e"
CARD: str = "#2a2a3e"
PRIMARY: str = "#7c3aed"
ACCENT: str = "#ec4899"
TEXT_PRIMARY: str = "#e2e8f0"
TEXT_SECONDARY: str = "#94a3b8"
SUCCESS: str = "#22c55e"
DANGER: str = "#ef4444"

# Pulse animation colors (alarm popup)
PULSE_COLOR_START: str = "#1a1a2e"
PULSE_COLOR_END: str = "#2d004d"

# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------
SNOOZE_MINUTES: list[int] = [5, 10, 15]
FADE_IN_DURATION: int = 30          # seconds
CHECK_INTERVAL: int = 30            # seconds between alarm checks
FADE_INTERVAL_MS: int = 200         # ms between fade steps
SNOOZE_CHECK_INTERVAL_MS: int = 10_000  # ms (10 s)

# ---------------------------------------------------------------------------
# UI dimensions
# ---------------------------------------------------------------------------
POPUP_WIDTH: int = 400
POPUP_HEIGHT: int = 300
PULSE_DURATION_MS: int = 1500
SCALE_DURATION_MS: int = 300

CARD_SHADOW_BLUR: int = 20
CARD_SHADOW_OFFSET: int = 4
CARD_SHADOW_OPACITY: float = 0.3
CARD_RADIUS: int = 16
BUTTON_RADIUS: int = 12
DISABLED_OPACITY: float = 0.5

# ---------------------------------------------------------------------------
# File / directory names
# ---------------------------------------------------------------------------
ALARMS_FILE: str = "alarms.json"
SOUNDS_DIR: str = "resources/sounds"
ICONS_DIR: str = "resources/icons"
STYLES_DIR: str = "resources/styles"
THEME_QSS: str = "theme.qss"
