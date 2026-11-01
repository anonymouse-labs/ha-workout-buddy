"""Constants for Workout Buddy."""

from __future__ import annotations

DOMAIN = "workout_buddy"

SUBENTRY_PERSON = "person"
SUBENTRY_SOURCE = "workout_source"

# Global options
CONF_SEND_SERVICE = "send_service"
CONF_RECIPIENT = "recipient"
CONF_DELAY = "delay"
CONF_HISTORY = "history_size"
CONF_COMPARE_AVG = "compare_average"
CONF_DAILY_MODE = "daily_mode"
CONF_JOINT_TIME = "joint_time"
CONF_JOINT_DEADLINE = "joint_deadline"
CONF_SEND_IMAGES = "send_images"
CONF_SEND_TEXT = "send_text"
CONF_CHART_PARTS = "chart_parts"
CONF_DAILY_CURVES = "daily_curves"
CHART_PARTS = ("numbers", "curves", "bars")
DAILY_CURVES = ("heart_rate", "steps", "distance", "active_kcal")
DEFAULT_DAILY_CURVES = ["heart_rate"]

DEFAULT_SEND_SERVICE = "script.whatsapp_melding"
DEFAULT_DELAY = 60
DEFAULT_HISTORY = 20
DEFAULT_JOINT_TIME = "20:00:00"
DEFAULT_JOINT_DEADLINE = "22:30:00"
AVERAGE_OVER = 5
MAX_ATTEMPTS = 3
RETRY_MINUTES = 15
JOINT_POLL_MINUTES = 5

DAILY_PER_PERSON = "per_person"
DAILY_JOINT = "joint"
DAILY_JOINT_WAIT = "joint_wait"

# Person subentry
CONF_COMPONENTS = "components"
CONF_DAILY_TIME = "daily_time"
DEFAULT_DAILY_TIME = "20:00:00"
COMPONENTS = (
    "steps",
    "distance",
    "heart_rate",
    "resting_heart_rate",
    "active_kcal",
    "sleep",
)
DEFAULT_COMPONENTS = ["steps", "distance", "heart_rate", "resting_heart_rate"]

# Source subentry
CONF_PERSON = "person"
CONF_SOURCE_TYPE = "source_type"
CONF_ENTITY_ID = "entity_id"
CONF_EVENT_TYPE = "event_type"
SOURCE_SENSOR = "sensor"
SOURCE_EVENT = "event"
SOURCE_TEXT = "text"

FIELDS = (
    "type",
    "start",
    "end",
    "duration",
    "distance",
    "kcal",
    "avg_hr",
    "max_hr",
)
CONF_DURATION_UNIT = "duration_unit"
CONF_DISTANCE_UNIT = "distance_unit"
CONF_ENERGY_UNIT = "energy_unit"

SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"
