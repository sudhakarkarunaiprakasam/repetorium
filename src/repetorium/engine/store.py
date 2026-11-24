"""Persistence for learner state, attempts, XP and settings."""

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from repetorium.core.db import transaction

IMPORTED_PROGRESS_REASON = "imported progress"


@dataclass
class SkillState:
    skill_id: str
    status: str = "new"  # new | learning | mastered
    reps: float = 0.0
    due: float | None = None
    last_reviewed: float | None = None
    lesson_streak: int = 0
    lesson_errors: int = 0
    fail_streak: int = 0
    placed: int = 0

    @property
    def mastered(self) -> bool:
        return self.status == "mastered"


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ----- skill state -----
    def load_states(self, skill_ids: list[str]) -> dict[str, SkillState]:
        rows = {}
        for start in range(0, len(skill_ids), 500):
            chunk = skill_ids[start:start + 500]
            placeholders = ", ".join("?" for _ in chunk)
            rows.update({
                row["skill_id"]: row
                for row in self.conn.execute(
                    f"SELECT * FROM skill_state WHERE skill_id IN ({placeholders})", chunk
                )
            })
        return {sid: SkillState(**dict(rows[sid])) if sid in rows else SkillState(sid)
                for sid in skill_ids}

    def save_states(self, states: list[SkillState]) -> None:
        if not states:
            return
        rows = [asdict(state) for state in states]
        columns = tuple(rows[0])
        statement = (
            f"INSERT OR REPLACE INTO skill_state ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )
        with transaction(self.conn):
            self.conn.executemany(statement, (tuple(row.values()) for row in rows))
            self.conn.executemany(
                "INSERT INTO skill_activity (skill_id, revision) VALUES (?, 1) "
                "ON CONFLICT(skill_id) DO UPDATE SET revision = revision + 1",
                ((state.skill_id,) for state in states),
            )

    def touch_skills(self, skill_ids: list[str]) -> None:
        with transaction(self.conn):
            self.conn.executemany(
                "INSERT INTO skill_activity (skill_id, revision) VALUES (?, 1) "
                "ON CONFLICT(skill_id) DO UPDATE SET revision = revision + 1",
                [(sid,) for sid in set(skill_ids)],
            )

    def skill_revisions(self) -> dict[str, int]:
        return dict(self.conn.execute("SELECT skill_id, revision FROM skill_activity"))

    # ----- attempts & xp -----
    def log_attempt(self, ts: float, skill_id: str, kind: str, seed: int, difficulty: int,
                    response: str, correct: bool, seconds: float,
                    confidence: str = "") -> None:
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO attempts (ts, skill_id, task_kind, seed, difficulty, response, "
                "correct, seconds, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, skill_id, kind, seed, difficulty, response, int(correct), seconds,
                 confidence),
            )
            self.touch_skills([skill_id])

    def log_quiz_completion(
        self, completed_at: float, correct: int = 0, total: int = 0
    ) -> None:
        if (
            isinstance(correct, bool) or not isinstance(correct, int) or correct < 0
            or isinstance(total, bool) or not isinstance(total, int) or total < 0
            or correct > total
        ):
            raise ValueError("Quiz results must have a valid correct and total question count.")
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO quiz_completions (completed_at, correct, total) VALUES (?, ?, ?)",
                (completed_at, correct, total),
            )

    def add_xp(self, ts: float, amount: int, reason: str, skill_id: str | None = None,
               case_run_id: int | None = None) -> None:
        if amount == 0:
            return
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO xp_ledger (ts, amount, reason, skill_id, case_run_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, amount, reason, skill_id, case_run_id),
            )

    def xp_total(self) -> int:
        return self.conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_ledger").fetchone()[0]

    def _imported_day_totals(self, key: str, *, allow_negative: bool) -> dict[str, int]:
        values = self.get(key, {})
        if not isinstance(values, dict):
            raise ValueError(f"Saved imported daily data for {key} is invalid.")
        for day, amount in values.items():
            try:
                valid_day = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
            except ValueError:
                valid_day = False
            if (
                not valid_day or isinstance(amount, bool) or not isinstance(amount, int)
                or not -(2**63) <= amount <= 2**63 - 1
                or (not allow_negative and amount < 0)
            ):
                raise ValueError(f"Saved imported daily data for {key} is invalid.")
        return values

    def _imported_xp_active_days(self) -> set[str]:
        values = self.get("progress.imported_xp_active_days", [])
        if not isinstance(values, list):
            raise ValueError("Saved imported progress activity is invalid.")
        days = set()
        for day in values:
            try:
                valid_day = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
            except ValueError:
                valid_day = False
            if not valid_day:
                raise ValueError("Saved imported progress activity is invalid.")
            days.add(day)
        return days

    def xp_history_by_day(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for ts, amount in self.conn.execute(
            "SELECT ts, amount FROM xp_ledger WHERE reason != ?", (IMPORTED_PROGRESS_REASON,)
        ):
            day = datetime.fromtimestamp(ts).date().isoformat()
            totals[day] = totals.get(day, 0) + amount
        imported = self._imported_day_totals(
            "progress.imported_xp_by_day", allow_negative=True
        )
        for day, amount in imported.items():
            if day not in totals or amount > totals[day]:
                totals[day] = amount
        return totals

    def xp_active_days(self) -> set[str]:
        active = self._imported_xp_active_days()
        active.update(
            datetime.fromtimestamp(ts).date().isoformat()
            for (ts,) in self.conn.execute(
                "SELECT ts FROM xp_ledger WHERE amount > 0 AND reason != ?",
                (IMPORTED_PROGRESS_REASON,),
            )
        )
        return active

    def merge_imported_daily_progress(
        self,
        xp_by_day: Mapping[str, int],
        xp_active_days: set[str],
        study_by_day: Mapping[str, int],
        streak_baseline: dict,
    ) -> None:
        incoming_xp = dict(xp_by_day)
        incoming_study = dict(study_by_day)
        for label, values, allow_negative in (
            ("progress points", incoming_xp, True),
            ("study time", incoming_study, False),
        ):
            for day, amount in values.items():
                try:
                    valid_day = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
                except ValueError:
                    valid_day = False
                if (
                    not valid_day or isinstance(amount, bool) or not isinstance(amount, int)
                    or not -(2**63) <= amount <= 2**63 - 1
                    or (not allow_negative and amount < 0)
                ):
                    raise ValueError(f"Imported daily {label} data is invalid.")
        for day in xp_active_days:
            try:
                valid_day = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
            except ValueError:
                valid_day = False
            if not valid_day:
                raise ValueError("Imported progress activity is invalid.")
        if (
            not isinstance(streak_baseline, dict)
            or isinstance(streak_baseline.get("count"), bool)
            or not isinstance(streak_baseline.get("count"), int)
            or not 0 <= streak_baseline["count"] <= 2**63 - 1
            or not isinstance(streak_baseline.get("exportedAt"), str)
        ):
            raise ValueError("Imported streak information is invalid.")
        try:
            datetime.fromisoformat(streak_baseline["exportedAt"].replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Imported streak information is invalid.") from error
        last_active = streak_baseline.get("lastActiveDay")
        if last_active is not None:
            try:
                valid_day = (
                    isinstance(last_active, str)
                    and date.fromisoformat(last_active).isoformat() == last_active
                )
            except ValueError:
                valid_day = False
            if not valid_day:
                raise ValueError("Imported streak information is invalid.")

        saved_xp = self._imported_day_totals("progress.imported_xp_by_day", allow_negative=True)
        saved_study = self._imported_day_totals(
            "progress.imported_study_by_day", allow_negative=False
        )
        saved_active = self._imported_xp_active_days()
        for day, amount in incoming_xp.items():
            if day not in saved_xp or amount > saved_xp[day]:
                saved_xp[day] = amount
        for day, seconds in incoming_study.items():
            if day not in saved_study or seconds > saved_study[day]:
                saved_study[day] = seconds
        saved_active.update(xp_active_days)

        existing_streak = self.get("progress.imported_streak_baseline")
        if existing_streak is not None:
            if (
                not isinstance(existing_streak, dict)
                or not isinstance(existing_streak.get("exportedAt"), str)
                or isinstance(existing_streak.get("count"), bool)
                or not isinstance(existing_streak.get("count"), int)
                or not 0 <= existing_streak["count"] <= 2**63 - 1
            ):
                raise ValueError("Saved imported streak information is invalid.")
            try:
                datetime.fromisoformat(existing_streak["exportedAt"].replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("Saved imported streak information is invalid.") from error
            previous_last_active = existing_streak.get("lastActiveDay")
            if previous_last_active is not None:
                try:
                    valid_day = (
                        isinstance(previous_last_active, str)
                        and date.fromisoformat(previous_last_active).isoformat()
                        == previous_last_active
                    )
                except ValueError:
                    valid_day = False
                if not valid_day:
                    raise ValueError("Saved imported streak information is invalid.")
            if existing_streak["exportedAt"] > streak_baseline["exportedAt"]:
                streak_baseline = existing_streak
        with transaction(self.conn):
            self.set("progress.imported_xp_by_day", saved_xp)
            self.set("progress.imported_study_by_day", saved_study)
            self.set("progress.imported_xp_active_days", sorted(saved_active))
            self.set("progress.imported_streak_baseline", streak_baseline)

    def xp_by_day(self, now: float, days: int) -> list[tuple[str, int]]:
        today = datetime.fromtimestamp(now).date()
        if days < 1:
            raise ValueError("days must be positive")
        first_day = today - timedelta(days=days - 1)
        start = datetime.combine(first_day, datetime.min.time()).timestamp()
        end = datetime.combine(today + timedelta(days=1), datetime.min.time()).timestamp()
        totals: dict[str, int] = {}
        for ts, amount in self.conn.execute(
            "SELECT ts, amount FROM xp_ledger WHERE reason != ? AND ts >= ? AND ts < ?",
            (IMPORTED_PROGRESS_REASON, start, end),
        ):
            key = datetime.fromtimestamp(ts).date().isoformat()
            totals[key] = totals.get(key, 0) + amount
        for key, amount in self._imported_day_totals(
            "progress.imported_xp_by_day", allow_negative=True
        ).items():
            if first_day.isoformat() <= key <= today.isoformat():
                totals[key] = max(totals.get(key, amount), amount)
        return [((today - timedelta(days=i)).isoformat(),
                 totals.get((today - timedelta(days=i)).isoformat(), 0))
                for i in reversed(range(days))]

    def study_seconds_total(self) -> int:
        imported = self.get("progress.imported_study_seconds", 0)
        if isinstance(imported, bool) or not isinstance(imported, int) or imported < 0:
            raise ValueError("Saved imported study time is invalid.")
        return round(
            self._recorded_study_seconds_total()
            + imported
        )

    def _recorded_study_seconds_total(self) -> float:
        attempts = self.conn.execute(
            "SELECT COALESCE(SUM(seconds), 0) FROM attempts WHERE task_kind != 'mock_test'"
        ).fetchone()[0]
        cases = self.conn.execute(
            "SELECT COALESCE(SUM(finished - started), 0) FROM case_runs "
            "WHERE finished IS NOT NULL"
        ).fetchone()[0]
        return attempts + cases

    def merge_imported_study_seconds(self, total_seconds: int) -> int:
        if isinstance(total_seconds, bool) or not isinstance(total_seconds, int) or total_seconds < 0:
            raise ValueError("Imported study time must be a nonnegative integer.")
        recorded = round(self._recorded_study_seconds_total())
        previous = self.get("progress.imported_study_seconds", 0)
        if (
            isinstance(previous, bool) or not isinstance(previous, int)
            or not 0 <= previous <= 2**63 - 1
        ):
            raise ValueError("Saved imported study time is invalid.")
        imported = max(previous, total_seconds - recorded, 0)
        if imported > 2**63 - 1:
            raise ValueError("Imported study time exceeds the supported range.")
        if imported == previous:
            return 0
        self.set("progress.imported_study_seconds", imported)
        return imported - previous

    def study_seconds_by_day(self, now: float, days: int) -> list[tuple[str, int]]:
        today = datetime.fromtimestamp(now).date()
        if days < 1:
            raise ValueError("days must be positive")
        first_day = today - timedelta(days=days - 1)
        start = datetime.combine(first_day, datetime.min.time()).timestamp()
        end = datetime.combine(today + timedelta(days=1), datetime.min.time()).timestamp()
        totals: dict[str, float] = {}
        records = (
            self.conn.execute(
                 "SELECT ts, seconds FROM attempts WHERE ts >= ? AND ts < ? "
                 "AND task_kind != 'mock_test'", (start, end)),
            self.conn.execute(
                 "SELECT finished, finished - started FROM case_runs "
                 "WHERE finished >= ? AND finished < ? AND finished IS NOT NULL", (start, end)),
        )
        for rows in records:
            for ts, seconds in rows:
                 day = datetime.fromtimestamp(ts).date().isoformat()
                 totals[day] = totals.get(day, 0) + seconds
        for day, seconds in self._imported_day_totals(
            "progress.imported_study_by_day", allow_negative=False
        ).items():
            if first_day.isoformat() <= day <= today.isoformat():
                totals[day] = max(totals.get(day, seconds), seconds)
        return [
            ((today - timedelta(days=i)).isoformat(),
             round(totals.get((today - timedelta(days=i)).isoformat(), 0)))
            for i in reversed(range(days))
        ]

    def dashboard_activity(self, now: float) -> dict[str, int]:
        today = datetime.fromtimestamp(now).date()
        week_start = datetime.combine(
            today - timedelta(days=today.weekday()), datetime.min.time()
        ).timestamp()
        lessons = self.conn.execute(
            "SELECT COUNT(DISTINCT skill_id) FROM attempts "
            "WHERE task_kind = 'lesson' AND ts >= ? AND ts <= ?",
            (week_start, now),
        ).fetchone()[0]
        practice_quizzes = self.conn.execute(
            "SELECT COUNT(*) FROM quiz_completions WHERE completed_at >= ? AND completed_at <= ?",
            (week_start, now),
        ).fetchone()[0]
        reviews = self.conn.execute(
            "SELECT COUNT(*) FROM attempts WHERE task_kind = 'review' AND ts >= ? AND ts <= ?",
            (week_start, now),
        ).fetchone()[0]
        total_quizzes, mastered_quizzes = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN total > 0 "
            "AND correct * 5 >= total * 4 THEN 1 ELSE 0 END), 0) "
            "FROM quiz_completions"
        ).fetchone()
        mock_tests = self.conn.execute(
            "SELECT COUNT(*) FROM mock_test_runs "
            "WHERE finished IS NOT NULL AND finished >= ? AND finished <= ?",
            (week_start, now),
        ).fetchone()[0]

        first_day = today - timedelta(days=6)
        start = datetime.combine(first_day, datetime.min.time()).timestamp()
        active_dates = set()
        records = (
            self.conn.execute(
                "SELECT ts FROM attempts WHERE ts >= ? AND ts <= ?", (start, now)
            ),
            self.conn.execute(
                "SELECT finished FROM mock_test_runs "
                "WHERE finished >= ? AND finished <= ? AND finished IS NOT NULL",
                (start, now),
            ),
            self.conn.execute(
                "SELECT finished FROM case_runs "
                "WHERE finished >= ? AND finished <= ? AND finished IS NOT NULL",
                (start, now),
            ),
        )
        for rows in records:
            active_dates.update(datetime.fromtimestamp(row[0]).date() for row in rows)
        active_dates.update(
            date.fromisoformat(day) for day in self._imported_xp_active_days()
            if first_day.isoformat() <= day <= today.isoformat()
        )
        active_dates.update(
            date.fromisoformat(day) for day, seconds in self._imported_day_totals(
                "progress.imported_study_by_day", allow_negative=False
            ).items()
            if seconds > 0 and first_day.isoformat() <= day <= today.isoformat()
        )
        return {
            "lessonsThisWeek": lessons,
            "practiceQuizzesThisWeek": practice_quizzes,
            "reviewsThisWeek": reviews,
            "totalQuizzes": total_quizzes,
            "masteredQuizzes": mastered_quizzes,
            "mockTestsThisWeek": mock_tests,
            "activeDaysLastSeven": len(active_dates),
        }

    def streak_days(self, now: float) -> int:
        imported_active = self._imported_xp_active_days()

        def has_xp(day) -> bool:
            if day <= datetime.fromtimestamp(now).date() and day.isoformat() in imported_active:
                return True
            start = datetime.combine(day, datetime.min.time()).timestamp()
            end = datetime.combine(day + timedelta(days=1), datetime.min.time()).timestamp()
            return self.conn.execute(
                "SELECT 1 FROM xp_ledger WHERE amount > 0 AND ts >= ? AND ts < ? "
                "AND ts <= ? AND reason != ? LIMIT 1", (start, end, now, IMPORTED_PROGRESS_REASON)
            ).fetchone() is not None

        day = datetime.fromtimestamp(now).date()
        if not has_xp(day):
            day -= timedelta(days=1)
            if not has_xp(day):
                return 0
        streak = 1
        streak_end = day
        day -= timedelta(days=1)
        while has_xp(day):
            streak += 1
            day -= timedelta(days=1)
        streak_start = day + timedelta(days=1)
        baseline = self.get("progress.imported_streak_baseline")
        if baseline is not None and (
            not isinstance(baseline, dict)
            or isinstance(baseline.get("count"), bool)
            or not isinstance(baseline.get("count"), int)
            or not 0 <= baseline["count"] <= 2**63 - 1
            or not isinstance(baseline.get("exportedAt"), str)
        ):
            raise ValueError("Saved imported streak information is invalid.")
        if baseline is not None and baseline.get("lastActiveDay") is not None:
            try:
                last_active = date.fromisoformat(baseline["lastActiveDay"])
            except (TypeError, ValueError) as error:
                raise ValueError("Saved imported streak information is invalid.") from error
            if last_active.isoformat() != baseline["lastActiveDay"]:
                raise ValueError("Saved imported streak information is invalid.")
            if streak_start <= last_active <= streak_end:
                streak = max(
                    streak,
                    baseline["count"] + (streak_end - last_active).days,
                )
        return streak

    def accuracy_by_skill(self, since: float) -> dict[str, tuple[int, int]]:
        return {r[0]: (r[1], r[2]) for r in self.conn.execute(
            "SELECT skill_id, SUM(correct), COUNT(*) FROM attempts WHERE ts >= ? "
            "GROUP BY skill_id", (since,))}

    def confidence_by_skill(self, since: float) -> dict[str, tuple[int, int]]:
        return {row["skill_id"]: (row["low_confidence"], row["rated"]) for row in self.conn.execute(
            "SELECT skill_id, "
            "SUM(CASE WHEN confidence IN ('unsure', 'guessed') THEN 1 ELSE 0 END) "
            "AS low_confidence, COUNT(*) AS rated FROM attempts "
            "WHERE ts >= ? AND confidence != '' GROUP BY skill_id", (since,))}

    def recent_skills(self, task_kind: str, limit: int = 8) -> list[str]:
        if limit == 0:
            return []
        recent = []
        seen = set()
        rows = self.conn.execute(
            "SELECT skill_id FROM attempts WHERE task_kind = ? ORDER BY id DESC", (task_kind,)
        )
        for row in rows:
            skill_id = row["skill_id"]
            if skill_id not in seen:
                seen.add(skill_id)
                recent.append(skill_id)
                if limit > 0 and len(recent) >= limit:
                    break
        return recent

    def attempts_for_skill(self, skill_id: str) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT seed, difficulty FROM attempts WHERE skill_id = ? ORDER BY id",
            (skill_id,),
        ))

    # ----- meta / settings -----
    def get(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value) -> None:
        with transaction(self.conn):
            self.conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                              (key, json.dumps(value)))

    def set_many(self, values: Mapping[str, object]) -> None:
        with transaction(self.conn):
            self.conn.executemany(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                [(key, json.dumps(value)) for key, value in values.items()],
            )

    def reset_progress(self) -> None:
        with transaction(self.conn):
            for table in ("skill_state", "attempts", "xp_ledger", "case_runs",
                          "mock_test_runs", "skill_activity", "quiz_completions"):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.execute(
                "DELETE FROM meta WHERE key NOT LIKE 'setting.%' AND key NOT LIKE 'reflection.%'"
            )
