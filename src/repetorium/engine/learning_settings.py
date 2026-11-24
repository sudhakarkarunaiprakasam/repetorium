"""Validated, per-profile controls for the adaptive learning schedule."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repetorium.engine.store import Store

ADAPTIVE_SETTING_DEFAULTS = {
    "mastery_streak": 3,
    "review_growth_factor": 2.5,
    "max_review_interval_days": 180,
    "review_retry_hours": 4,
    "mixed_quiz_every": 8,
    "mixed_quiz_size": 5,
}
REVIEW_GROWTH_FACTORS = (1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0)
INTEGER_SETTING_RANGES = {
    "mastery_streak": (2, 5),
    "max_review_interval_days": (30, 360),
    "review_retry_hours": (1, 24),
    "mixed_quiz_every": (4, 20),
    "mixed_quiz_size": (3, 8),
}
ADAPTIVE_PRESETS = {
    "easy": {
        "mastery_streak": 2,
        "review_growth_factor": 3.0,
        "max_review_interval_days": 360,
        "review_retry_hours": 8,
        "mixed_quiz_every": 12,
        "mixed_quiz_size": 3,
    },
    "balanced": ADAPTIVE_SETTING_DEFAULTS.copy(),
    "hard": {
        "mastery_streak": 5,
        "review_growth_factor": 1.5,
        "max_review_interval_days": 60,
        "review_retry_hours": 1,
        "mixed_quiz_every": 4,
        "mixed_quiz_size": 8,
    },
}


def validate_adaptive_setting(key: str, value: object) -> int | float:
    if key not in ADAPTIVE_SETTING_DEFAULTS:
        raise ValueError(f"Unknown adaptive learning setting: {key}.")
    if key == "review_growth_factor":
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not isfinite(value) or value not in REVIEW_GROWTH_FACTORS):
            choices = ", ".join(str(factor) for factor in REVIEW_GROWTH_FACTORS)
            raise ValueError(f"Review interval growth factor must be one of: {choices}.")
        return float(value)
    minimum, maximum = INTEGER_SETTING_RANGES[key]
    if (isinstance(value, bool) or not isinstance(value, int)
            or not minimum <= value <= maximum):
        raise ValueError(f"{key} must be an integer from {minimum} to {maximum}.")
    return value


@dataclass(frozen=True)
class AdaptiveSettings:
    mastery_streak: int = ADAPTIVE_SETTING_DEFAULTS["mastery_streak"]
    review_growth_factor: float = ADAPTIVE_SETTING_DEFAULTS["review_growth_factor"]
    max_review_interval_days: int = ADAPTIVE_SETTING_DEFAULTS["max_review_interval_days"]
    review_retry_hours: int = ADAPTIVE_SETTING_DEFAULTS["review_retry_hours"]
    mixed_quiz_every: int = ADAPTIVE_SETTING_DEFAULTS["mixed_quiz_every"]
    mixed_quiz_size: int = ADAPTIVE_SETTING_DEFAULTS["mixed_quiz_size"]

    @classmethod
    def from_store(cls, store: "Store") -> "AdaptiveSettings":
        values = {
            setting: validate_adaptive_setting(
                setting, store.get(f"setting.{setting}", default)
            )
            for setting, default in ADAPTIVE_SETTING_DEFAULTS.items()
        }
        return cls(**values)

    def with_setting(self, key: str, value: object) -> "AdaptiveSettings":
        validated = validate_adaptive_setting(key, value)
        return replace(self, **{key: validated})

    def with_settings(self, values: Mapping[str, object]) -> "AdaptiveSettings":
        if set(values) != set(ADAPTIVE_SETTING_DEFAULTS):
            raise ValueError("A preset must provide every adaptive learning setting.")
        updated = self
        for key, value in values.items():
            updated = updated.with_setting(key, value)
        return updated
