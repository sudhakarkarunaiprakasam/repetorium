"""The tutor: picks the next task, serves items, grades answers and updates learner state."""

import random
import sqlite3
import time
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps

from repetorium.core.db import transaction
from repetorium.engine.graph import KnowledgeGraph
from repetorium.engine.learning_settings import ADAPTIVE_SETTING_DEFAULTS, AdaptiveSettings
from repetorium.engine.scheduler import DAY, Scheduler
from repetorium.engine.store import SkillState, Store
from repetorium.generators import Item, check, generate
from repetorium.question_levels import question_level

LESSON_STREAK_TO_MASTER = ADAPTIVE_SETTING_DEFAULTS["mastery_streak"]
LESSON_MAX_ERRORS = 4
REVIEW_XP = 3
QUIZ_EVERY = ADAPTIVE_SETTING_DEFAULTS["mixed_quiz_every"]
QUIZ_SIZE = ADAPTIVE_SETTING_DEFAULTS["mixed_quiz_size"]
DIAGNOSTIC_MAX = 15
DIAGNOSTIC_BITSET_MIN = 128
DIAGNOSTIC_BITSET_MAX = 8192
RUSH_SECONDS = 4.0
LOW_CONFIDENCE = frozenset(("unsure", "guessed"))


def atomic_action(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.atomic():
            return method(self, *args, **kwargs)
    return wrapped


@dataclass
class Task:
    kind: str  # lesson | review | quiz | diagnostic
    skill_ids: list[str]
    title: str
    index: int = 0
    correct: int = 0
    answered: int = 0
    xp: int = 0
    done: bool = False
    summary: str = ""
    known: set[str] = field(default_factory=set)
    unknown: set[str] = field(default_factory=set)
    uncertain: set[str] = field(default_factory=set)
    diagnostic_responses: dict[str, list[bool | None]] = field(default_factory=dict)
    difficulty: int = 2


@dataclass
class Feedback:
    correct: bool
    answer: str
    solution: str
    xp: int
    task_done: bool
    summary: str


class Tutor:
    def __init__(self, conn: sqlite3.Connection, graph: KnowledgeGraph | None = None,
                 clock: Callable[[], float] = time.time, seed: int | None = None):
        self.graph = graph or KnowledgeGraph.load()
        from repetorium.cases.templates import load_templates
        from repetorium.generators.banks import load_bank

        if self.graph.practice_banks is None:
            self.graph.practice_banks = {
                skill.params["bank"]: deepcopy(load_bank(skill.params["bank"], self.graph.content_dir))
                for skill in self.graph.skills.values()
                if skill.generator.startswith("bank_") and "bank" in skill.params
            }
        if self.graph.case_templates is None:
            self.graph.case_templates = deepcopy(load_templates(self.graph.content_dir / "cases"))
        self.store = Store(conn)
        self.states = self.store.load_states(list(self.graph.skills))
        self.adaptive_settings = AdaptiveSettings.from_store(self.store)
        self.scheduler = Scheduler(self.graph, self.states, self.adaptive_settings)
        self.clock = clock
        self.rng = random.Random(seed)
        self.task: Task | None = None
        self.item: Item | None = None
        self.item_started = 0.0
        self.history: list[tuple[str, str]] = []
        self.recent_lesson_skills: list[str] = []
        self.task_prompts: dict[str, set[str]] = {}
        self._topo_index = {s: i for i, s in enumerate(self.graph.topological_order)}

    def set_adaptive_setting(self, key: str, value) -> None:
        updated = self.adaptive_settings.with_setting(key, value)
        self.store.set(f"setting.{key}", getattr(updated, key))
        self.adaptive_settings = updated
        self.scheduler.settings = updated

    def set_adaptive_settings(self, values: Mapping[str, object]) -> None:
        updated = self.adaptive_settings.with_settings(values)
        self.store.set_many({
            f"setting.{key}": getattr(updated, key)
            for key in values
        })
        self.adaptive_settings = updated
        self.scheduler.settings = updated

    @contextmanager
    def atomic(self):
        states = self.states
        task, task_before = self.task, deepcopy(self.task)
        item, started = self.item, self.item_started
        history = self.history[:]
        recent_lessons = self.recent_lesson_skills[:]
        task_prompts = deepcopy(self.task_prompts)
        rng = self.rng.getstate()
        try:
            with transaction(self.store.conn):
                yield
        except BaseException:
            # Persisted state is the rollback source; avoid copying every skill on success.
            restored = self.store.load_states(list(states))
            for sid, state in states.items():
                vars(state).update(vars(restored[sid]))
            self.states = states
            self.scheduler.states = states
            self.task = task
            if task is not None and task_before is not None:
                vars(task).update(vars(task_before))
            self.item, self.item_started = item, started
            self.history[:] = history
            self.recent_lesson_skills[:] = recent_lessons
            self.task_prompts = task_prompts
            self.rng.setstate(rng)
            raise

    # ----- graph helpers -----
    def category(self, skill_id: str) -> str:
        return self.graph.skills[skill_id].category

    def is_available(self, skill_id: str) -> bool:
        st = self.states[skill_id]
        return not st.mastered and all(
            self.states[p].mastered for p in self.graph.skills[skill_id].prereqs)

    def frontier(self) -> list[str]:
        return [s for s in self.graph.topological_order if self.is_available(s)]

    def mastered(self) -> list[str]:
        return [s for s, st in self.states.items() if st.mastered]

    # ----- task selection -----
    @atomic_action
    def select_task(self, mode: str = "next") -> Task | None:
        if mode not in ("next", "lesson", "review"):
            raise ValueError("Choose next, lesson, or review.")
        now = self.clock()
        self.item = None
        self.task_prompts = {}
        if mode == "lesson":
            self.task = self._lesson_task()
        elif mode == "review":
            self.task = self._due_review_task(now)
        else:
            self.task = self._remediation_task() or self._quiz_task() or self._review_or_lesson(now)
        if self.task and self.task.kind == "lesson":
            st = self.states[self.task.skill_ids[0]]
            if st.status == "new":
                st.status = "learning"
                self.store.save_states([st])
        return self.task

    def _remediation_task(self) -> Task | None:
        queue: list[str] = self.store.get("remediation", [])
        pending = []
        task = None
        while queue and task is None:
            sid = queue.pop(0)
            if sid not in self.states:
                continue
            title = self.graph.skills[sid].title
            if self.states[sid].mastered:
                task = Task("review", [sid], f"Refresher: {title}")
            elif self.is_available(sid):
                task = Task("lesson", [sid], f"Lesson: {title}")
            else:
                pending.append(sid)
        self.store.set("remediation", pending + queue)
        return task

    def _quiz_task(self) -> Task | None:
        mastered = self.mastered()
        quiz_size = self.adaptive_settings.mixed_quiz_size
        if (self.store.get("tasks_since_quiz", 0) < self.adaptive_settings.mixed_quiz_every
                or len(mastered) < quiz_size):
            return None
        pool = sorted(mastered, key=lambda s: (self.states[s].reps, self.states[s].due or 0))
        picks = self.rng.sample(pool[: quiz_size * 2], quiz_size)
        average_repetitions = sum(self.states[sid].reps for sid in picks) / quiz_size
        difficulty = 1 if average_repetitions < 1.5 else 2 if average_repetitions < 3 else 3
        label = question_level(difficulty)["label"]
        return Task("quiz", picks, f"Mixed quiz · {label}", difficulty=difficulty)

    def _review_or_lesson(self, now: float) -> Task | None:
        due = self.scheduler.due_skills(now)
        frontier = self.frontier()
        last_cat = self.category(self.history[-1][1]) if self.history else None
        recent_kinds = [k for k, _ in self.history[-2:]]
        if due and not (frontier and recent_kinds == ["review", "review"]):
            return self._due_review_task(now, due, last_cat)
        if frontier:
            return self._lesson_task(frontier)
        mastered = self.mastered()
        if mastered:
            best = min(mastered, key=lambda s: self.states[s].due or 0)
            return Task("review", [best], f"Review ahead: {self.graph.skills[best].title}")
        return None

    def _due_review_task(
        self, now: float, due: list[str] | None = None, last_category: str | None = None,
    ) -> Task | None:
        due = due if due is not None else self.scheduler.due_skills(now)
        if not due:
            return None
        if last_category is None and self.history:
            last_category = self.category(self.history[-1][1])
        due_set = set(due)
        best = max(due, key=lambda skill_id: (
            round(self.scheduler.review_value(skill_id, due_set), 2),
            self.category(skill_id) != last_category,
            -(self.states[skill_id].due or 0),
        ))
        return Task("review", [best], f"Review: {self.graph.skills[best].title}")

    def _lesson_task(self, frontier: list[str] | None = None) -> Task | None:
        frontier = frontier if frontier is not None else self.frontier()
        if not frontier:
            return None
        last_category = self.category(self.history[-1][1]) if self.history else None
        recent = []
        for skill_id in [*self.recent_lesson_skills, *self.store.recent_skills("lesson", 8)]:
            if skill_id in self.graph.skills and skill_id not in recent:
                recent.append(skill_id)
            if len(recent) == 8:
                break
        recently_seen = set(recent[:3])
        recent_categories = {
            category: sum(self.category(skill_id) == category for skill_id in recent)
            for category in {self.category(skill_id) for skill_id in recent}
        }
        recent_connections = {}
        seen_links = set()
        for skill_id in recent[:3]:
            for link in self.graph.connections_by_skill[skill_id]:
                if id(link) in seen_links:
                    continue
                seen_links.add(id(link))
                if link.kind not in ("application", "contrast"):
                    continue
                if link.source in recently_seen:
                    linked, candidate = link.source, link.target
                elif link.target in recently_seen:
                    linked, candidate = link.target, link.source
                else:
                    continue
                if self.category(linked) == self.category(candidate):
                    continue
                recent_connections[candidate] = max(
                    recent_connections.get(candidate, 0), link.strength
                )

        def interferes(skill_id: str) -> bool:
            return any(
                skill_id in self.graph.skills[recent_id].similar
                or recent_id in self.graph.skills[skill_id].similar
                for recent_id in recent[:3]
            )

        best = min(frontier, key=lambda skill_id: (
            self.states[skill_id].status != "learning", interferes(skill_id),
            recent_categories.get(self.category(skill_id), 0),
            -recent_connections.get(skill_id, 0),
            self.category(skill_id) == last_category,
            self.graph.depth[skill_id], self._topo_index[skill_id],
        ))
        return Task("lesson", [best], f"Lesson: {self.graph.skills[best].title}")

    def _ordered_learning_plan(self, limit: int = 7) -> list[str]:
        pack_ids = list(dict.fromkeys(
            pack_id for pack_id in self.graph.skill_pack_ids.values()
            if isinstance(pack_id, str) and pack_id
        ))
        selected_ids = self.store.get("setting.content_pack_ids")
        if isinstance(selected_ids, list):
            ordered_ids = [
                pack_id for pack_id in selected_ids
                if isinstance(pack_id, str) and pack_id in pack_ids
            ]
            pack_ids = ordered_ids + [
                pack_id for pack_id in pack_ids if pack_id not in ordered_ids
            ]

        plan_limit = max(limit, len(pack_ids))
        pack_slots = []
        if pack_ids:
            lesson_goal = self.store.get("setting.lessons_per_week_goal", 5)
            if (
                isinstance(lesson_goal, bool) or not isinstance(lesson_goal, int)
                or not 1 <= lesson_goal <= 50
            ):
                raise ValueError("Saved lessons per week goal is invalid.")
            saved_goals = self.store.get("setting.content_pack_weekly_goals", {})
            if not isinstance(saved_goals, dict):
                raise ValueError("Saved learning-pack weekly goals are invalid.")
            weights = []
            for pack_id in pack_ids:
                goal = saved_goals.get(pack_id, 1)
                if (
                    isinstance(goal, bool) or not isinstance(goal, int)
                    or not 0 <= goal <= 50
                ):
                    raise ValueError("Saved learning-pack weekly goals are invalid.")
                weights.append(goal)

            def weighted_slots(count: int) -> list[str]:
                slot_weights = weights if sum(weights) else [1] * len(pack_ids)
                total_weight = sum(slot_weights)
                allocated = [0] * len(pack_ids)
                slots = []
                for step in range(count):
                    index = max(
                        range(len(pack_ids)),
                        key=lambda candidate: (
                            (step + 1) * slot_weights[candidate] / total_weight
                            - allocated[candidate],
                            -candidate,
                        ),
                    )
                    slots.append(pack_ids[index])
                    allocated[index] += 1
                return slots

            if lesson_goal > limit:
                pack_slots = pack_ids + weighted_slots(plan_limit - len(pack_ids))
            else:
                pack_slots = (
                    weighted_slots(lesson_goal)
                    + weighted_slots(plan_limit - lesson_goal)
                )

        plan = []
        planned = set(self.mastered())

        def remaining_frontier() -> list[str]:
            return [
                skill_id for skill_id in self.graph.topological_order
                if skill_id not in planned
                and all(prerequisite in planned
                        for prerequisite in self.graph.skills[skill_id].prereqs)
            ]

        for pack_id in pack_slots:
            frontier = [
                skill_id for skill_id in remaining_frontier()
                if self.graph.skill_pack_ids.get(skill_id) == pack_id
            ]
            task = self._lesson_task(frontier)
            if task is not None:
                skill_id = task.skill_ids[0]
                plan.append(skill_id)
                planned.add(skill_id)

        while len(plan) < plan_limit:
            task = self._lesson_task(remaining_frontier())
            if task is None:
                break
            skill_id = task.skill_ids[0]
            plan.append(skill_id)
            planned.add(skill_id)
        return plan

    def start_diagnostic(self) -> Task:
        self.item = None
        self.task_prompts = {}
        self.task = Task("diagnostic", [], "Placement diagnostic")
        return self.task

    # ----- items -----
    @atomic_action
    def next_item(self) -> Item | None:
        task = self.task
        if task is None or task.done:
            return None
        if self.item is not None:
            return self.item
        if task.kind == "diagnostic":
            while True:
                sid = self._diagnostic_pick()
                if sid is None:
                    self._finish_diagnostic()
                    return None
                responses = task.diagnostic_responses.get(sid, [])
                difficulty = (
                    2 if not responses
                    else 3 if responses[0] is True
                    else 1 if responses[0] is False
                    else 2
                )
                seen = self.task_prompts.get(sid, set())
                item = None
                for _ in range(8 if responses else 1):
                    candidate = self.generate_practice_item(
                        sid, self.rng.randrange(2**31), difficulty, seen, record_prompt=False
                    )
                    if candidate.prompt not in seen:
                        item = candidate
                        break
                if item is None:
                    task.diagnostic_responses[sid].append(None)
                    task.uncertain.add(sid)
                    continue
                task.skill_ids.append(sid)
                self.task_prompts.setdefault(sid, set()).add(item.prompt)
                break
        elif task.kind == "lesson":
            sid = task.skill_ids[0]
            difficulty = min(3, 1 + self.states[sid].lesson_streak)
        elif task.kind == "review":
            sid = task.skill_ids[0]
            difficulty = 3 if self.states[sid].reps >= 3 else 2
        elif task.kind == "quiz":
            sid = task.skill_ids[task.index]
            difficulty = task.difficulty
        else:
            sid = task.skill_ids[task.index]
            difficulty = 2
        if task.kind != "diagnostic":
            self.item = self.generate_practice_item(
                sid, self.rng.randrange(2**31), difficulty, self.task_prompts.get(sid, set())
            )
            self.task_prompts.setdefault(sid, set()).add(self.item.prompt)
        else:
            self.item = item
        self.item_started = self.clock()
        return self.item

    def generate_practice_item(self, skill_id: str, seed: int, difficulty: int,
                               task_prompts: set[str] | None = None,
                               record_prompt: bool = True) -> Item:
        skill = self.graph.skills[skill_id]
        params = self.generator_params(skill_id)
        if skill.generator.startswith("bank_"):
            seen = self._seen_bank_prompts(skill_id)
            params["_exclude_prompts"] = seen | (task_prompts or set())
            if skill.generator == "bank_mixed":
                params["_recent_kinds"] = self.store.get(f"practice_kinds.{skill_id}", [])
        else:
            seen = set()
        item = generate(skill.generator, skill_id, seed, difficulty, params)
        if skill.generator.startswith("bank_") and record_prompt:
            seen.add(item.prompt)
            self.store.set(f"practice_prompts.{skill_id}", sorted(seen))
            if skill.generator == "bank_mixed":
                recent = self.store.get(f"practice_kinds.{skill_id}", [])
                self.store.set(f"practice_kinds.{skill_id}", [*recent, item.kind][-8:])
        return item

    def _seen_bank_prompts(self, skill_id: str) -> set[str]:
        key = f"practice_prompts.{skill_id}"
        seen = set(self.store.get(key, []))
        migration_key = f"practice_prompts_migrated.{skill_id}"
        skill = self.graph.skills[skill_id]
        if not self.store.get(migration_key, False):
            params = self.generator_params(skill_id)
            for attempt in self.store.attempts_for_skill(skill_id):
                item = generate(skill.generator, skill_id, attempt["seed"],
                                attempt["difficulty"], params)
                seen.add(item.prompt)
            self.store.set(key, sorted(seen))
            self.store.set(migration_key, True)
        bank = self.graph.practice_banks[skill.params["bank"]]
        entries = bank.get("items", []) if skill.generator == "bank_classify" else bank.get("entries", [])
        if skill.generator == "bank_choice" and "skill" in skill.params:
            entries = [entry for entry in entries if entry.get("skill") == skill_id]
        if entries and len(seen) >= len(entries):
            seen.clear()
            self.store.set(key, [])
        return seen

    def lesson_hint(self, skill_id: str, difficulty: int, requested_level: int) -> dict:
        if skill_id not in self.graph.skills:
            raise ValueError(f"Unknown skill: {skill_id}")
        if not 1 <= requested_level <= 4:
            raise ValueError("Hint level must be between 1 and 4.")
        skill = self.graph.skills[skill_id]
        guide = skill.guide
        if not guide:
            if not skill.lesson:
                raise ValueError(f"{skill_id} has no lesson content for hints.")
            return {"level": 1, "title": "Key idea", "text": skill.lesson[0], "guide": {}}
        state = self.states[skill_id]
        support = min(2, int(difficulty >= 3)
                      + int(state.fail_streak > 0 or state.lesson_errors > 0))
        level = min(4, requested_level + support)
        hints = [
            ("Start with the idea", guide["definition"]),
            ("Choose an approach", " ".join(guide["steps"][:2])),
            ("Compare with an example", guide["example"][0]),
            ("Check a common mistake", guide["pitfalls"][0]),
        ]
        title, text = hints[level - 1]
        return {"level": level, "title": title, "text": text, "guide": guide}

    def generator_params(self, skill_id: str) -> dict:
        return {**self.graph.skills[skill_id].params,
                "_content_dir": self.graph.content_dir, "_banks": self.graph.practice_banks}

    @atomic_action
    def submit(self, response: str, seconds: float | None = None,
               confidence: str = "", lesson_opened: bool = False) -> Feedback:
        task, item = self.task, self.item
        if task is None or item is None:
            raise RuntimeError("no active item")
        if confidence not in ("", "explained", "unsure", "guessed"):
            raise ValueError("Confidence must be explained, unsure, guessed, or empty.")
        now = self.clock()
        seconds = max(0.0, now - self.item_started) if seconds is None else max(0.0, seconds)
        correct = check(item, response)
        sid = item.skill_id
        self.store.log_attempt(now, sid, task.kind, item.seed, item.difficulty, response,
                               correct, seconds, confidence)
        task.answered += 1
        task.correct += int(correct)
        confidence_uncertain = confidence in LOW_CONFIDENCE or lesson_opened
        xp = 0
        if not correct and seconds < RUSH_SECONDS:
            xp -= 1
            self.store.add_xp(now, -1, "rushed answer", sid)

        if task.kind == "diagnostic":
            xp += self._on_diagnostic(task, sid, correct, now, confidence_uncertain)
        else:
            handler = {"lesson": self._on_lesson, "review": self._on_review,
                       "quiz": self._on_quiz}[task.kind]
            xp += handler(task, sid, correct, now, confidence_uncertain)
        task.xp += xp
        if task.kind == "quiz" and task.done:
            self.store.log_quiz_completion(now, task.correct, len(task.skill_ids))
        self.item = None
        if task.done:
            skill_id = task.skill_ids[0] if task.skill_ids else ""
            self.history.append((task.kind, skill_id))
            del self.history[:-2]
            if task.kind == "lesson" and skill_id:
                if skill_id in self.recent_lesson_skills:
                    self.recent_lesson_skills.remove(skill_id)
                self.recent_lesson_skills.insert(0, skill_id)
                del self.recent_lesson_skills[8:]
            if task.kind != "diagnostic":
                since = 0 if task.kind == "quiz" else self.store.get("tasks_since_quiz", 0) + 1
                self.store.set("tasks_since_quiz", since)
        return Feedback(correct, item.answer_text(), item.solution, xp, task.done, task.summary)

    # ----- handlers return XP earned -----
    def _on_lesson(
        self, task: Task, sid: str, correct: bool, now: float,
        confidence_uncertain: bool,
    ) -> int:
        st = self.states[sid]
        skill = self.graph.skills[sid]
        touched = [st]
        xp = 0
        if correct and not confidence_uncertain:
            st.lesson_streak += 1
            if st.lesson_streak >= self.adaptive_settings.mastery_streak:
                xp = max(skill.xp // 2, skill.xp - 2 * st.lesson_errors)
                touched = self.scheduler.master(sid, now)
                self.store.add_xp(now, xp, "lesson mastered", sid)
                task.done = True
                task.summary = f"Mastered “{skill.title}”."
        elif correct:
            st.lesson_streak = 0
        else:
            st.lesson_streak = 0
            st.lesson_errors += 1
            if st.lesson_errors >= LESSON_MAX_ERRORS:
                st.lesson_errors = 0
                self._enqueue_remediation(sid)
                task.done = True
                task.summary = ("This one needs a stronger foundation. "
                                "We'll refresh the prerequisites first and come back to it.")
        self.store.save_states(touched)
        return xp

    def _on_review(
        self, task: Task, sid: str, correct: bool, now: float,
        confidence_uncertain: bool,
    ) -> int:
        review_passed = correct and not confidence_uncertain
        touched = self.scheduler.review(sid, review_passed, now)
        if not review_passed and self.states[sid].fail_streak >= 2:
            self.states[sid].fail_streak = 0
            self._enqueue_remediation(sid)
        self.store.save_states(touched)
        xp = REVIEW_XP if review_passed else 0
        self.store.add_xp(now, xp, "review", sid)
        task.done = True
        task.summary = (
            "Review passed — next review pushed further out." if review_passed else
            "Correct, but your self-check was unsure; this skill will return soon."
            if correct else "Review missed — it will come back soon."
        )
        return xp

    def _on_quiz(
        self, task: Task, sid: str, correct: bool, now: float,
        confidence_uncertain: bool,
    ) -> int:
        self.store.save_states(
            self.scheduler.review(
                sid, correct and not confidence_uncertain, now, weight=0.5,
            )
        )
        xp = question_level(self.item.difficulty)["xp"] if correct else 0
        task.index += 1
        if task.index >= len(task.skill_ids):
            task.done = True
            if task.correct >= 0.8 * len(task.skill_ids):
                xp += 3
            task.summary = f"Quiz complete: {task.correct}/{len(task.skill_ids)} correct."
        self.store.add_xp(now, xp, "quiz", sid)
        return xp

    def _on_diagnostic(
        self, task: Task, sid: str, correct: bool, now: float,
        confidence_uncertain: bool,
    ) -> int:
        responses = task.diagnostic_responses.setdefault(sid, [])
        responses.append(None if confidence_uncertain else correct)
        if len(responses) == 2:
            if None in responses or responses[0] != responses[1]:
                task.uncertain.add(sid)
            elif responses[0]:
                task.known |= {sid} | self.graph.ancestors(sid)
            else:
                task.unknown.add(sid)
        return 0

    def _diagnostic_pick(self) -> str | None:
        task = self.task
        assert task is not None
        unclassified = set(self.graph.skills) - task.known - task.unknown - task.uncertain
        if task.answered >= DIAGNOSTIC_MAX:
            return None
        for sid, responses in task.diagnostic_responses.items():
            if len(responses) == 1:
                return sid
        if not unclassified:
            return None

        if DIAGNOSTIC_BITSET_MIN <= len(self.graph.skills) <= DIAGNOSTIC_BITSET_MAX:
            ancestors, descendants = self.graph._reachability_bitsets
            unclassified_bits = sum(1 << self._topo_index[sid] for sid in unclassified)

            def info(s: str) -> tuple:
                a = (ancestors[s] & unclassified_bits).bit_count()
                d = (descendants[s] & unclassified_bits).bit_count()
                return (min(a, d), a + d, -self._topo_index[s])
        else:
            def info(s: str) -> tuple:
                a = len(self.graph.ancestors(s) & unclassified)
                d = len(self.graph.descendants(s) & unclassified)
                return (min(a, d), a + d, -self._topo_index[s])

        return max(unclassified, key=info)

    def _finish_diagnostic(self) -> None:
        task = self.task
        assert task is not None
        now = self.clock()
        for sid, responses in task.diagnostic_responses.items():
            if len(responses) == 1:
                task.uncertain.add(sid)
        credited = task.known - task.unknown - task.uncertain
        unassessed = set(self.graph.skills) - task.known - task.unknown - task.uncertain
        placed: list[SkillState] = []
        for i, sid in enumerate(sorted(credited, key=self._topo_index.get)):
            st = self.states[sid]
            if st.mastered:
                continue
            st.status, st.placed, st.reps = "mastered", 1, 1.0
            st.last_reviewed = now
            st.due = now + (i % 4 + 1) * DAY / 2  # stagger first reviews
            placed.append(st)
        self.store.save_states(placed)
        self.store.set("diagnostic_done", True)
        task.done = True
        inferred = len(credited - set(task.diagnostic_responses))
        task.summary = (
            f"Placement estimate: {len(credited)} skills credited"
            f" ({inferred} prerequisite skills inferred from confirmed answers); "
            f"{len(task.unknown)} assessed skills need study; "
            f"{len(task.uncertain)} were inconclusive; {len(unassessed)} were not assessed. "
            "Only consistent responses earned credit. Use this as a starting point, "
            "not proof of mastery."
        )

    def _enqueue_remediation(self, sid: str) -> None:
        queue = self.store.get("remediation", [])
        path = set(self.graph.skills[sid].prereqs)
        path.update(
            ancestor for ancestor in self.graph.ancestors(sid)
            if not self.states[ancestor].mastered
        )
        path.add(sid)
        ordered_path = sorted(path, key=self._topo_index.get)
        queue.extend(
            candidate for candidate in ordered_path
            if candidate not in queue
        )
        self.store.set("remediation", queue)

    def record_assessment_result(self, skill_id: str, correct: bool, now: float,
                                 weight: float = 0.5) -> list[SkillState]:
        """Use objective exam or case evidence without crediting a new skill as mastered."""
        self.store.touch_skills([skill_id])
        state = self.states[skill_id]
        if state.mastered:
            touched = self.scheduler.review(skill_id, correct, now, weight)
            if not correct and state.fail_streak >= 2:
                state.fail_streak = 0
                self._enqueue_remediation(skill_id)
                touched.append(state)
            return touched
        if correct:
            if state.status == "new":
                state.status = "learning"
                return [state]
        else:
            self._enqueue_remediation(skill_id)
        return []

    # ----- reporting -----
    def dashboard(self) -> dict:
        now = self.clock()
        due = set(self.scheduler.due_skills(now))
        frontier = set(self.frontier())
        recommended_task = self._review_or_lesson(now)
        recommended_action = (
            recommended_task.kind
            if recommended_task and (
                (recommended_task.kind == "review" and due)
                or (recommended_task.kind == "lesson" and frontier)
            )
            else ""
        )
        critical_reviews = sorted(
            due,
            key=lambda skill_id: (
                -round(self.scheduler.review_value(skill_id, due), 2),
                self.states[skill_id].due or 0,
            ),
        )
        upcoming_review_limit = now + 7 * DAY
        upcoming_reviews = sorted(
            (
                skill_id for skill_id, state in self.states.items()
                if state.mastered and state.due is not None
                and now < state.due <= upcoming_review_limit
            ),
            key=lambda skill_id: self.states[skill_id].due or 0,
        )
        review_rows = (critical_reviews + upcoming_reviews)[:7]
        learning_plan = self._ordered_learning_plan()
        available_lessons = set(self.frontier())
        categories = {category: {"key": category, "title": self.graph.category_title(category),
                                 "mastered": 0, "total": 0}
                      for category in self.graph.categories}
        for skill in self.graph.skills.values():
            categories[skill.category]["total"] += 1
            categories[skill.category]["mastered"] += int(self.states[skill.id].mastered)
        return {
            **self.store.dashboard_activity(now),
            "weeklyLessonGoal": self.store.get("setting.lessons_per_week_goal", 5),
            "dueCount": len(due),
            "mastered": len(self.mastered()),
            "total": len(self.graph.skills),
            "available": len(available_lessons),
            "recommendedAction": recommended_action,
            "diagnosticDone": bool(self.store.get("diagnostic_done", False)),
            "learningPlan": [
                {"id": skill_id, "title": self.graph.skills[skill_id].title,
                 "category": self.graph.category_title(self.graph.skills[skill_id].category),
                 "learningPack": self.graph.skill_pack_names.get(
                     skill_id, "Personal Library"
                 ),
                 "available": skill_id in available_lessons}
                for skill_id in learning_plan
            ],
            "criticalReviews": [
                {"id": skill_id, "title": self.graph.skills[skill_id].title,
                 "category": self.graph.category_title(self.graph.skills[skill_id].category),
                 "overdueDays": max(
                     0, int((now - (self.states[skill_id].due or now)) / DAY)
                 ),
                 "dueNow": (self.states[skill_id].due or now) <= now,
                 "daysUntilDue": max(
                     0, (datetime.fromtimestamp(self.states[skill_id].due or now).date()
                         - datetime.fromtimestamp(now).date()).days
                 )}
                for skill_id in review_rows
            ],
            "categories": list(categories.values()),
        }

    def knowledge_map(self) -> dict:
        now = self.clock()
        related = {skill_id: [] for skill_id in self.graph.skills}
        for template in self.graph.case_templates.values():
            skill_ids = {question["skill"] for question in template.raw.get("questions", [])}
            for mapped in template.raw.get("rubric_skills", {}).values():
                skill_ids.update(mapped)
            for skill_id in skill_ids:
                if skill_id in related:
                    related[skill_id].append({"id": template.id, "title": template.title,
                                              "archetype": template.archetype})
        nodes = []
        for sid in self.graph.topological_order:
            s, st = self.graph.skills[sid], self.states[sid]
            status = st.status if st.status != "new" else (
                "available" if self.is_available(sid) else "locked")
            if st.mastered and st.due is not None and st.due <= now:
                status = "due"
            nodes.append({"id": sid, "title": s.title, "category": s.category,
                          "depth": self.graph.depth[sid], "status": status,
                          "definition": s.guide.get("definition", s.lesson[0] if s.lesson else ""),
                          "guide": s.guide, "lesson": s.lesson,
                          "domains": s.domains, "sources": s.sources,
                          "connections": [
                              {"id": link.target if link.source == sid else link.source,
                               "title": self.graph.skills[
                                   link.target if link.source == sid else link.source].title,
                               "kind": link.kind, "strength": link.strength, "note": link.note}
                              for link in self.graph.connections_by_skill[sid]
                          ],
                          "prerequisites": [{"id": prerequisite,
                                             "title": self.graph.skills[prerequisite].title}
                                            for prerequisite in s.prereqs],
                          "cases": related[sid],
                          "reps": round(st.reps, 2),
                          "dueInDays": None if st.due is None else round((st.due - now) / DAY, 1)})
        edges = [{"from": p, "to": s.id} for s in self.graph.skills.values() for p in s.prereqs]
        edges += [{"from": link.source, "to": link.target, "kind": link.kind,
                   "strength": link.strength, "note": link.note} for link in self.graph.connections]
        return {"nodes": nodes, "edges": edges}

    def stats(self) -> dict:
        now = self.clock()
        since = now - 30 * DAY
        acc = self.store.accuracy_by_skill(since)
        confidence = self.store.confidence_by_skill(since)
        per_cat = {category: {"title": self.graph.category_title(category), "correct": 0,
                              "total": 0}
                   for category in self.graph.categories}
        archived = {"title": "Archived skills", "correct": 0, "total": 0}
        confidence_by_category = {
            category: {"title": self.graph.category_title(category),
                       "confidenceLow": 0, "confidenceRated": 0}
            for category in self.graph.categories
        }
        archived_confidence = {
            "title": "Archived skills", "confidenceLow": 0, "confidenceRated": 0
        }
        for sid, (right, total) in acc.items():
            skill = self.graph.skills.get(sid)
            bucket = per_cat[skill.category] if skill is not None else archived
            bucket["correct"] += right
            bucket["total"] += total
        for sid, (low, rated) in confidence.items():
            skill = self.graph.skills.get(sid)
            bucket = (confidence_by_category[skill.category] if skill is not None
                      else archived_confidence)
            bucket["confidenceLow"] += low
            bucket["confidenceRated"] += rated
        categories = list(per_cat.values())
        confidence_categories = list(confidence_by_category.values())
        if archived["total"]:
            categories.append(archived)
            confidence_categories.append(archived_confidence)
        return {"xpByDay": [{"day": d[5:], "xp": x} for d, x in self.store.xp_by_day(now, 14)],
                "studyTimeByDay": [
                    {"day": d[5:], "seconds": seconds}
                    for d, seconds in self.store.study_seconds_by_day(now, 14)
                ],
                "categories": categories,
                "confidenceByCategory": confidence_categories,
                "attempts": sum(v[1] for v in acc.values())}

    @atomic_action
    def reset_progress(self) -> None:
        self.store.reset_progress()
        self.states = self.store.load_states(list(self.graph.skills))
        self.scheduler.states = self.states
        self.task = self.item = None
        self.history.clear()
        self.recent_lesson_skills.clear()
