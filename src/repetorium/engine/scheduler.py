"""Spaced repetition with implicit (fractional) repetition credit along encompassing edges.

Practising an advanced skill counts as partial review of the simpler skills it exercises,
so those reviews get pushed back instead of being scheduled separately.
"""

from math import isfinite, log

from repetorium.engine.graph import KnowledgeGraph
from repetorium.engine.learning_settings import ADAPTIVE_SETTING_DEFAULTS, AdaptiveSettings
from repetorium.engine.store import SkillState

DAY = 86_400.0
MAX_INTERVAL_DAYS = float(ADAPTIVE_SETTING_DEFAULTS["max_review_interval_days"])
RETRY_DELAY = ADAPTIVE_SETTING_DEFAULTS["review_retry_hours"] * 3600.0


def interval_days(
    reps: float,
    growth_factor: float = 2.5,
    max_interval_days: float = MAX_INTERVAL_DAYS,
) -> float:
    if not isfinite(reps) or reps < 0:
        raise ValueError("Repetition credit must be finite and nonnegative.")
    if not isfinite(growth_factor) or growth_factor <= 1:
        raise ValueError("Review interval growth factor must be finite and greater than 1.")
    if not isfinite(max_interval_days) or max_interval_days <= 0:
        raise ValueError("Maximum review interval must be finite and positive.")
    if reps < 1:
        return 0.5
    if reps >= 1 + log(max_interval_days, growth_factor):
        return max_interval_days
    return min(max_interval_days, growth_factor ** (reps - 1))


class Scheduler:
    def __init__(
        self,
        graph: KnowledgeGraph,
        states: dict[str, SkillState],
        settings: AdaptiveSettings | None = None,
    ):
        self.graph = graph
        self.states = states
        self.settings = settings or AdaptiveSettings()

    def master(self, skill_id: str, now: float) -> list[SkillState]:
        st = self.states[skill_id]
        st.status = "mastered"
        st.reps = max(st.reps, 1.0)
        st.lesson_streak = st.lesson_errors = st.fail_streak = 0
        st.last_reviewed = now
        st.due = now + self._interval_days(st.reps) * DAY
        return [st, *self._implicit(skill_id, 1.0, now)]

    def review(self, skill_id: str, correct: bool, now: float,
               weight: float = 1.0) -> list[SkillState]:
        """Explicit review result. `weight` < 1 for lighter evidence (e.g. a quiz item)."""
        st = self.states[skill_id]
        st.last_reviewed = now
        if correct:
            st.reps += weight
            st.fail_streak = 0
            st.due = max(st.due or now, now + self._interval_days(st.reps) * DAY)
            return [st, *self._implicit(skill_id, weight, now)]
        st.reps = max(1.0, st.reps / 2)
        st.fail_streak += 1
        st.due = now + self.settings.review_retry_hours * 3600
        touched = [st]
        for target, w in self.graph.skills[skill_id].encompasses.items():
            sub = self.states[target]
            if w >= 0.5 and sub.mastered:
                sub.due = min(sub.due or now, now + DAY)
                touched.append(sub)
        return touched

    def _implicit(self, skill_id: str, credit: float, now: float) -> list[SkillState]:
        touched = []
        for target, c in self.graph.implicit_credit(skill_id, credit).items():
            sub = self.states[target]
            if not sub.mastered:
                continue
            sub.reps += c
            sub.due = max(sub.due or now, now + c * self._interval_days(sub.reps) * DAY)
            touched.append(sub)
        return touched

    def _interval_days(self, reps: float) -> float:
        return interval_days(
            reps,
            self.settings.review_growth_factor,
            self.settings.max_review_interval_days,
        )

    def due_skills(self, now: float) -> list[str]:
        return [sid for sid, st in self.states.items()
                if st.mastered and st.due is not None and st.due <= now]

    def review_value(self, skill_id: str, due: set[str]) -> float:
        """How many due reviews one review of this skill would (partially) knock out."""
        credit = self.graph.implicit_credit(skill_id)
        return 1.0 + sum(c for t, c in credit.items() if t in due)
